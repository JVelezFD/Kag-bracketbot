"""
Tests for the BracketBot bracket engine.
Run with: pytest tests/
"""

import pytest
from agent.bracket_engine import (
    generate_bracket,
    _generate_single_elimination,
    _generate_round_robin,
    _next_power_of_two,
)


BASE_CONFIG = {
    "event_name": "Test Tournament",
    "sport": "Basketball",
    "player_count": 8,
    "individual_or_team": "team",
    "bracket_format": "Single Elimination",
    "seeding_type": "random",
    "match_format": "Best of 1",
    "player_names": [],
}


def test_single_elimination_8_players():
    """8-player single elimination should produce 3 rounds."""
    config = dict(BASE_CONFIG)
    result = generate_bracket(config)
    assert result["format"] == "Single Elimination"
    assert result["total_rounds"] == 3
    assert result["player_count"] == 8


def test_single_elimination_5_players():
    """5-player bracket needs byes to reach 8 — should have 3 byes."""
    config = dict(BASE_CONFIG)
    config["player_count"] = 5
    result = generate_bracket(config)
    assert result["bye_count"] == 3
    assert result["bracket_size"] == 8


def test_round_robin_6_players():
    """6-player round robin should have 5 rounds, 3 games per round."""
    config = dict(BASE_CONFIG)
    config["player_count"] = 6
    config["bracket_format"] = "Round Robin"
    result = generate_bracket(config)
    assert result["format"] == "Round Robin"
    assert len(result["rounds"]) == 5


def test_double_elimination_returns_both_brackets():
    """Double elimination should have winners, losers, and grand final."""
    config = dict(BASE_CONFIG)
    config["bracket_format"] = "Double Elimination"
    result = generate_bracket(config)
    assert "winners_bracket" in result
    assert "losers_bracket" in result
    assert "grand_final" in result


def test_pool_play_32_players():
    """32-player pool play should create 4 pools."""
    config = dict(BASE_CONFIG)
    config["player_count"] = 32
    config["bracket_format"] = "Double Elimination with Pool Play"
    result = generate_bracket(config)
    assert result["pool_count"] == 4
    assert len(result["pools"]) == 4


def test_next_power_of_two():
    """Verify power-of-two helper for bracket sizing."""
    assert _next_power_of_two(8) == 8
    assert _next_power_of_two(5) == 8
    assert _next_power_of_two(9) == 16
    assert _next_power_of_two(17) == 32


def test_named_players_appear_in_bracket():
    """Player names should appear in Round 1 matchups."""
    config = dict(BASE_CONFIG)
    config["player_count"] = 4
    config["seeding_type"] = "manual"
    config["player_names"] = ["Alice", "Bob", "Carol", "Dave"]
    result = generate_bracket(config)
    all_players = []
    for matchup in result["rounds"][0]["matchups"]:
        all_players.extend([matchup["player1"], matchup["player2"]])
    for name in ["Alice", "Bob", "Carol", "Dave"]:
        assert name in all_players
