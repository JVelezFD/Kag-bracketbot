"""
BracketBot — Manager Agent
Orchestrates the conversation flow, delegates to subagents,
and manages session memory across a conversation.
"""

import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

from agent.conversation import ConversationSubagent, sanitize_input, extract_player_count
from agent.bracket_engine import generate_bracket
from agent.prompts import MANAGER_SYSTEM_PROMPT, CONFIRMATION_TEMPLATE, BRACKET_INTRO

load_dotenv()


def _configure_gemini():
    """Configure the Gemini API client using the environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Copy .env.example to .env and add your key."
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=MANAGER_SYSTEM_PROMPT,
    )


class BracketBotAgent:
    """
    Manager agent that runs the BracketBot conversation.
    Maintains session state so the agent remembers context within a session.
    """

    def __init__(self):
        """Initialize the agent and configure the Gemini model."""
        self.model = _configure_gemini()
        # Session storage: session_id -> { conversation, state }
        self.sessions: dict[str, dict] = {}

    def _get_session(self, session_id: str) -> dict:
        """Retrieve or create a session for the given session ID."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "conversation": ConversationSubagent(),
                "history": [],
                "bracket": None,
            }
        return self.sessions[session_id]

    def chat(self, user_message: str, session_id: str = "default") -> dict:
        """
        Process a user message and return the agent's response.

        Args:
            user_message: Raw text from the organizer
            session_id: Identifies the session for memory continuity

        Returns:
            dict with keys: response (str), bracket (dict or None)
        """
        session = self._get_session(session_id)
        convo: ConversationSubagent = session["conversation"]

        # Sanitize input — prevent prompt injection
        clean_message = sanitize_input(user_message)

        # Try to extract player count if that field is still missing
        if convo.state.get("player_count") is None:
            count = extract_player_count(clean_message)
            if count:
                convo.update_state("player_count", count)

        # Check if organizer is confirming the setup
        if convo.is_complete() and not convo.confirmed:
            if self._is_confirmation(clean_message):
                convo.confirmed = True
                bracket = generate_bracket(convo.get_summary())
                session["bracket"] = bracket
                response_text = BRACKET_INTRO.format(
                    event_name=convo.state["event_name"]
                )
                return {"response": response_text, "bracket": bracket}

        # If setup is complete but not yet confirmed — show summary and ask
        if convo.is_complete() and not convo.confirmed:
            summary = convo.get_summary()
            response_text = CONFIRMATION_TEMPLATE.format(
                event_name=summary.get("event_name", "Your Tournament"),
                sport=summary.get("sport", "—"),
                tournament_type=summary.get("bracket_format", "—"),
                individual_or_team=summary.get("individual_or_team", "—"),
                player_count=summary.get("player_count", "—"),
                bracket_format=summary.get("bracket_format", "—"),
                seeding_type=summary.get("seeding_type", "—"),
                match_format=summary.get("match_format", "—"),
            )
            return {"response": response_text, "bracket": None}

        # Otherwise — use Gemini to determine what to extract and what to ask next
        response_text = self._call_gemini(clean_message, session)

        # Update state from Gemini's extraction (handled via conversation logic)
        next_q = convo.next_question()
        if next_q and next_q not in response_text:
            response_text = response_text.rstrip() + f"\n\n{next_q}"

        session["history"].append({"role": "user", "parts": clean_message})
        session["history"].append({"role": "model", "parts": response_text})

        return {"response": response_text, "bracket": None}

    def _call_gemini(self, message: str, session: dict) -> str:
        """
        Send the message to Gemini and return the text response.
        Passes conversation history for context continuity.
        """
        try:
            # Build history in Gemini format
            history = [
                {"role": h["role"], "parts": [h["parts"]]}
                for h in session["history"]
            ]
            chat = self.model.start_chat(history=history)
            response = chat.send_message(message)
            return response.text
        except Exception as e:
            # Surface a friendly error rather than crashing
            return (
                f"I ran into a hiccup connecting to the AI. "
                f"Please try again in a moment. (Error: {type(e).__name__})"
            )

    def _is_confirmation(self, message: str) -> bool:
        """
        Check if the organizer's message is a confirmation to generate the bracket.
        Matches common affirmative responses.
        """
        affirmatives = r"\b(yes|yeah|yep|correct|looks good|go ahead|do it|confirm|generate|create|make it|let's go|perfect|great|approved)\b"
        return bool(re.search(affirmatives, message.lower()))
