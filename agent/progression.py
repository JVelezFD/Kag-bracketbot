"""
BracketBot — Bracket Progression Subagent
Handles winner entry after the bracket is live.
Supports: Single Elimination, Double Elimination, Round Robin, Pool Play.
Features: strict winner extraction, undo last result, auto champion detection.
"""

import re
import copy


class BracketProgressionSubagent:
    """
    Processes winner input and updates the live bracket state.
    Maintains a history stack for undo support.
    """

    def __init__(self):
        """Initialize with empty history for undo support."""
        self._history = []  # Stack of previous bracket states

    def record_winner(self, message: str, bracket: dict) -> dict:
        """
        Parse the organizer's message and update the bracket.
        Supports win/loss phrasing and undo commands.
        """
        bracket_format = bracket.get("format", "").lower()
        msg_lower = message.lower().strip()

        # Handle undo command
        if any(w in msg_lower for w in ["undo", "undo last", "fix last", "go back", "reverse"]):
            return self._undo(bracket)

        # Save state before making changes
        self._history.append(copy.deepcopy(bracket))
        # Keep history limited to last 5 states
        if len(self._history) > 5:
            self._history.pop(0)

        if "double" in bracket_format and "pool" not in bracket_format:
            return self._progress_double_elim(message, bracket)
        elif "round robin" in bracket_format:
            return self._progress_round_robin(message, bracket)
        elif "pool" in bracket_format:
            return self._progress_pool_play(message, bracket)
        else:
            return self._progress_single_elim(message, bracket)

    def _undo(self, bracket: dict) -> dict:
        """Restore the previous bracket state."""
        if not self._history:
            return {
                "response": "Nothing to undo — no results have been recorded yet.",
                "bracket": bracket,
            }
        previous = self._history.pop()
        return {
            "response": "↩️ Last result undone. The bracket has been restored to the previous state.",
            "bracket": previous,
        }

    # ------------------------------------------------------------------
    # Single Elimination
    # ------------------------------------------------------------------

    def _progress_single_elim(self, message: str, bracket: dict) -> dict:
        """Record a winner and advance them to the next round."""
        rounds = bracket.get("rounds", [])
        winner_name = self._extract_winner(message, rounds)

        if not winner_name:
            return {
                "response": (
                    "I didn't catch who won. Try:\n"
                    "**'[Name] won'**, **'[Name] lost'**, or **'[Name] beat [Name]'**\n"
                    "To fix a mistake: **'undo'**"
                ),
                "bracket": bracket,
            }

        for r_idx, round_data in enumerate(rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None and match["player1"] not in ("TBD", "BYE") and match["player2"] not in ("TBD", "BYE"):
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        bracket["rounds"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        bracket = self._advance_single_elim(bracket, r_idx, m_idx, winner_name)
                        complete = self._is_bracket_complete(bracket)
                        champion = self._find_champion(bracket) if complete else None
                        return {
                            "response": self._winner_recorded_response(winner_name, bracket, complete, champion),
                            "bracket": bracket,
                        }

        return {
            "response": "I couldn't find an open match for that result. Check the bracket.\nTo fix a mistake: **'undo'**",
            "bracket": bracket,
        }

    def _advance_single_elim(self, bracket: dict, round_idx: int, match_idx: int, winner: str) -> dict:
        """Place winner into the next round TBD slot."""
        rounds = bracket["rounds"]
        next_r = round_idx + 1
        if next_r >= len(rounds):
            return bracket
        next_m = match_idx // 2
        slot = "player1" if match_idx % 2 == 0 else "player2"
        if next_m < len(rounds[next_r]["matchups"]):
            bracket["rounds"][next_r]["matchups"][next_m][slot] = winner
        return bracket

    # ------------------------------------------------------------------
    # Double Elimination
    # ------------------------------------------------------------------

    def _progress_double_elim(self, message: str, bracket: dict) -> dict:
        """
        Record a winner in Double Elimination.
        Winners advance in the winners bracket; losers drop to the losers bracket.
        Losers bracket winners advance through losers rounds to the Grand Final.
        """
        winners_rounds = bracket.get("winners_bracket", [])
        losers_rounds = bracket.get("losers_bracket", [])

        # --- Check Grand Final FIRST (all other rounds may be complete) ---
        gf = bracket.get("grand_final", {})
        p1 = gf.get("player1", "TBD")
        p2 = gf.get("player2", "TBD")
        placeholders = {"TBD", "Winners Champion", "Losers Champion"}
        if gf and gf.get("winner") is None and p1 not in placeholders and p2 not in placeholders:
            gf_winner = self._extract_winner(
                message,
                [{"matchups": [{"player1": p1, "player2": p2, "winner": None}]}]
            )
            if gf_winner:
                bracket["grand_final"]["winner"] = gf_winner
                return {
                    "response": f"🏆 **{gf_winner}** wins the Grand Final and is your champion!",
                    "bracket": bracket,
                }
            return {
                "response": (
                    f"The Grand Final is set: **{p1}** vs **{p2}**!\n"
                    f"Enter the result — e.g. **'{p1} won'** or **'{p2} won'**"
                ),
                "bracket": bracket,
            }

        # Extract winner from all open bracket matches
        all_rounds = winners_rounds + losers_rounds
        winner_name = self._extract_winner(message, all_rounds)

        if not winner_name:
            return {
                "response": (
                    "I didn't catch who won. Try:\n"
                    "**'[Name] won'**, **'[Name] lost'**, or **'[Name] beat [Name]'**\n"
                    "To fix a mistake: **'undo'**"
                ),
                "bracket": bracket,
            }

        # --- Check Winners Bracket ---
        for r_idx, round_data in enumerate(winners_rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None and match["player1"] not in ("TBD", "BYE") and match["player2"] not in ("TBD", "BYE"):
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        loser = match["player2"] if winner_name.lower() in match["player1"].lower() else match["player1"]
                        bracket["winners_bracket"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        bracket = self._advance_winners(bracket, r_idx, m_idx, winner_name)
                        bracket = self._drop_to_losers(bracket, loser, r_idx)
                        return {
                            "response": (
                                f"✅ **{winner_name}** advances in the winners bracket.\n"
                                f"❌ **{loser}** drops to the losers bracket — still alive!"
                            ),
                            "bracket": bracket,
                        }

        # --- Check Losers Bracket ---
        for r_idx, round_data in enumerate(losers_rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None and match["player1"] not in ("TBD", "BYE") and match["player2"] not in ("TBD", "BYE"):
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        loser = match["player2"] if winner_name.lower() in match["player1"].lower() else match["player1"]
                        bracket["losers_bracket"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        bracket = self._advance_losers(bracket, r_idx, m_idx, winner_name)
                        return {
                            "response": (
                                f"✅ **{winner_name}** survives the losers bracket.\n"
                                f"❌ **{loser}** is eliminated."
                            ),
                            "bracket": bracket,
                        }

        # --- Check Grand Final ---
        # (Grand Final with both real players is checked at the TOP of this function)
        # If we reach here, no open match was found
        return {
            "response": (
                "I couldn't find an open match for that result. Check the bracket.\n"
                "To fix a mistake: **'undo'**"
            ),
            "bracket": bracket,
        }

    def _advance_winners(self, bracket: dict, round_idx: int, match_idx: int, winner: str) -> dict:
        """Place winners bracket winner into next round. Last round goes to Grand Final player1."""
        winners = bracket.get("winners_bracket", [])
        next_r = round_idx + 1
        if next_r >= len(winners):
            bracket["grand_final"]["player1"] = winner
            return bracket
        next_m = match_idx // 2
        slot = "player1" if match_idx % 2 == 0 else "player2"
        if next_m < len(winners[next_r]["matchups"]):
            bracket["winners_bracket"][next_r]["matchups"][next_m][slot] = winner
        return bracket

    def _advance_losers(self, bracket: dict, round_idx: int, match_idx: int, winner: str) -> dict:
        """
        Place losers bracket winner into the correct slot of the next losers round.
        Last losers round winner goes to Grand Final as player2.

        When next round has SAME match count → direct 1:1 index, fill player1.
        When next round has FEWER matches → consolidate: even idx→player1, odd→player2.
        """
        losers = bracket.get("losers_bracket", [])
        next_r = round_idx + 1
        if next_r >= len(losers):
            bracket["grand_final"]["player2"] = winner
            return bracket

        current_count = len(losers[round_idx]["matchups"])
        next_count = len(losers[next_r]["matchups"])

        if next_count >= current_count:
            next_m = match_idx
            slot = "player1"
        else:
            next_m = match_idx // 2
            slot = "player1" if match_idx % 2 == 0 else "player2"

        if next_m < len(losers[next_r]["matchups"]):
            if losers[next_r]["matchups"][next_m][slot] == "TBD":
                bracket["losers_bracket"][next_r]["matchups"][next_m][slot] = winner
                return bracket
            other = "player2" if slot == "player1" else "player1"
            if losers[next_r]["matchups"][next_m][other] == "TBD":
                bracket["losers_bracket"][next_r]["matchups"][next_m][other] = winner
                return bracket

        # Fallback: find any open slot
        for m_idx, match in enumerate(losers[next_r]["matchups"]):
            for s in ["player1", "player2"]:
                if match[s] == "TBD":
                    bracket["losers_bracket"][next_r]["matchups"][m_idx][s] = winner
                    return bracket

        return bracket

    def _drop_to_losers(self, bracket: dict, loser: str, winners_round_idx: int) -> dict:
        """
        Place a winners bracket loser into the correct losers bracket round.

        Correct mapping for any tournament size:
          WR1 (idx 0) → LR1 (idx 0)  — QF losers play each other
          WR2 (idx 1) → LR2 (idx 1)  — play LR1 winners
          WR3 (idx 2) → LR4 (idx 3)  — play LR3 winners
          WR4 (idx 3) → LR6 (idx 5)  — play LR5 winners
          Winners Final → last losers round

        Formula: idx 0→0, 1→1, r>=2 → 2r-1, final→last
        """
        losers = bracket.get("losers_bracket", [])
        n_winners = len(bracket.get("winners_bracket", []))
        n_losers = len(losers)
        if not losers:
            return bracket

        if winners_round_idx == 0:
            target = 0
        elif winners_round_idx == 1:
            target = 1
        elif winners_round_idx >= n_winners - 1:
            target = n_losers - 1  # Finals loser → last losers round
        else:
            target = min(2 * winners_round_idx - 1, n_losers - 1)

        # QF losers (LR1) fill both player slots freely
        # All other drops fill player2 (waiting for losers bracket survivor in player1)
        if winners_round_idx == 0:
            for m_idx, match in enumerate(losers[target]["matchups"]):
                if match["player1"] == "TBD":
                    bracket["losers_bracket"][target]["matchups"][m_idx]["player1"] = loser
                    return bracket
                if match["player2"] == "TBD":
                    bracket["losers_bracket"][target]["matchups"][m_idx]["player2"] = loser
                    return bracket
        else:
            # Drop into player2 slot (survivor from previous LR round fills player1)
            for m_idx, match in enumerate(losers[target]["matchups"]):
                if match["player2"] == "TBD":
                    bracket["losers_bracket"][target]["matchups"][m_idx]["player2"] = loser
                    return bracket
                if match["player1"] == "TBD":
                    bracket["losers_bracket"][target]["matchups"][m_idx]["player1"] = loser
                    return bracket

        return bracket

    # ------------------------------------------------------------------
    # Round Robin
    # ------------------------------------------------------------------

    def _progress_round_robin(self, message: str, bracket: dict) -> dict:
        """Record a round robin result, update standings, declare champion when complete."""
        rounds = bracket.get("rounds", [])
        winner_name = self._extract_winner(message, rounds)

        if not winner_name:
            return {
                "response": "I didn't catch who won. Try: **'[Name] beat [Name]'**\nTo fix a mistake: **'undo'**",
                "bracket": bracket,
            }

        for r_idx, round_data in enumerate(rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None:
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        bracket["rounds"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        remaining = sum(1 for r in rounds for m in r["matchups"] if m["winner"] is None)
                        response = (
                            f"✅ **{winner_name}** wins that match! "
                            f"{remaining} game{'s' if remaining != 1 else ''} remaining."
                        )
                        if remaining == 0:
                            standings = self._calculate_standings(rounds)
                            bracket["standings"] = standings
                            response += f"\n\n🏁 **Round Robin complete!**\n{self._format_champion(standings)}"
                        return {"response": response, "bracket": bracket}

        return {
            "response": "Couldn't find that open match. Check the bracket.\nTo fix a mistake: **'undo'**",
            "bracket": bracket,
        }

    def _calculate_standings(self, rounds: list) -> list:
        """Count wins and losses per participant across all round robin matches."""
        wins = {}
        losses = {}
        for round_data in rounds:
            for match in round_data.get("matchups", []):
                p1 = match.get("player1", "")
                p2 = match.get("player2", "")
                winner = match.get("winner")
                for p in [p1, p2]:
                    if p and p != "BYE":
                        wins.setdefault(p, 0)
                        losses.setdefault(p, 0)
                if winner:
                    wins[winner] = wins.get(winner, 0) + 1
                    loser = p2 if winner == p1 else p1
                    if loser and loser != "BYE":
                        losses[loser] = losses.get(loser, 0) + 1
        standings = [
            {"name": n, "wins": wins[n], "losses": losses.get(n, 0)}
            for n in wins
        ]
        return sorted(standings, key=lambda x: x["wins"], reverse=True)

    def _format_champion(self, standings: list) -> str:
        """Format final standings with medals and declare champion or tie."""
        if not standings:
            return "Results tallied."
        top_wins = standings[0]["wins"]
        leaders = [s for s in standings if s["wins"] == top_wins]
        lines = ["**Final Standings:**"]
        for i, s in enumerate(standings):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
            lines.append(f"{medal} **{s['name']}** — {s['wins']}W / {s['losses']}L")
        if len(leaders) == 1:
            lines.append(f"\n🏆 **{leaders[0]['name']} is your champion!**")
        else:
            tied = ", ".join(f"**{l['name']}**" for l in leaders)
            lines.append(f"\n🤝 **Tie!** {tied} all finished with {top_wins} wins. Consider a tiebreaker match.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Pool Play
    # ------------------------------------------------------------------

    def _progress_pool_play(self, message: str, bracket: dict) -> dict:
        """Record a pool play result."""
        pools = bracket.get("pools", [])
        winner_name = self._extract_winner_from_text(message)

        if not winner_name:
            return {
                "response": "I didn't catch who won. Try: **'[Name] beat [Name]'**",
                "bracket": bracket,
            }

        for p_idx, pool in enumerate(pools):
            for r_idx, round_data in enumerate(pool["schedule"]):
                for m_idx, match in enumerate(round_data["matchups"]):
                    if match["winner"] is None:
                        if self._name_matches(winner_name, match["player1"], match["player2"]):
                            bracket["pools"][p_idx]["schedule"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                            return {
                                "response": f"✅ **{winner_name}** wins in Pool {pool['pool']}!",
                                "bracket": bracket,
                            }

        return {
            "response": "Couldn't find that match in pool play. Check the bracket.",
            "bracket": bracket,
        }

    # ------------------------------------------------------------------
    # Winner extraction
    # ------------------------------------------------------------------

    def _extract_winner(self, message: str, rounds: list) -> str | None:
        """
        Strictly extract a winner from the message.
        Requires an explicit win or lose keyword — never matches on name alone.
        """
        open_matches = []
        for round_data in rounds:
            for match in round_data.get("matchups", []):
                p1 = match.get("player1", "")
                p2 = match.get("player2", "")
                if match.get("winner") is None and p1 not in ("TBD", "BYE") and p2 not in ("TBD", "BYE"):
                    open_matches.append(match)

        if not open_matches:
            return None

        msg_lower = message.lower().strip()

        # Check for LOSER keywords first
        loser_keywords = ["lost", "loses", "is out", "is eliminated", "got eliminated", "was eliminated"]
        for match in open_matches:
            p1, p2 = match["player1"], match["player2"]
            for kw in loser_keywords:
                if re.search(rf'\b{re.escape(p1.lower())}\b.*\b{re.escape(kw)}\b', msg_lower):
                    return p2
                if re.search(rf'\b{re.escape(p2.lower())}\b.*\b{re.escape(kw)}\b', msg_lower):
                    return p1

        # Check for WINNER keywords
        winner_keywords = ["won", "wins", "beat", "defeated", "takes it", "wins it"]
        for match in open_matches:
            p1, p2 = match["player1"], match["player2"]
            for kw in winner_keywords:
                if re.search(rf'\b{re.escape(p1.lower())}\b.*\b{re.escape(kw)}\b', msg_lower):
                    return p1
                if re.search(rf'\b{re.escape(p2.lower())}\b.*\b{re.escape(kw)}\b', msg_lower):
                    return p2
                if kw == "beat":
                    if re.search(rf'\b{re.escape(p1.lower())}\b.*beat.*\b{re.escape(p2.lower())}\b', msg_lower):
                        return p1
                    if re.search(rf'\b{re.escape(p2.lower())}\b.*beat.*\b{re.escape(p1.lower())}\b', msg_lower):
                        return p2

        # Check "winner: [Name]" format
        winner_label = re.search(r'winner[:\s]+(.+)', msg_lower)
        if winner_label:
            named = winner_label.group(1).strip()
            for match in open_matches:
                if named in match["player1"].lower():
                    return match["player1"]
                if named in match["player2"].lower():
                    return match["player2"]

        return None

    def _extract_winner_from_text(self, message: str) -> str | None:
        """Fallback pattern extraction for pool play."""
        patterns = [
            r"([A-Za-z0-9 &'._-]+?)\s+(?:won|wins|wins it|takes it)",
            r"([A-Za-z0-9 &'._-]+?)\s+beat\s+",
            r"([A-Za-z0-9 &'._-]+?)\s+defeated\s+",
            r"winner[:\s]+([A-Za-z0-9 &'._-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _name_matches(self, winner: str, player1: str, player2: str) -> bool:
        """Return True if winner name loosely matches either player."""
        w = winner.lower().strip()
        return w in player1.lower() or w in player2.lower()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_bracket_complete(self, bracket: dict) -> bool:
        """Return True when all matches have a winner."""
        for round_data in bracket.get("rounds", []):
            for match in round_data["matchups"]:
                if match["winner"] is None:
                    return False
        return True

    def _find_champion(self, bracket: dict) -> str | None:
        """Return the winner of the final match."""
        rounds = bracket.get("rounds", [])
        if rounds:
            last = rounds[-1]
            if last["matchups"]:
                return last["matchups"][0].get("winner")
        return None

    def _winner_recorded_response(
        self, winner: str, bracket: dict, complete: bool, champion: str | None
    ) -> str:
        """Build response after a winner is recorded."""
        if complete and champion:
            return f"🏆 **{champion}** is your champion! The tournament is complete."
        remaining = sum(
            1 for r in bracket.get("rounds", [])
            for m in r["matchups"]
            if m["winner"] is None
        )
        return (
            f"✅ **{winner}** advances! "
            f"{remaining} match{'es' if remaining != 1 else ''} remaining.\n"
            f"To fix a mistake: **'undo'**"
        )