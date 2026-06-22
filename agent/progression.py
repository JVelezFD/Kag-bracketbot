"""
BracketBot — Bracket Progression Subagent
Handles winner entry after the bracket is live.
Accepts organizer input like "Team A beat Team B" and advances the bracket.
Handles both winners bracket and losers bracket in Double Elimination.
"""

import re


class BracketProgressionSubagent:
    """
    Processes winner input and updates the live bracket state.
    Works with any bracket format returned by bracket_engine.py.
    """

    def record_winner(self, message: str, bracket: dict) -> dict:
        """
        Parse the organizer's winner input and advance the bracket.

        Args:
            message: Organizer text, e.g. "Team A won" or "Alice beat Bob"
            bracket: Current bracket state dictionary

        Returns:
            { "response": str, "bracket": updated bracket dict }
        """
        bracket_format = bracket.get("format", "").lower()

        if "double" in bracket_format and "pool" not in bracket_format:
            return self._progress_double_elim(message, bracket)
        elif "round robin" in bracket_format:
            return self._progress_round_robin(message, bracket)
        elif "pool" in bracket_format:
            return self._progress_pool_play(message, bracket)
        else:
            return self._progress_single_elim(message, bracket)

    # ------------------------------------------------------------------
    # Single Elimination progression
    # ------------------------------------------------------------------

    def _progress_single_elim(self, message: str, bracket: dict) -> dict:
        """
        Find the first unplayed match in the winners bracket,
        record the winner, and advance the TBD slot in the next round.
        """
        rounds = bracket.get("rounds", [])
        winner_name = self._extract_winner(message, rounds)

        if not winner_name:
            return {
                "response": (
                    "I didn't catch who won. Try something like:\n"
                    "**'[Team name] won'** or **'[Team A] beat [Team B]'**"
                ),
                "bracket": bracket,
            }

        # Find the first open match and record the winner
        for r_idx, round_data in enumerate(rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None and "TBD" not in (match["player1"], match["player2"]):
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        bracket["rounds"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        bracket = self._advance_winner(bracket, r_idx, m_idx, winner_name)
                        complete = self._is_bracket_complete(bracket)
                        champion = self._find_champion(bracket) if complete else None
                        response = self._winner_recorded_response(
                            winner_name, bracket, complete, champion
                        )
                        return {"response": response, "bracket": bracket}

        return {
            "response": "I couldn't find an open match for that result. Check the bracket and try again.",
            "bracket": bracket,
        }

    def _progress_double_elim(self, message: str, bracket: dict) -> dict:
        """
        Record a winner in either the winners or losers bracket of a Double Elimination.
        Losers from the winners bracket drop into the losers bracket automatically.
        """
        winners_rounds = bracket.get("winners_bracket", [])
        losers_rounds = bracket.get("losers_bracket", [])
        winner_name = self._extract_winner(message, winners_rounds + losers_rounds)

        if not winner_name:
            return {
                "response": (
                    "I didn't catch who won. Try:\n"
                    "**'[Name] won'** or **'[Name] beat [Name]'**"
                ),
                "bracket": bracket,
            }

        # Check winners bracket first
        for r_idx, round_data in enumerate(winners_rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None and "TBD" not in (match["player1"], match["player2"]):
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        loser = (
                            match["player2"]
                            if winner_name.lower() in match["player1"].lower()
                            else match["player1"]
                        )
                        bracket["winners_bracket"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        # Drop loser into losers bracket
                        bracket = self._drop_to_losers(bracket, loser, r_idx)
                        response = (
                            f"✅ **{winner_name}** advances in the winners bracket.\n"
                            f"❌ **{loser}** drops to the losers bracket — still alive!"
                        )
                        return {"response": response, "bracket": bracket}

        # Check losers bracket
        for r_idx, round_data in enumerate(losers_rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None and "TBD" not in (match["player1"], match["player2"]):
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        loser = (
                            match["player2"]
                            if winner_name.lower() in match["player1"].lower()
                            else match["player1"]
                        )
                        bracket["losers_bracket"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        response = (
                            f"✅ **{winner_name}** survives the losers bracket.\n"
                            f"❌ **{loser}** is eliminated."
                        )
                        return {"response": response, "bracket": bracket}

        # Check grand final
        gf = bracket.get("grand_final", {})
        if gf and gf.get("winner") is None and "TBD" not in (gf.get("player1","TBD"), gf.get("player2","TBD")):
            bracket["grand_final"]["winner"] = winner_name
            return {
                "response": f"🏆 **{winner_name}** wins the Grand Final and is your champion!",
                "bracket": bracket,
            }

        return {
            "response": "I couldn't find an open match for that result. Check the bracket.",
            "bracket": bracket,
        }

    def _progress_round_robin(self, message: str, bracket: dict) -> dict:
        """Record a round robin result and update standings."""
        rounds = bracket.get("rounds", [])
        winner_name = self._extract_winner(message, rounds)

        if not winner_name:
            return {
                "response": "I didn't catch who won. Try: **'[Name] beat [Name]'**",
                "bracket": bracket,
            }

        for r_idx, round_data in enumerate(rounds):
            for m_idx, match in enumerate(round_data["matchups"]):
                if match["winner"] is None:
                    if self._name_matches(winner_name, match["player1"], match["player2"]):
                        bracket["rounds"][r_idx]["matchups"][m_idx]["winner"] = winner_name
                        remaining = sum(
                            1 for r in rounds for m in r["matchups"] if m["winner"] is None
                        )
                        response = (
                            f"✅ **{winner_name}** wins that match! "
                            f"{remaining} game{'s' if remaining != 1 else ''} remaining."
                        )
                        if remaining == 0:
                            response += "\n\n🏁 **Round Robin complete!** Tally up the wins to determine your finalist(s)."
                        return {"response": response, "bracket": bracket}

        return {
            "response": "Couldn't find that open match. Check the bracket and try again.",
            "bracket": bracket,
        }

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
    # Helpers
    # ------------------------------------------------------------------

    def _extract_winner(self, message: str, rounds: list) -> str | None:
        """
        Try to match a participant name from the bracket against the message.
        Checks for patterns like '[Name] won', '[Name] beat [Name]', '[Name] wins'.
        """
        # Collect all known participant names from open matches
        candidates = set()
        for round_data in rounds:
            for match in round_data.get("matchups", []):
                if match.get("winner") is None:
                    candidates.add(match["player1"])
                    candidates.add(match["player2"])

        msg_lower = message.lower()
        for name in candidates:
            if name.lower() in msg_lower and name not in ("TBD", "BYE"):
                return name

        return self._extract_winner_from_text(message)

    def _extract_winner_from_text(self, message: str) -> str | None:
        """
        Fallback: extract a winner name using regex patterns.
        Matches: '[Name] won', '[Name] beat [Name]', '[Name] wins'.
        """
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
        """Return True if winner name loosely matches either player in the match."""
        w = winner.lower().strip()
        return w in player1.lower() or w in player2.lower()

    def _advance_winner(
        self, bracket: dict, round_idx: int, match_idx: int, winner: str
    ) -> dict:
        """
        Place the winner into the correct TBD slot in the next round.
        Even match indices fill player1; odd indices fill player2.
        """
        next_round_idx = round_idx + 1
        if next_round_idx >= len(bracket["rounds"]):
            return bracket  # This was the final

        next_match_idx = match_idx // 2
        slot = "player1" if match_idx % 2 == 0 else "player2"

        rounds = bracket["rounds"]
        if next_match_idx < len(rounds[next_round_idx]["matchups"]):
            bracket["rounds"][next_round_idx]["matchups"][next_match_idx][slot] = winner

        return bracket

    def _drop_to_losers(self, bracket: dict, loser: str, winners_round_idx: int) -> dict:
        """
        Place a loser from the winners bracket into the next available
        TBD slot in the losers bracket.
        """
        losers = bracket.get("losers_bracket", [])
        target_round = min(winners_round_idx, len(losers) - 1)
        if target_round < 0:
            return bracket

        for m_idx, match in enumerate(losers[target_round]["matchups"]):
            if match["player1"] == "TBD":
                bracket["losers_bracket"][target_round]["matchups"][m_idx]["player1"] = loser
                return bracket
            if match["player2"] == "TBD":
                bracket["losers_bracket"][target_round]["matchups"][m_idx]["player2"] = loser
                return bracket

        return bracket

    def _is_bracket_complete(self, bracket: dict) -> bool:
        """Return True when all matches in the bracket have a winner."""
        for round_data in bracket.get("rounds", []):
            for match in round_data["matchups"]:
                if match["winner"] is None:
                    return False
        return True

    def _find_champion(self, bracket: dict) -> str | None:
        """Return the winner of the final match."""
        rounds = bracket.get("rounds", [])
        if rounds:
            final_round = rounds[-1]
            if final_round["matchups"]:
                return final_round["matchups"][0].get("winner")
        return None

    def _winner_recorded_response(
        self, winner: str, bracket: dict, complete: bool, champion: str | None
    ) -> str:
        """Build the response message after a winner is recorded."""
        if complete and champion:
            return f"🏆 **{champion}** is your champion! The tournament is complete."
        remaining = sum(
            1
            for r in bracket.get("rounds", [])
            for m in r["matchups"]
            if m["winner"] is None
        )
        return (
            f"✅ **{winner}** advances! "
            f"{remaining} match{'es' if remaining != 1 else ''} remaining."
        )
