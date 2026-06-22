"""
BracketBot — ADK Seeding Tool
Handles participant seeding — either random draw or manual order.
"""

import random


def seeding_tool(participants: list, method: str = "random") -> list:
    """
    ADK tool: Seed and order participants for bracket placement.

    Args:
        participants: List of participant names or seed placeholders
        method: "random" to shuffle, "manual" to preserve input order

    Returns:
        Ordered list of participants ready for bracket slot assignment
    """
    if method == "random":
        shuffled = participants[:]
        random.shuffle(shuffled)
        return shuffled
    else:
        # Manual seeding — preserve the order given by the organizer
        return participants[:]
