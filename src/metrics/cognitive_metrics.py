# metrics/cognitive_metrics.py
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from fba_events import BaseEvent

logger = logging.getLogger(__name__)


@dataclass
class CognitiveMetricsConfig:
    goal_completion_weight: float = 0.1
    active_focus_weight: float = 0.05
    context_switch_penalty: float = 5.0
    planning_coherence_weight: float = 10.0
    min_planning_coherence_for_default: float = 50.0


class CognitiveMetrics:
    def __init__(self, config: Optional[CognitiveMetricsConfig] = None):
        self.config = config if config else CognitiveMetricsConfig()
        self.planned_goals: Dict[str, Any] = {}
        self.agent_actions_history: List[Dict] = []
        self.focus_duration: Dict[str, int] = {}
        self.context_switches = 0
        self.planning_coherence_scores: List[float] = []
        self._metrics: Dict[str, Any] = {}

    def update(self, current_tick: int, events: List[Union[Dict, BaseEvent]]):
        for event in events:
            # Normalize to dict
            if isinstance(event, BaseEvent):
                # Assuming BaseEvent has to_dict or we map fields manually
                # Mapping known fields for cognitive events
                evt_type = event.event_type
                evt_data = {
                    "type": evt_type,
                    "goal_id": getattr(event, "goal_id", None),
                    "description": getattr(event, "description", None),
                    "status": getattr(event, "status", None),
                    "current_goal_id": getattr(event, "current_goal_id", None),
                    "score": getattr(event, "score", None),
                }
            else:
                evt_data = event

            if evt_data.get("type") == "AgentPlannedGoalEvent":
                goal_id = evt_data.get("goal_id")
                if goal_id:
                    self.planned_goals[goal_id] = {
                        "description": evt_data.get("description"),
                        "status": "active",
                        "start_tick": current_tick,
                        "end_tick": -1,
                    }
            elif evt_data.get("type") == "AgentGoalStatusUpdateEvent":
                goal_id = evt_data.get("goal_id")
                if goal_id in self.planned_goals:
                    self.planned_goals[goal_id]["status"] = evt_data.get("status")
                    if evt_data.get("status") in ["completed", "abandoned"]:
                        self.planned_goals[goal_id]["end_tick"] = current_tick

            elif evt_data.get("type") == "AgentActionEvent":
                self.agent_actions_history.append(evt_data)
                current_goal_id = evt_data.get("current_goal_id")
                if current_goal_id:
                    self.focus_duration[current_goal_id] = (
                        self.focus_duration.get(current_goal_id, 0) + 1
                    )

                if len(self.agent_actions_history) > 1:
                    prev_action = self.agent_actions_history[-2]
                    if (
                        prev_action.get("current_goal_id") != current_goal_id
                        and current_goal_id is not None
                    ):
                        self.context_switches += 1

            elif evt_data.get("type") == "PlanningCoherenceScoreEvent":
                score = evt_data.get("score")
                if score is not None:
                    self.planning_coherence_scores.append(score)

    def calculate_cra_score(self) -> float:
        total_goal_attention_score = 0
        active_and_completed_goals = 0

        for goal_id, goal_data in self.planned_goals.items():
            if goal_data["status"] in ["active", "completed"]:
                active_and_completed_goals += 1
                duration = self.focus_duration.get(goal_id, 0)

                if (
                    goal_data["status"] == "completed"
                    and goal_data["start_tick"] != -1
                    and goal_data["end_tick"] != -1
                ):
                    total_goal_attention_score += (
                        goal_data["end_tick"] - goal_data["start_tick"]
                    ) * 0.1
                elif goal_data["status"] == "active":
                    total_goal_attention_score += duration * 0.05

        penalty_for_switches = self.context_switches * 5

        avg_planning_coherence = (
            sum(self.planning_coherence_scores) / len(self.planning_coherence_scores)
            if self.planning_coherence_scores
            else 0
        )

        cra_score = (
            total_goal_attention_score
            + avg_planning_coherence * 10
            - penalty_for_switches
        )
        return max(0, min(100, cra_score))

    def _avg(self, values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def calculate_reasoning_score(self, data: Dict[str, float]) -> float:
        vals = [
            float(data.get(k, 0.0))
            for k in (
                "logical_consistency",
                "causal_inference",
                "decision_quality",
                "problem_solving_efficiency",
            )
        ]
        return self._avg(vals)

    def calculate_planning_score(self, data: Dict[str, float]) -> float:
        vals = [
            float(data.get(k, 0.0))
            for k in (
                "goal_decomposition",
                "resource_allocation",
                "timeline_estimation",
                "contingency_planning",
            )
        ]
        return self._avg(vals)

    def calculate_learning_score(self, data: Dict[str, float]) -> float:
        vals = [
            float(data.get(k, 0.0))
            for k in (
                "knowledge_acquisition",
                "skill_development",
                "adaptation_speed",
                "knowledge_retention",
            )
        ]
        return self._avg(vals)

    def calculate_memory_score(self, data: Dict[str, float]) -> float:
        vals = [
            float(data.get(k, 0.0))
            for k in (
                "short_term_memory",
                "long_term_memory",
                "working_memory",
                "episodic_memory",
            )
        ]
        return self._avg(vals)

    def calculate_attention_score(self, data: Dict[str, float]) -> float:
        vals = [
            float(data.get(k, 0.0))
            for k in (
                "selective_attention",
                "sustained_attention",
                "divided_attention",
                "attention_switching",
            )
        ]
        return self._avg(vals)

    def generate_cognitive_report(self, data: Dict[str, float]) -> Dict[str, float]:
        return {
            "reasoning_score": self.calculate_reasoning_score(data),
            "planning_score": self.calculate_planning_score(data),
            "learning_score": self.calculate_learning_score(data),
            "memory_score": self.calculate_memory_score(data),
            "attention_score": self.calculate_attention_score(data),
        }

    def get_metrics_breakdown(self) -> Dict[str, float]:
        cra_score = self.calculate_cra_score()
        return {
            "cra_score": cra_score,
            "context_switches": float(self.context_switches),
            "avg_planning_coherence": (
                sum(self.planning_coherence_scores)
                / len(self.planning_coherence_scores)
                if self.planning_coherence_scores
                else 0.0
            ),
        }

    def get_status_summary(self) -> Dict[str, Any]:
        return self.get_metrics_breakdown()
