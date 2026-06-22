"""
BracketBot — Manager Agent
Orchestrates the full conversation using Google ADK.
Delegates to specialized subagents based on conversation state.
Maintains session memory so organizers can build their bracket step by step.
"""

import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv

from agent.conversation import ConversationSubagent, sanitize_input, extract_player_count
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


def _configure_gemini() -> genai.GenerativeModel:
    """
    Load the Gemini API key from environment and return a configured model.
    Raises a clear error if the key is missing so the user knows exactly what to fix.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Copy .env.example to .env and add your Gemini API key."
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=MANAGER_SYSTEM_PROMPT,
    )


class BracketBotAgent:
    """
    Manager agent that runs the full BracketBot conversation.

    Responsibilities:
    - Receive organizer messages and sanitize input
    - Delegate to ConversationSubagent to track setup state
    - Call FormatAdvisor to recommend bracket type when player count is known
    - Trigger BracketEngine once organizer confirms setup
    - Hand off to BracketProgressionSubagent for winner entry after bracket is live
    - Maintain session memory for continuity within a conversation
    """

    def __init__(self):
        """Initialize the Gemini model and empty session store."""
        self.model = _configure_gemini()
        # session_id -> { conversation, progression, history, bracket }
        self.sessions: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chat(self, user_message: str, session_id: str = "default") -> dict:
        """
        Process one message from the organizer and return the agent response.

        Args:
            user_message: Raw text typed by the organizer
            session_id:   Identifies the conversation (enables session memory)

        Returns:
            {
                "response": str,          # Text to display in the chat UI
                "bracket":  dict | None,  # Bracket data when generated, else None
                "state":    str,          # Current phase: setup | confirm | active | progression
            }
        """
        session = self._get_or_create_session(session_id)
        convo: ConversationSubagent = session["conversation"]
        progression: BracketProgressionSubagent = session["progression"]

        # Always sanitize before touching any logic
        clean = sanitize_input(user_message)

        # --- PHASE: bracket is live, handle winner entry ---
        if session["bracket"] is not None:
            result = progression.record_winner(clean, session["bracket"])
            session["bracket"] = result["bracket"]
            return {
                "response": result["response"],
                "bracket": session["bracket"],
                "state": "progression",
            }

        # --- PHASE: setup — extract fields from organizer message ---

        # Pull player count out of natural language if not yet known
        if convo.state.get("player_count") is None:
            count = extract_player_count(clean)
            if count:
                convo.update_state("player_count", count)

        # If player count just became known, get format recommendation
        if (
            convo.state.get("player_count")
            and convo.state.get("bracket_format") is None
            and "format_recommendation" not in session
        ):
            rec = format_advisor_tool(convo.state["player_count"])
            session["format_recommendation"] = rec

        # Let Gemini extract any other fields from the message
        self._extract_fields_with_gemini(clean, convo, session)

        # --- PHASE: all fields collected — check for confirmation ---
        if convo.is_complete() and not convo.confirmed:
            if self._is_confirmation(clean):
                convo.confirmed = True
                bracket = generate_bracket(convo.get_summary())
                session["bracket"] = bracket
                return {
                    "response": BRACKET_INTRO.format(
                        event_name=convo.state["event_name"]
                    ),
                    "bracket": bracket,
                    "state": "active",
                }
            else:
                # Show summary and ask for confirmation
                summary = convo.get_summary()
                response = CONFIRMATION_TEMPLATE.format(
                    event_name=summary.get("event_name", "Your Tournament"),
                    sport=summary.get("sport", "—"),
                    individual_or_team=summary.get("individual_or_team", "—"),
                    player_count=summary.get("player_count", "—"),
                    bracket_format=summary.get("bracket_format", "—"),
                    seeding_type=summary.get("seeding_type", "—"),
                    match_format=summary.get("match_format", "—"),
                )
                return {"response": response, "bracket": None, "state": "confirm"}

        # --- PHASE: still collecting — ask next question ---
        response = self._ask_next_question(clean, convo, session)
        return {"response": response, "bracket": None, "state": "setup"}

    def new_tournament(self, session_id: str) -> dict:
        """
        Reset a session so the organizer can set up a new tournament.
        Called when the organizer clicks 'New Tournament' in the UI.
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
        return {
            "response": GREETING,
            "bracket": None,
            "state": "setup",
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_session(self, session_id: str) -> dict:
        """Return the existing session or create a fresh one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "conversation": ConversationSubagent(),
                "progression": BracketProgressionSubagent(),
                "history": [],
                "bracket": None,
                "format_recommendation": None,
            }
        return self.sessions[session_id]

    def _extract_fields_with_gemini(
        self, message: str, convo: ConversationSubagent, session: dict
    ) -> None:
        """
        Ask Gemini to pull structured field values out of the organizer message.
        Updates conversation state with anything Gemini finds.
        Uses JSON mode so extraction is reliable and parseable.
        """
        # Only extract fields that are still missing
        missing = [f for f in convo.state if convo.state[f] is None]
        if not missing:
            return

        extraction_prompt = f"""
Extract tournament setup information from this organizer message.
Only extract values for these fields if they are clearly stated: {missing}

Message: "{message}"

Respond ONLY with a JSON object. Use null for fields not found.
Example: {{"event_name": "Summer Slam", "sport": null, "player_count": null}}
"""
        try:
            result = self.model.generate_content(extraction_prompt)
            raw = result.text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r"```json|```", "", raw).strip()
            extracted = json.loads(raw)
            for field, value in extracted.items():
                if value is not None and convo.state.get(field) is None:
                    convo.update_state(field, value)
        except (json.JSONDecodeError, Exception):
            # Silent fallback — the conversation continues even if extraction fails
            pass

    def _ask_next_question(
        self, message: str, convo: ConversationSubagent, session: dict
    ) -> str:
        """
        Generate the next conversational response using Gemini.
        Appends the next required question so the flow always moves forward.
        """
        next_q = convo.next_question()

        # Build a prompt that gives Gemini the full context
        format_rec = session.get("format_recommendation")
        format_hint = ""
        if format_rec and convo.state.get("bracket_format") is None:
            format_hint = (
                f"Format recommendation for {convo.state.get('player_count')} players: "
                f"{format_rec['recommendation']}. Reason: {format_rec['reason']}."
            )

        prompt = f"""
The organizer just said: "{message}"

Current setup state: {json.dumps(convo.get_summary(), default=str)}
{format_hint}

Next question to ask: {next_q}

Write a short, warm response (1-2 sentences max) that acknowledges what they said
and then asks the next question naturally. Do not add any extra questions.
"""
        try:
            history = [
                {"role": h["role"], "parts": [h["parts"]]}
                for h in session["history"][-10:]  # Last 10 turns for context
            ]
            chat = self.model.start_chat(history=history)
            response = chat.send_message(prompt)
            text = response.text.strip()
        except Exception as e:
            text = f"Got it! {next_q}"  # Graceful fallback

        # Store turn in history
        session["history"].append({"role": "user", "parts": message})
        session["history"].append({"role": "model", "parts": text})

        return text

    def _is_confirmation(self, message: str) -> bool:
        """
        Return True if the organizer is confirming the setup.
        Matches common affirmative phrases.
        """
        pattern = r"\b(yes|yeah|yep|yup|correct|looks good|go ahead|do it|confirm|generate|create|let'?s go|perfect|great|approved|that'?s right|sounds good)\b"
        return bool(re.search(pattern, message.lower()))
