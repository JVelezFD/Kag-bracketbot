"""
BracketBot — Bracket Engine Subagent
Generates tournament bracket structures from confirmed setup config.
Supports Single Elimination, Double Elimination, Round Robin, and Pool Play.
Uses standard tournament seeding (1 vs 8, 2 vs 7, etc.) when names are provided.
"""

import math
import random
from typing import Optional


def generate_bracket(config: dict) -> dict:
    """
    Generate a complete bracket from a confirmed tournament config.

    Args:
        config: Dictionary with keys: event_name, player_count, bracket_format,
                seeding_type, match_format, player_names, individual_or_team

    Returns:
        Dictionary with full bracket data including rounds, matchups, metadata.
    """
    player_count = config.get("player_count", 8)
    bracket_format = (config.get("bracket_format") or "Single Elimination").lower()
    seeding_type = config.get("seeding_type", "random")
    player_names = config.get("player_names") or []
    individual_or_team = config.get("individual_or_team", "individual")

    participants = _build_participant_list(
        player_count, player_names, seeding_type, individual_or_team
    )

    if "round robin" in bracket_format:
        return _generate_round_robin(config, participants)
    elif "pool" in bracket_format:
        return _generate_pool_play(config, participants)
    elif "double" in bracket_format:
        return _generate_double_elimination(config, participants)
    else:
        return _generate_single_elimination(config, participants)


def _build_participant_list(
    player_count: int,
    player_names: list,
    seeding_type: str,
    individual_or_team: str,
) -> list:
    """
    Build the ordered participant list.
    - If names provided and seeding is manual: use names in listed order (already seeded by organizer)
    - If names provided and seeding is random: shuffle the names
    - If no names: auto-generate Team 1 / Competitor 1 labels
    """
    prefix = "Team" if individual_or_team == "team" else "Competitor"

    if player_names and len(player_names) >= player_count:
        participants = [str(n) for n in player_names[:player_count]]
        if seeding_type == "random":
            random.shuffle(participants)
    else:
        # Auto-assigned labels
        participants = [f"{prefix} {i+1}" for i in range(player_count)]
        if seeding_type == "random":
            random.shuffle(participants)

    return participants


def _apply_standard_seeding(participants: list) -> list:
    """
    Reorder participants using standard tournament bracket seeding.
    Uses recursive halving so top seeds face lowest seeds in early rounds.

    For 8 participants the matchup pairs are:
        1 vs 8,  4 vs 5,  2 vs 7,  3 vs 6

    Works correctly for any bracket size including non-powers-of-2 (uses BYEs).
    """
    n = len(participants)
    if n < 2:
        return participants

    bracket_size = _next_power_of_two(n)

    def _build_slots(size: int) -> list:
        """Recursively build 1-indexed seed position list."""
        if size == 2:
            return [1, 2]
        half = _build_slots(size // 2)
        result = []
        for s in half:
            result.append(s)
            result.append(size + 1 - s)
        return result

    slots = _build_slots(bracket_size)  # 1-indexed seed positions

    seeded = []
    for slot in slots:
        if slot <= n:
            seeded.append(participants[slot - 1])  # convert to 0-indexed
        else:
            seeded.append("BYE")

    return seeded


def _next_power_of_two(n: int) -> int:
    """Return smallest power of 2 >= n."""
    return 2 ** math.ceil(math.log2(n)) if n > 1 else 1


def _generate_single_elimination(config: dict, participants: list) -> dict:
    """
    Build a single elimination bracket with standard seeding.
    Adds byes as needed to reach the next power of 2.
    """
    n = len(participants)
    bracket_size = _next_power_of_two(n)
    bye_count = bracket_size - n

    # Apply standard seeding — BYEs are inserted by the seeding function
    seeded = _apply_standard_seeding(participants)

    # Build Round 1 matchups
    rounds = []
    round1_matchups = []
    for i in range(0, len(seeded), 2):
        p1 = seeded[i]
        p2 = seeded[i + 1] if i + 1 < len(seeded) else "BYE"

        if p2 == "BYE":
            round1_matchups.append({
                "match": len(round1_matchups) + 1,
                "player1": p1,
                "player2": "BYE",
                "winner": p1,  # Auto-advance
            })
        elif p1 == "BYE":
            round1_matchups.append({
                "match": len(round1_matchups) + 1,
                "player1": "BYE",
                "player2": p2,
                "winner": p2,
            })
        else:
            round1_matchups.append({
                "match": len(round1_matchups) + 1,
                "player1": p1,
                "player2": p2,
                "winner": None,
            })

    rounds.append({
        "round": 1,
        "label": _round_label(1, len(round1_matchups)),
        "matchups": round1_matchups,
    })

    # Build subsequent rounds with TBD slots
    current_match_count = len(round1_matchups) // 2
    round_num = 2
    while current_match_count >= 1:
        label = _round_label(round_num, current_match_count)
        matchups = [
            {"match": i + 1, "player1": "TBD", "player2": "TBD", "winner": None}
            for i in range(current_match_count)
        ]
        rounds.append({"round": round_num, "label": label, "matchups": matchups})
        if current_match_count == 1:
            break
        current_match_count = current_match_count // 2
        round_num += 1

    # Pre-advance bye winners into Round 2
    rounds = _advance_byes(rounds)

    return {
        "format": "Single Elimination",
        "event_name": config.get("event_name", "Tournament"),
        "player_count": n,
        "bracket_size": bracket_size,
        "bye_count": bye_count,
        "match_format": config.get("match_format", "Best of 1"),
        "rounds": rounds,
        "total_rounds": len(rounds),
    }


def _advance_byes(rounds: list) -> list:
    """
    After building Round 1, auto-advance bye winners into Round 2 TBD slots.
    """
    if len(rounds) < 2:
        return rounds

    for m_idx, match in enumerate(rounds[0]["matchups"]):
        if match["winner"] and match["winner"] not in ("TBD", "BYE"):
            next_match_idx = m_idx // 2
            slot = "player1" if m_idx % 2 == 0 else "player2"
            if next_match_idx < len(rounds[1]["matchups"]):
                rounds[1]["matchups"][next_match_idx][slot] = match["winner"]

    return rounds


def _generate_double_elimination(config: dict, participants: list) -> dict:
    """
    Build a double elimination bracket.
    Every participant must lose twice to be eliminated.
    """
    winners = _generate_single_elimination(config, participants)

    # Losers bracket mirrors winners bracket depth
    losers_rounds = []
    for i, r in enumerate(winners["rounds"][:-1]):
        losers_rounds.append({
            "round": i + 1,
            "label": f"Losers Round {i + 1}",
            "matchups": [
                {
                    "match": j + 1,
                    "player1": "TBD",
                    "player2": "TBD",
                    "winner": None,
                }
                for j in range(max(1, len(r["matchups"]) // 2))
            ],
        })

    return {
        "format": "Double Elimination",
        "event_name": config.get("event_name", "Tournament"),
        "player_count": len(participants),
        "match_format": config.get("match_format", "Best of 1"),
        "winners_bracket": winners["rounds"],
        "losers_bracket": losers_rounds,
        "grand_final": {
            "player1": "Winners Champion",
            "player2": "Losers Champion",
            "winner": None,
        },
        "total_rounds": len(winners["rounds"]) + len(losers_rounds) + 1,
    }


def _generate_round_robin(config: dict, participants: list) -> dict:
    """
    Build a round robin schedule — every participant plays every other once.
    Uses the circle rotation algorithm.
    """
    n = len(participants)
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
        # Rotate all except first
        team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]

    return {
        "format": "Round Robin",
        "event_name": config.get("event_name", "Tournament"),
        "player_count": config.get("player_count", n),
        "match_format": config.get("match_format", "Best of 1"),
        "rounds": rounds,
        "total_games": sum(len(r["matchups"]) for r in rounds),
    }


def _generate_pool_play(config: dict, participants: list) -> dict:
    """
    Split participants into pools, run round robin within each pool,
    then feed top finishers into a single elimination playoff.
    Used for 32+ player tournaments.
    """
    player_count = len(participants)

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
        pool_schedule = _generate_round_robin(config, pool_participants)
        pools.append({
            "pool": chr(65 + i),
            "participants": pool_participants,
            "schedule": pool_schedule["rounds"],
        })

    playoff_participants = [
        f"Pool {chr(65+i)} {place}"
        for i in range(pool_count)
        for place in ["1st", "2nd"]
    ]
    playoff = _generate_single_elimination(config, playoff_participants)

    return {
        "format": "Double Elimination with Pool Play",
        "event_name": config.get("event_name", "Tournament"),
        "player_count": player_count,
        "pool_count": pool_count,
        "match_format": config.get("match_format", "Best of 1"),
        "pools": pools,
        "playoff": playoff,
        "advancement": f"Top 2 from each pool advance to the {pool_count * 2}-team playoff bracket",
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