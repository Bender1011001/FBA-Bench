from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional


class MetaLearning:
    """Stores learning experience metadata and recommends strategies/hyperparameters."""

    def __init__(self) -> None:
        self._meta_knowledge: Dict[str, Dict[str, Any]] = {}
        self._learning_strategies: Dict[str, Dict[str, Any]] = {}

    def record_learning_experience(self, experience_data: Dict[str, Any]) -> str:
        experience_id = str(experience_data.get("experience_id") or "")
        if not experience_id:
            raise ValueError("experience_id is required")
        self._meta_knowledge[experience_id] = dict(experience_data)
        return experience_id

    def _score_performance(self, performance: Dict[str, Any]) -> float:
        try:
            acc = float(performance.get("accuracy", 0.0))
        except (TypeError, ValueError):
            acc = 0.0
        try:
            eff = float(performance.get("efficiency", 0.0))
        except (TypeError, ValueError):
            eff = 0.0
        return acc + eff

    def recommend_learning_strategy(
        self, task_description: Dict[str, Any]
    ) -> Dict[str, Any]:
        task_type = task_description.get("task_type")
        meta = task_description.get("metadata") or {}

        best: Optional[Dict[str, Any]] = None
        best_score = float("-inf")
        for exp in self._meta_knowledge.values():
            if exp.get("task_type") != task_type:
                continue
            # Prefer exact metadata match when present.
            exp_meta = exp.get("metadata") or {}
            if meta and exp_meta and exp_meta != meta:
                continue
            perf = exp.get("performance") or {}
            score = self._score_performance(perf)
            if score > best_score:
                best_score = score
                best = exp

        if best is None:
            return {
                "strategy": "reinforcement_learning",
                "hyperparameters": {},
                "expected_performance": {},
            }

        return {
            "strategy": best.get("strategy_used"),
            "hyperparameters": dict(best.get("hyperparameters") or {}),
            "expected_performance": dict(best.get("performance") or {}),
        }

    def adapt_hyperparameters(
        self, current_hyperparameters: Dict[str, Any], task_description: Dict[str, Any]
    ) -> Dict[str, Any]:
        rec = self.recommend_learning_strategy(task_description)
        adapted = dict(current_hyperparameters)
        adapted.update(rec.get("hyperparameters") or {})
        return adapted

    def extract_meta_patterns(self) -> Dict[str, Any]:
        per_strategy_scores: Dict[str, list[float]] = defaultdict(list)
        per_task: Dict[str, int] = defaultdict(int)

        for exp in self._meta_knowledge.values():
            strategy = str(exp.get("strategy_used") or "unknown")
            task = str(exp.get("task_type") or "unknown")
            per_task[task] += 1
            score = self._score_performance(exp.get("performance") or {})
            per_strategy_scores[strategy].append(score)

        strategy_perf = {
            s: (sum(v) / len(v) if v else 0.0) for s, v in per_strategy_scores.items()
        }
        return {
            "strategy_performance": strategy_perf,
            "hyperparameter_importance": {},
            "task_characteristics": dict(per_task),
        }

    def get_meta_knowledge_summary(self) -> Dict[str, Any]:
        task_types = sorted(
            {
                str(e.get("task_type") or "")
                for e in self._meta_knowledge.values()
                if e.get("task_type")
            }
        )
        strategies = sorted(
            {
                str(e.get("strategy_used") or "")
                for e in self._meta_knowledge.values()
                if e.get("strategy_used")
            }
        )
        perf_scores = [
            self._score_performance(e.get("performance") or {})
            for e in self._meta_knowledge.values()
        ]
        avg_score = sum(perf_scores) / len(perf_scores) if perf_scores else 0.0
        return {
            "total_experiences": len(self._meta_knowledge),
            "task_types": task_types,
            "strategies_used": strategies,
            "performance_summary": {"avg_score": avg_score},
        }
