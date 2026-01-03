from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AgentRole(str, Enum):
    """Agent roles used in multi-agent scenarios."""

    SELLER = "seller"
    SUPPLIER = "supplier"
    PLATFORM = "platform"
    COMPETITOR = "competitor"
    ANALYST = "analyst"


class CoordinationMode(str, Enum):
    """Coordination modes for multi-agent orchestration."""

    COOPERATIVE = "cooperative"
    COMPETITIVE = "competitive"
    ADAPTIVE = "adaptive"


@dataclass
class CoordinationStats:
    """Runtime metrics for coordination effectiveness."""

    total_events: int = 0
    total_actions: int = 0
    coordinated_events: int = 0
    competitive_conflicts: int = 0
    cooperation_successes: int = 0
    coordination_effectiveness: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "total_actions": self.total_actions,
            "coordinated_events": self.coordinated_events,
            "competitive_conflicts": self.competitive_conflicts,
            "cooperation_successes": self.cooperation_successes,
            "coordination_effectiveness": self.coordination_effectiveness,
        }


@dataclass
class MultiAgentCoordinator:
    """
    Orchestrates coordination across multiple agents for scenario events.

    Expected to be used by tests via:
      - MultiAgentCoordinator(agent_ids, coordination_mode=CoordinationMode.ADAPTIVE)
      - await coordinate_responses(market_events, {aid: agents[aid]["skill_coordinator"]})
      - await coordinate_complex_responses(market_events, external_factors, {...})
      - await process_agent_interactions(agent_actions)
      - await get_coordination_metrics()
    """

    agent_ids: List[str]
    coordination_mode: CoordinationMode = CoordinationMode.COOPERATIVE
    agent_roles: Dict[str, AgentRole] = field(default_factory=dict)
    _stats: CoordinationStats = field(default_factory=CoordinationStats)

    # ------------------------ Internal utilities ------------------------

    @staticmethod
    def _is_async_callable(obj: Any, name: str) -> bool:
        fn = getattr(obj, name, None)
        return asyncio.iscoroutinefunction(fn)

    async def _dispatch_with_coordinator(
        self,
        coordinator: Any,
        event: Any,
    ) -> List[Any]:
        """
        Calls coordinator.dispatch_event(event) if available and returns list of actions.
        Tolerates coordinators that return non-list values.
        """
        actions: List[Any] = []
        if coordinator is None:
            return actions

        if self._is_async_callable(coordinator, "dispatch_event"):
            try:
                result = await coordinator.dispatch_event(event)
                if isinstance(result, list):
                    actions.extend(result)
                elif result is not None:
                    actions.append(result)
            except (AttributeError, TypeError, ValueError, RuntimeError):
                # Non-fatal; skip broken coordinator output
                pass
        return actions

    def _score_cooperation(self, all_actions: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Rough heuristic:
          - Cooperation success if multiple distinct action_types present across agents for same event.
          - Competitive conflict if multiple agents emit the same exclusive action type (e.g., 'set_price') simultaneously.
        """
        if not all_actions:
            return (0, 0)
        types = [
            a.get("action_type") or a.get("type")
            for a in all_actions
            if isinstance(a, dict)
        ]
        distinct = len(set(types))
        cooperation_success = 1 if distinct > 1 else 0

        # simplistic notion of conflict: many identical action types in same event window
        conflict = 1 if any(types.count(t) > 1 for t in set(types)) else 0
        return (cooperation_success, conflict)

    def _update_effectiveness(self) -> None:
        # Effectiveness = (cooperation_successes - conflicts) normalized by total_events (>=1)
        denom = max(1, self._stats.total_events)
        raw = (
            self._stats.cooperation_successes - self._stats.competitive_conflicts
        ) / denom
        # clamp to [0,1]
        self._stats.coordination_effectiveness = max(
            0.0, min(1.0, raw + 0.5)
        )  # center 0 at 0.5

    # ------------------------ Public API used by tests ------------------------

    async def coordinate_responses(
        self,
        market_events: List[Any],
        skill_coordinators_by_agent: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Coordinate agent responses for a batch of market events.
        Returns a flat list of action dicts.

        Each coordinator is expected (but not required) to implement:
          async def dispatch_event(event) -> list[ActionDict] | ActionDict | None
        """
        aggregated_actions: List[Dict[str, Any]] = []
        for event in market_events or []:
            self._stats.total_events += 1
            event_actions: List[Dict[str, Any]] = []
            # Fan-out event to each agent's SkillCoordinator
            for agent_id, coordinator in (skill_coordinators_by_agent or {}).items():
                actions = await self._dispatch_with_coordinator(coordinator, event)
                # annotate actions with agent_id if missing
                for a in actions:
                    if isinstance(a, dict):
                        a.setdefault("agent_id", agent_id)
                        a.setdefault("source", "skill_coordinator")
                        event_actions.append(a)
            self._stats.total_actions += len(event_actions)
            if len(event_actions) > 1:
                self._stats.coordinated_events += 1

            coop, conflict = self._score_cooperation(event_actions)
            self._stats.cooperation_successes += coop
            self._stats.competitive_conflicts += conflict
            self._update_effectiveness()

            aggregated_actions.extend(event_actions)
        return aggregated_actions

    async def coordinate_complex_responses(
        self,
        market_events: List[Any],
        external_factors: Dict[str, Any],
        skill_coordinators_by_agent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Advanced coordination that can weigh roles, external factors, and mode.

        Returns a summary dict with:
          {
            "actions": [...],
            "mode": str,
            "external_factors_used": bool,
            "coordination_metrics": {...}
          }
        """
        actions = await self.coordinate_responses(
            market_events, skill_coordinators_by_agent
        )

        # Apply simple prioritization based on mode and agent roles
        if self.coordination_mode == CoordinationMode.COMPETITIVE:
            # Prefer competitor/platform actions first
            priority_roles = {AgentRole.COMPETITOR, AgentRole.PLATFORM}
        elif self.coordination_mode == CoordinationMode.COOPERATIVE:
            # Prefer seller/supplier collaboration actions
            priority_roles = {AgentRole.SELLER, AgentRole.SUPPLIER}
        else:  # ADAPTIVE
            # If external volatility high, prefer platform/analyst stabilization; else seller/supplier
            volatility = float(
                external_factors.get("market_volatility", 0.0)
                if external_factors
                else 0.0
            )
            priority_roles = (
                {AgentRole.PLATFORM, AgentRole.ANALYST}
                if volatility >= 0.5
                else {AgentRole.SELLER, AgentRole.SUPPLIER}
            )

        def role_of(agent_id: str) -> Optional[AgentRole]:
            return self.agent_roles.get(agent_id)

        def role_priority(agent_id: str) -> int:
            r = role_of(agent_id)
            return 0 if r in priority_roles else 1

        # Stable sort with role-based priority, then by action_type for determinism
        actions.sort(
            key=lambda a: (
                (
                    role_priority(a.get("agent_id", "")),
                    str(a.get("action_type") or a.get("type") or ""),
                )
                if isinstance(a, dict)
                else (1, "")
            )
        )

        summary = {
            "actions": actions,
            "mode": self.coordination_mode.value,
            "external_factors_used": bool(external_factors),
            "coordination_metrics": await self.get_coordination_metrics(),
        }
        return summary

    async def process_agent_interactions(
        self, agent_actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Processes interactions among actions (e.g., merge compatible ones or flag conflicts).
        Returns a summary with merged actions and conflict indicators.
        """
        # Build buckets by action_type for simple interaction processing
        type_buckets: Dict[str, List[Dict[str, Any]]] = {}
        for a in agent_actions or []:
            if isinstance(a, dict):
                t = str(a.get("action_type") or a.get("type") or "unknown")
                type_buckets.setdefault(t, []).append(a)

        merged: List[Dict[str, Any]] = []
        conflicts: List[str] = []

        for t, bucket in type_buckets.items():
            if len(bucket) == 1:
                merged.append(bucket[0])
            else:
                # if cooperative mode, try to merge parameters; otherwise mark as conflict
                if self.coordination_mode == CoordinationMode.COOPERATIVE:
                    combined = dict(bucket[0])  # shallow copy
                    combined["merged_from"] = [a.get("agent_id") for a in bucket]
                    merged.append(combined)
                    self._stats.cooperation_successes += 1
                else:
                    conflicts.append(t)
                    self._stats.competitive_conflicts += 1

        self._update_effectiveness()
        return {
            "merged_actions": merged,
            "conflicts": conflicts,
            "coordination_metrics": await self.get_coordination_metrics(),
        }

    async def get_coordination_metrics(self) -> Dict[str, Any]:
        """Return current coordination metrics as a dict."""
        return self._stats.as_dict()
