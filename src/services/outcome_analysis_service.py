"""
OutcomeAnalysisService: analyzes post-tick outcomes and produces SkillOutcome objects for agent learning.
The service reads from EventBus recording (AsyncioQueueBackend.start_recording()) and summarizes recent events
into an actionable SkillOutcome to pass into AgentRunner.learn().
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from agents.skill_modules.base_skill import SkillOutcome
from fba_bench_core.event_bus import EventBus

logger = logging.getLogger(__name__)


class OutcomeAnalysisService:
    """
    Subscribes to the EventBus and provides per-agent outcome analyses since the last analysis call.
    It relies on EventBus.get_recorded_events() which contains summary-dict entries for each event.
    """

    def __init__(self) -> None:
        self.event_bus: Optional[EventBus] = None
        # Track last processed index per agent to avoid double counting
        self._last_index_per_agent: Dict[str, int] = {}

    async def start(self, event_bus: EventBus) -> None:
        """
        Initialize the service with the event bus. Recording should already be enabled.
        """
        self.event_bus = event_bus
        logger.info("OutcomeAnalysisService started.")

    async def stop(self) -> None:
        logger.info("OutcomeAnalysisService stopped.")

    async def analyze_tick_outcome(self, agent_id: str) -> Optional[SkillOutcome]:
        """
        Build a SkillOutcome for the specified agent based on recorded events since last analysis.
        Heuristics:
          - success=True if no critical violations occurred and at least some positive signal observed (sales/profit).
          - impact_metrics include revenue, profit, units sold, ad spend, and ROI when available.
        """
        if not self.event_bus:
            logger.warning("OutcomeAnalysisService has no event_bus; cannot analyze.")
            return None

        rec = self.event_bus.get_recorded_events()
        start_idx = self._last_index_per_agent.get(agent_id, 0)
        if start_idx >= len(rec):
            return None

        # Aggregate outcomes for this slice
        revenue = 0.0
        profit = 0.0
        units = 0
        ad_spend = 0.0
        errors = 0
        action_event_id: Optional[str] = None
        confidence_validation = 0.0

        for idx in range(start_idx, len(rec)):
            ev = rec[idx]
            etype = ev.get("event_type", "")
            data = ev.get("data", {}) or {}
            # Agent association can come from various fields in summaries
            ev_agent = (
                data.get("agent_id") or data.get("agent") or data.get("source_agent")
            )
            if ev_agent and ev_agent != agent_id:
                continue

            # Treat commands and explicit agent decision signals as the "action anchor"
            if etype.endswith("Command") or etype.endswith("AgentDecisionEvent"):
                action_event_id = ev.get("event_id", action_event_id)

            if etype == "SaleOccurred":
                tr = data.get("total_revenue")
                tp = data.get("total_profit")
                try:
                    if tr is not None:
                        revenue += float(str(tr).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    pass
                try:
                    if tp is not None:
                        profit += float(str(tp).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    pass
                units += int(data.get("units_sold", 0))
                # Positive reinforcement when sales follow actions
                confidence_validation += 0.1

            if etype == "AdSpendEvent":
                sp = data.get("spend")
                try:
                    if sp is not None:
                        ad_spend += float(str(sp).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    pass

            if etype in (
                "ComplianceViolationEvent",
                "BudgetWarning",
                "BudgetViolation",
            ):
                errors += 1
                confidence_validation -= 0.1

        # Mark index processed for this agent
        self._last_index_per_agent[agent_id] = len(rec)

        success = (units > 0 or profit > 0.0) and errors == 0
        confidence_validation = max(0.0, min(1.0, confidence_validation))

        roi = (profit / ad_spend) if ad_spend > 0 else 0.0

        outcome = SkillOutcome(
            action_id=action_event_id or f"{agent_id}-no_action",
            success=success,
            impact_metrics={
                "revenue": round(revenue, 2),
                "profit": round(profit, 2),
                "units_sold": int(units),
                "ad_spend": round(ad_spend, 2),
                "roi": round(roi, 4),
            },
            execution_time=0.0,
            resource_cost={"ad_spend": ad_spend},
            lessons_learned=[
                (
                    "Observed positive sales following actions"
                    if units > 0
                    else "No sales impact observed"
                ),
                (
                    "Maintain compliance to avoid violations"
                    if errors == 0
                    else "Address compliance issues detected"
                ),
            ],
            confidence_validation=confidence_validation,
        )
        logger.debug(f"OutcomeAnalysisService outcome for {agent_id}: {outcome}")
        return outcome
