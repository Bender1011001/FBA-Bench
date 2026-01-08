"""
Skill Configuration System for FBA-Bench Multi-Domain Agent Architecture.

This module provides configuration management for skill modules, coordination
strategies, and multi-domain operations with support for different operational
modes and performance tuning.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicts between skills."""

    STRATEGIC_ALIGNMENT = "strategic_alignment"
    PRIORITY_OVERRIDE = "priority_override"
    RESOURCE_OPTIMIZATION = "resource_optimization"
    CONSENSUS_VOTING = "consensus_voting"
    SKILL_EXPERTISE = "skill_expertise"


class ResourceAllocationMethod(Enum):
    """Methods for allocating resources across skills."""

    PROPORTIONAL = "proportional"
    PRIORITY_BASED = "priority_based"
    DEMAND_DRIVEN = "demand_driven"
    STRATEGIC_FOCUS = "strategic_focus"
    BALANCED = "balanced"


@dataclass
class SkillConfig:
    """
    Configuration for skill coordination and multi-domain operations.

    Attributes:
        max_concurrent_skills: Maximum number of skills that can operate concurrently
        skill_priority_weights: Priority weights for different skills
        conflict_resolution_strategy: Strategy for resolving skill conflicts
        resource_allocation_method: Method for distributing resources
        performance_tracking_enabled: Whether to track skill performance metrics
        auto_adjustment_enabled: Whether to auto-adjust based on performance
        coordination_timeout_seconds: Timeout for skill coordination operations
        memory_integration_enabled: Whether skills can access agent memory
        strategic_alignment_threshold: Minimum alignment score for action approval
        emergency_override_enabled: Whether emergency protocols can override normal rules
    """

    max_concurrent_skills: int = 3
    skill_priority_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "SupplyManager": 1.0,
            "MarketingManager": 1.0,
            "CustomerService": 1.0,
            "FinancialAnalyst": 1.2,  # Slightly higher priority for financial oversight
        }
    )
    conflict_resolution_strategy: ConflictResolutionStrategy = (
        ConflictResolutionStrategy.STRATEGIC_ALIGNMENT
    )
    resource_allocation_method: ResourceAllocationMethod = (
        ResourceAllocationMethod.PROPORTIONAL
    )
    performance_tracking_enabled: bool = True
    auto_adjustment_enabled: bool = True
    coordination_timeout_seconds: float = 5.0
    memory_integration_enabled: bool = True
    strategic_alignment_threshold: float = 0.6
    emergency_override_enabled: bool = True

    # Skill-specific configurations
    skill_configurations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Resource limits
    total_budget_cents: int = 1000000  # $10,000
    token_budget: int = 100000
    daily_action_limit: int = 100

    # Performance thresholds
    min_success_rate: float = 0.6
    max_response_time_seconds: float = 3.0
    min_confidence_threshold: float = 0.5

    # Coordination parameters
    consensus_threshold: float = 0.7  # For consensus-based decisions
    expertise_bonus_multiplier: float = 1.3  # Bonus for skill expertise
    strategic_bonus_multiplier: float = 1.5  # Bonus for strategic alignment

    def __post_init__(self):
        """Initialize default skill configurations if not provided."""
        if not self.skill_configurations:
            self.skill_configurations = self._get_default_skill_configurations()

    def _get_default_skill_configurations(self) -> Dict[str, Dict[str, Any]]:
        """Get default configurations for each skill type."""
        return {
            "SupplyManager": {
                "safety_stock_days": 7,
                "reorder_lead_time": 14,
                "max_order_budget_cents": 500000,  # $5,000
                "stockout_risk_threshold": 0.3,
                "auto_reorder_enabled": True,
                "supplier_evaluation_frequency": 30,  # days
            },
            "MarketingManager": {
                "target_profit_margin": 0.20,  # 20%
                "max_ad_budget_cents": 200000,  # $2,000
                "price_change_threshold": 0.05,  # 5%
                "competitor_response_delay": 2,  # ticks
                "campaign_optimization_frequency": 5,  # ticks
                "price_elasticity_learning_enabled": True,
            },
            "CustomerService": {
                "response_time_hours": 12,
                "satisfaction_target": 0.85,  # 85%
                "escalation_threshold": 0.3,  # 30% negative sentiment
                "auto_response_enabled": True,
                "proactive_engagement_enabled": True,
                "survey_frequency_days": 30,
            },
            "FinancialAnalyst": {
                "total_budget_cents": 1000000,  # $10,000
                "warning_threshold": 0.8,  # 80% budget utilization
                "critical_threshold": 0.95,  # 95% budget utilization
                "min_cash_reserve_cents": 100000,  # $1,000
                "forecast_horizon_days": 30,
                "cost_optimization_frequency": 10,  # ticks
            },
        }

    def get_skill_config(self, skill_name: str) -> Dict[str, Any]:
        """Get configuration for a specific skill."""
        return self.skill_configurations.get(skill_name, {})

    def update_skill_config(
        self, skill_name: str, config_updates: Dict[str, Any]
    ) -> None:
        """Update configuration for a specific skill."""
        if skill_name not in self.skill_configurations:
            self.skill_configurations[skill_name] = {}

        self.skill_configurations[skill_name].update(config_updates)
        logger.info(f"Updated configuration for {skill_name}: {config_updates}")

    def get_priority_weight(self, skill_name: str) -> float:
        """Get priority weight for a skill."""
        return self.skill_priority_weights.get(skill_name, 1.0)

    def set_priority_weight(self, skill_name: str, weight: float) -> None:
        """Set priority weight for a skill."""
        self.skill_priority_weights[skill_name] = max(
            0.1, min(3.0, weight)
        )  # Clamp between 0.1 and 3.0
        logger.info(f"Set priority weight for {skill_name}: {weight}")

    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues if any."""
        issues = []

        # Validate concurrent skills limit
        if self.max_concurrent_skills < 1 or self.max_concurrent_skills > 10:
            issues.append("max_concurrent_skills must be between 1 and 10")

        # Validate thresholds
        if not 0.0 <= self.strategic_alignment_threshold <= 1.0:
            issues.append("strategic_alignment_threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.min_success_rate <= 1.0:
            issues.append("min_success_rate must be between 0.0 and 1.0")

        if not 0.0 <= self.min_confidence_threshold <= 1.0:
            issues.append("min_confidence_threshold must be between 0.0 and 1.0")

        # Validate timeouts
        if self.coordination_timeout_seconds <= 0:
            issues.append("coordination_timeout_seconds must be positive")

        if self.max_response_time_seconds <= 0:
            issues.append("max_response_time_seconds must be positive")

        # Validate budgets
        if self.total_budget_cents <= 0:
            issues.append("total_budget_cents must be positive")

        if self.token_budget <= 0:
            issues.append("token_budget must be positive")

        # Validate priority weights
        for skill_name, weight in self.skill_priority_weights.items():
            if weight <= 0:
                issues.append(f"Priority weight for {skill_name} must be positive")

        return issues


@dataclass
class OperationalMode:
    """
    Operational mode configuration for different scenarios.

    Attributes:
        mode_name: Name of the operational mode
        description: Description of when this mode should be used
        skill_config: Skill configuration for this mode
        resource_multipliers: Resource allocation multipliers
        performance_targets: Performance targets for this mode
        activation_conditions: Conditions that trigger this mode
    """

    mode_name: str
    description: str
    skill_config: SkillConfig
    resource_multipliers: Dict[str, float] = field(default_factory=dict)
    performance_targets: Dict[str, float] = field(default_factory=dict)
    activation_conditions: Dict[str, Any] = field(default_factory=dict)


class SkillConfigurationManager:
    """
    Manager for skill configurations and operational modes.

    Handles configuration loading, validation, mode switching, and
    dynamic adjustment based on performance and business conditions.
    """

    def __init__(self, agent_id: str, default_mode: str = "balanced"):
        """
        Initialize the configuration manager.

        Args:
            agent_id: ID of the agent this manager serves
            default_mode: Default operational mode
        """
        self.agent_id = agent_id
        self.current_mode = default_mode
        self.configuration_history: List[Tuple[str, SkillConfig]] = []

        # Initialize operational modes
        self.operational_modes = self._initialize_operational_modes()
        self.current_config = self.operational_modes[default_mode].skill_config

        # Performance tracking for auto-adjustment
        self.performance_history: Dict[str, List[float]] = {
            "success_rate": [],
            "response_time": [],
            "resource_efficiency": [],
            "strategic_alignment": [],
        }

        logger.info(
            f"SkillConfigurationManager initialized for agent {agent_id} in {default_mode} mode"
        )

    def _initialize_operational_modes(self) -> Dict[str, OperationalMode]:
        """Initialize predefined operational modes."""
        modes = {}

        # Balanced Mode - Default operational mode
        balanced_config = SkillConfig()
        modes["balanced"] = OperationalMode(
            mode_name="balanced",
            description="Balanced approach across all business domains",
            skill_config=balanced_config,
            resource_multipliers={"all": 1.0},
            performance_targets={
                "success_rate": 0.7,
                "response_time": 2.0,
                "resource_efficiency": 0.8,
            },
            activation_conditions={"default": True},
        )

        # Crisis Mode - For emergency situations
        crisis_config = SkillConfig(
            max_concurrent_skills=2,  # Reduce complexity
            conflict_resolution_strategy=ConflictResolutionStrategy.PRIORITY_OVERRIDE,
            resource_allocation_method=ResourceAllocationMethod.PRIORITY_BASED,
            coordination_timeout_seconds=3.0,  # Faster decisions
            strategic_alignment_threshold=0.4,  # Lower threshold for speed
            skill_priority_weights={
                "FinancialAnalyst": 2.0,  # Highest priority in crisis
                "CustomerService": 1.5,  # Maintain customer relations
                "SupplyManager": 1.0,
                "MarketingManager": 0.5,  # Lower priority in crisis
            },
        )
        modes["crisis"] = OperationalMode(
            mode_name="crisis",
            description="Emergency mode prioritizing financial stability and damage control",
            skill_config=crisis_config,
            resource_multipliers={
                "FinancialAnalyst": 1.5,
                "CustomerService": 1.2,
                "SupplyManager": 0.8,
                "MarketingManager": 0.5,
            },
            performance_targets={
                "success_rate": 0.8,  # Higher success rate needed
                "response_time": 1.5,  # Faster response needed
                "resource_efficiency": 0.9,
            },
            activation_conditions={
                "financial_health": {"operator": "<", "value": 0.3},
                "cash_position": {"operator": "==", "value": "critical"},
            },
        )

        # Growth Mode - For expansion periods
        growth_config = SkillConfig(
            max_concurrent_skills=4,  # Allow more concurrent operations
            conflict_resolution_strategy=ConflictResolutionStrategy.STRATEGIC_ALIGNMENT,
            resource_allocation_method=ResourceAllocationMethod.STRATEGIC_FOCUS,
            strategic_alignment_threshold=0.7,  # Higher alignment needed
            skill_priority_weights={
                "MarketingManager": 1.8,  # Focus on growth
                "SupplyManager": 1.5,  # Scale inventory
                "CustomerService": 1.2,  # Maintain satisfaction
                "FinancialAnalyst": 1.0,
            },
        )
        modes["growth"] = OperationalMode(
            mode_name="growth",
            description="Growth-focused mode emphasizing marketing and expansion",
            skill_config=growth_config,
            resource_multipliers={
                "MarketingManager": 1.8,
                "SupplyManager": 1.3,
                "CustomerService": 1.1,
                "FinancialAnalyst": 0.9,
            },
            performance_targets={
                "success_rate": 0.75,
                "response_time": 2.5,
                "resource_efficiency": 0.7,  # Accept lower efficiency for growth
            },
            activation_conditions={
                "financial_health": {"operator": ">", "value": 0.8},
                "cash_position": {"operator": "==", "value": "healthy"},
            },
        )

        # Optimization Mode - For efficiency improvements
        optimization_config = SkillConfig(
            max_concurrent_skills=3,
            conflict_resolution_strategy=ConflictResolutionStrategy.RESOURCE_OPTIMIZATION,
            resource_allocation_method=ResourceAllocationMethod.DEMAND_DRIVEN,
            performance_tracking_enabled=True,
            auto_adjustment_enabled=True,
            strategic_alignment_threshold=0.65,
            skill_priority_weights={
                "FinancialAnalyst": 1.5,  # Focus on optimization
                "SupplyManager": 1.3,  # Efficient operations
                "CustomerService": 1.0,
                "MarketingManager": 1.0,
            },
        )
        modes["optimization"] = OperationalMode(
            mode_name="optimization",
            description="Efficiency-focused mode emphasizing cost optimization and process improvement",
            skill_config=optimization_config,
            resource_multipliers={
                "FinancialAnalyst": 1.3,
                "SupplyManager": 1.2,
                "CustomerService": 1.0,
                "MarketingManager": 1.0,
            },
            performance_targets={
                "success_rate": 0.8,
                "response_time": 2.0,
                "resource_efficiency": 0.9,  # High efficiency target
            },
            activation_conditions={
                "operational_efficiency": {"operator": "<", "value": 0.7}
            },
        )

        return modes

    def get_current_config(self) -> SkillConfig:
        """Get current skill configuration."""
        return self.current_config

    def switch_mode(self, mode_name: str, reason: str = "manual") -> bool:
        """
        Switch to a different operational mode.

        Args:
            mode_name: Name of the mode to switch to
            reason: Reason for the mode switch

        Returns:
            True if switch successful, False otherwise
        """
        if mode_name not in self.operational_modes:
            logger.error(f"Unknown operational mode: {mode_name}")
            return False

        previous_mode = self.current_mode
        previous_config = self.current_config

        # Store configuration history
        from datetime import datetime

        self.configuration_history.append((datetime.now().isoformat(), previous_config))

        # Switch to new mode
        self.current_mode = mode_name
        self.current_config = self.operational_modes[mode_name].skill_config

        logger.info(
            f"Switched from {previous_mode} to {mode_name} mode (reason: {reason})"
        )

        # Keep history manageable
        if len(self.configuration_history) > 100:
            self.configuration_history = self.configuration_history[-50:]

        return True

    def auto_adjust_mode(self, business_state: Dict[str, Any]) -> Optional[str]:
        """
        Automatically adjust operational mode based on business state.

        Args:
            business_state: Current business state metrics

        Returns:
            New mode name if switch occurred, None otherwise
        """
        # Check activation conditions for each mode
        for mode_name, mode in self.operational_modes.items():
            if mode_name == self.current_mode:
                continue  # Skip current mode

            if self._check_activation_conditions(
                business_state, mode.activation_conditions
            ):
                if self.switch_mode(mode_name, "auto_adjustment"):
                    return mode_name

        return None

    def _check_activation_conditions(
        self, business_state: Dict[str, Any], conditions: Dict[str, Any]
    ) -> bool:
        """Check if activation conditions are met."""
        for condition_key, condition_spec in conditions.items():
            if condition_key == "default":
                continue

            if condition_key not in business_state:
                continue

            current_value = business_state[condition_key]
            operator = condition_spec.get("operator", "==")
            target_value = condition_spec.get("value")

            if (
                operator == "<"
                and current_value >= target_value
                or operator == ">"
                and current_value <= target_value
                or operator == "=="
                and current_value != target_value
                or operator == "<="
                and current_value > target_value
                or operator == ">="
                and current_value < target_value
            ):
                return False

        return True

    def update_performance_metrics(self, metrics: Dict[str, float]) -> None:
        """Update performance metrics for auto-adjustment."""
        for metric_name, value in metrics.items():
            if metric_name in self.performance_history:
                self.performance_history[metric_name].append(value)

                # Keep recent history only
                if len(self.performance_history[metric_name]) > 50:
                    self.performance_history[metric_name] = self.performance_history[
                        metric_name
                    ][-25:]

    def get_performance_analysis(self) -> Dict[str, Any]:
        """Get analysis of recent performance trends."""
        analysis = {}

        for metric_name, values in self.performance_history.items():
            if not values:
                continue

            recent_values = values[-10:]  # Last 10 measurements
            analysis[metric_name] = {
                "current": recent_values[-1] if recent_values else 0.0,
                "average": sum(recent_values) / len(recent_values),
                "trend": (
                    "improving"
                    if len(recent_values) > 1 and recent_values[-1] > recent_values[0]
                    else "declining"
                ),
                "target": self.operational_modes[
                    self.current_mode
                ].performance_targets.get(metric_name, 0.0),
                "target_met": (
                    recent_values[-1]
                    >= self.operational_modes[
                        self.current_mode
                    ].performance_targets.get(metric_name, 0.0)
                    if recent_values
                    else False
                ),
            }

        return analysis

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration and status."""
        return {
            "current_mode": self.current_mode,
            "mode_description": self.operational_modes[self.current_mode].description,
            "max_concurrent_skills": self.current_config.max_concurrent_skills,
            "conflict_resolution_strategy": self.current_config.conflict_resolution_strategy.value,
            "resource_allocation_method": self.current_config.resource_allocation_method.value,
            "strategic_alignment_threshold": self.current_config.strategic_alignment_threshold,
            "performance_tracking_enabled": self.current_config.performance_tracking_enabled,
            "skill_priority_weights": self.current_config.skill_priority_weights,
            "total_budget": self.current_config.total_budget_cents
            / 100.0,  # Convert to dollars
            "available_modes": list(self.operational_modes.keys()),
            "configuration_changes": len(self.configuration_history),
        }

    def validate_current_config(self) -> List[str]:
        """Validate current configuration."""
        return self.current_config.validate_configuration()

    def export_config(self) -> Dict[str, Any]:
        """Export current configuration for backup or transfer."""
        return {
            "agent_id": self.agent_id,
            "current_mode": self.current_mode,
            "skill_config": {
                "max_concurrent_skills": self.current_config.max_concurrent_skills,
                "skill_priority_weights": self.current_config.skill_priority_weights,
                "conflict_resolution_strategy": self.current_config.conflict_resolution_strategy.value,
                "resource_allocation_method": self.current_config.resource_allocation_method.value,
                "performance_tracking_enabled": self.current_config.performance_tracking_enabled,
                "strategic_alignment_threshold": self.current_config.strategic_alignment_threshold,
                "total_budget_cents": self.current_config.total_budget_cents,
                "skill_configurations": self.current_config.skill_configurations,
            },
            "performance_history": self.performance_history,
            "configuration_history_count": len(self.configuration_history),
        }

    def import_config(self, config_data: Dict[str, Any]) -> bool:
        """Import configuration from backup or transfer."""
        try:
            # Validate required fields
            required_fields = ["current_mode", "skill_config"]
            for field in required_fields:
                if field not in config_data:
                    logger.error(f"Missing required field in config import: {field}")
                    return False

            # Create new configuration
            skill_config_data = config_data["skill_config"]
            imported_config = SkillConfig(
                max_concurrent_skills=skill_config_data.get("max_concurrent_skills", 3),
                skill_priority_weights=skill_config_data.get(
                    "skill_priority_weights", {}
                ),
                conflict_resolution_strategy=ConflictResolutionStrategy(
                    skill_config_data.get(
                        "conflict_resolution_strategy", "strategic_alignment"
                    )
                ),
                resource_allocation_method=ResourceAllocationMethod(
                    skill_config_data.get("resource_allocation_method", "proportional")
                ),
                performance_tracking_enabled=skill_config_data.get(
                    "performance_tracking_enabled", True
                ),
                strategic_alignment_threshold=skill_config_data.get(
                    "strategic_alignment_threshold", 0.6
                ),
                total_budget_cents=skill_config_data.get("total_budget_cents", 1000000),
                skill_configurations=skill_config_data.get("skill_configurations", {}),
            )

            # Validate imported configuration
            issues = imported_config.validate_configuration()
            if issues:
                logger.error(f"Invalid imported configuration: {issues}")
                return False

            # Apply imported configuration
            self.current_config = imported_config
            self.current_mode = config_data["current_mode"]

            # Import performance history if available
            if "performance_history" in config_data:
                self.performance_history = config_data["performance_history"]

            logger.info(
                f"Successfully imported configuration for mode: {self.current_mode}"
            )
            return True

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error importing configuration: {e}")
            return False


def get_skill_config(agent_id: str, mode: str = "balanced") -> SkillConfig:
    """
    Factory function to get skill configuration for an agent.

    Args:
        agent_id: ID of the agent
        mode: Operational mode

    Returns:
        SkillConfig instance
    """
    config_manager = SkillConfigurationManager(agent_id, mode)
    return config_manager.get_current_config()


def create_custom_config(overrides: Dict[str, Any]) -> SkillConfig:
    """
    Create custom skill configuration with overrides.

    Args:
        overrides: Configuration overrides

    Returns:
        SkillConfig instance with custom settings
    """
    config = SkillConfig()

    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            logger.warning(f"Unknown configuration key: {key}")

    return config
