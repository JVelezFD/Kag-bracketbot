"""
BracketBot — Conversation Subagent
Manages the clarifying question flow and tracks tournament setup state.
Extracts information from organizer messages and determines what to ask next.
"""

import re
import bleach


# Fields required before bracket generation can begin
REQUIRED_FIELDS = [
    "event_name",
    "sport",
    "player_count",
    "individual_or_team",
    "bracket_format",
    "seeding_type",
    "match_format",
]

# Questions asked in order when a field is missing
QUESTION_MAP = {
    "event_name": "What's the name of your event or tournament?",
    "sport": "What sport or activity is this tournament for?",
    "player_count": "How many participants or teams will be competing?",
    "individual_or_team": "Will this be an individual player tournament or a team tournament?",
    "bracket_format": None,  # Dynamically generated based on player count
    "seeding_type": "How would you like to seed the bracket — random draw, or would you like to enter names manually?",
    "match_format": "What's the match format — Best of 1, Best of 3, or Best of 5?",
}


def sanitize_input(text: str) -> str:
    """
    Strip HTML tags and limit characters to prevent prompt injection.
    Always sanitize user input before passing to the model.
    """
    cleaned = bleach.clean(text, tags=[], strip=True)
    # Remove characters commonly used in prompt injection attempts
    cleaned = re.sub(r"[<>{}\[\]\\]", "", cleaned)
    return cleaned[:2000].strip()


def extract_player_count(message: str) -> int | None:
    """
    Pull a number out of the user's message to use as player count.
    Returns None if no clear number is found.
    """
    numbers = re.findall(r"\b(\d{1,3})\b", message)
    if numbers:
        count = int(numbers[0])
        if 2 <= count <= 512:  # Reasonable tournament size bounds
            return count
    return None


def get_bracket_format_question(player_count: int) -> str:
    """
    Generate a bracket format question with a recommendation
    based on the number of players.
    """
    if player_count <= 8:
        recommendation = "Single Elimination or Round Robin work great for this size"
        options = "Single Elimination, Round Robin"
    elif player_count <= 16:
        recommendation = "Single Elimination or Double Elimination both work well"
        options = "Single Elimination, Double Elimination"
    elif player_count <= 32:
        recommendation = "I'd recommend Double Elimination so everyone gets at least two games"
        options = "Single Elimination, Double Elimination"
    else:
        recommendation = "I'd recommend Double Elimination with pool play — gives everyone a warm-up round before the bracket"
        options = "Double Elimination with pools, Single Elimination with pools"

    return (
        f"What bracket format would you like? ({recommendation}.) "
        f"Options: {options}."
    )


class ConversationSubagent:
    """
    Tracks the state of a tournament setup conversation.
    Determines what information is still needed and what question to ask next.
    """

    def __init__(self):
        """Initialize an empty tournament setup state."""
        self.state = {field: None for field in REQUIRED_FIELDS}
        self.confirmed = False
        self.player_names = []

    def update_state(self, field: str, value) -> None:
        """Store a confirmed field value in the conversation state."""
        self.state[field] = value

    def next_missing_field(self) -> str | None:
        """Return the name of the next required field that hasn't been filled in."""
        for field in REQUIRED_FIELDS:
            if self.state[field] is None:
                return field
        return None  # All fields collected

    def next_question(self) -> str | None:
        """
        Return the next question to ask the organizer.
        Returns None when all required information has been collected.
        """
        field = self.next_missing_field()
        if field is None:
            return None

        if field == "bracket_format" and self.state["player_count"]:
            return get_bracket_format_question(self.state["player_count"])

        return QUESTION_MAP.get(field)

    def is_complete(self) -> bool:
        """Return True when all required fields have been filled in."""
        return self.next_missing_field() is None

    def get_summary(self) -> dict:
        """Return the full tournament setup state as a dictionary."""
        return dict(self.state)
