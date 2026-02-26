"""
Refined Scenarios - High-quality benchmark scenarios for FBA simulation.

This module provides refined, production-ready benchmark scenarios for
testing and evaluating agent performance in FBA (Fulfillment by Amazon)
simulation environments.
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ScenarioDifficulty(str, Enum):
    """Difficulty levels for scenarios."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class ScenarioType(str, Enum):
    """Types of scenarios."""

    PRICING = "pricing"
    INVENTORY = "inventory"
    MARKETING = "marketing"
    SUPPLY_CHAIN = "supply_chain"
    COMPETITIVE = "competitive"
    MULTI_OBJECTIVE = "multi_objective"


@dataclass
class ScenarioMetrics:
    """
    Metrics for evaluating scenario performance.

    Attributes:
        revenue: Total revenue generated
        profit: Total profit earned
        costs: Total costs incurred
        market_share: Market share percentage
        customer_satisfaction: Customer satisfaction score
        inventory_turnover: Inventory turnover rate
        order_fulfillment_rate: Order fulfillment rate
        competitive_position: Competitive position score
    """

    revenue: float = 0.0
    profit: float = 0.0
    costs: float = 0.0
    market_share: float = 0.0
    customer_satisfaction: float = 0.0
    inventory_turnover: float = 0.0
    order_fulfillment_rate: float = 0.0
    competitive_position: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary."""
        return {
            "revenue": self.revenue,
            "profit": self.profit,
            "costs": self.costs,
            "market_share": self.market_share,
            "customer_satisfaction": self.customer_satisfaction,
            "inventory_turnover": self.inventory_turnover,
            "order_fulfillment_rate": self.order_fulfillment_rate,
            "competitive_position": self.competitive_position,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "ScenarioMetrics":
        """Create metrics from dictionary."""
        return cls(**data)


@dataclass
class ScenarioContext:
    """
    Context information for a scenario.

    Attributes:
        tick: Current simulation tick
        time_elapsed: Time elapsed in simulation
        product_state: Current state of products
        market_state: Current state of the market
        competitor_state: Current state of competitors
        agent_state: Current state of the agent
        history: Historical data
    """

    tick: int = 0
    time_elapsed: float = 0.0
    product_state: Dict[str, Any] = field(default_factory=dict)
    market_state: Dict[str, Any] = field(default_factory=dict)
    competitor_state: Dict[str, Any] = field(default_factory=dict)
    agent_state: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "tick": self.tick,
            "time_elapsed": self.time_elapsed,
            "product_state": self.product_state,
            "market_state": self.market_state,
            "competitor_state": self.competitor_state,
            "agent_state": self.agent_state,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioContext":
        """Create a permissive context from arbitrary initial_state dict.

        Unknown keys are stored under product_state to avoid constructor errors in tests.
        """
        # Start with defaults
        ctx = cls()
        try:
            # Shallow-copy to avoid caller mutation
            initial = dict(data or {})
        except Exception:
            initial = {}
        # Populate reasonable defaults if provided explicitly
        for k in ("tick", "time_elapsed"):
            if k in initial:
                try:
                    setattr(ctx, k, initial.pop(k))
                except Exception:
                    pass
        # Stash remaining keys as part of product_state for scenarios to consume
        try:
            ctx.product_state.update(initial)
        except Exception:
            ctx.product_state = dict(initial)
        return ctx


@dataclass
class ScenarioConfig:
    """
    Configuration for a scenario.

    Attributes:
        name: Name of the scenario
        description: Description of the scenario
        difficulty: Difficulty level
        scenario_type: Type of scenario
        max_ticks: Maximum number of ticks
        time_limit: Time limit in seconds
        initial_state: Initial state for the scenario
        success_criteria: Criteria for success
        failure_criteria: Criteria for failure
        metadata: Additional metadata
    """

    name: str
    description: str
    difficulty: ScenarioDifficulty
    scenario_type: ScenarioType
    max_ticks: int = 1000
    time_limit: float = 300.0  # 5 minutes
    initial_state: Dict[str, Any] = field(default_factory=dict)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    failure_criteria: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "difficulty": self.difficulty.value,
            "scenario_type": self.scenario_type.value,
            "max_ticks": self.max_ticks,
            "time_limit": self.time_limit,
            "initial_state": self.initial_state,
            "success_criteria": self.success_criteria,
            "failure_criteria": self.failure_criteria,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioConfig":
        """Create config from dictionary."""
        data = data.copy()
        data["difficulty"] = ScenarioDifficulty(data["difficulty"])
        data["scenario_type"] = ScenarioType(data["scenario_type"])
        return cls(**data)


class BaseScenario(ABC):
    """
    Base class for all scenarios.

    This abstract class defines the interface that all scenarios must implement.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the scenario.

        Args:
            config: Configuration for the scenario
        """
        self.config = config
        self.context = ScenarioContext.from_dict(config.initial_state)
        self.metrics = ScenarioMetrics()
        self.is_complete = False
        self.is_success = False
        self.start_time = None
        self.end_time = None

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the scenario.

        This method is called once at the beginning of the scenario.
        It should set up the initial state and prepare for execution.
        """

    @abstractmethod
    def step(self, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute one step of the scenario.

        Args:
            action: Action taken by the agent

        Returns:
            Result of the step, including updated context and metrics
        """

    @abstractmethod
    def evaluate(self) -> Tuple[bool, str]:
        """
        Evaluate the scenario completion status.

        Returns:
            Tuple of (is_complete, status_message)
        """

    @abstractmethod
    def get_metrics(self) -> ScenarioMetrics:
        """
        Get the current metrics for the scenario.

        Returns:
            Current metrics
        """

    @abstractmethod
    def get_context(self) -> ScenarioContext:
        """
        Get the current context for the scenario.

        Returns:
            Current context
        """

    def reset(self) -> None:
        """
        Reset the scenario to its initial state.
        """
        self.context = ScenarioContext.from_dict(self.config.initial_state)
        self.metrics = ScenarioMetrics()
        self.is_complete = False
        self.is_success = False
        self.start_time = None
        self.end_time = None
        self.initialize()

    def start(self) -> None:
        """
        Start the scenario.
        """
        self.start_time = time.time()  # type: ignore[assignment]
        self.initialize()

    def end(self) -> None:
        """
        End the scenario.
        """
        self.end_time = time.time()  # type: ignore[assignment]
        self.is_complete = True

    def get_elapsed_time(self) -> float:
        """
        Get the elapsed time since the scenario started.

        Returns:
            Elapsed time in seconds
        """
        if self.start_time is None:
            return 0.0
        end_time = self.end_time or time.time()
        return end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the scenario to a dictionary representation.

        Returns:
            Dictionary representation of the scenario
        """
        return {
            "config": self.config.to_dict(),
            "context": self.context.to_dict(),
            "metrics": self.metrics.to_dict(),
            "is_complete": self.is_complete,
            "is_success": self.is_success,
            "elapsed_time": self.get_elapsed_time(),
        }


class PricingScenario(BaseScenario):
    """
    Scenario focused on pricing decisions.

    This scenario tests an agent's ability to make optimal pricing decisions
    in a dynamic market environment.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the pricing scenario.

        Args:
            config: Configuration for the scenario
        """
        super().__init__(config)

        # Pricing-specific parameters
        self.base_price = self.config.initial_state.get("base_price", 10.0)
        self.cost_per_unit = self.config.initial_state.get("cost_per_unit", 5.0)
        self.max_price = self.config.initial_state.get("max_price", 20.0)
        self.min_price = self.config.initial_state.get("min_price", 5.0)
        self.price_elasticity = self.config.initial_state.get("price_elasticity", -1.5)
        self.competitor_price = self.config.initial_state.get("competitor_price", 10.0)
        self.competitor_price_volatility = self.config.initial_state.get(
            "competitor_price_volatility", 0.1
        )

        # Current state
        self.current_price = self.base_price
        self.demand = 100
        self.revenue = 0.0
        self.profit = 0.0

    def initialize(self) -> None:
        """Initialize the pricing scenario."""
        logger.info(f"Initializing pricing scenario: {self.config.name}")

        # Set initial context
        self.context.product_state = {
            "price": self.current_price,
            "cost_per_unit": self.cost_per_unit,
            "inventory": 1000,
        }

        self.context.market_state = {
            "demand": self.demand,
            "price_elasticity": self.price_elasticity,
        }

        self.context.competitor_state = {
            "price": self.competitor_price,
            "market_share": 0.5,
        }

        self.context.agent_state = {
            "total_revenue": 0.0,
            "total_profit": 0.0,
            "total_units_sold": 0,
        }

    def step(self, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute one step of the pricing scenario.

        Args:
            action: Action taken by the agent (should include 'price')

        Returns:
            Result of the step
        """
        if self.is_complete:
            return {"error": "Scenario is already complete"}

        # Update tick
        self.context.tick += 1
        self.context.time_elapsed = self.get_elapsed_time()

        # Process agent action
        if action and "price" in action:
            new_price = action["price"]
            # Validate price
            new_price = max(self.min_price, min(self.max_price, new_price))
            self.current_price = new_price

        # Update competitor price (with some randomness)
        price_change = random.gauss(0, self.competitor_price_volatility)
        self.competitor_price = max(
            self.min_price,
            min(self.max_price, self.competitor_price * (1 + price_change)),
        )

        # Calculate demand based on prices
        price_ratio = self.current_price / self.competitor_price
        demand_factor = price_ratio**self.price_elasticity
        self.demand = int(100 * demand_factor)

        # Calculate revenue and profit
        units_sold = min(self.demand, self.context.product_state["inventory"])
        self.revenue = units_sold * self.current_price
        self.profit = units_sold * (self.current_price - self.cost_per_unit)

        # Update inventory
        self.context.product_state["inventory"] -= units_sold

        # Update agent state
        self.context.agent_state["total_revenue"] += self.revenue
        self.context.agent_state["total_profit"] += self.profit
        self.context.agent_state["total_units_sold"] += units_sold

        # Update metrics
        self.metrics.revenue = self.context.agent_state["total_revenue"]
        self.metrics.profit = self.context.agent_state["total_profit"]
        self.metrics.costs = (
            self.context.agent_state["total_units_sold"] * self.cost_per_unit
        )

        # Update context
        self.context.product_state["price"] = self.current_price
        self.context.market_state["demand"] = self.demand
        self.context.competitor_state["price"] = self.competitor_price

        # Add to history
        self.context.history.append(
            {
                "tick": self.context.tick,
                "price": self.current_price,
                "competitor_price": self.competitor_price,
                "demand": self.demand,
                "units_sold": units_sold,
                "revenue": self.revenue,
                "profit": self.profit,
            }
        )

        # Check completion
        is_complete, status_message = self.evaluate()
        if is_complete:
            self.is_complete = True
            self.end()

        return {
            "tick": self.context.tick,
            "price": self.current_price,
            "competitor_price": self.competitor_price,
            "demand": self.demand,
            "units_sold": units_sold,
            "revenue": self.revenue,
            "profit": self.profit,
            "inventory": self.context.product_state["inventory"],
            "is_complete": self.is_complete,
            "status_message": status_message,
        }

    def evaluate(self) -> Tuple[bool, str]:
        """
        Evaluate the scenario completion status.

        Returns:
            Tuple of (is_complete, status_message)
        """
        # Check time limit
        if self.get_elapsed_time() >= self.config.time_limit:
            self.is_success = self.metrics.profit > 0
            return True, f"Time limit reached. Profit: ${self.metrics.profit:.2f}"

        # Check tick limit
        if self.context.tick >= self.config.max_ticks:
            self.is_success = self.metrics.profit > 0
            return True, f"Tick limit reached. Profit: ${self.metrics.profit:.2f}"

        # Check inventory
        if self.context.product_state["inventory"] <= 0:
            self.is_success = self.metrics.profit > 0
            return True, f"Inventory depleted. Profit: ${self.metrics.profit:.2f}"

        # Check success criteria
        if "min_profit" in self.config.success_criteria:
            if self.metrics.profit >= self.config.success_criteria["min_profit"]:
                self.is_success = True
                return True, f"Success criteria met. Profit: ${self.metrics.profit:.2f}"

        # Check failure criteria
        if "max_loss" in self.config.failure_criteria:
            if self.metrics.profit <= self.config.failure_criteria["max_loss"]:
                self.is_success = False
                return True, f"Failure criteria met. Profit: ${self.metrics.profit:.2f}"

        return False, "Scenario in progress"

    def get_metrics(self) -> ScenarioMetrics:
        """
        Get the current metrics for the scenario.

        Returns:
            Current metrics
        """
        return self.metrics

    def get_context(self) -> ScenarioContext:
        """
        Get the current context for the scenario.

        Returns:
            Current context
        """
        return self.context


class InventoryScenario(BaseScenario):
    """
    Scenario focused on inventory management.

    This scenario tests an agent's ability to manage inventory levels
    optimally, balancing stockouts against holding costs.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the inventory scenario.

        Args:
            config: Configuration for the scenario
        """
        super().__init__(config)

        # Inventory-specific parameters
        self.initial_inventory = self.config.initial_state.get("initial_inventory", 100)
        self.holding_cost_per_unit = self.config.initial_state.get(
            "holding_cost_per_unit", 0.1
        )
        self.stockout_cost_per_unit = self.config.initial_state.get(
            "stockout_cost_per_unit", 2.0
        )
        self.order_cost_per_order = self.config.initial_state.get(
            "order_cost_per_order", 10.0
        )
        self.lead_time = self.config.initial_state.get("lead_time", 3)
        self.max_order_quantity = self.config.initial_state.get(
            "max_order_quantity", 200
        )
        self.demand_mean = self.config.initial_state.get("demand_mean", 20)
        self.demand_std = self.config.initial_state.get("demand_std", 5)

        # Current state
        self.current_inventory = self.initial_inventory
        self.pending_orders: list = []  # List of (delivery_tick, quantity)  # type: ignore[var-annotated]
        self.total_holding_cost = 0.0
        self.total_stockout_cost = 0.0
        self.total_order_cost = 0.0
        self.total_cost = 0.0

    def initialize(self) -> None:
        """Initialize the inventory scenario."""
        logger.info(f"Initializing inventory scenario: {self.config.name}")

        # Set initial context
        self.context.product_state = {
            "inventory": self.current_inventory,
            "pending_orders": self.pending_orders,
        }

        self.context.market_state = {
            "demand_mean": self.demand_mean,
            "demand_std": self.demand_std,
        }

        self.context.agent_state = {
            "total_holding_cost": 0.0,
            "total_stockout_cost": 0.0,
            "total_order_cost": 0.0,
            "total_cost": 0.0,
            "total_orders_placed": 0,
            "total_units_ordered": 0,
        }

    def step(self, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute one step of the inventory scenario.

        Args:
            action: Action taken by the agent (should include 'order_quantity')

        Returns:
            Result of the step
        """
        if self.is_complete:
            return {"error": "Scenario is already complete"}

        # Update tick
        self.context.tick += 1
        self.context.time_elapsed = self.get_elapsed_time()

        # Process agent action (place order)
        if action and "order_quantity" in action:
            order_quantity = action["order_quantity"]
            # Validate order quantity
            order_quantity = max(0, min(self.max_order_quantity, order_quantity))

            if order_quantity > 0:
                # Place order
                delivery_tick = self.context.tick + self.lead_time
                self.pending_orders.append((delivery_tick, order_quantity))

                # Update costs and metrics
                self.total_order_cost += self.order_cost_per_order
                self.context.agent_state["total_order_cost"] = self.total_order_cost
                self.context.agent_state["total_orders_placed"] += 1
                self.context.agent_state["total_units_ordered"] += order_quantity

        # Process pending orders (deliveries)
        delivered_quantity = 0
        remaining_orders = []

        for delivery_tick, quantity in self.pending_orders:
            if delivery_tick <= self.context.tick:
                # Order has arrived
                self.current_inventory += quantity
                delivered_quantity += quantity
            else:
                # Order still pending
                remaining_orders.append((delivery_tick, quantity))

        self.pending_orders = remaining_orders

        # Generate demand
        demand = max(0, int(random.gauss(self.demand_mean, self.demand_std)))

        # Fulfill demand
        units_sold = min(demand, self.current_inventory)
        stockout_quantity = demand - units_sold

        # Update inventory
        self.current_inventory -= units_sold

        # Calculate costs
        holding_cost = self.current_inventory * self.holding_cost_per_unit
        stockout_cost = stockout_quantity * self.stockout_cost_per_unit

        self.total_holding_cost += holding_cost
        self.total_stockout_cost += stockout_cost
        self.total_cost = (
            self.total_holding_cost + self.total_stockout_cost + self.total_order_cost
        )

        # Update agent state
        self.context.agent_state["total_holding_cost"] = self.total_holding_cost
        self.context.agent_state["total_stockout_cost"] = self.total_stockout_cost
        self.context.agent_state["total_cost"] = self.total_cost

        # Update metrics
        self.metrics.costs = self.total_cost
        self.metrics.order_fulfillment_rate = units_sold / max(1, demand)
        self.metrics.inventory_turnover = self.context.agent_state[
            "total_units_ordered"
        ] / max(1, self.current_inventory)

        # Update context
        self.context.product_state["inventory"] = self.current_inventory
        self.context.product_state["pending_orders"] = self.pending_orders
        self.context.market_state["demand"] = demand

        # Add to history
        self.context.history.append(
            {
                "tick": self.context.tick,
                "inventory": self.current_inventory,
                "demand": demand,
                "units_sold": units_sold,
                "stockout_quantity": stockout_quantity,
                "delivered_quantity": delivered_quantity,
                "holding_cost": holding_cost,
                "stockout_cost": stockout_cost,
                "total_cost": self.total_cost,
            }
        )

        # Check completion
        is_complete, status_message = self.evaluate()
        if is_complete:
            self.is_complete = True
            self.end()

        return {
            "tick": self.context.tick,
            "inventory": self.current_inventory,
            "demand": demand,
            "units_sold": units_sold,
            "stockout_quantity": stockout_quantity,
            "delivered_quantity": delivered_quantity,
            "holding_cost": holding_cost,
            "stockout_cost": stockout_cost,
            "total_cost": self.total_cost,
            "pending_orders": len(self.pending_orders),
            "is_complete": self.is_complete,
            "status_message": status_message,
        }

    def evaluate(self) -> Tuple[bool, str]:
        """
        Evaluate the scenario completion status.

        Returns:
            Tuple of (is_complete, status_message)
        """
        # Check time limit
        if self.get_elapsed_time() >= self.config.time_limit:
            self.is_success = self.total_cost < 1000  # Example success criteria
            return True, f"Time limit reached. Total cost: ${self.total_cost:.2f}"

        # Check tick limit
        if self.context.tick >= self.config.max_ticks:
            self.is_success = self.total_cost < 1000  # Example success criteria
            return True, f"Tick limit reached. Total cost: ${self.total_cost:.2f}"

        # Check success criteria
        if "max_cost" in self.config.success_criteria:
            if self.total_cost <= self.config.success_criteria["max_cost"]:
                self.is_success = True
                return True, f"Success criteria met. Total cost: ${self.total_cost:.2f}"

        # Check failure criteria
        if "min_fulfillment_rate" in self.config.failure_criteria:
            if (
                self.metrics.order_fulfillment_rate
                < self.config.failure_criteria["min_fulfillment_rate"]
            ):
                self.is_success = False
                return (
                    True,
                    f"Failure criteria met. Fulfillment rate: {self.metrics.order_fulfillment_rate:.2%}",
                )

        return False, "Scenario in progress"

    def get_metrics(self) -> ScenarioMetrics:
        """
        Get the current metrics for the scenario.

        Returns:
            Current metrics
        """
        return self.metrics

    def get_context(self) -> ScenarioContext:
        """
        Get the current context for the scenario.

        Returns:
            Current context
        """
        return self.context


class CompetitiveScenario(BaseScenario):
    """
    Scenario focused on competitive dynamics.

    This scenario tests an agent's ability to compete effectively
    against other agents in a dynamic market environment.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the competitive scenario.

        Args:
            config: Configuration for the scenario
        """
        super().__init__(config)

        # Competitive-specific parameters
        self.num_competitors = self.config.initial_state.get("num_competitors", 3)
        self.market_size = self.config.initial_state.get("market_size", 1000)
        self.competitor_strategies = self.config.initial_state.get(
            "competitor_strategies", ["aggressive", "moderate", "conservative"]
        )
        self.price_sensitivity = self.config.initial_state.get("price_sensitivity", 1.0)
        self.quality_sensitivity = self.config.initial_state.get(
            "quality_sensitivity", 0.8
        )
        self.marketing_sensitivity = self.config.initial_state.get(
            "marketing_sensitivity", 0.5
        )

        # Current state
        self.agent_price = self.config.initial_state.get("agent_price", 10.0)
        self.agent_quality = self.config.initial_state.get("agent_quality", 0.7)
        self.agent_marketing = self.config.initial_state.get("agent_marketing", 0.5)
        self.agent_market_share = 1.0 / (self.num_competitors + 1)

        # Competitor state
        self.competitors = []
        for i in range(self.num_competitors):
            strategy = self.competitor_strategies[i % len(self.competitor_strategies)]
            competitor = {
                "id": i,
                "strategy": strategy,
                "price": random.uniform(8.0, 12.0),
                "quality": random.uniform(0.5, 0.9),
                "marketing": random.uniform(0.3, 0.7),
                "market_share": 1.0 / (self.num_competitors + 1),
            }
            self.competitors.append(competitor)

        # Metrics
        self.total_revenue = 0.0
        self.total_profit = 0.0

    def initialize(self) -> None:
        """Initialize the competitive scenario."""
        logger.info(f"Initializing competitive scenario: {self.config.name}")

        # Set initial context
        self.context.product_state = {
            "price": self.agent_price,
            "quality": self.agent_quality,
            "marketing": self.agent_marketing,
        }

        self.context.market_state = {
            "market_size": self.market_size,
            "price_sensitivity": self.price_sensitivity,
            "quality_sensitivity": self.quality_sensitivity,
            "marketing_sensitivity": self.marketing_sensitivity,
        }

        self.context.competitor_state = {"competitors": self.competitors}

        self.context.agent_state = {
            "market_share": self.agent_market_share,
            "total_revenue": 0.0,
            "total_profit": 0.0,
        }

    def step(self, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute one step of the competitive scenario.

        Args:
            action: Action taken by the agent (should include 'price', 'quality', 'marketing')

        Returns:
            Result of the step
        """
        if self.is_complete:
            return {"error": "Scenario is already complete"}

        # Update tick
        self.context.tick += 1
        self.context.time_elapsed = self.get_elapsed_time()

        # Process agent action
        if action:
            if "price" in action:
                self.agent_price = max(1.0, action["price"])
            if "quality" in action:
                self.agent_quality = max(0.1, min(1.0, action["quality"]))
            if "marketing" in action:
                self.agent_marketing = max(0.0, min(1.0, action["marketing"]))

        # Update competitors
        for competitor in self.competitors:
            # Simple competitor behavior based on strategy
            if competitor["strategy"] == "aggressive":
                # Aggressive competitors focus on price
                competitor["price"] *= random.uniform(0.95, 0.98)
                competitor["quality"] *= random.uniform(0.99, 1.01)
                competitor["marketing"] *= random.uniform(0.99, 1.01)
            elif competitor["strategy"] == "moderate":
                # Moderate competitors balance all factors
                competitor["price"] *= random.uniform(0.98, 1.02)
                competitor["quality"] *= random.uniform(0.99, 1.01)
                competitor["marketing"] *= random.uniform(0.99, 1.01)
            else:  # conservative
                # Conservative competitors focus on quality
                competitor["price"] *= random.uniform(1.0, 1.03)
                competitor["quality"] *= random.uniform(1.0, 1.02)
                competitor["marketing"] *= random.uniform(0.98, 1.02)

            # Ensure values are in reasonable ranges
            competitor["price"] = max(1.0, min(20.0, competitor["price"]))
            competitor["quality"] = max(0.1, min(1.0, competitor["quality"]))
            competitor["marketing"] = max(0.0, min(1.0, competitor["marketing"]))

        # Calculate market shares
        all_players = [
            {
                "price": self.agent_price,
                "quality": self.agent_quality,
                "marketing": self.agent_marketing,
                "is_agent": True,
            }
        ] + [
            {
                "price": comp["price"],
                "quality": comp["quality"],
                "marketing": comp["marketing"],
                "is_agent": False,
            }
            for comp in self.competitors
        ]

        # Calculate attractiveness scores
        for player in all_players:
            # Normalize factors
            price_factor = 1.0 / (player["price"] ** self.price_sensitivity)
            quality_factor = player["quality"] ** self.quality_sensitivity
            marketing_factor = player["marketing"] ** self.marketing_sensitivity

            # Calculate overall attractiveness
            player["attractiveness"] = price_factor * quality_factor * marketing_factor

        # Calculate market shares based on attractiveness
        total_attractiveness = sum(p["attractiveness"] for p in all_players)

        if total_attractiveness > 0:
            for player in all_players:
                player["market_share"] = player["attractiveness"] / total_attractiveness
        else:
            # Equal shares if all attractiveness is zero
            equal_share = 1.0 / len(all_players)
            for player in all_players:
                player["market_share"] = equal_share

        # Update agent market share
        self.agent_market_share = all_players[0]["market_share"]

        # Update competitor market shares
        for i, competitor in enumerate(self.competitors):
            competitor["market_share"] = all_players[i + 1]["market_share"]

        # Calculate sales and revenue
        agent_sales = int(self.market_size * self.agent_market_share)
        agent_revenue = agent_sales * self.agent_price
        agent_profit = agent_revenue - (agent_sales * 5.0)  # Assume $5 cost per unit

        self.total_revenue += agent_revenue
        self.total_profit += agent_profit

        # Update metrics
        self.metrics.revenue = self.total_revenue
        self.metrics.profit = self.total_profit
        self.metrics.market_share = self.agent_market_share
        self.metrics.competitive_position = self.agent_market_share / max(
            0.01, 1.0 / (self.num_competitors + 1)
        )

        # Update context
        self.context.product_state["price"] = self.agent_price
        self.context.product_state["quality"] = self.agent_quality
        self.context.product_state["marketing"] = self.agent_marketing

        self.context.competitor_state["competitors"] = self.competitors

        self.context.agent_state["market_share"] = self.agent_market_share
        self.context.agent_state["total_revenue"] = self.total_revenue
        self.context.agent_state["total_profit"] = self.total_profit

        # Add to history
        self.context.history.append(
            {
                "tick": self.context.tick,
                "agent_price": self.agent_price,
                "agent_quality": self.agent_quality,
                "agent_marketing": self.agent_marketing,
                "agent_market_share": self.agent_market_share,
                "agent_sales": agent_sales,
                "agent_revenue": agent_revenue,
                "agent_profit": agent_profit,
                "competitors": [comp.copy() for comp in self.competitors],
            }
        )

        # Check completion
        is_complete, status_message = self.evaluate()
        if is_complete:
            self.is_complete = True
            self.end()

        return {
            "tick": self.context.tick,
            "agent_price": self.agent_price,
            "agent_quality": self.agent_quality,
            "agent_marketing": self.agent_marketing,
            "agent_market_share": self.agent_market_share,
            "agent_sales": agent_sales,
            "agent_revenue": agent_revenue,
            "agent_profit": agent_profit,
            "competitors": [comp.copy() for comp in self.competitors],
            "is_complete": self.is_complete,
            "status_message": status_message,
        }

    def evaluate(self) -> Tuple[bool, str]:
        """
        Evaluate the scenario completion status.

        Returns:
            Tuple of (is_complete, status_message)
        """
        # Check time limit
        if self.get_elapsed_time() >= self.config.time_limit:
            self.is_success = self.agent_market_share > 0.3  # Example success criteria
            return (
                True,
                f"Time limit reached. Market share: {self.agent_market_share:.2%}",
            )

        # Check tick limit
        if self.context.tick >= self.config.max_ticks:
            self.is_success = self.agent_market_share > 0.3  # Example success criteria
            return (
                True,
                f"Tick limit reached. Market share: {self.agent_market_share:.2%}",
            )

        # Check success criteria
        if "min_market_share" in self.config.success_criteria:
            if (
                self.agent_market_share
                >= self.config.success_criteria["min_market_share"]
            ):
                self.is_success = True
                return (
                    True,
                    f"Success criteria met. Market share: {self.agent_market_share:.2%}",
                )

        # Check failure criteria
        if "max_market_share" in self.config.failure_criteria:
            if (
                self.agent_market_share
                <= self.config.failure_criteria["max_market_share"]
            ):
                self.is_success = False
                return (
                    True,
                    f"Failure criteria met. Market share: {self.agent_market_share:.2%}",
                )

        return False, "Scenario in progress"

    def get_metrics(self) -> ScenarioMetrics:
        """
        Get the current metrics for the scenario.

        Returns:
            Current metrics
        """
        return self.metrics

    def get_context(self) -> ScenarioContext:
        """
        Get the current context for the scenario.

        Returns:
            Current context
        """
        return self.context


class ScenarioFactory:
    """
    Factory for creating scenario instances.
    """

    @staticmethod
    def create_scenario(config: ScenarioConfig) -> BaseScenario:
        """
        Create a scenario instance based on the configuration.

        Args:
            config: Configuration for the scenario

        Returns:
            Scenario instance

        Raises:
            ValueError: If the scenario type is not supported
        """
        if config.scenario_type == ScenarioType.PRICING:
            return PricingScenario(config)
        elif config.scenario_type == ScenarioType.INVENTORY:
            return InventoryScenario(config)
        elif config.scenario_type == ScenarioType.COMPETITIVE:
            return CompetitiveScenario(config)
        else:
            raise ValueError(f"Unsupported scenario type: {config.scenario_type}")

    @staticmethod
    def create_pricing_scenario(
        name: str, difficulty: ScenarioDifficulty = ScenarioDifficulty.MEDIUM, **kwargs
    ) -> PricingScenario:
        """
        Create a pricing scenario with default configuration.

        Args:
            name: Name of the scenario
            difficulty: Difficulty level
            **kwargs: Additional configuration parameters

        Returns:
            PricingScenario instance
        """
        config = ScenarioConfig(
            name=name,
            description="Pricing optimization scenario",
            difficulty=difficulty,
            scenario_type=ScenarioType.PRICING,
            **kwargs,
        )
        return PricingScenario(config)

    @staticmethod
    def create_inventory_scenario(
        name: str, difficulty: ScenarioDifficulty = ScenarioDifficulty.MEDIUM, **kwargs
    ) -> InventoryScenario:
        """
        Create an inventory scenario with default configuration.

        Args:
            name: Name of the scenario
            difficulty: Difficulty level
            **kwargs: Additional configuration parameters

        Returns:
            InventoryScenario instance
        """
        config = ScenarioConfig(
            name=name,
            description="Inventory management scenario",
            difficulty=difficulty,
            scenario_type=ScenarioType.INVENTORY,
            **kwargs,
        )
        return InventoryScenario(config)

    @staticmethod
    def create_competitive_scenario(
        name: str, difficulty: ScenarioDifficulty = ScenarioDifficulty.MEDIUM, **kwargs
    ) -> CompetitiveScenario:
        """
        Create a competitive scenario with default configuration.

        Args:
            name: Name of the scenario
            difficulty: Difficulty level
            **kwargs: Additional configuration parameters

        Returns:
            CompetitiveScenario instance
        """
        config = ScenarioConfig(
            name=name,
            description="Competitive dynamics scenario",
            difficulty=difficulty,
            scenario_type=ScenarioType.COMPETITIVE,
            **kwargs,
        )
        return CompetitiveScenario(config)
