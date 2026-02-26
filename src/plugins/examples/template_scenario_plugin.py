"""
Template Scenario Plugin for FBA-Bench

This template provides a comprehensive starting point for creating custom scenario plugins.
It includes all required methods, optional features, and extensive documentation to help
you understand how to implement your own market scenarios.

To use this template:
1. Copy this file and rename it to your plugin name
2. Update the class name and metadata
3. Implement the scenario-specific logic in each method
4. Test your plugin thoroughly before submission

For more information, see the Plugin Development Guide in plugins/README.md
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Import the base scenario plugin class
from plugins.scenario_plugins.base_scenario_plugin import ScenarioPlugin


class MarketCondition(Enum):
    """Enumeration of different market conditions."""

    STABLE = "stable"
    VOLATILE = "volatile"
    BULLISH = "bullish"
    BEARISH = "bearish"
    CRISIS = "crisis"


@dataclass
class MarketEvent:
    """Represents a market event that can occur during simulation."""

    event_id: str
    event_type: str
    timestamp: float
    impact_magnitude: float
    affected_products: List[str]
    event_data: Dict[str, Any]


class TemplateScenarioPlugin(ScenarioPlugin):
    """
    Template Scenario Plugin

    This template demonstrates how to create a custom scenario plugin with
    advanced features like dynamic events, market conditions, and configuration
    validation.

    Example Use Cases:
    - Custom market dynamics (seasonal, competitive, regulatory)
    - Specific industry scenarios (electronics, clothing, books)
    - Crisis simulation (supply chain disruption, economic downturns)
    - Growth scenarios (viral products, market expansion)
    """

    def __init__(self):
        """Initialize the template scenario plugin."""
        super().__init__()

        # Plugin state
        self.market_condition = MarketCondition.STABLE
        self.event_queue: List[MarketEvent] = []
        self.scenario_metrics = {}
        self.custom_parameters = {}

        # Logger for this plugin
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return plugin metadata.

        This metadata is used by the plugin system for discovery, validation,
        and display purposes. Make sure to update all fields appropriately.
        """
        return {
            # Basic Information
            "name": "Template Scenario Plugin",
            "description": "A comprehensive template for creating custom market scenarios",
            "version": "1.0.0",
            "author": "FBA-Bench Team",
            "email": "contact@fba-bench.org",
            "website": "https://github.com/fba-bench/scenarios",
            # Plugin Classification
            "category": "template",
            "difficulty": "beginner",  # beginner, intermediate, advanced, expert
            "market_type": "general",  # general, niche, specialized
            "tags": ["template", "example", "tutorial", "custom-events"],
            # Technical Information
            "framework_compatibility": ["3.0.0+"],
            "python_version": ">=3.8",
            "supported_agents": ["all"],  # or specific agent types
            "estimated_duration": "30-60 minutes",
            # Features
            "features": [
                "dynamic_events",
                "market_conditions",
                "custom_metrics",
                "configuration_validation",
                "real_time_adjustments",
            ],
            # Resource Requirements
            "resource_requirements": {
                "memory_mb": 64,
                "cpu_cores": 1,
                "storage_mb": 10,
            },
            # Documentation
            "documentation_url": "https://docs.fba-bench.org/plugins/scenarios/template",
            "example_configs": [
                "scenarios/template_basic.yaml",
                "scenarios/template_advanced.yaml",
            ],
        }

    async def initialize_scenario(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize the scenario with the provided configuration.

        Args:
            config: Scenario configuration dictionary

        Returns:
            Dictionary containing the initial scenario state

        This method is called once at the beginning of the simulation.
        Use it to set up initial conditions, load data, and prepare
        the scenario environment.
        """
        self.logger.info("Initializing Template Scenario Plugin")

        # Store configuration for later use
        self.custom_parameters = config.copy()

        # Extract common configuration parameters
        simulation_duration = config.get("simulation_duration_days", 30)
        market_volatility = config.get("market_volatility", 0.3)
        competitor_count = config.get("competitor_count", 5)
        initial_condition = config.get("initial_market_condition", "stable")

        # Set initial market condition
        try:
            self.market_condition = MarketCondition(initial_condition)
        except ValueError:
            self.logger.warning(
                f"Invalid market condition '{initial_condition}', using STABLE"
            )
            self.market_condition = MarketCondition.STABLE

        # Initialize event queue with scheduled events
        await self._initialize_event_queue(config)

        # Set up scenario metrics tracking
        self.scenario_metrics = {
            "total_events_triggered": 0,
            "market_condition_changes": 0,
            "scenario_start_time": datetime.now().isoformat(),
            "custom_metric_example": 0.0,
        }

        # Return initial scenario state
        initial_state = {
            # Market Configuration
            "market_condition": self.market_condition.value,
            "volatility_factor": market_volatility,
            "competitor_count": competitor_count,
            "simulation_duration": simulation_duration,
            # Product Information
            "available_products": await self._generate_product_catalog(config),
            "market_segments": await self._define_market_segments(config),
            # Economic Factors
            "base_demand_multiplier": config.get("base_demand_multiplier", 1.0),
            "price_sensitivity": config.get("price_sensitivity", 0.5),
            "seasonal_factor": self._calculate_seasonal_factor(),
            # Scenario-Specific Data
            "custom_scenario_data": {
                "event_count": len(self.event_queue),
                "next_event_time": (
                    self.event_queue[0].timestamp if self.event_queue else None
                ),
                "market_condition": self.market_condition.value,
            },
        }

        self.logger.info(f"Scenario initialized with {len(self.event_queue)} events")
        return initial_state

    async def inject_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Inject a dynamic event into the scenario.

        Args:
            event_type: Type of event to inject
            event_data: Event-specific data

        This method is called to inject events during simulation runtime.
        It allows for dynamic scenario modification based on agent actions
        or external triggers.
        """
        self.logger.info(f"Injecting event: {event_type}")

        # Update metrics
        self.scenario_metrics["total_events_triggered"] += 1

        # Handle different event types
        if event_type == "market_volatility_change":
            await self._handle_volatility_change(event_data)

        elif event_type == "competitor_entry":
            await self._handle_competitor_entry(event_data)

        elif event_type == "demand_spike":
            await self._handle_demand_spike(event_data)

        elif event_type == "supply_disruption":
            await self._handle_supply_disruption(event_data)

        elif event_type == "market_condition_change":
            await self._handle_market_condition_change(event_data)

        elif event_type == "regulatory_change":
            await self._handle_regulatory_change(event_data)

        elif event_type == "seasonal_event":
            await self._handle_seasonal_event(event_data)

        else:
            # Handle custom events
            await self._handle_custom_event(event_type, event_data)

        # Log event for analysis
        self._log_event(event_type, event_data)

    def validate_configuration(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate the scenario configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages (empty if valid)

        This method should check all configuration parameters and return
        detailed error messages for any invalid values.
        """
        errors = []

        # Validate simulation duration
        duration = config.get("simulation_duration_days")
        if duration is not None:
            if not isinstance(duration, (int, float)) or duration <= 0:
                errors.append("simulation_duration_days must be a positive number")
            elif duration > 365:
                errors.append("simulation_duration_days cannot exceed 365 days")

        # Validate market volatility
        volatility = config.get("market_volatility")
        if volatility is not None:
            if (
                not isinstance(volatility, (int, float))
                or volatility < 0
                or volatility > 2.0
            ):
                errors.append("market_volatility must be between 0 and 2.0")

        # Validate competitor count
        competitors = config.get("competitor_count")
        if competitors is not None:
            if not isinstance(competitors, int) or competitors < 0 or competitors > 100:
                errors.append("competitor_count must be an integer between 0 and 100")

        # Validate market condition
        market_condition = config.get("initial_market_condition")
        if market_condition is not None:
            valid_conditions = [condition.value for condition in MarketCondition]
            if market_condition not in valid_conditions:
                errors.append(
                    f"initial_market_condition must be one of: {valid_conditions}"
                )

        # Validate custom parameters
        if "custom_parameters" in config:
            custom_errors = self._validate_custom_parameters(
                config["custom_parameters"]
            )
            errors.extend(custom_errors)

        # Validate event configuration
        if "events" in config:
            event_errors = self._validate_event_configuration(config["events"])
            errors.extend(event_errors)

        return errors

    async def get_scenario_state(self) -> Dict[str, Any]:
        """
        Get the current scenario state.

        Returns:
            Dictionary containing current scenario state

        This method is called periodically to get the current state
        of the scenario for monitoring and analysis purposes.
        """
        return {
            "current_market_condition": self.market_condition.value,
            "events_in_queue": len(self.event_queue),
            "next_event": self._get_next_event_info(),
            "scenario_metrics": self.scenario_metrics.copy(),
            "custom_state": await self._get_custom_state(),
        }

    async def cleanup_scenario(self) -> None:
        """
        Clean up scenario resources.

        This method is called when the scenario ends. Use it to clean up
        any resources, save data, or perform final calculations.
        """
        self.logger.info("Cleaning up Template Scenario Plugin")

        # Update final metrics
        self.scenario_metrics["scenario_end_time"] = datetime.now().isoformat()

        # Save scenario data if needed
        await self._save_scenario_data()

        # Clean up resources
        self.event_queue.clear()
        self.custom_parameters.clear()

    # Helper Methods (Private)

    async def _initialize_event_queue(self, config: Dict[str, Any]) -> None:
        """Initialize the event queue with scheduled events."""
        events_config = config.get("events", [])

        for event_config in events_config:
            event = MarketEvent(
                event_id=event_config.get("id", f"event_{len(self.event_queue)}"),
                event_type=event_config["type"],
                timestamp=event_config["timestamp"],
                impact_magnitude=event_config.get("impact", 1.0),
                affected_products=event_config.get("affected_products", []),
                event_data=event_config.get("data", {}),
            )
            self.event_queue.append(event)

        # Sort events by timestamp
        self.event_queue.sort(key=lambda e: e.timestamp)

        # Add default events if none specified
        if not self.event_queue:
            await self._add_default_events(config)

    async def _add_default_events(self, config: Dict[str, Any]) -> None:
        """Add default events to demonstrate event system."""
        duration = config.get("simulation_duration_days", 30)

        # Add a mid-simulation market volatility spike
        mid_event = MarketEvent(
            event_id="default_volatility_spike",
            event_type="market_volatility_change",
            timestamp=duration * 0.5,  # Halfway through simulation
            impact_magnitude=1.5,
            affected_products=[],
            event_data={"new_volatility": 0.8, "duration_days": 3},
        )
        self.event_queue.append(mid_event)

        # Add a late-simulation competitor entry
        late_event = MarketEvent(
            event_id="default_competitor_entry",
            event_type="competitor_entry",
            timestamp=duration * 0.75,  # 3/4 through simulation
            impact_magnitude=1.2,
            affected_products=[],
            event_data={
                "competitor_strategy": "aggressive_pricing",
                "market_share": 0.1,
            },
        )
        self.event_queue.append(late_event)

    async def _generate_product_catalog(
        self, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate a product catalog for the scenario."""
        product_count = config.get("product_count", 5)

        products = []
        for i in range(product_count):
            product = {
                "product_id": f"TEMPLATE_PROD_{i+1:03d}",
                "name": f"Template Product {i+1}",
                "category": f"Category {(i % 3) + 1}",
                "base_price": 20.0 + (i * 10.0),
                "base_demand": 100 + (i * 50),
                "price_elasticity": 0.5 + (i * 0.1),
                "seasonal_factor": 1.0 + ((i % 4) * 0.2),
            }
            products.append(product)

        return products

    async def _define_market_segments(
        self, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Define market segments for the scenario."""
        return [
            {
                "segment_id": "budget_conscious",
                "name": "Budget Conscious",
                "price_sensitivity": 0.8,
                "quality_sensitivity": 0.3,
                "market_share": 0.4,
            },
            {
                "segment_id": "premium_seekers",
                "name": "Premium Seekers",
                "price_sensitivity": 0.2,
                "quality_sensitivity": 0.9,
                "market_share": 0.3,
            },
            {
                "segment_id": "mainstream",
                "name": "Mainstream",
                "price_sensitivity": 0.5,
                "quality_sensitivity": 0.5,
                "market_share": 0.3,
            },
        ]

    def _calculate_seasonal_factor(self) -> float:
        """Calculate current seasonal factor based on time of year."""
        # Simple seasonal calculation - in real scenarios, this could be more complex
        day_of_year = datetime.now().timetuple().tm_yday
        seasonal_factor = 1.0 + 0.2 * (day_of_year / 365.0)
        return seasonal_factor

    # Event Handlers

    async def _handle_volatility_change(self, event_data: Dict[str, Any]) -> None:
        """Handle market volatility change events."""
        new_volatility = event_data.get("new_volatility", 0.5)
        duration = event_data.get("duration_days", 1)

        self.logger.info(
            f"Market volatility changed to {new_volatility} for {duration} days"
        )

        # Update scenario state
        self.custom_parameters["current_volatility"] = new_volatility

        # Schedule volatility return event if needed
        if event_data.get("temporary", True):
            restore_event = MarketEvent(
                event_id=f"restore_volatility_{datetime.now().timestamp()}",
                event_type="volatility_restore",
                timestamp=duration,
                impact_magnitude=1.0,
                affected_products=[],
                event_data={
                    "original_volatility": self.custom_parameters.get(
                        "market_volatility", 0.3
                    )
                },
            )
            self.event_queue.append(restore_event)
            self.event_queue.sort(key=lambda e: e.timestamp)

    async def _handle_competitor_entry(self, event_data: Dict[str, Any]) -> None:
        """Handle new competitor entry events."""
        competitor_strategy = event_data.get("competitor_strategy", "standard")
        market_share = event_data.get("market_share", 0.05)  # noqa: F841

        self.logger.info(f"New competitor entered with {competitor_strategy} strategy")

        # Update competitor count
        current_competitors = self.custom_parameters.get("competitor_count", 5)
        self.custom_parameters["competitor_count"] = current_competitors + 1

    async def _handle_demand_spike(self, event_data: Dict[str, Any]) -> None:
        """Handle demand spike events."""
        affected_products = event_data.get("affected_products", [])
        spike_magnitude = event_data.get("spike_magnitude", 2.0)

        self.logger.info(
            f"Demand spike of {spike_magnitude}x for products: {affected_products}"
        )

    async def _handle_supply_disruption(self, event_data: Dict[str, Any]) -> None:
        """Handle supply chain disruption events."""
        affected_products = event_data.get("affected_products", [])
        disruption_severity = event_data.get("severity", "moderate")

        self.logger.info(
            f"Supply disruption ({disruption_severity}) affecting: {affected_products}"
        )

    async def _handle_market_condition_change(self, event_data: Dict[str, Any]) -> None:
        """Handle market condition change events."""
        new_condition = event_data.get("new_condition", "stable")

        try:
            old_condition = self.market_condition
            self.market_condition = MarketCondition(new_condition)
            self.scenario_metrics["market_condition_changes"] += 1

            self.logger.info(
                f"Market condition changed from {old_condition.value} to {new_condition}"
            )

        except ValueError:
            self.logger.error(f"Invalid market condition: {new_condition}")

    async def _handle_regulatory_change(self, event_data: Dict[str, Any]) -> None:
        """Handle regulatory change events."""
        regulation_type = event_data.get("regulation_type", "unknown")
        impact_severity = event_data.get("impact_severity", "low")

        self.logger.info(
            f"Regulatory change: {regulation_type} with {impact_severity} impact"
        )

    async def _handle_seasonal_event(self, event_data: Dict[str, Any]) -> None:
        """Handle seasonal events (holidays, sales periods, etc.)."""
        season_type = event_data.get("season_type", "general")
        duration_days = event_data.get("duration_days", 7)

        self.logger.info(f"Seasonal event: {season_type} for {duration_days} days")

    async def _handle_custom_event(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> None:
        """Handle custom event types specific to this scenario."""
        self.logger.info(f"Custom event: {event_type}")

        # Update custom metrics
        self.scenario_metrics["custom_metric_example"] += event_data.get(
            "metric_delta", 1.0
        )

    # Validation Helpers

    def _validate_custom_parameters(self, custom_params: Dict[str, Any]) -> List[str]:
        """Validate custom parameters specific to this scenario."""
        errors = []  # type: ignore[var-annotated]

        # Add custom validation logic here
        # Example: validate custom parameter ranges, types, etc.

        return errors

    def _validate_event_configuration(
        self, events_config: List[Dict[str, Any]]
    ) -> List[str]:
        """Validate event configuration."""
        errors = []

        for i, event_config in enumerate(events_config):
            # Check required fields
            if "type" not in event_config:
                errors.append(f"Event {i}: 'type' field is required")

            if "timestamp" not in event_config:
                errors.append(f"Event {i}: 'timestamp' field is required")
            else:
                timestamp = event_config["timestamp"]
                if not isinstance(timestamp, (int, float)) or timestamp < 0:
                    errors.append(
                        f"Event {i}: 'timestamp' must be a non-negative number"
                    )

        return errors

    # State and Utility Methods

    def _get_next_event_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the next scheduled event."""
        if not self.event_queue:
            return None

        next_event = self.event_queue[0]
        return {
            "event_id": next_event.event_id,
            "event_type": next_event.event_type,
            "timestamp": next_event.timestamp,
            "impact_magnitude": next_event.impact_magnitude,
        }

    async def _get_custom_state(self) -> Dict[str, Any]:
        """Get custom state information specific to this scenario."""
        return {
            "template_specific_metric": self.scenario_metrics.get(
                "custom_metric_example", 0.0
            ),
            "market_stability_index": self._calculate_market_stability(),
            "scenario_complexity_score": len(self.event_queue) * 0.1,
        }

    def _calculate_market_stability(self) -> float:
        """Calculate a market stability index."""
        volatility = self.custom_parameters.get("current_volatility", 0.3)
        condition_stability = {
            MarketCondition.STABLE: 1.0,
            MarketCondition.VOLATILE: 0.3,
            MarketCondition.BULLISH: 0.7,
            MarketCondition.BEARISH: 0.5,
            MarketCondition.CRISIS: 0.1,
        }

        base_stability = condition_stability.get(self.market_condition, 0.5)
        volatility_factor = max(0.0, 1.0 - volatility)

        return base_stability * volatility_factor

    def _log_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log event for analysis and debugging."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "market_condition": self.market_condition.value,
            "event_data": event_data,
        }

        # In a real scenario, you might save this to a file or database
        self.logger.debug(f"Event logged: {json.dumps(log_entry)}")

    async def _save_scenario_data(self) -> None:
        """Save scenario data for analysis."""
        scenario_data = {
            "metadata": self.get_metadata(),
            "final_metrics": self.scenario_metrics,
            "final_state": await self.get_scenario_state(),
            "configuration": self.custom_parameters,
        }

        # In a real scenario, you might save this to a file
        self.logger.info(f"Scenario data saved: {len(json.dumps(scenario_data))} bytes")


# Example usage and testing
if __name__ == "__main__":

    async def test_template_plugin():
        """Test the template plugin with example configuration."""

        # Create plugin instance
        plugin = TemplateScenarioPlugin()

        # Test configuration
        test_config = {
            "simulation_duration_days": 30,
            "market_volatility": 0.4,
            "competitor_count": 7,
            "initial_market_condition": "stable",
            "product_count": 3,
            "events": [
                {
                    "type": "market_volatility_change",
                    "timestamp": 15,
                    "data": {"new_volatility": 0.8, "duration_days": 5},
                }
            ],
        }

        # Validate configuration
        errors = plugin.validate_configuration(test_config)
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return

        # Initialize scenario
        initial_state = await plugin.initialize_scenario(test_config)
        print("Scenario initialized successfully")
        print(f"Initial state keys: {list(initial_state.keys())}")

        # Test event injection
        await plugin.inject_event(
            "demand_spike",
            {"affected_products": ["TEMPLATE_PROD_001"], "spike_magnitude": 2.5},
        )

        # Get scenario state
        current_state = await plugin.get_scenario_state()
        print(f"Current scenario state: {current_state}")

        # Cleanup
        await plugin.cleanup_scenario()
        print("Plugin test completed successfully")

    # Run the test
    asyncio.run(test_template_plugin())
