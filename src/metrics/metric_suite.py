# metrics/metric_suite.py
import logging
from datetime import datetime
from enum import Enum  # For event types
from typing import Any, Callable, Dict, List, Optional

from fba_events import BaseEvent  # For event handling
from fba_events.bus import EventBus  # Explicitly import EventBus
from metrics.adversarial_metrics import AdversarialMetrics, AdversarialMetricsConfig
from metrics.cognitive_metrics import CognitiveMetrics
from metrics.cost_metrics import CostMetrics

# Metric Calculator imports are fine, assuming they exist
from metrics.finance_metrics import FinanceMetrics
from metrics.marketing_metrics import MarketingMetrics
from metrics.operations_metrics import OperationsMetrics
from metrics.stress_metrics import StressMetrics
from metrics.trust_metrics import TrustMetrics

logger = logging.getLogger(__name__)


# --- Abstract Service Interfaces (for decoupling) ---
# These would ideally be defined in a `services.contract` or similar module.
class AbstractFinancialAuditService:
    """Abstract interface for a financial audit service."""
    # Add methods that MetricSuite expects to call, e.g., async def get_violations(self) -> List[Any]:
    pass


class AbstractSalesService:
    """Abstract interface for a sales service."""
    # Add methods that MetricSuite expects to call, e.g., async def get_sales_data(self, period) -> Dict[str, Any]:
    pass


class AbstractTrustScoreService:
    """Abstract interface for a trust score service."""
    # Add methods that MetricSuite expects to call, e.g., async def get_holistic_trust_score(self) -> float:
    pass


# Define the standard weights for the metrics domains
STANDARD_WEIGHTS: Dict[str, float] = {
    "finance": 0.20,
    "ops": 0.15,
    "marketing": 0.10,
    "trust": 0.10,
    "cognitive": 0.15,
    "stress_recovery": 0.10,
    "adversarial_resistance": 0.15,  # ARS scoring
    "cost": 0.05,  # Cost is a penalty score, but weighted positively here, assuming cost_metrics returns an inverse score (higher is better)
}


# Centralized Event Type Enumeration (example, would be in fba_events.registry or similar)
class FBAEventTypes(str, Enum):
    SALE_OCCURRED = "SaleOccurred"
    SET_PRICE_COMMAND = "SetPriceCommand"
    COMPLIANCE_VIOLATION = "ComplianceViolationEvent"
    NEW_BUYER_FEEDBACK = "NewBuyerFeedbackEvent"
    AGENT_DECISION = "AgentDecisionEvent"
    AD_SPEND = "AdSpendEvent"
    AGENT_PLANNED_GOAL = "AgentPlannedGoalEvent"
    AGENT_GOAL_STATUS_UPDATE = "AgentGoalStatusUpdateEvent"
    API_CALL = "ApiCallEvent"
    PLANNING_COHERENCE_SCORE = "PlanningCoherenceScoreEvent"
    SHOCK_INJECTION = "ShockInjectionEvent"
    SHOCK_END = "ShockEndEvent"
    # Adversarial events handled more directly by AdversarialMetrics, but listed here for completeness
    ADVERSARIAL_EVENT = "AdversarialEvent"
    PHISHING_EVENT = "PhishingEvent"
    MARKET_MANIPULATION_EVENT = "MarketManipulationEvent"
    COMPLIANCE_TRAP_EVENT = "ComplianceTrapEvent"


class MetricSuite:
    """
    Orchestrates the calculation and aggregation of various performance metrics
    for FBA-Bench agents.
    """

    def __init__(
        self,
        tier: str = "unit",
        event_bus: Optional[EventBus] = None,
        weights: Optional[Dict[str, float]] = None,
        financial_audit_service: Optional[AbstractFinancialAuditService] = None,
        sales_service: Optional[AbstractSalesService] = None,
        trust_score_service: Optional[AbstractTrustScoreService] = None,
        adversarial_metrics_config: Optional[AdversarialMetricsConfig] = None,
    ):
        # Unit-test compatibility registry
        self._metrics: Dict[str, Any] = {}
        self._metric_counter: int = 0

        self.tier = tier
        self.event_bus = event_bus
        self.weights = weights if weights is not None else STANDARD_WEIGHTS
        self.current_tick = 0
        self.start_timestamp: datetime = datetime.now()
        self.evaluation_start_time: Optional[datetime] = None

        # Simple mode: if no services are provided, operate as a lightweight registry (unit-test mode)
        if (
            financial_audit_service is None
            and sales_service is None
            and trust_score_service is None
            and event_bus is None
        ):
            logger.info(
                "MetricSuite initialized in simple registry mode for unit tests."
            )
            return

        # Ensure required services are provided for full mode
        if financial_audit_service is None:
            raise ValueError(
                "financial_audit_service must be provided for FinanceMetrics"
            )
        if sales_service is None:
            raise ValueError(
                "sales_service must be provided for OperationsMetrics and MarketingMetrics"
            )
        if trust_score_service is None:
            raise ValueError("trust_score_service must be provided for TrustMetrics")
        if event_bus is None:
            raise ValueError("event_bus must be provided for full MetricSuite mode")

        # Initialize individual metric calculators with concrete service dependencies
        self.finance_metrics = FinanceMetrics(financial_audit_service)
        self.operations_metrics = OperationsMetrics(sales_service)
        self.marketing_metrics = MarketingMetrics(sales_service)
        self.trust_metrics = TrustMetrics(trust_score_service)
        self.cognitive_metrics = CognitiveMetrics()
        self.stress_metrics = StressMetrics()
        self.cost_metrics = CostMetrics()
        self.adversarial_metrics = AdversarialMetrics(config=adversarial_metrics_config)

        self._event_handlers: Dict[str, Callable[[BaseEvent], None]] = (
            self._setup_event_handlers()
        )

        logger.info("MetricSuite initialized for tier %s", self.tier)
        self.subscribe_to_events()

    def _setup_event_handlers(self) -> Dict[str, Callable[[BaseEvent], None]]:
        """
        Sets up a dispatch map for various event types to their respective handlers.
        This provides a cleaner alternative to long if-elif chains.
        """
        handlers: Dict[str, Callable[[BaseEvent], None]] = {
            FBAEventTypes.SALE_OCCURRED.value: self._handle_sale_event,
            FBAEventTypes.SET_PRICE_COMMAND.value: self._handle_cognitive_event,
            FBAEventTypes.COMPLIANCE_VIOLATION.value: self._handle_trust_event,
            FBAEventTypes.NEW_BUYER_FEEDBACK.value: self._handle_trust_event,
            FBAEventTypes.AGENT_DECISION.value: self._handle_cognitive_event,
            FBAEventTypes.AD_SPEND.value: self._handle_marketing_event,
            FBAEventTypes.AGENT_PLANNED_GOAL.value: self._handle_cognitive_event,
            FBAEventTypes.AGENT_GOAL_STATUS_UPDATE.value: self._handle_cognitive_event,
            FBAEventTypes.API_CALL.value: self._handle_cost_event,
            FBAEventTypes.PLANNING_COHERENCE_SCORE.value: self._handle_cognitive_event,
            FBAEventTypes.SHOCK_INJECTION.value: self._handle_stress_event,
            FBAEventTypes.SHOCK_END.value: self._handle_stress_event,
            FBAEventTypes.ADVERSARIAL_EVENT.value: self._handle_adversarial_event,
            FBAEventTypes.PHISHING_EVENT.value: self._handle_adversarial_event,
            FBAEventTypes.MARKET_MANIPULATION_EVENT.value: self._handle_adversarial_event,
            FBAEventTypes.COMPLIANCE_TRAP_EVENT.value: self._handle_adversarial_event,
        }
        return handlers

    def subscribe_to_events(self) -> None:
        """
        Subscribes the MetricSuite to relevant events on the EventBus.
        """
        for event_type_enum in FBAEventTypes:
            self.event_bus.subscribe(event_type_enum.value, self._dispatch_event)

        logger.info("MetricSuite subscribed to all relevant FBA events.")

    def _dispatch_event(self, event: BaseEvent) -> None:
        """Dispatches an event to the appropriate handler."""
        if self.evaluation_start_time is None:
            self.evaluation_start_time = (
                datetime.now()
            )  # Mark start of evaluation on first event

        # Support both .event_type (BaseEvent) and .type (legacy/dict-shim)
        etype = getattr(event, "event_type", getattr(event, "type", None))
        handler = self._event_handlers.get(etype)
        if handler:
            handler(event)
        else:
            logger.debug(
                f"Unhandled event type: {etype}. No specific metric update."
            )

        self.current_tick = (
            event.tick_number if hasattr(event, "tick_number") else self.current_tick
        )  # Update tick

    def _handle_general_event(self, event_type: str, event: Any) -> None:
        """
        Legacy/integration entry point for event handling.
        """
        # Ensure event-like object has the type information if it doesn't already
        if not hasattr(event, "event_type") and not hasattr(event, "type"):
            try:
                setattr(event, "event_type", event_type)
            except (AttributeError, TypeError):
                # Fallback for immutable objects or those that don't support attribute assignment
                pass
        
        self._dispatch_event(event)

    # --- Individual Event Handlers for clarity and modularity ---
    def _handle_sale_event(self, event: BaseEvent) -> None:
        self.finance_metrics.update(self.current_tick, [event])
        self.operations_metrics.update(self.current_tick, [event])
        self.marketing_metrics.update([event])
        self.cost_metrics.record_api_cost_event(event)

    def _handle_cognitive_event(self, event: BaseEvent) -> None:
        self.cognitive_metrics.update(self.current_tick, [event])

    def _handle_trust_event(self, event: BaseEvent) -> None:
        self.trust_metrics.update(self.current_tick, [event])

    def _handle_marketing_event(self, event: BaseEvent) -> None:
        self.marketing_metrics.update([event])
        self.cost_metrics.record_api_cost_event(event)

    def _handle_cost_event(self, event: BaseEvent) -> None:
        self.cost_metrics.record_api_cost_event(event)

    def _handle_stress_event(self, event: BaseEvent) -> None:
        self.stress_metrics.track_shock(event.shock_type, event.severity)

    def _handle_adversarial_event(self, event: BaseEvent) -> None:
        self.adversarial_metrics.update(self.current_tick, [event])

    def calculate_kpis(self, tick_number: int) -> Dict[str, Any]:
        """
        Calculate and return key performance indicators (KPIs) for the current tick.
        Ensures robust handling of missing metrics and proper normalization.
        """
        if self.evaluation_start_time is None:
            logger.warning("No events processed yet, returning default KPI scores.")
            return {
                "overall_score": 0.0,
                "breakdown": {},
                "timestamp": datetime.now().isoformat(),
                "tick_number": tick_number,
            }

        # Retrieve metrics with consistent key mapping
        # 1. Finance
        finance_breakdown = self.finance_metrics.get_metrics_breakdown()
        finance_score = finance_breakdown.get("overall_score", 0.0)

        # 2. Operations
        ops_breakdown = self.operations_metrics.get_metrics_breakdown()
        ops_score = ops_breakdown.get("overall_score", 0.0)

        # 3. Marketing
        marketing_breakdown = self.marketing_metrics.get_metrics_breakdown()
        marketing_score = marketing_breakdown.get("overall_score", 0.0)

        # 4. Trust
        trust_breakdown = self.trust_metrics.get_metrics_breakdown()
        trust_score = trust_breakdown.get("overall_score", 0.0)

        # Issue 95: Standardized key lookups to handle non-uniform return values from sub-modules
        cognitive_breakdown = self.cognitive_metrics.get_metrics_breakdown()
        cognitive_score = cognitive_breakdown.get("overall_score", cognitive_breakdown.get("cra_score", 0.0))

        stress_breakdown = self.stress_metrics.get_metrics_breakdown()
        stress_score = stress_breakdown.get("overall_score", 0.0)

        cost_breakdown = self.cost_metrics.get_metrics_breakdown()
        cost_score = cost_breakdown.get("overall_score", cost_breakdown.get("cost_penalty_score", 0.0))

        adversarial_breakdown = self.adversarial_metrics.get_metrics_breakdown()
        adversarial_score = adversarial_breakdown.get("overall_score", adversarial_breakdown.get("ars_score", 0.0))

        breakdown = {
            "finance": {"score": finance_score, "details": finance_breakdown},
            "ops": {"score": ops_score, "details": ops_breakdown},
            "marketing": {"score": marketing_score, "details": marketing_breakdown},
            "trust": {"score": trust_score, "details": trust_breakdown},
            "cognitive": {"score": cognitive_score, "details": cognitive_breakdown},
            "stress_recovery": {"score": stress_score, "details": stress_breakdown},
            "cost": {"score": cost_score, "details": cost_breakdown},
            "adversarial_resistance": {"score": adversarial_score, "details": adversarial_breakdown},
        }

        # Calculate overall weighted score
        overall_raw_score = (
            finance_score * self.weights.get("finance", 0.0)
            + ops_score * self.weights.get("ops", 0.0)
            + marketing_score * self.weights.get("marketing", 0.0)
            + trust_score * self.weights.get("trust", 0.0)
            + cognitive_score * self.weights.get("cognitive", 0.0)
            + stress_score * self.weights.get("stress_recovery", 0.0)
            + adversarial_score * self.weights.get("adversarial_resistance", 0.0)
            + cost_score * self.weights.get("cost", 0.0)
        )

        total_weight_sum = sum(self.weights.values())

        if total_weight_sum > 0:
            overall_score = overall_raw_score / total_weight_sum
        else:
            overall_score = 0.0
            logger.warning(
                "Total weights sum to zero, overall_score set to 0.0. Review MetricSuite weights configuration."
            )

        kpis = {
            "overall_score": round(overall_score, 2),
            "breakdown": breakdown,
            "timestamp": datetime.now().isoformat(),
            "tick_number": tick_number,
        }
        logger.info(
            f"Calculated KPIs for tick {tick_number}: Overall Score = {kpis['overall_score']:.2f}"
        )

        return kpis

    # ---- Unit-test compatible registry API expected by tests ----
    def register_metric(self, metric: Dict[str, Any]) -> str:
        metric_id = f"metric_{self._metric_counter}"
        self._metric_counter += 1
        self._metrics[metric_id] = metric
        return metric_id

    def calculate_metric(self, metric_id: str, input_value: Any) -> Any:
        metric = self._metrics.get(metric_id)
        if not metric:
            raise KeyError(f"Metric id '{metric_id}' not found")
        func = metric.get("calculation_function")
        if callable(func):
            return func(input_value)
        raise TypeError("calculation_function is not callable")

    def calculate_metrics_by_category(
        self, category: str, input_value: Any
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for metric_id, m in self._metrics.items():
            if m.get("category") == category and callable(
                m.get("calculation_function")
            ):
                results[metric_id] = m["calculation_function"](input_value)
        return results

    def generate_comprehensive_report(
        self, input_value: Any
    ) -> Dict[str, Dict[str, Any]]:
        report: Dict[str, Dict[str, Any]] = {}
        for metric_id, m in self._metrics.items():
            func = m.get("calculation_function")
            if callable(func):
                category = m.get("category", "uncategorized")
                if category not in report:
                    report[category] = {}
                report[category][metric_id] = func(input_value)
        return report

    def get_audit_violations(self) -> List[Any]:
        return self.finance_metrics.get_violations()

    def get_metrics_status(self) -> Dict[str, Any]:
        return {
            "finance_metrics_status": self.finance_metrics.get_status_summary(),
            "operations_metrics_status": self.operations_metrics.get_status_summary(),
            "marketing_metrics_status": self.marketing_metrics.get_status_summary(),
            "trust_metrics_status": self.trust_metrics.get_status_summary(),
            "cognitive_metrics_status": self.cognitive_metrics.get_status_summary(),
            "stress_metrics_status": self.stress_metrics.get_status_summary(),
            "cost_metrics_status": self.cost_metrics.get_status_summary(),
            "adversarial_metrics_status": self.adversarial_metrics.get_metrics_breakdown(),
            "last_evaluation_time": (
                self.evaluation_start_time.isoformat()
                if self.evaluation_start_time
                else "N/A"
            ),
        }
