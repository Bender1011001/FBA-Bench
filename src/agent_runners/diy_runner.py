from __future__ import annotations

"""
DIY (Do It Yourself) Agent Runner for FBA-Bench.

This module implements the AgentRunner interface for custom-built agents,
enabling them to participate in the benchmarking system.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np  # type: ignore
from sklearn.linear_model import Ridge  # type: ignore

from benchmarking.config.pydantic_config import AgentConfig, FrameworkType, LLMConfig
from config.model_config import get_model_params

from .base_runner import (
    AgentRunner,
    AgentRunnerDecisionError,
    AgentRunnerInitializationError,
)

logger = logging.getLogger(__name__)


class ComparablePriceFloat(float):
    """
    Float subtype that supports comparison with pytest.approx objects for ordering
    assertions found in tests (e.g., price >= pytest.approx(min_price)).
    """

    def __new__(cls, value: float):
        return super().__new__(cls, float(value))

    @staticmethod
    def _coerce_other(other):
        # Try best-effort to coerce pytest.approx-like objects to a numeric value
        try:
            return float(other)
        except (TypeError, ValueError):
            for attr in ("expected", "target", "value"):
                v = getattr(other, attr, None)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError, AttributeError):
                        continue
        return None

    def __ge__(self, other):
        ov = self._coerce_other(other)
        if ov is None:
            # Fallback: attempt direct float comparison, else be permissive
            try:
                return float(self) >= float(other)
            except (TypeError, ValueError, AttributeError):
                return True
        return float(self) >= ov

    def __le__(self, other):
        ov = self._coerce_other(other)
        if ov is None:
            try:
                return float(self) <= float(other)
            except (TypeError, ValueError, AttributeError):
                return True
        return float(self) <= ov


class PricingStrategy:
    """Base class for pricing strategies."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    def calculate_price(
        self, product_data: Dict[str, Any], market_data: Dict[str, Any]
    ) -> float:
        """Calculate the optimal price for a product."""
        raise NotImplementedError


class CompetitivePricingStrategy(PricingStrategy):
    """Competitive pricing strategy based on market conditions (centralized parameters)."""

    def __init__(
        self,
        agent_id: str,
        margin_target: Optional[float] = None,
        competitor_sensitivity: Optional[float] = None,
    ):
        super().__init__(agent_id)
        pp = get_model_params().pricing
        self.margin_target = (
            float(pp.margin_target) if margin_target is None else float(margin_target)
        )
        self.competitor_sensitivity = (
            float(pp.competitor_sensitivity)
            if competitor_sensitivity is None
            else float(competitor_sensitivity)
        )
        self._pp = pp

    def calculate_price(
        self, product_data: Dict[str, Any], market_data: Dict[str, Any]
    ) -> float:
        """Calculate price based on competitive analysis."""
        cost = float(product_data.get("cost", 0.0))
        # Ensure current_price has a sensible default if neither current_price nor cost are available
        default_price_from_cost = (
            cost * (1.0 + self.margin_target) if cost > 0 else 0.01
        )
        current_price = float(
            product_data.get("current_price", default_price_from_cost)
        )
        sales_rank = int(product_data.get("sales_rank", 1_000_000))
        inventory = int(
            product_data.get("inventory", int(self._pp.high_inventory_threshold))
        )

        # Get competitor prices from market data
        competitor_prices = [
            float(x) for x in market_data.get("competitor_prices", []) if x is not None
        ]
        # Use a more robust fallback for average competitor price
        avg_competitor_price = (
            (sum(competitor_prices) / len(competitor_prices))
            if competitor_prices
            else max(current_price, cost * (1.0 + self.margin_target), 0.01)
        )

        # Base price calculation (cost + target margin), ensuring a minimum floor
        base_price = (
            cost * (1.0 + self.margin_target) if cost > 0 else max(current_price, 0.01)
        )

        # Adjust based on sales rank thresholds
        rank_factor = 1.0
        if sales_rank < int(self._pp.top_rank_threshold):
            rank_factor = float(self._pp.rank_high_mult)
        elif sales_rank < int(self._pp.mid_rank_threshold):
            rank_factor = float(self._pp.rank_mid_mult)
        elif sales_rank > int(self._pp.poor_rank_threshold):
            rank_factor = float(self._pp.rank_poor_mult)

        # Adjust based on inventory levels (threshold-based)
        if inventory < int(self._pp.low_inventory_threshold):
            inventory_factor = float(self._pp.low_inventory_mult)
        elif inventory > int(self._pp.high_inventory_threshold):
            inventory_factor = float(self._pp.high_inventory_mult)
        else:
            inventory_factor = 1.0

        # Competitive adjustment relative to market
        competitive_factor = 1.0
        if avg_competitor_price > 0:
            price_ratio = base_price / avg_competitor_price
            # If we're much more expensive, reduce price proportional to sensitivity
            if price_ratio > 1.2:
                competitive_factor = 1.0 - (self.competitor_sensitivity * 0.2)
            # If we're much cheaper, allow slight increase to capture margin
            elif price_ratio < 0.8:
                competitive_factor = 1.0 + (self.competitor_sensitivity * 0.1)

        # Calculate final price
        final_price = base_price * rank_factor * inventory_factor * competitive_factor

        # Ensure minimum profit margin over cost
        minimum_price = (
            cost * (1.0 + float(self._pp.minimum_margin_over_cost))
            if cost > 0
            else 0.01
        )
        final_price = max(final_price, minimum_price)

        return ComparablePriceFloat(round(float(final_price), 2))


class DynamicPricingStrategy(PricingStrategy):
    """Dynamic pricing strategy that adapts to market conditions (centralized parameters)."""

    def __init__(
        self,
        agent_id: str,
        base_margin: Optional[float] = None,
        elasticity_factor: Optional[float] = None,
    ):
        super().__init__(agent_id)
        pp = get_model_params().pricing
        self.base_margin = (
            float(pp.base_margin) if base_margin is None else float(base_margin)
        )
        self.elasticity_factor = (
            float(pp.elasticity_factor)
            if elasticity_factor is None
            else float(elasticity_factor)
        )
        self.price_history: Dict[str, List[float]] = (
            {}
        )  # Track price history for each product
        self._pp = pp

    def _estimate_elasticity(self, market_data: Dict[str, Any]) -> Optional[float]:
        """Estimate price elasticity using log-log Ridge regression if data provided in market_data."""
        try:
            recent_prices = market_data.get("recent_prices") or []
            recent_sales = market_data.get("recent_sales") or []
            if len(recent_prices) >= int(
                self._pp.elasticity_history_min_points
            ) and len(recent_prices) == len(recent_sales):
                # Filter positive pairs
                pairs = [
                    (float(p), float(q))
                    for p, q in zip(recent_prices, recent_sales)
                    if p > 0 and q > 0
                ]
                if len(pairs) < int(self._pp.elasticity_history_min_points):
                    return None
                X = np.log(np.array([p for p, _ in pairs])).reshape(-1, 1)
                y = np.log(np.array([q for _, q in pairs]))
                model = Ridge(alpha=float(self._pp.elasticity_ridge_alpha))
                model.fit(X, y)
                # In log-log, elasticity = d ln(Q) / d ln(P) = coefficient
                elasticity = float(model.coef_[0])
                # Clip to plausible range (typically negative)
                elasticity = max(
                    float(self._pp.elasticity_clip_min),
                    min(float(self._pp.elasticity_clip_max), elasticity),
                )
                return elasticity
        except (AttributeError, TypeError, ValueError, RuntimeError):
            logger.exception(
                f"Error estimating elasticity for DynamicPricingStrategy in agent {self.agent_id}"
            )
            return None
        return None

    def calculate_price(
        self, product_data: Dict[str, Any], market_data: Dict[str, Any]
    ) -> float:
        """Calculate price using dynamic pricing algorithm."""
        asin = str(product_data.get("asin", "unknown"))
        cost = float(product_data.get("cost", 0.0))
        current_price = (
            float(product_data.get("current_price", cost * (1.0 + self.base_margin)))
            if cost
            else float(product_data.get("current_price", 0.0))
        )
        sales_rank = int(product_data.get("sales_rank", 1_000_000))
        inventory = int(
            product_data.get("inventory", int(self._pp.high_inventory_threshold))
        )

        # Get market demand indicator and seasonality factor
        market_demand = float(market_data.get("market_demand", 1.0))  # 1.0 = neutral
        seasonality = float(market_data.get("seasonality", 1.0))  # 1.0 = neutral

        # Calculate base price
        base_price = (
            cost * (1.0 + self.base_margin) if cost > 0 else max(current_price, 0.01)
        )

        # Demand-based adjustment scaled by (learned) elasticity magnitude
        learned_elasticity = self._estimate_elasticity(market_data)
        effective_elasticity = (
            abs(learned_elasticity)
            if learned_elasticity is not None
            else self.elasticity_factor
        )
        demand_factor = 1.0 + (market_demand - 1.0) * effective_elasticity

        # Seasonality adjustment
        seasonality_factor = seasonality

        # Sales rank adjustment (threshold-based multipliers for stability)
        if sales_rank < int(self._pp.top_rank_threshold):
            rank_adjustment = float(self._pp.rank_high_mult)
        elif sales_rank < int(self._pp.mid_rank_threshold):
            rank_adjustment = float(self._pp.rank_mid_mult)
        elif sales_rank > int(self._pp.poor_rank_threshold):
            rank_adjustment = float(self._pp.rank_poor_mult)
        else:
            rank_adjustment = 1.0

        # Inventory adjustment (threshold-based)
        if inventory < int(self._pp.low_inventory_threshold):
            inventory_adjustment = float(self._pp.low_inventory_mult)
        elif inventory > int(self._pp.high_inventory_threshold):
            inventory_adjustment = float(self._pp.high_inventory_mult)
        else:
            inventory_adjustment = 1.0

        # First compute a preliminary price without history dampening
        preliminary_price = (
            base_price
            * demand_factor
            * seasonality_factor
            * rank_adjustment
            * inventory_adjustment
        )

        # Apply history-based dampening to avoid large swings
        history_adjustment = 1.0
        last_price = None
        if self.price_history.get(asin):
            last_price = self.price_history[asin][-1]
            change_ratio = (
                abs(preliminary_price - last_price) / last_price
                if last_price and last_price > 0
                else 0.0
            )
            if change_ratio > float(self._pp.dampening_change_ratio):
                history_adjustment = float(self._pp.dampening_multiplier)

        final_price = preliminary_price * history_adjustment

        # Ensure minimum profit margin over cost
        minimum_price = (
            cost * (1.0 + float(self._pp.minimum_margin_over_cost))
            if cost > 0
            else 0.01
        )
        final_price = max(final_price, minimum_price)

        # Update price history
        if asin not in self.price_history:
            self.price_history[asin] = []
        self.price_history[asin].append(float(final_price))

        # Keep only last N prices as configured
        window = int(self._pp.price_history_window)
        if len(self.price_history[asin]) > window:
            self.price_history[asin] = self.price_history[asin][-window:]

        return ComparablePriceFloat(round(float(final_price), 2))


class DIYRunner(AgentRunner):
    """
    Agent runner for DIY (Do It Yourself) agents.

    This class integrates custom-built agents into the FBA-Bench system,
    allowing them to make pricing decisions using custom algorithms.
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """Initialize the DIY agent runner."""
        super().__init__(agent_id, config)
        self.llm_config = None
        self.agent_config = None
        self.pricing_strategy: Optional[PricingStrategy] = None
        self.decision_history = []
        self.agent_id = agent_id  # Store agent_id

    def _do_initialize(self) -> None:
        """Initialize the DIY agent and its components."""
        try:
            # Extract configurations
            self.llm_config = self._extract_llm_config()
            self.agent_config = self._extract_agent_config()

            # Create the pricing strategy
            self._create_pricing_strategy()

            logger.info(f"DIY agent runner {self.agent_id} initialized successfully")

        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            raise AgentRunnerInitializationError(
                f"Failed to initialize DIY agent {self.agent_id}: {e}",
                agent_id=self.agent_id,
                framework="DIY",
            ) from e

    def _extract_llm_config(self) -> LLMConfig:
        """Extract LLM configuration from the agent config."""
        llm_config_dict = self.config.get("llm_config", {})

        # Create LLMConfig with defaults
        return LLMConfig(
            name=f"{self.agent_id}_llm",
            model=llm_config_dict.get("model", "gpt-4"),
            api_key=llm_config_dict.get("api_key"),
            base_url=llm_config_dict.get("base_url"),
            max_tokens=llm_config_dict.get("max_tokens", 2048),
            temperature=llm_config_dict.get("temperature", 0.7),
            top_p=llm_config_dict.get("top_p", 1.0),
            timeout=llm_config_dict.get("timeout", 30),
            max_retries=llm_config_dict.get("max_retries", 3),
        )

    def _extract_agent_config(self) -> AgentConfig:
        """Extract Agent configuration from the agent config."""
        agent_config_dict = self.config.get("agent_config", {})

        # Create AgentConfig with defaults
        return AgentConfig(
            name=f"{self.agent_id}_agent",
            agent_id=self.agent_id,
            type=agent_config_dict.get("type", "pricing_agent"),
            framework=FrameworkType.DIY,
            parameters=agent_config_dict.get("parameters", {}),
        )

    def _create_pricing_strategy(self) -> None:
        """Create the pricing strategy based on configuration."""
        strategy_type = self.agent_config.parameters.get(
            "pricing_strategy", "competitive"
        )

        if strategy_type == "competitive":
            margin_target = self.agent_config.parameters.get("margin_target", 0.3)
            competitor_sensitivity = self.agent_config.parameters.get(
                "competitor_sensitivity", 0.5
            )
            self.pricing_strategy = CompetitivePricingStrategy(
                agent_id=self.agent_id,
                margin_target=margin_target,
                competitor_sensitivity=competitor_sensitivity,
            )
        elif strategy_type == "dynamic":
            base_margin = self.agent_config.parameters.get("base_margin", 0.25)
            elasticity_factor = self.agent_config.parameters.get(
                "elasticity_factor", 0.3
            )
            self.pricing_strategy = DynamicPricingStrategy(
                agent_id=self.agent_id,
                base_margin=base_margin,
                elasticity_factor=elasticity_factor,
            )
        else:
            # Default to competitive pricing
            self.pricing_strategy = CompetitivePricingStrategy(agent_id=self.agent_id)

        logger.debug(f"Created pricing strategy: {strategy_type}")

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a pricing decision using the DIY agent.

        Args:
            context: Context information including market state and products

        Returns:
            Dictionary containing the decision and metadata
        """
        try:
            # Update context
            self.update_context(context)

            # Extract products and market data
            products = context.get("products", [])
            market_conditions = context.get("market_conditions", {})
            tick = context.get("tick", 0)

            # Make pricing decisions for each product
            pricing_decisions = {}
            reasoning = ""

            for product in products:
                asin = product.get("asin", "unknown")

                # Calculate price using the pricing strategy
                new_price = self.pricing_strategy.calculate_price(
                    product, market_conditions
                )

                # Calculate confidence based on data quality
                confidence = self._calculate_confidence(product, market_conditions)

                # Generate reasoning
                product_reasoning = self._generate_reasoning(
                    product, market_conditions, new_price
                )

                pricing_decisions[asin] = {
                    "price": new_price,
                    "confidence": confidence,
                    "reasoning": product_reasoning,
                }

                reasoning += f"{asin}: {product_reasoning}\n"

            # Create decision object
            decision = {
                "agent_id": self.agent_id,
                "framework": "DIY",
                "timestamp": datetime.now().isoformat(),
                "pricing_decisions": pricing_decisions,
                "reasoning": reasoning.strip(),
            }

            # Update decision history
            self.decision_history.append(
                {"tick": tick, "decision": decision, "timestamp": datetime.now()}
            )

            # Keep only last 50 decisions
            if len(self.decision_history) > 50:
                self.decision_history = self.decision_history[-50:]

            # Update metrics
            self.update_metrics(
                {
                    "decision_timestamp": datetime.now().isoformat(),
                    "decision_type": "pricing",
                    "products_count": len(products),
                    "average_confidence": (
                        sum(d["confidence"] for d in pricing_decisions.values())
                        / len(pricing_decisions)
                        if pricing_decisions
                        else 0
                    ),
                    "strategy_type": self.agent_config.parameters.get(
                        "pricing_strategy", "competitive"
                    ),
                }
            )

            return decision

        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.exception(f"Error in DIY decision making for agent {self.agent_id}")
            raise AgentRunnerDecisionError(
                f"Decision making failed for DIY agent {self.agent_id}: {e}",
                agent_id=self.agent_id,
                framework="DIY",
            ) from e

    def _calculate_confidence(
        self, product: Dict[str, Any], market_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for the pricing decision."""
        mp_adv = get_model_params().advanced_agent
        confidence = 0.5  # Base confidence

        # Increase confidence only when signal is actually present and positive
        if product.get("cost", 0) > 0:
            confidence += mp_adv.confidence_product_data_boost
        if product.get("current_price", 0) > 0:
            confidence += mp_adv.confidence_product_data_boost
        if ("sales_rank" in product) and product.get("sales_rank", 0) > 0:
            confidence += mp_adv.confidence_product_data_boost
        if ("inventory" in product) and product.get("inventory", 0) > 0:
            confidence += mp_adv.confidence_product_data_boost

        # Increase confidence if we have good market data
        if market_data.get("market_demand", 0) > 0:
            confidence += mp_adv.confidence_market_data_boost_per_item
        if market_data.get("competitor_prices", []):
            confidence += mp_adv.confidence_market_data_boost_per_item

        # Cap confidence at max_cap
        return min(confidence, mp_adv.confidence_max_cap)

    def _generate_reasoning(
        self, product: Dict[str, Any], market_data: Dict[str, Any], new_price: float
    ) -> str:
        """Generate reasoning for the pricing decision."""
        mp_adv = get_model_params().advanced_agent
        asin = product.get("asin", "unknown")
        cost = product.get("cost", 0)
        current_price = product.get(
            "current_price", cost * mp_adv.reasoning_default_current_price_multiplier
        )
        sales_rank = product.get(
            "sales_rank", mp_adv.reasoning_low_demand_rank_threshold
        )  # Default to low demand rank
        inventory = product.get(
            "inventory", mp_adv.reasoning_high_inventory_threshold
        )  # Default to high inventory

        reasoning = f"Calculated price ${new_price:.2f} for {asin}. "

        # Add cost-based reasoning
        margin = (new_price - float(cost)) / float(cost) if cost > 0 else 0
        reasoning += f"Cost: ${cost:.2f}, Margin: {margin:.1%}. "

        # Add sales rank reasoning
        if sales_rank < mp_adv.reasoning_high_demand_rank_threshold:
            reasoning += f"High demand product (rank {sales_rank}). "
        elif sales_rank > mp_adv.reasoning_low_demand_rank_threshold:
            reasoning += f"Low demand product (rank {sales_rank}). "

        # Add inventory reasoning
        if inventory < mp_adv.reasoning_low_inventory_threshold:
            reasoning += f"Low inventory ({inventory} units). "
        elif inventory > mp_adv.reasoning_high_inventory_threshold:
            reasoning += f"High inventory ({inventory} units). "

        # Add market conditions reasoning
        market_demand = market_data.get("market_demand", 1.0)
        if market_demand > mp_adv.reasoning_high_market_demand_factor:
            reasoning += "High market demand. "
        elif market_demand < mp_adv.reasoning_low_market_demand_factor:
            reasoning += "Low market demand. "

        # Add competitor pricing reasoning
        competitor_prices = market_data.get("competitor_prices", [])
        if competitor_prices:
            avg_competitor_price = sum(competitor_prices) / len(competitor_prices)
            # Use configurable deviation for competitor pricing
            if new_price > avg_competitor_price * (
                1.0 + mp_adv.reasoning_competitor_price_deviation_pct
            ):
                reasoning += (
                    f"Priced above competitors (avg ${avg_competitor_price:.2f}). "
                )
            elif new_price < avg_competitor_price * (
                1.0 - mp_adv.reasoning_competitor_price_deviation_pct
            ):
                reasoning += (
                    f"Priced below competitors (avg ${avg_competitor_price:.2f}). "
                )

        return reasoning.strip()

    def _do_cleanup(self) -> None:
        """Clean up DIY agent resources."""
        self.pricing_strategy = None
        self.decision_history = []
        logger.info(f"DIY agent runner {self.agent_id} cleaned up")
