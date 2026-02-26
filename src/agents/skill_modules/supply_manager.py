"""
Supply Manager Skill Module for FBA-Bench Multi-Domain Agent Architecture.

This module handles inventory and supplier management, monitoring stock levels,
evaluating reorder needs, selecting optimal suppliers, and negotiating terms
through LLM-driven decision making.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fba_bench_core.money import Money

from fba_events.base import BaseEvent
from fba_events.inventory import InventoryUpdate
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent

from .base_skill import BaseSkill, SkillAction, SkillContext, SkillOutcome

logger = logging.getLogger(__name__)


@dataclass
class SupplierProfile:
    """
    Profile of a supplier for inventory sourcing decisions.

    Attributes:
        supplier_id: Unique identifier for the supplier
        name: Supplier company name
        reliability_score: Historical reliability (0.0 to 1.0)
        price_competitiveness: Price competitiveness rating (0.0 to 1.0)
        lead_time_days: Typical lead time in days
        minimum_order_quantity: Minimum order quantity
        quality_score: Product quality rating (0.0 to 1.0)
        payment_terms: Payment terms offered
        last_interaction: Last time we interacted with this supplier
        performance_history: Historical performance metrics
    """

    supplier_id: str
    name: str
    reliability_score: float = 0.8
    price_competitiveness: float = 0.7
    lead_time_days: int = 14
    minimum_order_quantity: int = 100
    quality_score: float = 0.9
    payment_terms: str = "Net 30"
    last_interaction: Optional[datetime] = None
    performance_history: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InventoryAnalysis:
    """
    Analysis of current inventory situation for decision making.

    Attributes:
        asin: Product ASIN being analyzed
        current_stock: Current inventory level
        daily_sales_velocity: Average daily sales rate
        days_of_inventory: How many days current stock will last
        reorder_point: Stock level that triggers reorder
        optimal_order_quantity: Recommended order quantity
        stockout_risk: Risk of stockout (0.0 to 1.0)
        carrying_cost: Cost of holding current inventory
        recommended_action: Recommended action to take
    """

    asin: str
    current_stock: int
    daily_sales_velocity: float
    days_of_inventory: float
    reorder_point: int
    optimal_order_quantity: int
    stockout_risk: float
    carrying_cost: Money
    recommended_action: str


class SupplyManagerSkill(BaseSkill):
    """
    Supply Manager Skill for inventory and supplier management.

    Handles inventory monitoring, reorder point calculations, supplier selection,
    and procurement decision making to maintain optimal stock levels while
    minimizing costs and stockout risks.
    """

    def __init__(self, agent_id: str, event_bus, config: Dict[str, Any] = None):
        """
        Initialize the Supply Manager Skill.

        Args:
            agent_id: ID of the agent this skill belongs to
            event_bus: Event bus for communication
            config: Configuration parameters for supply management
        """
        super().__init__("SupplyManager", agent_id, event_bus)

        # Configuration parameters
        self.config = config or {}
        self.safety_stock_days = self.config.get("safety_stock_days", 7)
        self.reorder_lead_time = self.config.get("reorder_lead_time", 14)
        self.max_order_budget = Money(
            self.config.get("max_order_budget_cents", 500000)
        )  # $5000
        self.stockout_risk_threshold = self.config.get("stockout_risk_threshold", 0.3)

        # Inventory tracking
        self.inventory_levels: Dict[str, int] = {}
        self.sales_velocity: Dict[str, float] = {}
        self.inventory_history: Dict[str, List[Tuple[datetime, int]]] = {}
        self.last_reorder_check = datetime.now()

        # Supplier management
        self.suppliers: Dict[str, SupplierProfile] = {}
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
        self.supplier_performance: Dict[str, Dict[str, float]] = {}

        # Performance tracking
        self.stockout_events: List[Dict[str, Any]] = []
        self.successful_reorders: int = 0
        self.total_reorder_attempts: int = 0

        # Initialize default suppliers
        self._initialize_default_suppliers()

        logger.info(f"SupplyManagerSkill initialized for agent {agent_id}")

    def _initialize_default_suppliers(self):
        """Initialize default supplier profiles."""
        self.suppliers = {
            "supplier_001": SupplierProfile(
                supplier_id="supplier_001",
                name="ReliableCorp",
                reliability_score=0.9,
                price_competitiveness=0.7,
                lead_time_days=10,
                minimum_order_quantity=50,
                quality_score=0.95,
            ),
            "supplier_002": SupplierProfile(
                supplier_id="supplier_002",
                name="FastShip Inc",
                reliability_score=0.8,
                price_competitiveness=0.9,
                lead_time_days=5,
                minimum_order_quantity=100,
                quality_score=0.85,
            ),
            "supplier_003": SupplierProfile(
                supplier_id="supplier_003",
                name="BudgetSupply Co",
                reliability_score=0.7,
                price_competitiveness=0.95,
                lead_time_days=20,
                minimum_order_quantity=200,
                quality_score=0.8,
            ),
        }

    async def process_event(self, event: BaseEvent) -> Optional[List[SkillAction]]:
        """
        Process events relevant to supply management and generate actions.

        Args:
            event: Event to process

        Returns:
            List of supply management actions or None
        """
        actions = []

        try:
            if isinstance(event, InventoryUpdate):
                actions.extend(await self._handle_inventory_update(event))
            elif isinstance(event, SaleOccurred):
                actions.extend(await self._handle_sale_occurred(event))
            elif isinstance(event, TickEvent):
                actions.extend(await self._handle_tick_event(event))

            # Filter actions by confidence threshold
            confidence_threshold = self.adaptation_parameters.get(
                "confidence_threshold", 0.6
            )
            filtered_actions = [
                action
                for action in actions
                if action.confidence >= confidence_threshold
            ]

            return filtered_actions if filtered_actions else None

        except Exception as e:
            logger.error(f"Error processing event in SupplyManagerSkill: {e}")
            return None

    async def _handle_inventory_update(
        self, event: InventoryUpdate
    ) -> List[SkillAction]:
        """Handle inventory level updates."""
        actions = []

        # Update our tracking
        self.inventory_levels[event.asin] = event.new_quantity

        # Record inventory history
        if event.asin not in self.inventory_history:
            self.inventory_history[event.asin] = []
        self.inventory_history[event.asin].append((datetime.now(), event.new_quantity))

        # Keep only recent history
        if len(self.inventory_history[event.asin]) > 100:
            self.inventory_history[event.asin] = self.inventory_history[event.asin][
                -50:
            ]

        # Analyze if reorder is needed
        analysis = await self._analyze_inventory_needs(event.asin)
        if analysis and analysis.recommended_action == "reorder":
            reorder_action = await self._create_reorder_action(analysis)
            if reorder_action:
                actions.append(reorder_action)

        return actions

    async def _handle_sale_occurred(self, event: SaleOccurred) -> List[SkillAction]:
        """Handle sales events to update velocity calculations."""
        actions = []

        # Update sales velocity
        self._update_sales_velocity(event.asin, event.units_sold)

        # Check if sale caused low inventory situation
        current_stock = self.inventory_levels.get(event.asin, 0)
        if current_stock > 0:  # Only if we track this inventory
            # Update inventory level (assuming sale reduces stock)
            new_stock = max(0, current_stock - event.units_sold)
            self.inventory_levels[event.asin] = new_stock

            # Check if emergency reorder needed
            analysis = await self._analyze_inventory_needs(event.asin)
            if analysis and analysis.stockout_risk > 0.7:
                emergency_action = await self._create_emergency_reorder_action(analysis)
                if emergency_action:
                    actions.append(emergency_action)

        return actions

    async def _handle_tick_event(self, event: TickEvent) -> List[SkillAction]:
        """Handle periodic tick events for regular inventory monitoring."""
        actions = []  # type: ignore[var-annotated]

        # Only check every few ticks to avoid excessive processing
        if event.tick_number % 5 != 0:
            return actions

        # Periodic inventory analysis for all tracked items
        for asin in self.inventory_levels.keys():
            analysis = await self._analyze_inventory_needs(asin)
            if analysis and analysis.recommended_action in [
                "reorder",
                "urgent_reorder",
            ]:
                reorder_action = await self._create_reorder_action(analysis)
                if reorder_action:
                    actions.append(reorder_action)

        # Supplier performance review
        if event.tick_number % 20 == 0:  # Every 20 ticks
            await self._review_supplier_performance()

        return actions

    async def learn(self, outcome: SkillOutcome) -> None:
        """
        Adjust supplier reliability heuristics from fulfillment-related outcomes.
        For simplicity, penalize reliability when success=False or no units sold.
        """
        try:
            success = bool(outcome.success)
            units = int(outcome.impact_metrics.get("units_sold", 0))
            delta = 0.01 if success and units > 0 else -0.02
            for sid, prof in self.suppliers.items():
                prof.reliability_score = max(
                    0.0, min(1.0, prof.reliability_score + delta)
                )
        except Exception as e:
            logger.warning(f"SupplyManagerSkill.learn failed: {e}")

    async def generate_actions(
        self, context: SkillContext, constraints: Dict[str, Any]
    ) -> List[SkillAction]:
        """
        Generate supply management actions based on current context.

        Args:
            context: Current context information
            constraints: Active constraints and limits

        Returns:
            List of recommended supply management actions
        """
        actions = []

        try:
            # Get budget constraints
            budget_limit = constraints.get("budget_limit", self.max_order_budget)
            if isinstance(budget_limit, (int, float)):
                budget_limit = Money(int(budget_limit))

            # Analyze all inventory positions
            for asin, stock_level in self.inventory_levels.items():
                analysis = await self._analyze_inventory_needs(asin)

                if analysis and analysis.recommended_action != "none":
                    # Check if we can afford the order
                    estimated_cost = self._estimate_order_cost(
                        analysis.optimal_order_quantity
                    )
                    if estimated_cost <= budget_limit:
                        action = await self._create_reorder_action(analysis)
                        if action:
                            actions.append(action)
                            # Reduce available budget
                            budget_limit = Money(
                                budget_limit.cents - estimated_cost.cents
                            )

            # Sort by priority (stockout risk)
            actions.sort(key=lambda x: x.priority, reverse=True)

            return actions

        except Exception as e:
            logger.error(f"Error generating supply management actions: {e}")
            return []

    def get_priority_score(self, event: BaseEvent) -> float:
        """Calculate priority score for supply management events."""
        if isinstance(event, InventoryUpdate):
            asin = event.asin
            if asin in self.inventory_levels:
                # Higher priority for low inventory items
                stock_level = event.new_quantity
                velocity = self.sales_velocity.get(asin, 1.0)
                days_remaining = stock_level / max(velocity, 0.1)

                if days_remaining < 3:
                    return 0.9  # Very high priority
                elif days_remaining < 7:
                    return 0.7  # High priority
                elif days_remaining < 14:
                    return 0.5  # Medium priority
                else:
                    return 0.2  # Low priority
            return 0.3

        elif isinstance(event, SaleOccurred):
            # Sales events are medium priority for velocity tracking
            return 0.4

        elif isinstance(event, TickEvent):
            # Regular monitoring is lower priority
            return 0.2

        return 0.1

    async def _analyze_inventory_needs(self, asin: str) -> Optional[InventoryAnalysis]:
        """Analyze inventory needs for a specific ASIN."""
        if asin not in self.inventory_levels:
            return None

        try:
            current_stock = self.inventory_levels[asin]
            daily_velocity = self.sales_velocity.get(asin, 1.0)

            # Calculate days of inventory remaining
            days_remaining = current_stock / max(daily_velocity, 0.1)

            # Calculate reorder point (lead time + safety stock)
            reorder_point = int(
                (self.reorder_lead_time + self.safety_stock_days) * daily_velocity
            )

            # Calculate optimal order quantity (simple EOQ approximation)
            optimal_quantity = max(
                int(30 * daily_velocity), 100
            )  # 30 days worth  # Minimum order

            # Calculate stockout risk
            stockout_risk = max(
                0.0,
                min(
                    1.0,
                    1.0
                    - (
                        days_remaining
                        / (self.reorder_lead_time + self.safety_stock_days)
                    ),
                ),
            )

            # Estimate carrying cost (simplified)
            carrying_cost = Money(int(current_stock * 50))  # $0.50 per unit per period

            # Determine recommended action
            if current_stock <= reorder_point:
                if stockout_risk > 0.7:
                    recommended_action = "urgent_reorder"
                else:
                    recommended_action = "reorder"
            else:
                recommended_action = "none"

            return InventoryAnalysis(
                asin=asin,
                current_stock=current_stock,
                daily_sales_velocity=daily_velocity,
                days_of_inventory=days_remaining,
                reorder_point=reorder_point,
                optimal_order_quantity=optimal_quantity,
                stockout_risk=stockout_risk,
                carrying_cost=carrying_cost,
                recommended_action=recommended_action,
            )

        except Exception as e:
            logger.error(f"Error analyzing inventory needs for {asin}: {e}")
            return None

    async def _create_reorder_action(
        self, analysis: InventoryAnalysis
    ) -> Optional[SkillAction]:
        """Create a reorder action based on inventory analysis."""
        try:
            # Select optimal supplier
            selected_supplier = await self._select_optimal_supplier(analysis)
            if not selected_supplier:
                return None

            # Calculate priority based on stockout risk
            priority = min(0.9, analysis.stockout_risk + 0.2)

            # Estimate confidence based on historical success and data quality
            confidence = self._calculate_reorder_confidence(analysis, selected_supplier)

            # Prepare negotiation terms
            negotiation_terms = await self._prepare_negotiation_terms(
                selected_supplier, analysis
            )

            # Create action parameters
            parameters = {
                "supplier_id": selected_supplier.supplier_id,
                "asin": analysis.asin,
                "quantity": analysis.optimal_order_quantity,
                "max_price": negotiation_terms["max_unit_price"],
                "urgency": "high" if analysis.stockout_risk > 0.5 else "normal",
                "delivery_requirement": f"within {selected_supplier.lead_time_days} days",
                "negotiation_terms": negotiation_terms,
            }

            reasoning = (
                f"Reorder needed for {analysis.asin}: {analysis.days_of_inventory:.1f} days remaining, "
                f"{analysis.stockout_risk:.1%} stockout risk. Selected {selected_supplier.name} "
                f"(reliability: {selected_supplier.reliability_score:.1%})"
            )

            return SkillAction(
                action_type="place_order",
                parameters=parameters,
                confidence=confidence,
                reasoning=reasoning,
                priority=priority,
                resource_requirements={
                    "budget": self._estimate_order_cost(
                        analysis.optimal_order_quantity
                    ).cents,
                    "lead_time": selected_supplier.lead_time_days,
                },
                expected_outcome={
                    "inventory_increase": analysis.optimal_order_quantity,
                    "days_of_coverage": analysis.optimal_order_quantity
                    / analysis.daily_sales_velocity,
                    "stockout_risk_reduction": analysis.stockout_risk * 0.8,
                },
                skill_source=self.skill_name,
            )

        except Exception as e:
            logger.error(f"Error creating reorder action: {e}")
            return None

    async def _create_emergency_reorder_action(
        self, analysis: InventoryAnalysis
    ) -> Optional[SkillAction]:
        """Create an emergency reorder action for critical stock situations."""
        # Similar to regular reorder but with higher priority and expedited shipping
        action = await self._create_reorder_action(analysis)
        if action:
            action.priority = 0.95  # Very high priority
            action.parameters["urgency"] = "emergency"
            action.parameters["expedited_shipping"] = True
            action.reasoning = f"EMERGENCY: {action.reasoning}"
        return action

    async def _select_optimal_supplier(
        self, analysis: InventoryAnalysis
    ) -> Optional[SupplierProfile]:
        """Select the optimal supplier based on current needs and performance."""
        if not self.suppliers:
            return None

        best_supplier = None
        best_score = 0.0

        for supplier in self.suppliers.values():
            # Check if supplier can meet minimum order requirements
            if analysis.optimal_order_quantity < supplier.minimum_order_quantity:
                continue

            # Calculate composite score
            urgency_weight = 0.4 if analysis.stockout_risk > 0.5 else 0.2
            cost_weight = 0.3
            quality_weight = 0.2
            reliability_weight = 0.3

            # Adjust weights based on urgency
            if analysis.stockout_risk > 0.7:
                urgency_weight = 0.6  # Prioritize speed
                cost_weight = 0.1

            # Calculate lead time score (faster is better for urgent situations)
            lead_time_score = max(0.1, 1.0 - (supplier.lead_time_days / 30.0))

            composite_score = (
                (lead_time_score * urgency_weight)
                + (supplier.price_competitiveness * cost_weight)
                + (supplier.quality_score * quality_weight)
                + (supplier.reliability_score * reliability_weight)
            )

            if composite_score > best_score:
                best_score = composite_score
                best_supplier = supplier

        return best_supplier

    async def _prepare_negotiation_terms(
        self, supplier: SupplierProfile, analysis: InventoryAnalysis
    ) -> Dict[str, Any]:
        """Prepare negotiation terms for supplier interaction."""
        # Base price calculation (simplified)
        base_unit_price = 10.0  # $10 base price

        # Adjust based on urgency and quantity
        urgency_multiplier = 1.1 if analysis.stockout_risk > 0.5 else 1.0
        quantity_discount = max(
            0.9, 1.0 - (analysis.optimal_order_quantity / 1000.0) * 0.1
        )

        max_unit_price = base_unit_price * urgency_multiplier * quantity_discount

        return {
            "max_unit_price": max_unit_price,
            "payment_terms": (
                "Net 30" if supplier.reliability_score > 0.8 else "Payment on delivery"
            ),
            "quality_requirements": (
                "Standard" if supplier.quality_score > 0.8 else "Enhanced inspection"
            ),
            "delivery_terms": f"Within {supplier.lead_time_days} days",
            "quantity_flexibility": (
                "±10%" if analysis.stockout_risk < 0.3 else "Exact quantity required"
            ),
        }

    def _calculate_reorder_confidence(
        self, analysis: InventoryAnalysis, supplier: SupplierProfile
    ) -> float:
        """Calculate confidence score for reorder decision."""
        base_confidence = 0.7

        # Adjust based on data quality
        velocity_confidence = (
            0.9 if len(self.inventory_history.get(analysis.asin, [])) > 10 else 0.6
        )

        # Adjust based on supplier reliability
        supplier_confidence = supplier.reliability_score

        # Adjust based on urgency (higher urgency = lower confidence due to limited options)
        urgency_penalty = analysis.stockout_risk * 0.2

        confidence = (
            base_confidence * velocity_confidence * supplier_confidence
            - urgency_penalty
        )
        return max(0.3, min(0.95, confidence))

    def _update_sales_velocity(self, asin: str, units_sold: int):
        """Update rolling sales velocity calculation."""
        if asin not in self.sales_velocity:
            self.sales_velocity[asin] = float(units_sold)
        else:
            # Exponential moving average
            self.sales_velocity[asin] = (self.sales_velocity[asin] * 0.8) + (
                units_sold * 0.2
            )

    def _estimate_order_cost(self, quantity: int, unit_price: float = 10.0) -> Money:
        """Estimate total cost of an order."""
        return Money(int(quantity * unit_price * 100))  # Convert to cents

    async def _review_supplier_performance(self):
        """Periodic review and update of supplier performance scores."""
        # This would analyze recent orders and update supplier ratings
        # Simplified implementation for now
        for supplier_id, supplier in self.suppliers.items():
            # Simulate performance updates based on recent history
            if supplier_id in self.supplier_performance:
                performance = self.supplier_performance[supplier_id]
                # Update scores based on performance (simplified)
                supplier.reliability_score = min(
                    0.95,
                    supplier.reliability_score * 0.95
                    + performance.get("on_time_delivery", 0.8) * 0.05,
                )
                supplier.quality_score = min(
                    0.95,
                    supplier.quality_score * 0.95
                    + performance.get("quality_rating", 0.8) * 0.05,
                )

        logger.debug(
            f"Completed supplier performance review for {len(self.suppliers)} suppliers"
        )

    async def evaluate_reorder_needs(self) -> Dict[str, InventoryAnalysis]:
        """Evaluate reorder needs for all tracked inventory."""
        analyses = {}
        for asin in self.inventory_levels.keys():
            analysis = await self._analyze_inventory_needs(asin)
            if analysis:
                analyses[asin] = analysis
        return analyses

    async def select_optimal_supplier(
        self, asin: str, quantity: int
    ) -> Optional[SupplierProfile]:
        """Public method to select optimal supplier for external use."""
        # Create mock analysis for supplier selection
        mock_analysis = InventoryAnalysis(
            asin=asin,
            current_stock=0,
            daily_sales_velocity=1.0,
            days_of_inventory=0,
            reorder_point=100,
            optimal_order_quantity=quantity,
            stockout_risk=0.5,
            carrying_cost=Money(0),
            recommended_action="reorder",
        )
        return await self._select_optimal_supplier(mock_analysis)

    async def negotiate_terms(
        self, supplier_id: str, quantity: int, urgency: str = "normal"
    ) -> Dict[str, Any]:
        """Negotiate terms with a specific supplier."""
        if supplier_id not in self.suppliers:
            return {}

        supplier = self.suppliers[supplier_id]
        mock_analysis = InventoryAnalysis(
            asin="mock",
            current_stock=0,
            daily_sales_velocity=1.0,
            days_of_inventory=0,
            reorder_point=100,
            optimal_order_quantity=quantity,
            stockout_risk=0.7 if urgency == "high" else 0.3,
            carrying_cost=Money(0),
            recommended_action="reorder",
        )

        return await self._prepare_negotiation_terms(supplier, mock_analysis)


# Alias for backward compatibility
SupplyManager = SupplyManagerSkill
