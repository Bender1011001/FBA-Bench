from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScenarioTemplate(str, Enum):
    """Built-in scenario generation templates."""

    BASIC = "basic"
    MODERATE = "moderate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass(frozen=True)
class GenerationConfig:
    """Configuration for generating a scenario."""

    tier: int  # 0..3
    template: ScenarioTemplate = ScenarioTemplate.BASIC
    seed: Optional[int] = 42
    expected_duration: int = 10
    # knobs to shape markets
    market_volatility: float = 0.1
    competition_level: float = 0.1
    # external events
    num_events: int = 2
    # business parameters
    categories: List[str] = field(default_factory=lambda: ["general"])
    supply_chain_complexity: str = "low"


class ScenarioGenerator:
    """
    Deterministic scenario generator that produces scenario dicts compatible with ScenarioEngine
    and tests expecting scenarios.scenario_generator.{ScenarioGenerator, GenerationConfig, ScenarioTemplate}.
    """

    def __init__(self, default_seed: int = 42) -> None:
        self.default_seed = default_seed

    def _rng(self, cfg: GenerationConfig) -> random.Random:
        return random.Random(cfg.seed if cfg.seed is not None else self.default_seed)

    def _template_defaults(self, cfg: GenerationConfig) -> Dict[str, Any]:
        # Map template to reasonable defaults, overridden by cfg
        mapping = {
            ScenarioTemplate.BASIC: {
                "duration": 5,
                "volatility": 0.05,
                "competition": 0.1,
                "events": 0,
                "supply_complexity": "low",
            },
            ScenarioTemplate.MODERATE: {
                "duration": 10,
                "volatility": 0.15,
                "competition": 0.2,
                "events": 2,
                "supply_complexity": "medium",
            },
            ScenarioTemplate.ADVANCED: {
                "duration": 15,
                "volatility": 0.3,
                "competition": 0.35,
                "events": 3,
                "supply_complexity": "high",
            },
            ScenarioTemplate.EXPERT: {
                "duration": 20,
                "volatility": 0.5,
                "competition": 0.5,
                "events": 4,
                "supply_complexity": "very_high",
            },
        }
        base = mapping.get(cfg.template, mapping[ScenarioTemplate.BASIC])
        return {
            "expected_duration": cfg.expected_duration or base["duration"],
            "market_volatility": max(cfg.market_volatility, base["volatility"]),  # type: ignore[call-overload]
            "competition_level": max(cfg.competition_level, base["competition"]),  # type: ignore[call-overload]
            "num_events": max(cfg.num_events, base["events"]),  # type: ignore[call-overload]
            "supply_chain_complexity": cfg.supply_chain_complexity
            or base["supply_complexity"],
        }

    def _make_events(
        self, cfg: GenerationConfig, rng: random.Random, count: int
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for i in range(count):
            events.append(
                {
                    "name": f"AutoEvent_{i+1}",
                    "tick": 1
                    + rng.randint(1, max(2, int(0.8 * (cfg.expected_duration or 10)))),
                    "type": rng.choice(
                        ["market_event", "demand_spike", "fee_hike", "supplier_delay"]
                    ),
                    "impact": rng.choice(["small", "moderate", "significant"]),
                }
            )
        # ensure deterministic order by tick then name
        events.sort(key=lambda e: (e["tick"], e["name"]))
        return events

    def generate(self, cfg: GenerationConfig) -> Dict[str, Any]:
        """
        Generate a single scenario configuration dict that ScenarioEngine.run_simulation can consume.
        Keys produced align with scenarios/scenario_config.py expectations.
        """
        rng = self._rng(cfg)
        defaults = self._template_defaults(cfg)
        categories = cfg.categories or ["general"]

        scenario: Dict[str, Any] = {
            "scenario_name": f"Generated T{cfg.tier} {cfg.template.value.capitalize()}",
            "difficulty_tier": int(cfg.tier),
            "expected_duration": int(defaults["expected_duration"]),
            "success_criteria": {
                "profit_target": float(
                    1000 * (cfg.tier + 1)
                ),  # progressively higher target by tier
            },
            "market_conditions": {
                "economic_cycles": rng.choice(["stable", "seasonal", "volatile"]),
                "market_volatility": float(defaults["market_volatility"]),
                "competition_level": float(defaults["competition_level"]),
            },
            "external_events": self._make_events(cfg, rng, int(defaults["num_events"])),
            "agent_constraints": {
                "initial_capital": int(10000 * (1 + 0.25 * cfg.tier)),
                "max_debt_ratio": 0.75 if cfg.tier < 3 else 0.6,
            },
            "business_parameters": {
                "product_categories": categories,
                "supply_chain_complexity": defaults["supply_chain_complexity"],
            },
        }
        return scenario

    @staticmethod
    def generate_for_tier(
        tier: int,
        template: Optional[ScenarioTemplate] = None,
        count: int = 3,
        seed: Optional[int] = 42,
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to generate N scenarios for a tier.
        """
        gen = ScenarioGenerator(default_seed=seed or 42)
        scenarios: List[Dict[str, Any]] = []
        # pick template progression if not provided
        tmap = {
            0: ScenarioTemplate.BASIC,
            1: ScenarioTemplate.MODERATE,
            2: ScenarioTemplate.ADVANCED,
            3: ScenarioTemplate.EXPERT,
        }
        base_template = template or tmap.get(int(tier), ScenarioTemplate.BASIC)
        for i in range(max(1, int(count))):
            cfg = GenerationConfig(
                tier=int(tier),
                template=base_template,
                seed=(seed + i) if isinstance(seed, int) else None,
                expected_duration=10 + 2 * int(tier),
                market_volatility=0.05 + 0.1 * int(tier),
                competition_level=0.1 + 0.15 * int(tier),
                num_events=min(5, 1 + int(tier) + (i % 2)),
                categories=(
                    ["general"]
                    if tier == 0
                    else (
                        ["general", "healthcare"]
                        if tier == 1
                        else (
                            ["general", "finance", "healthcare"]
                            if tier == 2
                            else ["general", "finance", "healthcare", "supply_chain"]
                        )
                    )
                ),
                supply_chain_complexity=(
                    "low"
                    if tier == 0
                    else "medium" if tier == 1 else "high" if tier == 2 else "very_high"
                ),
            )
            scenarios.append(gen.generate(cfg))
        return scenarios
