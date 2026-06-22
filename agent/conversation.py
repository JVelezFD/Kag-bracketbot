"""
BracketBot — Conversation Subagent
Manages question flow and tournament setup state.
Handles the updated naming/seeding flow:
  - Ask if organizer has names
  - If yes: collect names, then ask about seeding order
  - If no: auto-assign labels, skip seeding question
"""

import re
import bleach


def sanitize_input(text: str) -> str:
    """
    Strip HTML and remove prompt injection characters.
    Always call this before passing user input to any logic.
    """
    cleaned = bleach.clean(text, tags=[], strip=True)
    cleaned = re.sub(r"[<>{}\[\]\\]", "", cleaned)
    return cleaned[:2000].strip()


def extract_player_count(message: str) -> int | None:
    """
    Pull a number from the message to use as player/team count.
    Returns None if no valid number found.
    """
    numbers = re.findall(r"\b(\d{1,3})\b", message)
    if numbers:
        count = int(numbers[0])
        if 2 <= count <= 512:
            return count
    return None


def parse_names_from_message(message: str) -> list[str]:
    """
    Parse a list of names from a message.
    Supports comma-separated and newline-separated formats.
    Strips whitespace, removes empty entries.

    Accepts:
        "Alice, Bob, Carol"
        "Alice\nBob\nCarol"
        "Alice, Bob\nCarol, Dave"
    """
    # Split on commas or newlines
    raw = re.split(r"[,\n]+", message)
    names = [n.strip() for n in raw if n.strip()]
    return names


def get_bracket_format_question(player_count: int, individual_or_team: str) -> str:
    """
    Build a bracket format question with a recommendation
    based on player count and tournament type.
    """
    label = "teams" if individual_or_team == "team" else "players"

    if player_count <= 8:
        rec = "Single Elimination or Round Robin work great for this size"
        options = "Single Elimination or Round Robin"
    elif player_count <= 16:
        rec = "Single Elimination or Double Elimination both work well"
        options = "Single Elimination or Double Elimination"
    elif player_count <= 32:
        rec = "I'd recommend Double Elimination so everyone gets at least two games"
        options = "Single Elimination or Double Elimination"
    else:
        rec = "I'd recommend Double Elimination with Pool Play — gives everyone a warm-up round"
        options = "Double Elimination with Pool Play, or Single Elimination with Pool Play"

    return f"What bracket format would you like for {player_count} {label}? ({rec}.) Options: {options}."


class ConversationSubagent:
    """
    Tracks tournament setup state and drives the question flow.

    Flow:
      event_name → sport → player_count → individual_or_team → bracket_format
      → has_names (yes/no)
        → yes: collecting_names → seeding_type → match_format
        → no:  auto-assign labels → match_format (skip seeding)
      → confirmation → bracket generated
    """

    def __init__(self):
        """Initialize empty state for a new tournament setup."""
        self.state = {
            "event_name":        None,
            "sport":             None,
            "player_count":      None,
            "individual_or_team": None,
            "bracket_format":    None,
            "has_names":         None,   # True/False — does organizer have names?
            "player_names":      None,   # list of names if has_names is True
            "seeding_type":      None,   # "manual" | "random" — only asked if has_names
            "match_format":      None,
        }
        self.confirmed = False
        # Tracks whether we are currently in the name-collection phase
        self._collecting_names = False

    def update_state(self, field: str, value) -> None:
        """Store a value for a field in the conversation state."""
        self.state[field] = value

    def is_collecting_names(self) -> bool:
        """Return True when we are actively waiting for the organizer to send names."""
        return self._collecting_names

    def start_collecting_names(self) -> None:
        """Enter the name-collection phase."""
        self._collecting_names = True

    def finish_collecting_names(self, names: list[str]) -> None:
        """Store collected names and exit the collection phase."""
        self.state["player_names"] = names
        self._collecting_names = False

    def next_missing_field(self) -> str | None:
        """
        Return the name of the next required field that hasn't been filled.
        Respects the conditional flow for names/seeding.
        """
        # Core setup fields — always required in order
        for field in ["event_name", "sport", "player_count", "individual_or_team", "bracket_format"]:
            if self.state[field] is None:
                return field

        # Names question
        if self.state["has_names"] is None:
            return "has_names"

        # If organizer has names — collect them, then ask about seeding
        if self.state["has_names"] is True:
            if self.state["player_names"] is None:
                return "player_names"
            if self.state["seeding_type"] is None:
                return "seeding_type"

        # If organizer does NOT have names — skip to match format
        # (seeding_type stays None, bracket engine uses auto labels)

        if self.state["match_format"] is None:
            return "match_format"

        return None  # All required fields collected

    def next_question(self) -> str | None:
        """
        Return the question text for the next missing field.
        Returns None when all required information has been collected.
        """
        field = self.next_missing_field()
        if field is None:
            return None

        # Dynamic questions
        if field == "bracket_format":
            count = self.state.get("player_count", 0)
            kind = self.state.get("individual_or_team", "individual")
            return get_bracket_format_question(count, kind)

        if field == "has_names":
            kind = self.state.get("individual_or_team", "individual")
            label = "team names" if kind == "team" else "player names"
            return (
                f"Do you have the {label} ready? "
                f"Reply **yes** to enter them, or **no** to auto-assign numbers."
            )

        if field == "player_names":
            kind = self.state.get("individual_or_team", "individual")
            label = "teams" if kind == "team" else "players"
            count = self.state.get("player_count", "")
            return (
                f"Go ahead and list all {count} {label}. "
                f"You can separate them with commas or paste one per line:\n\n"
                f"Example: *Team Alpha, Team Beta, Team Gamma*\n"
                f"Or:\n*Team Alpha*\n*Team Beta*\n*Team Gamma*"
            )

        if field == "seeding_type":
            kind = self.state.get("individual_or_team", "individual")
            label = "teams" if kind == "team" else "players"
            return (
                f"Would you like to seed the {label} in the order you listed them, "
                f"or do a **random draw**?"
            )

        # Static questions
        static = {
            "event_name":         "What's the name of your event or tournament?",
            "sport":              "What sport or activity is this tournament for?",
            "player_count":       "How many participants or teams will be competing?",
            "individual_or_team": "Will this be an individual player tournament or a team tournament?",
            "match_format":       "What's the match format — Best of 1, Best of 3, or Best of 5?",
        }
        return static.get(field)

    def is_complete(self) -> bool:
        """Return True when all required fields are filled."""
        return self.next_missing_field() is None

    def get_summary(self) -> dict:
        """Return the full tournament state as a dictionary."""
        return dict(self.state)

    def build_auto_labels(self) -> list[str]:
        """
        Generate auto-assigned labels when organizer has no names.
        Uses 'Team 1, Team 2...' or 'Competitor 1, Competitor 2...' based on type.
        """
        count = self.state.get("player_count", 8)
        kind = self.state.get("individual_or_team", "individual")
        prefix = "Team" if kind == "team" else "Competitor"
        return [f"{prefix} {i+1}" for i in range(count)]