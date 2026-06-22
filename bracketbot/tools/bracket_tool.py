"""
BracketBot — ADK Bracket Tool
Exposes bracket generation as an ADK-compatible tool
that the manager agent can call directly.
"""

from agent.bracket_engine import generate_bracket


def bracket_tool(config: dict) -> dict:
    """
    ADK tool: Generate a tournament bracket from a confirmed config.

    Args:
        config: Confirmed tournament setup dictionary

    Returns:
        Complete bracket structure ready for display
    """
    return generate_bracket(config)
