"""
Template Agent Plugin for FBA-Bench

This template provides a comprehensive starting point for creating custom agent plugins.
It includes all required methods, optional features, and extensive documentation to help
you understand how to implement your own AI agents for FBA simulations.

To use this template:
1. Copy this file and rename it to your plugin name
2. Update the class name and metadata
3. Implement the agent-specific logic in each method
4. Test your agent thoroughly before submission

For more information, see the Plugin Development Guide in plugins/README.md
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

# Import the base agent plugin class
from plugins.agent_plugins.base_agent_plugin import AgentPlugin


class TradingStrategy(Enum):
    """Enumeration of different trading strategies."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    ADAPTIVE = "adaptive"


class MarketPosition(Enum):
    """Enumeration of market positions."""

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class TradingDecision:
    """Represents a trading decision made by the agent."""

    action_type: str
    confidence: float
    reasoning: str
    parameters: Dict[str, Any]
    risk_level: str
    expected_outcome: Optional[Dict[str, Any]] = None


class TemplateAgentPlugin(AgentPlugin):
    """
    Template Agent Plugin

    This template demonstrates how to create a custom agent plugin with
    advanced features like strategy adaptation, performance tracking,
    and decision-making logic.

    Example Use Cases:
    - Machine learning trading agents
    - Rule-based decision systems
    - Hybrid adaptive strategies
    - Multi-objective optimization agents
    """

    def __init__(self):
        """Initialize the template agent plugin."""
        super().__init__()

        # Agent state
        self.strategy = TradingStrategy.MODERATE
        self.market_position = MarketPosition.NEUTRAL
        self.performance_history = []
        self.decision_history = []
        self.learning_rate = 0.01

        # Agent memory and knowledge
        self.market_knowledge = {}
        self.product_performance = {}
        self.competitor_analysis = {}

        # Risk management
        self.risk_tolerance = 0.5
        self.max_loss_threshold = 0.1
        self.position_limits = {}

        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.total_profit = 0.0
        self.max_drawdown = 0.0

        # Logger for this plugin
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return agent metadata.

        This metadata is used by the plugin system for discovery, validation,
        and display purposes. Make sure to update all fields appropriately.
        """
        return {
            # Basic Information
            "name": "Template Agent Plugin",
            "description": "A comprehensive template for creating custom trading agents",
            "version": "1.0.0",
            "author": "FBA-Bench Team",
            "email": "contact@fba-bench.org",
            "website": "https://github.com/fba-bench/agents",
            # Agent Classification
            "category": "template",
            "agent_type": "hybrid",  # rule_based, ml_based, hybrid
            "trading_style": "adaptive",  # conservative, moderate, aggressive, adaptive
            "complexity": "intermediate",  # simple, intermediate, advanced, expert
            "tags": ["template", "example", "adaptive", "multi-strategy"],
            # Technical Information
            "framework_compatibility": ["3.0.0+"],
            "python_version": ">=3.8",
            "supported_scenarios": ["all"],  # or specific scenario types
            "performance_tier": "medium",  # low, medium, high, premium
            # Capabilities
            "capabilities": [
                "adaptive_strategy",
                "risk_management",
                "performance_tracking",
                "learning_adaptation",
                "multi_product_trading",
            ],
            # Resource Requirements
            "resource_requirements": {
                "memory_mb": 128,
                "cpu_cores": 1,
                "gpu_required": False,
                "storage_mb": 50,
            },
            # Performance Characteristics
            "performance_characteristics": {
                "decision_latency_ms": 100,
                "throughput_decisions_per_second": 10,
                "memory_efficiency": "medium",
                "scalability": "good",
            },
            # Configuration Options
            "configurable_parameters": [
                "strategy",
                "risk_tolerance",
                "learning_rate",
                "position_limits",
            ],
            # Documentation
            "documentation_url": "https://docs.fba-bench.org/plugins/agents/template",
            "example_configs": [
                "agents/template_conservative.yaml",
                "agents/template_aggressive.yaml",
            ],
        }

    async def initialize_agent(self, config: Dict[str, Any]) -> None:
        """
        Initialize the agent with configuration.

        Args:
            config: Agent configuration dictionary

        This method is called once at the beginning of the simulation.
        Use it to set up initial parameters, load models, and prepare
        the agent for decision-making.
        """
        self.logger.info("Initializing Template Agent Plugin")

        # Extract and apply configuration
        strategy_name = config.get("strategy", "moderate")
        try:
            self.strategy = TradingStrategy(strategy_name)
        except ValueError:
            self.logger.warning(f"Invalid strategy '{strategy_name}', using MODERATE")
            self.strategy = TradingStrategy.MODERATE

        # Configure risk management
        self.risk_tolerance = config.get("risk_tolerance", 0.5)
        self.max_loss_threshold = config.get("max_loss_threshold", 0.1)

        # Configure learning parameters
        self.learning_rate = config.get("learning_rate", 0.01)

        # Set position limits
        self.position_limits = config.get(
            "position_limits",
            {
                "max_inventory_value": 10000.0,
                "max_single_position": 1000.0,
                "max_positions": 10,
            },
        )

        # Initialize strategy-specific parameters
        await self._initialize_strategy_parameters(config)

        # Load any pre-trained models or data
        await self._load_agent_models(config)

        # Initialize market knowledge
        await self._initialize_market_knowledge()

        self.logger.info(f"Agent initialized with {self.strategy.value} strategy")

    async def make_decision(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a trading decision based on current market observation.

        Args:
            observation: Current market state and available information

        Returns:
            Dictionary containing the agent's decision and reasoning

        This is the core method where your agent analyzes the market
        and decides what action to take.
        """
        # Update internal state with new observation
        await self._update_market_knowledge(observation)

        # Analyze market conditions
        market_analysis = await self._analyze_market_conditions(observation)

        # Assess current portfolio and risk
        risk_assessment = await self._assess_risk(observation)

        # Generate potential actions based on strategy
        potential_actions = await self._generate_potential_actions(
            observation, market_analysis
        )

        # Select best action using decision logic
        selected_action = await self._select_best_action(
            potential_actions, risk_assessment
        )

        # Validate action against constraints
        validated_action = await self._validate_action(selected_action, observation)

        # Create decision object
        decision = TradingDecision(
            action_type=validated_action["action_type"],
            confidence=validated_action["confidence"],
            reasoning=validated_action["reasoning"],
            parameters=validated_action["parameters"],
            risk_level=risk_assessment["overall_risk"],
            expected_outcome=validated_action.get("expected_outcome"),
        )

        # Store decision for learning
        self.decision_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "observation": observation.copy(),
                "decision": decision,
                "market_analysis": market_analysis,
            }
        )

        # Log decision
        self.logger.info(
            f"Decision: {decision.action_type} (confidence: {decision.confidence:.2f})"
        )

        return {
            "action_type": decision.action_type,
            "parameters": decision.parameters,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "metadata": {
                "strategy": self.strategy.value,
                "risk_level": decision.risk_level,
                "expected_outcome": decision.expected_outcome,
            },
        }

    async def update_strategy(self, feedback: Dict[str, Any]) -> None:
        """
        Update agent strategy based on performance feedback.

        Args:
            feedback: Performance feedback including rewards, outcomes, etc.

        This method is called after actions are executed to provide
        feedback for learning and strategy adaptation.
        """
        self.logger.info("Updating strategy based on feedback")

        # Extract feedback information
        reward = feedback.get("reward", 0.0)
        outcome = feedback.get("outcome", {})
        success = feedback.get("success", False)

        # Update performance tracking
        self.total_trades += 1
        if success:
            self.successful_trades += 1

        profit = outcome.get("profit", 0.0)
        self.total_profit += profit

        # Update performance history
        performance_entry = {
            "timestamp": datetime.now().isoformat(),
            "reward": reward,
            "profit": profit,
            "success": success,
            "action_type": feedback.get("action_type"),
            "outcome": outcome,
        }
        self.performance_history.append(performance_entry)

        # Learn from feedback
        await self._learn_from_feedback(feedback)

        # Adapt strategy if needed
        await self._adapt_strategy(feedback)

        # Update risk parameters
        await self._update_risk_parameters(feedback)

        # Log performance update
        success_rate = (
            self.successful_trades / self.total_trades if self.total_trades > 0 else 0
        )
        self.logger.info(
            f"Performance update: {success_rate:.2%} success rate, ${self.total_profit:.2f} total profit"
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Return agent-specific performance metrics.

        Returns:
            Dictionary containing detailed performance metrics

        This method provides insights into the agent's performance
        for analysis and comparison purposes.
        """
        success_rate = (
            self.successful_trades / self.total_trades if self.total_trades > 0 else 0
        )

        # Calculate advanced metrics
        profits = [
            entry["profit"] for entry in self.performance_history if "profit" in entry
        ]

        if profits:
            avg_profit = np.mean(profits)
            max_profit = np.max(profits)
            min_profit = np.min(profits)
            profit_volatility = np.std(profits)

            # Calculate Sharpe ratio (simplified)
            sharpe_ratio = (
                avg_profit / profit_volatility if profit_volatility > 0 else 0
            )

            # Calculate maximum drawdown
            cumulative_profits = np.cumsum(profits)
            running_max = np.maximum.accumulate(cumulative_profits)
            drawdowns = running_max - cumulative_profits
            max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        else:
            avg_profit = max_profit = min_profit = profit_volatility = sharpe_ratio = (
                max_drawdown
            ) = 0

        return {
            # Basic Performance Metrics
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "success_rate": success_rate,
            "total_profit": self.total_profit,
            # Advanced Performance Metrics
            "average_profit_per_trade": avg_profit,
            "max_profit": max_profit,
            "min_profit": min_profit,
            "profit_volatility": profit_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            # Strategy Metrics
            "current_strategy": self.strategy.value,
            "risk_tolerance": self.risk_tolerance,
            "market_position": self.market_position.value,
            # Learning Metrics
            "learning_rate": self.learning_rate,
            "decision_count": len(self.decision_history),
            "adaptation_count": getattr(self, "adaptation_count", 0),
            # Custom Metrics
            "market_knowledge_depth": len(self.market_knowledge),
            "product_tracking_count": len(self.product_performance),
            "competitor_analysis_depth": len(self.competitor_analysis),
        }

    # Strategy Implementation Methods

    async def _initialize_strategy_parameters(self, config: Dict[str, Any]) -> None:
        """Initialize strategy-specific parameters."""
        strategy_config = config.get("strategy_config", {})

        if self.strategy == TradingStrategy.CONSERVATIVE:
            self.risk_tolerance = min(self.risk_tolerance, 0.3)
            self.position_limits["max_single_position"] = 500.0

        elif self.strategy == TradingStrategy.AGGRESSIVE:
            self.risk_tolerance = max(self.risk_tolerance, 0.7)
            self.learning_rate = max(self.learning_rate, 0.02)

        elif self.strategy == TradingStrategy.ADAPTIVE:
            # Adaptive strategy adjusts parameters dynamically
            self.adaptation_threshold = strategy_config.get("adaptation_threshold", 0.1)
            self.adaptation_count = 0

    async def _load_agent_models(self, config: Dict[str, Any]) -> None:
        """Load any pre-trained models or data."""
        model_config = config.get("model_config", {})

        # Example: Load a pre-trained ML model
        model_path = model_config.get("model_path")
        if model_path:
            # In a real implementation, you would load your model here
            self.logger.info(f"Loading model from: {model_path}")
            # self.model = load_model(model_path)

        # Load historical data for analysis
        data_path = model_config.get("historical_data_path")
        if data_path:
            self.logger.info(f"Loading historical data from: {data_path}")
            # self.historical_data = load_data(data_path)

    async def _initialize_market_knowledge(self) -> None:
        """Initialize market knowledge base."""
        self.market_knowledge = {
            "price_trends": {},
            "volatility_patterns": {},
            "seasonal_effects": {},
            "correlation_matrix": {},
            "support_resistance_levels": {},
        }

    # Decision Making Methods

    async def _update_market_knowledge(self, observation: Dict[str, Any]) -> None:
        """Update internal market knowledge with new observation."""
        # Extract market data
        current_prices = observation.get("current_prices", {})
        market_data = observation.get("market_data", {})  # noqa: F841

        # Update price trends
        for product_id, price in current_prices.items():
            if product_id not in self.market_knowledge["price_trends"]:
                self.market_knowledge["price_trends"][product_id] = []

            self.market_knowledge["price_trends"][product_id].append(
                {"timestamp": datetime.now().isoformat(), "price": price}
            )

            # Keep only recent data (last 100 points)
            if len(self.market_knowledge["price_trends"][product_id]) > 100:
                self.market_knowledge["price_trends"][product_id] = (
                    self.market_knowledge["price_trends"][product_id][-100:]
                )

    async def _analyze_market_conditions(
        self, observation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze current market conditions."""
        analysis = {
            "market_trend": "neutral",
            "volatility_level": "medium",
            "opportunity_score": 0.5,
            "risk_factors": [],
            "market_sentiment": "neutral",
        }

        # Analyze price trends
        current_prices = observation.get("current_prices", {})
        historical_prices = observation.get("historical_prices", {})

        if current_prices and historical_prices:
            # Simple trend analysis
            price_changes = []
            for product_id in current_prices:
                if product_id in historical_prices:
                    hist_price = (
                        historical_prices[product_id][-1]
                        if historical_prices[product_id]
                        else current_prices[product_id]
                    )
                    change = (current_prices[product_id] - hist_price) / hist_price
                    price_changes.append(change)

            if price_changes:
                avg_change = np.mean(price_changes)
                volatility = np.std(price_changes)

                # Determine trend
                if avg_change > 0.02:
                    analysis["market_trend"] = "bullish"
                elif avg_change < -0.02:
                    analysis["market_trend"] = "bearish"

                # Determine volatility
                if volatility > 0.05:
                    analysis["volatility_level"] = "high"
                elif volatility < 0.02:
                    analysis["volatility_level"] = "low"

                # Calculate opportunity score
                analysis["opportunity_score"] = min(1.0, abs(avg_change) + volatility)

        # Analyze competitor actions
        competitor_data = observation.get("competitor_data", {})
        if competitor_data:
            aggressive_competitors = sum(
                1
                for comp in competitor_data.values()
                if comp.get("strategy") == "aggressive"
            )
            if aggressive_competitors > len(competitor_data) * 0.5:
                analysis["risk_factors"].append("high_competition")  # type: ignore[attr-defined]

        return analysis

    async def _assess_risk(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Assess current risk levels."""
        portfolio = observation.get("portfolio", {})
        market_data = observation.get("market_data", {})

        # Calculate portfolio risk
        total_value = sum(item.get("value", 0) for item in portfolio.values())
        max_position_ratio = (
            max(
                (item.get("value", 0) / total_value for item in portfolio.values()),
                default=0,
            )
            if total_value > 0
            else 0
        )

        # Assess market risk
        market_volatility = market_data.get("volatility", 0.3)

        # Calculate overall risk
        portfolio_risk = "low"
        if max_position_ratio > 0.5:
            portfolio_risk = "high"
        elif max_position_ratio > 0.3:
            portfolio_risk = "medium"

        market_risk = "low"
        if market_volatility > 0.6:
            market_risk = "high"
        elif market_volatility > 0.4:
            market_risk = "medium"

        # Overall risk assessment
        risk_levels = {"low": 1, "medium": 2, "high": 3}
        overall_risk_level = max(risk_levels[portfolio_risk], risk_levels[market_risk])
        overall_risk = {1: "low", 2: "medium", 3: "high"}[overall_risk_level]

        return {
            "portfolio_risk": portfolio_risk,
            "market_risk": market_risk,
            "overall_risk": overall_risk,
            "max_position_ratio": max_position_ratio,
            "total_portfolio_value": total_value,
            "risk_score": overall_risk_level / 3.0,
        }

    async def _generate_potential_actions(
        self, observation: Dict[str, Any], market_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate potential actions based on current state."""
        actions = []

        current_prices = observation.get("current_prices", {})
        portfolio = observation.get("portfolio", {})
        available_cash = observation.get("available_cash", 0)

        # Generate buy actions
        for product_id, price in current_prices.items():
            if available_cash >= price:
                confidence = self._calculate_buy_confidence(
                    product_id, price, market_analysis
                )
                actions.append(
                    {
                        "action_type": "buy",
                        "parameters": {
                            "product_id": product_id,
                            "quantity": 1,
                            "price": price,
                        },
                        "confidence": confidence,
                        "reasoning": f"Buy {product_id} based on market analysis",
                    }
                )

        # Generate sell actions
        for product_id, item in portfolio.items():
            if item.get("quantity", 0) > 0:
                current_price = current_prices.get(product_id, 0)
                confidence = self._calculate_sell_confidence(
                    product_id, current_price, item, market_analysis
                )
                actions.append(
                    {
                        "action_type": "sell",
                        "parameters": {
                            "product_id": product_id,
                            "quantity": 1,
                            "price": current_price,
                        },
                        "confidence": confidence,
                        "reasoning": f"Sell {product_id} for profit realization",
                    }
                )

        # Generate hold action
        actions.append(
            {
                "action_type": "hold",
                "parameters": {},
                "confidence": 0.5,
                "reasoning": "Wait for better market conditions",
            }
        )

        return actions

    def _calculate_buy_confidence(
        self, product_id: str, price: float, market_analysis: Dict[str, Any]
    ) -> float:
        """Calculate confidence for a buy action."""
        base_confidence = 0.5

        # Adjust based on market trend
        if market_analysis["market_trend"] == "bullish":
            base_confidence += 0.2
        elif market_analysis["market_trend"] == "bearish":
            base_confidence -= 0.2

        # Adjust based on strategy
        if self.strategy == TradingStrategy.AGGRESSIVE:
            base_confidence += 0.1
        elif self.strategy == TradingStrategy.CONSERVATIVE:
            base_confidence -= 0.1

        return max(0.0, min(1.0, base_confidence))

    def _calculate_sell_confidence(
        self,
        product_id: str,
        current_price: float,
        item: Dict[str, Any],
        market_analysis: Dict[str, Any],
    ) -> float:
        """Calculate confidence for a sell action."""
        base_confidence = 0.5

        # Check profitability
        purchase_price = item.get("purchase_price", current_price)
        profit_ratio = (
            (current_price - purchase_price) / purchase_price
            if purchase_price > 0
            else 0
        )

        if profit_ratio > 0.1:  # 10% profit
            base_confidence += 0.3
        elif profit_ratio < -0.05:  # 5% loss
            base_confidence += 0.2  # Cut losses

        # Adjust based on market trend
        if market_analysis["market_trend"] == "bearish":
            base_confidence += 0.2

        return max(0.0, min(1.0, base_confidence))

    async def _select_best_action(
        self, potential_actions: List[Dict[str, Any]], risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Select the best action from potential actions."""
        if not potential_actions:
            return {
                "action_type": "hold",
                "parameters": {},
                "confidence": 0.5,
                "reasoning": "No viable actions available",
            }

        # Score actions based on confidence and risk
        scored_actions = []
        for action in potential_actions:
            score = action["confidence"]

            # Adjust score based on risk tolerance and current risk
            if risk_assessment["overall_risk"] == "high" and action["action_type"] in [
                "buy"
            ]:
                score *= 1 - self.risk_tolerance

            scored_actions.append((score, action))

        # Select action with highest score
        scored_actions.sort(key=lambda x: x[0], reverse=True)
        return scored_actions[0][1]

    async def _validate_action(
        self, action: Dict[str, Any], observation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate action against constraints and limits."""
        action_type = action["action_type"]
        parameters = action["parameters"]

        # Validate position limits
        if action_type == "buy":
            product_id = parameters.get("product_id")  # noqa: F841
            quantity = parameters.get("quantity", 1)
            price = parameters.get("price", 0)

            total_cost = quantity * price
            max_position = self.position_limits.get("max_single_position", float("inf"))

            if total_cost > max_position:
                # Reduce quantity to fit limits
                new_quantity = int(max_position / price)
                if new_quantity > 0:
                    parameters["quantity"] = new_quantity
                    action[
                        "reasoning"
                    ] += f" (reduced quantity to {new_quantity} due to position limits)"
                else:
                    # Convert to hold if can't afford
                    return {
                        "action_type": "hold",
                        "parameters": {},
                        "confidence": 0.3,
                        "reasoning": "Position limits exceeded, holding instead",
                    }

        return action

    # Learning and Adaptation Methods

    async def _learn_from_feedback(self, feedback: Dict[str, Any]) -> None:
        """Learn from performance feedback."""
        reward = feedback.get("reward", 0.0)
        success = feedback.get("success", False)

        # Simple learning: adjust risk tolerance based on performance
        if success and reward > 0:
            # Successful trade, slightly increase risk tolerance
            self.risk_tolerance = min(
                1.0, self.risk_tolerance + self.learning_rate * 0.1
            )
        elif not success or reward < 0:
            # Failed trade, slightly decrease risk tolerance
            self.risk_tolerance = max(
                0.0, self.risk_tolerance - self.learning_rate * 0.1
            )

        # Update product performance tracking
        action_type = feedback.get("action_type")
        if action_type in ["buy", "sell"]:
            product_id = feedback.get("product_id")
            if product_id:
                if product_id not in self.product_performance:
                    self.product_performance[product_id] = {
                        "trades": 0,
                        "success_rate": 0.5,
                    }

                self.product_performance[product_id]["trades"] += 1
                current_success_rate = self.product_performance[product_id][
                    "success_rate"
                ]
                new_success_rate = (
                    current_success_rate + (1.0 if success else 0.0)
                ) / 2
                self.product_performance[product_id]["success_rate"] = new_success_rate

    async def _adapt_strategy(self, feedback: Dict[str, Any]) -> None:
        """Adapt trading strategy based on performance."""
        if self.strategy != TradingStrategy.ADAPTIVE:
            return

        # Check if adaptation is needed
        recent_performance = (
            self.performance_history[-10:]
            if len(self.performance_history) >= 10
            else []
        )

        if len(recent_performance) >= 10:
            success_rate = sum(1 for p in recent_performance if p["success"]) / len(
                recent_performance
            )
            avg_profit = np.mean([p["profit"] for p in recent_performance])

            # Adapt based on performance
            if success_rate < 0.4 or avg_profit < -10:
                # Poor performance, become more conservative
                self.risk_tolerance = max(0.1, self.risk_tolerance - 0.1)
                self.logger.info(
                    "Adapting to more conservative strategy due to poor performance"
                )
                self.adaptation_count += 1

            elif success_rate > 0.7 and avg_profit > 10:
                # Good performance, become more aggressive
                self.risk_tolerance = min(0.9, self.risk_tolerance + 0.1)
                self.logger.info(
                    "Adapting to more aggressive strategy due to good performance"
                )
                self.adaptation_count += 1

    async def _update_risk_parameters(self, feedback: Dict[str, Any]) -> None:
        """Update risk management parameters."""
        # Calculate current drawdown
        if len(self.performance_history) > 0:
            profits = [p["profit"] for p in self.performance_history]
            cumulative = np.cumsum(profits)
            running_max = np.maximum.accumulate(cumulative)
            current_drawdown = (
                (running_max[-1] - cumulative[-1]) / running_max[-1]
                if running_max[-1] > 0
                else 0
            )

            # If drawdown exceeds threshold, reduce risk
            if current_drawdown > self.max_loss_threshold:
                self.risk_tolerance = max(0.1, self.risk_tolerance * 0.8)
                self.logger.warning(
                    f"Reducing risk tolerance due to drawdown: {current_drawdown:.2%}"
                )

    # Utility Methods

    def get_agent_state(self) -> Dict[str, Any]:
        """Get current agent state for monitoring."""
        return {
            "strategy": self.strategy.value,
            "market_position": self.market_position.value,
            "risk_tolerance": self.risk_tolerance,
            "total_trades": self.total_trades,
            "success_rate": (
                self.successful_trades / self.total_trades
                if self.total_trades > 0
                else 0
            ),
            "total_profit": self.total_profit,
            "learning_rate": self.learning_rate,
            "market_knowledge_items": len(self.market_knowledge),
            "recent_decisions": (
                len(self.decision_history[-10:]) if self.decision_history else 0
            ),
        }

    async def export_agent_state(self, export_path: str) -> None:
        """Export agent state for persistence or analysis."""
        export_data = {
            "metadata": self.get_metadata(),
            "configuration": {
                "strategy": self.strategy.value,
                "risk_tolerance": self.risk_tolerance,
                "learning_rate": self.learning_rate,
                "position_limits": self.position_limits,
            },
            "performance_history": self.performance_history,
            "performance_metrics": self.get_performance_metrics(),
            "market_knowledge": self.market_knowledge,
            "product_performance": self.product_performance,
            "agent_state": self.get_agent_state(),
            "export_timestamp": datetime.now().isoformat(),
        }

        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2)

        self.logger.info(f"Agent state exported to: {export_path}")


# Example usage and testing
if __name__ == "__main__":

    async def test_template_agent():
        """Test the template agent with example scenarios."""

        # Create agent instance
        agent = TemplateAgentPlugin()

        # Test configuration
        test_config = {
            "strategy": "adaptive",
            "risk_tolerance": 0.6,
            "learning_rate": 0.02,
            "position_limits": {
                "max_inventory_value": 5000.0,
                "max_single_position": 500.0,
                "max_positions": 5,
            },
        }

        # Initialize agent
        await agent.initialize_agent(test_config)
        print("Agent initialized successfully")

        # Test decision making
        test_observation = {
            "current_prices": {"PROD001": 25.50, "PROD002": 42.75, "PROD003": 18.20},
            "portfolio": {
                "PROD001": {"quantity": 2, "purchase_price": 24.00, "value": 51.00}
            },
            "available_cash": 1000.0,
            "market_data": {"volatility": 0.35},
            "competitor_data": {
                "COMP001": {"strategy": "aggressive"},
                "COMP002": {"strategy": "conservative"},
            },
        }

        # Make decision
        decision = await agent.make_decision(test_observation)
        print(f"Agent decision: {decision}")

        # Test feedback update
        feedback = {
            "reward": 15.5,
            "success": True,
            "outcome": {"profit": 15.5},
            "action_type": decision["action_type"],
        }

        await agent.update_strategy(feedback)

        # Get performance metrics
        metrics = agent.get_performance_metrics()
        print(f"Performance metrics: {metrics}")

        # Test export
        await agent.export_agent_state("./test_agent_export.json")
        print("Agent test completed successfully")

    # Run the test
    asyncio.run(test_template_agent())
