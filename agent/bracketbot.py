"""
BracketBot — Manager Agent
Orchestrates the full conversation using Google ADK.
Uses direct field extraction for reliability, Gemini for conversational warmth.
Handles the updated naming/seeding flow with conditional branching.
"""

import os
import re
import json
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv

from agent.conversation import (
    ConversationSubagent,
    sanitize_input,
    extract_player_count,
    parse_names_from_message,
)
from agent.bracket_engine import generate_bracket
from agent.progression import BracketProgressionSubagent
from agent.prompts import (
    MANAGER_SYSTEM_PROMPT,
    CONFIRMATION_TEMPLATE,
    BRACKET_INTRO,
    GREETING,
)
from tools.format_tool import format_advisor_tool

load_dotenv()


def _configure_gemini() -> genai.Client:
    """Load API key and return a configured Gemini client."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Copy .env.example to .env and add your Gemini API key."
        )
    return genai.Client(api_key=api_key)


def _direct_extract(message: str, field: str, convo: ConversationSubagent) -> bool:
    """
    Extract a field value directly from the message using pattern matching.
    Returns True if a value was found and saved.
    This is the primary extraction method — no API call needed.
    """
    msg = message.strip()
    msg_lower = msg.lower()

    if field == "event_name":
        if msg and len(msg) < 120 and not msg.startswith("__"):
            convo.update_state("event_name", msg)
            return True

    elif field == "sport":
        if msg and len(msg) < 80:
            convo.update_state("sport", msg)
            return True

    elif field == "player_count":
        count = extract_player_count(msg)
        if count:
            convo.update_state("player_count", count)
            return True

    elif field == "individual_or_team":
        if any(w in msg_lower for w in ["team", "teams", "club", "clubs"]):
            convo.update_state("individual_or_team", "team")
            return True
        elif any(w in msg_lower for w in ["individual", "singles", "solo", "player", "players", "person"]):
            convo.update_state("individual_or_team", "individual")
            return True
        elif len(msg) < 30:
            convo.update_state("individual_or_team", msg)
            return True

    elif field == "bracket_format":
        if any(w in msg_lower for w in ["double", "double elim"]):
            convo.update_state("bracket_format", "Double Elimination")
            return True
        elif any(w in msg_lower for w in ["single", "single elim"]):
            convo.update_state("bracket_format", "Single Elimination")
            return True
        elif any(w in msg_lower for w in ["round robin", "robin"]):
            convo.update_state("bracket_format", "Round Robin")
            return True
        elif any(w in msg_lower for w in ["pool", "pools"]):
            convo.update_state("bracket_format", "Double Elimination with Pool Play")
            return True
        elif len(msg) < 40:
            convo.update_state("bracket_format", msg)
            return True

    elif field == "has_names":
        if any(w in msg_lower for w in ["yes", "yeah", "yep", "yup", "have", "ready", "sure", "got them", "i do"]):
            convo.update_state("has_names", True)
            convo.start_collecting_names()
            return True
        elif any(w in msg_lower for w in ["no", "nope", "don't", "dont", "auto", "assign", "number", "skip"]):
            convo.update_state("has_names", False)
            # Auto-assign labels and skip seeding entirely
            labels = convo.build_auto_labels()
            convo.update_state("player_names", labels)
            convo.update_state("seeding_type", "random")
            return True

    elif field == "player_names":
        # We are in name-collection phase — parse whatever they send
        names = parse_names_from_message(msg)
        if names:
            convo.finish_collecting_names(names)
            return True

    elif field == "seeding_type":
        if any(w in msg_lower for w in ["seed", "seeded", "order", "ranked", "ranking", "listed", "that order", "same order"]):
            convo.update_state("seeding_type", "manual")
            return True
        elif any(w in msg_lower for w in ["random", "randomly", "draw", "shuffle", "mix"]):
            convo.update_state("seeding_type", "random")
            return True
        elif len(msg) < 30:
            # Short answer — default to random
            convo.update_state("seeding_type", "random")
            return True

    elif field == "match_format":
        if "best of 1" in msg_lower or "bo1" in msg_lower or msg_lower.strip() == "1":
            convo.update_state("match_format", "Best of 1")
            return True
        elif "best of 3" in msg_lower or "bo3" in msg_lower or msg_lower.strip() == "3":
            convo.update_state("match_format", "Best of 3")
            return True
        elif "best of 5" in msg_lower or "bo5" in msg_lower or msg_lower.strip() == "5":
            convo.update_state("match_format", "Best of 5")
            return True
        elif len(msg) < 30:
            convo.update_state("match_format", "Best of 1")
            return True

    return False


class BracketBotAgent:
    """
    Manager agent that runs the full BracketBot conversation.
    Uses direct extraction for field capture, Gemini for conversational warmth.
    """

    def __init__(self):
        """Initialize the Gemini client and empty session store."""
        self.client = _configure_gemini()
        self.model_name = "gemini-1.5-flash"
        self.sessions: dict[str, dict] = {}

    def chat(self, user_message: str, session_id: str = "default") -> dict:
        """
        Process one message and return the agent response.

        Returns:
            { "response": str, "bracket": dict|None, "state": str }
        """
        session = self._get_or_create_session(session_id)
        convo: ConversationSubagent = session["conversation"]
        progression: BracketProgressionSubagent = session["progression"]

        clean = sanitize_input(user_message)

        # --- PHASE: bracket is live — handle winner entry ---
        if session["bracket"] is not None:
            result = progression.record_winner(clean, session["bracket"])
            session["bracket"] = result["bracket"]
            return {
                "response": result["response"],
                "bracket": session["bracket"],
                "state": "progression",
            }

        # --- PHASE: setup — extract the next missing field ---
        next_field = convo.next_missing_field()
        if next_field:
            _direct_extract(clean, next_field, convo)

        # Get format recommendation once player count is known
        if (
            convo.state.get("player_count")
            and convo.state.get("bracket_format") is None
            and "format_recommendation" not in session
        ):
            rec = format_advisor_tool(convo.state["player_count"])
            session["format_recommendation"] = rec

        # --- DOUBLE ELIMINATION PLAYER COUNT CHECK ---
        # Double Elimination works correctly only with power-of-2 player counts
        # (4, 8, 16, 32). Other counts create bye gaps in the losers bracket.
        # Catch this early and ask the organizer to adjust.
        player_count = convo.state.get("player_count")
        bracket_format = convo.state.get("bracket_format", "")
        if (
            player_count
            and "double" in str(bracket_format).lower()
            and "pool" not in str(bracket_format).lower()
            and not session.get("de_count_flagged")
        ):
            is_power_of_2 = player_count > 0 and (player_count & (player_count - 1)) == 0
            if not is_power_of_2:
                session["de_count_flagged"] = True
                # Clear bracket format so organizer can re-pick after adjusting
                convo.update_state("bracket_format", None)
                kind = convo.state.get("individual_or_team", "individual")
                label = "teams" if kind == "team" else "players"
                # Find nearest power-of-2 options
                import math
                lower = 2 ** math.floor(math.log2(player_count))
                upper = 2 ** math.ceil(math.log2(player_count))
                return {
                    "response": (
                        f"Double Elimination works best with **{lower}** or **{upper}** {label} "
                        f"(powers of 2 keep the bracket perfectly balanced). "
                        f"You have **{player_count}** — would you like to adjust to "
                        f"**{lower}** or **{upper}**? "
                        f"Or I can use **Single Elimination**, which handles any number cleanly."
                    ),
                    "bracket": None,
                    "state": "setup",
                }

        # --- PHASE: all fields collected — check for confirmation ---
        if convo.is_complete() and not convo.confirmed:
            if self._is_confirmation(clean):
                convo.confirmed = True
                config = convo.get_summary()
                bracket = generate_bracket(config)
                session["bracket"] = bracket

                # Check if bracket engine auto-switched the format
                note = bracket.get("note", "")
                response = BRACKET_INTRO.format(event_name=convo.state["event_name"])
                if note:
                    response += f"\n\n⚠️ {note}"

                return {
                    "response": response,
                    "bracket": bracket,
                    "state": "active",
                }
            else:
                return {
                    "response": self._build_confirmation(convo),
                    "bracket": None,
                    "state": "confirm",
                }

        # --- PHASE: names just collected — trigger drag-and-drop seed widget ---
        # If names were just saved and seeding_type is still missing, show the widget
        if (
            convo.state.get("player_names") is not None
            and convo.state.get("has_names") is True
            and convo.state.get("seeding_type") is None
        ):
            names = convo.state["player_names"]
            kind = convo.state.get("individual_or_team", "individual")
            label = "teams" if kind == "team" else "players"
            return {
                "response": (
                    f"Got all {len(names)} {label}! "
                    f"Drag to set your seed order — Seed 1 will face Seed {len(names)}, "
                    f"Seed 2 faces Seed {len(names)-1}, and so on. "
                    f"When you're happy with the order, click the button to generate."
                ),
                "bracket": None,
                "state": "seeding",
                "show_seed_widget": True,
                "names": names,
            }

        # --- PHASE: still collecting — generate next question ---
        response = self._ask_next_question(clean, convo, session)
        return {"response": response, "bracket": None, "state": "setup"}

    def new_tournament(self, session_id: str) -> dict:
        """Reset the session for a new tournament."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        return {"response": GREETING, "bracket": None, "state": "setup"}

    def _get_or_create_session(self, session_id: str) -> dict:
        """Return existing session or create a fresh one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "conversation": ConversationSubagent(),
                "progression": BracketProgressionSubagent(),
                "history": [],
                "bracket": None,
                "format_recommendation": None,
            }
        return self.sessions[session_id]

    def _build_confirmation(self, convo: ConversationSubagent) -> str:
        """Build the confirmation summary message."""
        summary = convo.get_summary()
        names = summary.get("player_names", [])
        has_names = summary.get("has_names", False)

        # Format the names display
        if has_names and names:
            name_display = f"Names entered: {len(names)} {'✓' if names else '—'}"
        else:
            kind = summary.get("individual_or_team", "individual")
            label = "Team" if kind == "team" else "Competitor"
            name_display = f"Names: Auto-assigned ({label} 1, {label} 2...)"

        seeding = summary.get("seeding_type", "random")
        seeding_display = "Seeded in listed order" if seeding == "manual" else "Random draw"

        return (
            f"Here's your tournament setup — does everything look right?\n\n"
            f"**{summary.get('event_name', '—')}**\n"
            f"Sport / Activity: {summary.get('sport', '—')}\n"
            f"Tournament type: {summary.get('individual_or_team', '—')}\n"
            f"Players / Teams: {summary.get('player_count', '—')}\n"
            f"Bracket format: {summary.get('bracket_format', '—')}\n"
            f"{name_display}\n"
            f"Seeding: {seeding_display}\n"
            f"Match format: {summary.get('match_format', '—')}\n\n"
            f"Reply **yes** to generate your bracket, or tell me what you'd like to change."
        )

    def _call_gemini(self, prompt: str, session: dict) -> str:
        """
        Send a prompt to Gemini for a warm conversational response.
        Falls back gracefully if the API call fails.
        """
        try:
            contents = []
            for h in session["history"][-6:]:
                role = "user" if h["role"] == "user" else "model"
                contents.append(
                    types.Content(role=role, parts=[types.Part(text=h["parts"])])
                )
            contents.append(
                types.Content(role="user", parts=[types.Part(text=prompt)])
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=MANAGER_SYSTEM_PROMPT,
                    max_output_tokens=150,
                    temperature=0.7,
                ),
            )
            return response.text.strip()
        except Exception:
            return ""

    def _ask_next_question(
        self, message: str, convo: ConversationSubagent, session: dict
    ) -> str:
        """
        Generate a warm conversational response and ask the next question.
        Always falls back to the direct question so the flow never stalls.
        """
        next_q = convo.next_question()
        if not next_q:
            return "Got it! Let me put that together..."

        # Build Gemini prompt
        format_rec = session.get("format_recommendation")
        format_hint = ""
        if format_rec and convo.state.get("bracket_format") is None:
            format_hint = (
                f"Suggest: {format_rec['recommendation']} "
                f"({format_rec['reason']}). "
            )

        # For the player names question — include the format hint in the question itself
        if convo.next_missing_field() == "player_names":
            # Don't call Gemini for this — the question has formatting examples
            text = f"Got it! {next_q}"
        else:
            prompt = (
                f'Organizer said: "{message}". '
                f"State so far: {json.dumps({k: v for k, v in convo.get_summary().items() if k != 'player_names'}, default=str)}. "
                f"{format_hint}"
                f"Write ONE warm short sentence acknowledging what they said, "
                f'then ask exactly this next question: "{next_q}" '
                f"Do not add anything else."
            )
            gemini_text = self._call_gemini(prompt, session)

            if gemini_text and len(gemini_text) > 10:
                text = gemini_text
                if next_q not in text:
                    text = f"{text} {next_q}"
            else:
                text = f"Got it! {next_q}"

        session["history"].append({"role": "user", "parts": message})
        session["history"].append({"role": "model", "parts": text})

        return text

    def _is_confirmation(self, message: str) -> bool:
        """Return True if the organizer is confirming the setup."""
        pattern = r"\b(yes|yeah|yep|yup|correct|looks good|go ahead|do it|confirm|generate|create|let'?s go|perfect|great|approved|that'?s right|sounds good)\b"
        return bool(re.search(pattern, message.lower()))


    def confirm_seed_order(self, names: list, session_id: str) -> dict:
        """
        Receive the final confirmed seed order from the drag-and-drop widget.
        Stores names, sets seeding to manual, then asks for match format.
        """
        session = self._get_or_create_session(session_id)
        convo: ConversationSubagent = session["conversation"]

        # Store the confirmed seed order
        convo.finish_collecting_names(names)
        convo.update_state("seeding_type", "manual")

        # Ask next question (match format)
        next_q = convo.next_question()
        if next_q:
            return {
                "response": f"Perfect — {len(names)} {'teams' if convo.state.get('individual_or_team') == 'team' else 'players'} locked in! {next_q}",
                "bracket": None,
                "state": "setup",
            }

        # If somehow complete, show confirmation
        return {
            "response": self._build_confirmation(convo),
            "bracket": None,
            "state": "confirm",
        }