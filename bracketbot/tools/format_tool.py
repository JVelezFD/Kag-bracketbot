"""
BracketBot — ADK Format Advisor Tool
Recommends the appropriate bracket format based on player count.
Called by the manager agent during the conversation flow.
"""


def format_advisor_tool(player_count: int) -> dict:
    """
    ADK tool: Recommend a bracket format based on the number of players.

    Args:
        player_count: Number of participants or teams

    Returns:
        Dictionary with recommendation and available format options
    """
    if player_count <= 8:
        return {
            "recommendation": "Single Elimination or Round Robin",
            "options": ["Single Elimination", "Round Robin"],
            "reason": "Small group — everyone gets quick games and a clear winner.",
        }
    elif player_count <= 16:
        return {
            "recommendation": "Single Elimination or Double Elimination",
            "options": ["Single Elimination", "Double Elimination"],
            "reason": "Mid-size — Double Elimination lets everyone play at least twice.",
        }
    elif player_count <= 32:
        return {
            "recommendation": "Double Elimination",
            "options": ["Single Elimination", "Double Elimination"],
            "reason": "Larger field — Double Elimination ensures competitive fairness.",
        }
    else:
        return {
            "recommendation": "Double Elimination with Pool Play",
            "options": ["Double Elimination with Pool Play", "Single Elimination with Pool Play"],
            "reason": "Large field — pools warm everyone up before the main bracket.",
        }
