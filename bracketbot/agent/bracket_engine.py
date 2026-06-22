"""
BracketBot — Bracket Engine Subagent
Generates tournament bracket structures based on confirmed setup configuration.
Handles Single Elimination, Double Elimination, and Round Robin formats.
Supports pool play for 32+ player tournaments.
"""

import math
import random
from typing import Optional


def generate_bracket(config: dict) -> dict:
    """
    Generate a complete bracket structure from a confirmed tournament config.

    Args:
        config: Dictionary with keys: event_name, player_count, bracket_format,
                seeding_type, match_format, player_names (optional)

    Returns:
        Dictionary with bracket data including rounds, matchups, and metadata.
    """
    player_count = config["player_count"]
    bracket_format = config["bracket_format"].lower()
    seeding_type = config.get("seeding_type", "random")
    player_names = config.get("player_names", [])

    # Build the participant list — use names if provided, otherwise generate seeds
    participants = _build_participant_list(player_count, player_names, seeding_type)

    if "round robin" in bracket_format:
        return _generate_round_robin(config, participants)
    elif "pool" in bracket_format:
        return _generate_pool_play(config, participants)
    elif "double" in bracket_format:
        return _generate_double_elimination(config, participants)
    else:
        return _generate_single_elimination(config, participants)


def _build_participant_list(
    player_count: int, player_names: list, seeding_type: str
) -> list:
    """
    Build the ordered list of participants.
    If names are provided, use them. Otherwise create Seed 1, Seed 2, etc.
    Randomizes order if seeding is set to random.
    """
    if player_names and len(player_names) >= player_count:
        participants = player_names[:player_count]
    else:
        participants = [f"Seed {i+1}" for i in range(player_count)]

    if seeding_type.lower() == "random":
        random.shuffle(participants)

    return participants


def _next_power_of_two(n: int) -> int:
    """Return the smallest power of 2 that is >= n. Used to calculate bye rounds."""
    return 2 ** math.ceil(math.log2(n)) if n > 1 else 1


def _generate_single_elimination(config: dict, participants: list) -> dict:
    """
    Build a single elimination bracket.
    Adds byes as needed to reach the next power of 2.
    """
    bracket_size = _next_power_of_two(len(participants))
    bye_count = bracket_size - len(participants)

    # Pad with byes to fill the bracket
    seeded = participants + ["BYE"] * bye_count
    rounds = []
    current_round = [seeded[i:i+2] for i in range(0, len(seeded), 2)]

    round_num = 1
    while len(current_round) > 1 or (len(current_round) == 1 and round_num == 1):
        round_label = _round_label(round_num, len(current_round))
        matchups = [
            {"match": i + 1, "player1": m[0], "player2": m[1], "winner": None}
            for i, m in enumerate(current_round)
            if "BYE" not in m  # Skip bye matchups — auto-advance
        ]
        rounds.append({"round": round_num, "label": round_label, "matchups": matchups})
        # Next round slots — TBD until winners are entered
        current_round = [["TBD", "TBD"] for _ in range(len(current_round) // 2)]
        round_num += 1

    return {
        "format": "Single Elimination",
        "event_name": config["event_name"],
        "player_count": len(participants),
        "bracket_size": bracket_size,
        "bye_count": bye_count,
        "match_format": config.get("match_format", "Best of 1"),
        "rounds": rounds,
        "total_rounds": len(rounds),
    }


def _generate_double_elimination(config: dict, participants: list) -> dict:
    """
    Build a double elimination bracket (winners side + losers side).
    Every player must lose twice to be eliminated.
    """
    winners = _generate_single_elimination(config, participants)

    # Losers bracket: mirrors the winners bracket depth
    losers_rounds = []
    for i, r in enumerate(winners["rounds"][:-1]):  # No losers round from the final
        losers_rounds.append({
            "round": i + 1,
            "label": f"Losers Round {i + 1}",
            "matchups": [
                {"match": j + 1, "player1": "TBD", "player2": "TBD", "winner": None}
                for j in range(max(1, len(r["matchups"]) // 2))
            ],
        })

    return {
        "format": "Double Elimination",
        "event_name": config["event_name"],
        "player_count": len(participants),
        "match_format": config.get("match_format", "Best of 1"),
        "winners_bracket": winners["rounds"],
        "losers_bracket": losers_rounds,
        "grand_final": {"player1": "Winners Champion", "player2": "Losers Champion", "winner": None},
        "total_rounds": len(winners["rounds"]) + len(losers_rounds) + 1,
    }


def _generate_round_robin(config: dict, participants: list) -> dict:
    """
    Build a round robin schedule where every participant plays every other participant once.
    Uses the round-robin algorithm (rotate all but the first participant each round).
    """
    n = len(participants)
    # If odd number, add a bye
    if n % 2 != 0:
        participants = participants + ["BYE"]
        n += 1

    rounds = []
    team_list = participants[:]

    for round_num in range(n - 1):
        matchups = []
        for i in range(n // 2):
            p1 = team_list[i]
            p2 = team_list[n - 1 - i]
            if "BYE" not in (p1, p2):
                matchups.append({
                    "match": i + 1,
                    "player1": p1,
                    "player2": p2,
                    "winner": None,
                })
        rounds.append({
            "round": round_num + 1,
            "label": f"Round {round_num + 1}",
            "matchups": matchups,
        })
        # Rotate all except first position
        team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]

    return {
        "format": "Round Robin",
        "event_name": config["event_name"],
        "player_count": config["player_count"],
        "match_format": config.get("match_format", "Best of 1"),
        "rounds": rounds,
        "total_games": sum(len(r["matchups"]) for r in rounds),
    }


def _generate_pool_play(config: dict, participants: list) -> dict:
    """
    Split participants into pools, run round robin within each pool,
    then feed top finishers into a single elimination playoff bracket.
    Used for 32+ player tournaments.
    """
    player_count = len(participants)

    # Determine pool count — aim for pools of 4–6 players
    if player_count <= 32:
        pool_count = 4
    elif player_count <= 64:
        pool_count = 8
    else:
        pool_count = 16

    pool_size = player_count // pool_count
    pools = []

    for i in range(pool_count):
        start = i * pool_size
        end = start + pool_size if i < pool_count - 1 else player_count
        pool_participants = participants[start:end]
        pool_config = dict(config)
        pool_schedule = _generate_round_robin(pool_config, pool_participants)
        pools.append({
            "pool": chr(65 + i),  # Pool A, B, C...
            "participants": pool_participants,
            "schedule": pool_schedule["rounds"],
        })

    # Playoff bracket — top 2 from each pool advance
    playoff_slots = pool_count * 2
    playoff_participants = [f"Pool {chr(65+i)} 1st/2nd" for i in range(pool_count) for _ in range(2)]
    playoff_config = dict(config)
    playoff = _generate_single_elimination(playoff_config, playoff_participants)

    return {
        "format": "Double Elimination with Pool Play",
        "event_name": config["event_name"],
        "player_count": player_count,
        "pool_count": pool_count,
        "match_format": config.get("match_format", "Best of 1"),
        "pools": pools,
        "playoff": playoff,
        "advancement": f"Top 2 from each pool advance to the {playoff_slots}-team playoff bracket",
    }


def _round_label(round_num: int, matchup_count: int) -> str:
    """Return a human-readable label for a bracket round."""
    if matchup_count == 1:
        return "Final"
    if matchup_count == 2:
        return "Semifinals"
    if matchup_count == 4:
        return "Quarterfinals"
    return f"Round {round_num}"
