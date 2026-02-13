from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class _EpisodeIndex:
    episode_id: str
    agent_id: str
    scenario_id: str
    start_time: datetime
    end_time: datetime


class EpisodicLearning:
    """In-memory episodic learning store with simple retrieval and summaries."""

    def __init__(self) -> None:
        self._episodes: Dict[str, Dict[str, Any]] = {}
        self._memories: List[_EpisodeIndex] = []

    def record_episode(self, episode_data: Dict[str, Any]) -> str:
        episode_id = str(episode_data.get("episode_id") or "")
        if not episode_id:
            raise ValueError("episode_id is required")
        self._episodes[episode_id] = dict(episode_data)

        agent_id = str(episode_data.get("agent_id") or "")
        scenario_id = str(episode_data.get("scenario_id") or "")
        start_time = episode_data.get("start_time") or datetime.now()
        end_time = episode_data.get("end_time") or datetime.now()

        self._memories.append(
            _EpisodeIndex(
                episode_id=episode_id,
                agent_id=agent_id,
                scenario_id=scenario_id,
                start_time=start_time,
                end_time=end_time,
            )
        )
        return episode_id

    def retrieve_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        return self._episodes.get(episode_id)

    def find_similar_episodes(
        self, query_episode: Dict[str, Any], threshold: float = 0.8
    ):
        """
        Return a list of episodes "similar" to query_episode.

        Similarity here is intentionally lightweight: we compute overlap of action types.
        """
        query_actions = query_episode.get("actions") or []
        query_types = {a.get("type") for a in query_actions if isinstance(a, dict)}
        if not query_types:
            return []

        results: List[Dict[str, Any]] = []
        for ep in self._episodes.values():
            ep_actions = ep.get("actions") or []
            ep_types = {a.get("type") for a in ep_actions if isinstance(a, dict)}
            if not ep_types:
                continue
            overlap = len(query_types & ep_types) / max(1, len(query_types))
            if overlap >= float(threshold):
                results.append(ep)
        return results

    def extract_lessons(self, episode_id: str) -> Dict[str, Any]:
        ep = self._episodes.get(episode_id)
        if ep is None:
            raise KeyError(episode_id)
        outcomes = ep.get("outcomes") or {}
        metrics = ep.get("metrics") or {}
        return {
            "patterns": {
                "action_types": [
                    a.get("type")
                    for a in (ep.get("actions") or [])
                    if isinstance(a, dict)
                ]
            },
            "insights": {
                "profit": outcomes.get("profit"),
                "accuracy": metrics.get("accuracy"),
            },
            "recommendations": [
                "Review pricing and inventory actions for improvements."
            ],
        }

    def get_episode_statistics(self, agent_id: str) -> Dict[str, Any]:
        episodes = [e for e in self._episodes.values() if e.get("agent_id") == agent_id]
        count = len(episodes)
        profits: List[float] = []
        accuracies: List[float] = []
        for e in episodes:
            outcomes = e.get("outcomes") or {}
            metrics = e.get("metrics") or {}
            if "profit" in outcomes:
                try:
                    profits.append(float(outcomes["profit"]))
                except (TypeError, ValueError):
                    pass
            if "accuracy" in metrics:
                try:
                    accuracies.append(float(metrics["accuracy"]))
                except (TypeError, ValueError):
                    pass
        avg_profit = sum(profits) / len(profits) if profits else 0.0
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0
        return {"count": count, "avg_profit": avg_profit, "avg_accuracy": avg_accuracy}
