# src/scenarios/tier_manager.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TierLevel(str, Enum):
    """Curriculum tier levels compatible with tests."""

    T0 = "T0"  # Basic single-agent scenarios
    T1 = "T1"  # Advanced single-agent scenarios
    T2 = "T2"  # Multi-agent competitive scenarios
    T3 = "T3"  # Complex market dynamics scenarios


@dataclass(frozen=True)
class TierRequirements:
    """Requirements to progress across tiers."""

    required_successes: Dict[TierLevel, int] = field(
        default_factory=lambda: {
            TierLevel.T0: 3,
            TierLevel.T1: 5,
            TierLevel.T2: 4,
            TierLevel.T3: 3,  # Final tier - still tracked for reporting
        }
    )


@dataclass
class TierProgression:
    """Tracks an agent's progression and history across tiers."""

    agent_id: str
    current_tier: TierLevel = TierLevel.T0
    completed_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    tier_completions: Dict[TierLevel, bool] = field(
        default_factory=lambda: {t: False for t in TierLevel}
    )
    tier_attempts: Dict[TierLevel, int] = field(
        default_factory=lambda: {t: 0 for t in TierLevel}
    )
    progression_timestamps: Dict[str, str] = field(default_factory=dict)

    def record_attempt(self, tier: TierLevel) -> None:
        self.tier_attempts[tier] = self.tier_attempts.get(tier, 0) + 1

    def record_completion(self, result: Dict[str, Any]) -> None:
        """
        Append a completed scenario result for auditing and downstream analysis.

        Expected keys in result (best-effort, tests tolerate variation):
        - scenario_name: str
        - tier_level: TierLevel or str
        - success: bool
        - performance_metrics: Dict[str, float]
        - duration_seconds: float
        """
        self.completed_scenarios.append(result)


class TierManager:
    """
    Provides tier requirements and promotion logic used by scenario curriculum tests.
    """

    def __init__(self, requirements: Optional[TierRequirements] = None) -> None:
        self._requirements = requirements or TierRequirements()

    @property
    def requirements(self) -> TierRequirements:
        return self._requirements

    @staticmethod
    def next_tier(current: TierLevel) -> TierLevel:
        mapping = {
            TierLevel.T0: TierLevel.T1,
            TierLevel.T1: TierLevel.T2,
            TierLevel.T2: TierLevel.T3,
            TierLevel.T3: TierLevel.T3,  # Final tier
        }
        return mapping[current]

    def should_progress(self, progression: TierProgression) -> bool:
        """
        Determine if an agent should progress to the next tier based on
        the number of successful scenarios completed at the current tier.
        """
        required = self._requirements.required_successes.get(
            progression.current_tier, 999
        )
        succeeded = 0
        for s in progression.completed_scenarios:
            tier_val = s.get("tier_level")
            # Accept both Enum and string for robustness
            if isinstance(tier_val, TierLevel):
                same_tier = tier_val == progression.current_tier
            else:
                same_tier = str(tier_val) == progression.current_tier.value
            
            # Relaxed boolean check for robustness (Issue 66)
            if same_tier and bool(s.get("success")):
                succeeded += 1
        return succeeded >= required

    def record_scenario_completion(
        self, progression: TierProgression, result: Dict[str, Any]
    ) -> TierProgression:
        """
        Update attempts, record result, and promote if requirements are met.
        Returns the updated progression object (for chaining).
        """
        # Normalize and record attempt for the scenario's tier (defaults to current tier)
        tier_level = result.get("tier_level") or progression.current_tier
        if not isinstance(tier_level, TierLevel):
            try:
                tier_level = TierLevel(str(tier_level))
            except Exception:
                tier_level = progression.current_tier

        progression.record_attempt(tier_level)
        progression.record_completion(result)

        # If this result corresponds to current tier, check progression
        if tier_level == progression.current_tier and self.should_progress(progression):
            old = progression.current_tier
            new_tier = self.next_tier(old)
            if new_tier != old:
                progression.current_tier = new_tier
                progression.tier_completions[old] = True
                progression.progression_timestamps[new_tier.value] = (
                    datetime.now().isoformat()
                )
        return progression
