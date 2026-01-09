import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScoreTracker:
    def __init__(self, data_file: str = "scores.json", artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.data_file_path = os.path.join(self.artifacts_dir, data_file)
        self.scores: Dict[str, Dict[str, List[Dict[str, Any]]]] = self._load_scores()

        os.makedirs(self.artifacts_dir, exist_ok=True)

    def _load_scores(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Loads historical scores from a JSON file."""
        if os.path.exists(self.data_file_path):
            with open(self.data_file_path) as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    logger.error(
                        "ScoreTracker: corrupt JSON in %s - starting with empty store",
                        self.data_file_path,
                    )
                    return {}  # Return empty if file is corrupt
        return {}

    def _save_scores(self):
        """Saves current scores to the JSON file."""
        with open(self.data_file_path, "w") as f:
            json.dump(self.scores, f, indent=2)

    def add_run_result(self, bot_name: str, tier: str, score: float, run_details: Dict[str, Any], verified: bool = False):
        """
        Adds a new run result to the tracker with strict input validation.

        Args:
            bot_name: The name of the bot.
            tier: The curriculum tier the bot ran in.
            score: The final score achieved in the run.
            run_details: A dictionary containing all details of the run, e.g., cost, tokens, breakdown.
            verified: Whether the run was autonomously performed by an LLM (verified only).
        """
        if not isinstance(bot_name, str) or not bot_name.strip():
            raise ValueError("bot_name must be a non-empty string")
        if not isinstance(tier, str) or not tier.strip():
            raise ValueError("tier must be a non-empty string")
        if not isinstance(score, (int, float)):
            raise ValueError("score must be numeric")
        if not isinstance(run_details, dict):
            raise ValueError("run_details must be a dictionary")

        # Normalize
        bot_name = bot_name.strip()
        tier = tier.strip()
        score = float(score)

        if bot_name not in self.scores:
            self.scores[bot_name] = {}
        if tier not in self.scores[bot_name]:
            self.scores[bot_name][tier] = []

        run_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "score": score,
            "verified": verified,
            "details": run_details,
        }
        self.scores[bot_name][tier].append(run_entry)
        self._save_scores()

    def get_all_tracked_scores(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Returns all tracked scores (a copy)."""
        return self.scores.copy()

    def get_scores_for_bot(self, bot_name: str, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns scores for a specific bot, optionally filtered by tier.
        Ordered oldest to newest.
        """
        if bot_name not in self.scores:
            return []

        if tier:
            return self.scores[bot_name].get(tier, [])

        all_runs = []
        for tier_data in self.scores[bot_name].values():
            all_runs.extend(tier_data)

        # Sort by timestamp to ensure chronological order regardless of how tiers were added
        all_runs.sort(key=lambda x: x["timestamp"])
        return all_runs

    def get_latest_score(self, bot_name: str, tier: str) -> Optional[Dict[str, Any]]:
        """Returns the latest score for a specific bot and tier."""
        if bot_name in self.scores and tier in self.scores[bot_name]:
            runs = self.scores[bot_name][tier]
            if runs:
                return runs[-1]  # Last entry is the latest
        return None

    def reset_scores(self):
        """Resets all tracked scores."""
        self.scores = {}
        self._save_scores()
        logger.info("ScoreTracker: All scores reset.")


# Example Usage:
# if __name__ == "__main__":
#     tracker = ScoreTracker()
#     tracker.reset_scores() # Start fresh for example

#     # Add some dummy data
#     tracker.add_run_result("GPT-3.5", "T0", 35.1, {"cost_usd": 0.01, "tokens": 500})
#     tracker.add_run_result("GreedyScript", "T0", 8.2, {"cost_usd": 0.00, "tokens": 0})
#     tracker.add_run_result("GPT-3.5", "T0", 36.5, {"cost_usd": 0.012, "tokens": 550})
#     tracker.add_run_result("Claude 3.5 Sonnet", "T1", 68.9, {"cost_usd": 0.05, "tokens": 2000})

#     print("\nAll tracked scores:")
#     print(json.dumps(tracker.get_all_tracked_scores(), indent=2))

#     print("\nLatest score for GPT-3.5 in T0:")
#     print(tracker.get_latest_score("GPT-3.5", "T0"))

#     print("\nScores for GreedyScript:")
#     print(tracker.get_scores_for_bot("GreedyScript"))
