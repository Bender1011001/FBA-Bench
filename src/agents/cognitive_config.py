"""
Cognitive Configuration for FBA-Bench Enhanced Agent Architecture

Centralizes configuration parameters for all cognitive components including
hierarchical planning, structured reflection, and memory validation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class CognitiveMode(Enum):
    """Operating modes for cognitive systems."""

    BASIC = "basic"  # Basic cognitive functions only
    ENHANCED = "enhanced"  # Full cognitive capabilities
    EXPERIMENTAL = "experimental"  # Experimental features enabled
    DEBUG = "debug"  # Debug mode with extensive logging


class ReflectionMode(Enum):
    """Modes for reflection system operation."""

    DISABLED = "disabled"
    PERIODIC_ONLY = "periodic_only"
    EVENT_DRIVEN_ONLY = "event_driven_only"
    ADAPTIVE = "adaptive"  # Combines all trigger types
    CONTINUOUS = "continuous"  # High-frequency reflection


class PlanningMode(Enum):
    """Modes for hierarchical planning system."""

    REACTIVE = "reactive"  # No strategic planning, reactive only
    TACTICAL = "tactical"  # Short-term tactical planning only
    STRATEGIC = "strategic"  # Strategic planning with tactical execution
    FULL_HIERARCHY = "full_hierarchy"  # Complete hierarchical planning


class ValidationMode(Enum):
    """Modes for memory validation system."""

    DISABLED = "disabled"
    MONITORING = "monitoring"  # Monitor but don't block actions
    ADVISORY = "advisory"  # Provide warnings
    BLOCKING = "blocking"  # Block inconsistent actions


@dataclass
class ReflectionConfig:
    """Configuration for structured reflection system."""

    # Reflection scheduling
    reflection_interval: int = 7  # days between reflection cycles
    min_reflection_interval_hours: int = 6  # minimum hours between reflections
    max_reflection_interval_days: int = 14  # maximum days without reflection

    # Trigger configuration
    periodic_enabled: bool = True
    event_driven_enabled: bool = True
    performance_threshold_enabled: bool = True

    # Performance thresholds for triggering reflection
    performance_degradation_threshold: float = 0.2  # 20% performance drop
    failure_rate_threshold: float = 0.3  # 30% failure rate triggers reflection
    confidence_drop_threshold: float = 0.25  # 25% confidence drop

    # Analysis parameters
    analysis_lookback_days: int = 7  # days of history to analyze
    min_decisions_for_analysis: int = 5  # minimum decisions needed for analysis
    insight_confidence_threshold: float = 0.6  # minimum confidence for insights

    # Policy adjustment parameters
    policy_adjustment_enabled: bool = True
    max_adjustments_per_reflection: int = 5
    adjustment_confidence_threshold: float = 0.7

    # Reflection quality parameters
    min_insight_novelty_score: float = 0.3
    min_actionability_score: float = 0.5
    target_analysis_depth: float = 0.8


@dataclass
class StrategicPlanningConfig:
    """Configuration for strategic planning system."""

    # Planning horizons
    strategic_planning_horizon: int = 90  # days for strategic plans
    tactical_planning_horizon: int = 7  # days for tactical plans
    plan_review_interval: int = 14  # days between plan reviews

    # Objective management
    max_concurrent_objectives: int = 5
    objective_priority_rebalancing: bool = True
    auto_objective_generation: bool = True

    # Strategic adaptation
    strategy_adaptation_enabled: bool = True
    external_event_sensitivity: float = 0.7  # sensitivity to external events
    performance_adaptation_threshold: float = (
        0.15  # performance change to trigger adaptation
    )

    # Action generation
    tactical_action_generation: bool = True
    max_concurrent_actions: int = 5
    action_scheduling_optimization: bool = True

    # Planning quality parameters
    plan_validation_enabled: bool = True
    objective_feasibility_checking: bool = True
    resource_constraint_validation: bool = True


@dataclass
class MemoryValidationConfig:
    """Configuration for memory validation system."""

    # Validation behavior
    memory_validation_enabled: bool = True
    validation_mode: ValidationMode = ValidationMode.ADVISORY
    pre_action_validation: bool = True
    post_action_learning: bool = True

    # Consistency checking parameters
    contradiction_threshold: float = 0.8  # threshold for detecting contradictions
    temporal_consistency_window_hours: int = 24  # time window for temporal checks
    confidence_threshold: float = 0.6  # minimum confidence for reliable memories
    stale_information_threshold_hours: int = 48  # when information becomes stale

    # Validation scope
    validate_pricing_actions: bool = True
    validate_inventory_actions: bool = True
    validate_marketing_actions: bool = True
    validate_customer_actions: bool = True

    # Learning parameters
    learning_from_outcomes: bool = True
    pattern_recognition_enabled: bool = True
    adaptive_threshold_adjustment: bool = True

    # Inconsistency handling
    auto_resolve_minor_inconsistencies: bool = False
    escalate_critical_inconsistencies: bool = True
    inconsistency_logging_level: str = "INFO"


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring and optimization."""

    # Performance tracking
    performance_monitoring_enabled: bool = True
    track_decision_success_rate: bool = True
    track_response_times: bool = True
    track_resource_usage: bool = True

    # Optimization parameters
    auto_performance_optimization: bool = True
    optimization_trigger_threshold: float = 0.1  # 10% performance degradation
    optimization_frequency_hours: int = 24

    # Metrics collection
    collect_cognitive_metrics: bool = True
    metric_aggregation_interval_minutes: int = 15
    historical_metric_retention_days: int = 30


@dataclass
class IntegrationConfig:
    """Configuration for system integration and coordination."""

    # Event system integration
    publish_cognitive_events: bool = True
    subscribe_to_external_events: bool = True
    event_filtering_enabled: bool = True

    # Component coordination
    hierarchical_coordination: bool = True  # coordinate between planning levels
    reflection_planning_integration: bool = True  # integrate reflection with planning
    memory_planning_sync: bool = True  # sync memory with planning updates

    # Error handling and resilience
    graceful_degradation: bool = True  # degrade gracefully on component failure
    component_isolation: bool = True  # isolate component failures
    auto_recovery_enabled: bool = True

    # Debug and monitoring
    comprehensive_logging: bool = False  # detailed logging for debugging
    performance_profiling: bool = False  # profile cognitive operations
    trace_cognitive_decisions: bool = True


@dataclass
class CognitiveConfig:
    """
    Comprehensive configuration for cognitive architecture.

    This dataclass centralizes all configuration parameters for the enhanced
    cognitive capabilities including reflection, planning, and memory validation.
    """

    # Core configuration
    agent_id: str = ""
    cognitive_mode: CognitiveMode = CognitiveMode.ENHANCED

    # Component configurations
    reflection: ReflectionConfig = field(default_factory=ReflectionConfig)
    strategic_planning: StrategicPlanningConfig = field(
        default_factory=StrategicPlanningConfig
    )
    memory_validation: MemoryValidationConfig = field(
        default_factory=MemoryValidationConfig
    )
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    integration: IntegrationConfig = field(default_factory=IntegrationConfig)

    # Global cognitive parameters
    cognitive_load_management: bool = True
    adaptive_cognitive_scheduling: bool = True
    cognitive_resource_limits: Dict[str, int] = field(
        default_factory=lambda: {
            "max_concurrent_reflections": 1,
            "max_concurrent_planning_sessions": 2,
            "max_concurrent_validations": 5,
            "max_memory_operations_per_minute": 100,
        }
    )

    # Emergency and fallback settings
    emergency_mode_triggers: Dict[str, float] = field(
        default_factory=lambda: {
            "critical_performance_threshold": 0.3,
            "system_overload_threshold": 0.9,
            "memory_inconsistency_threshold": 0.8,
        }
    )

    fallback_behavior: Dict[str, str] = field(
        default_factory=lambda: {
            "on_reflection_failure": "continue_with_basic_analysis",
            "on_planning_failure": "fall_back_to_reactive_mode",
            "on_validation_failure": "proceed_with_warning",
            "on_memory_corruption": "reset_to_baseline_memory",
        }
    )

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_configuration()
        logger.info(
            f"CognitiveConfig initialized for agent {self.agent_id} in {self.cognitive_mode.value} mode"
        )

    def _validate_configuration(self):
        """Validate configuration parameters for consistency."""
        # Validate reflection intervals
        if self.reflection.reflection_interval < 1:
            raise ValueError("Reflection interval must be at least 1 day")

        if self.reflection.min_reflection_interval_hours >= 24:
            raise ValueError("Minimum reflection interval should be less than 24 hours")

        # Validate planning horizons
        if (
            self.strategic_planning.strategic_planning_horizon
            <= self.strategic_planning.tactical_planning_horizon
        ):
            raise ValueError(
                "Strategic planning horizon must be longer than tactical horizon"
            )

        # Validate thresholds
        if not (0.0 <= self.reflection.performance_degradation_threshold <= 1.0):
            raise ValueError(
                "Performance degradation threshold must be between 0.0 and 1.0"
            )

        if not (0.0 <= self.memory_validation.contradiction_threshold <= 1.0):
            raise ValueError("Contradiction threshold must be between 0.0 and 1.0")

        # Validate resource limits
        for limit_name, limit_value in self.cognitive_resource_limits.items():
            if limit_value <= 0:
                raise ValueError(f"Resource limit {limit_name} must be positive")

    def get_mode_specific_config(self) -> Dict[str, Any]:
        """Get configuration adjustments based on cognitive mode."""
        mode_configs = {
            CognitiveMode.BASIC: {
                "reflection_enabled": False,
                "strategic_planning_enabled": False,
                "memory_validation_mode": ValidationMode.DISABLED,
                "performance_monitoring_basic": True,
            },
            CognitiveMode.ENHANCED: {
                "reflection_enabled": True,
                "strategic_planning_enabled": True,
                "memory_validation_mode": ValidationMode.ADVISORY,
                "performance_monitoring_full": True,
            },
            CognitiveMode.EXPERIMENTAL: {
                "reflection_enabled": True,
                "strategic_planning_enabled": True,
                "memory_validation_mode": ValidationMode.BLOCKING,
                "experimental_features": True,
                "advanced_analytics": True,
            },
            CognitiveMode.DEBUG: {
                "reflection_enabled": True,
                "strategic_planning_enabled": True,
                "memory_validation_mode": ValidationMode.MONITORING,
                "comprehensive_logging": True,
                "performance_profiling": True,
                "debug_mode": True,
            },
        }

        return mode_configs.get(self.cognitive_mode, {})

    def optimize_for_performance(self):
        """Optimize configuration for better performance."""
        logger.info("Optimizing cognitive configuration for performance")

        # Reduce reflection frequency
        self.reflection.reflection_interval = min(  # type: ignore[assignment]
            14, self.reflection.reflection_interval * 1.5
        )

        # Reduce planning complexity
        self.strategic_planning.max_concurrent_objectives = min(
            3, self.strategic_planning.max_concurrent_objectives
        )
        self.strategic_planning.max_concurrent_actions = min(
            3, self.strategic_planning.max_concurrent_actions
        )

        # Optimize memory validation
        self.memory_validation.contradiction_threshold *= (
            1.1  # Make validation less strict
        )
        self.memory_validation.temporal_consistency_window_hours = min(
            12, self.memory_validation.temporal_consistency_window_hours
        )

        # Adjust resource limits
        for key in self.cognitive_resource_limits:
            self.cognitive_resource_limits[key] = int(
                self.cognitive_resource_limits[key] * 0.8
            )

    def optimize_for_accuracy(self):
        """Optimize configuration for better accuracy."""
        logger.info("Optimizing cognitive configuration for accuracy")

        # Increase reflection frequency
        self.reflection.reflection_interval = max(
            3, int(self.reflection.reflection_interval * 0.7)
        )

        # Increase analysis depth
        self.reflection.analysis_lookback_days = min(  # type: ignore[assignment]
            14, self.reflection.analysis_lookback_days * 1.5
        )
        self.reflection.min_decisions_for_analysis = max(
            3, self.reflection.min_decisions_for_analysis - 1
        )

        # Stricter validation
        self.memory_validation.contradiction_threshold *= (
            0.9  # Make validation more strict
        )
        self.memory_validation.confidence_threshold *= 1.1

        # More comprehensive planning
        self.strategic_planning.plan_review_interval = max(
            7, int(self.strategic_planning.plan_review_interval * 0.8)
        )

    def apply_emergency_mode(self):
        """Apply emergency mode configuration."""
        logger.warning("Applying emergency mode configuration")

        # Minimal cognitive load
        self.reflection.reflection_interval = 14  # Reduce reflection frequency
        self.strategic_planning.max_concurrent_objectives = 2
        self.strategic_planning.max_concurrent_actions = 2

        # Relaxed validation
        self.memory_validation.validation_mode = ValidationMode.MONITORING
        self.memory_validation.contradiction_threshold = 0.9

        # Conservative resource limits
        self.cognitive_resource_limits = {
            "max_concurrent_reflections": 1,
            "max_concurrent_planning_sessions": 1,
            "max_concurrent_validations": 2,
            "max_memory_operations_per_minute": 50,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "agent_id": self.agent_id,
            "cognitive_mode": self.cognitive_mode.value,
            "reflection": {
                "reflection_interval": self.reflection.reflection_interval,
                "performance_degradation_threshold": self.reflection.performance_degradation_threshold,
                "analysis_lookback_days": self.reflection.analysis_lookback_days,
                "policy_adjustment_enabled": self.reflection.policy_adjustment_enabled,
            },
            "strategic_planning": {
                "strategic_planning_horizon": self.strategic_planning.strategic_planning_horizon,
                "tactical_planning_horizon": self.strategic_planning.tactical_planning_horizon,
                "max_concurrent_objectives": self.strategic_planning.max_concurrent_objectives,
                "strategy_adaptation_enabled": self.strategic_planning.strategy_adaptation_enabled,
            },
            "memory_validation": {
                "memory_validation_enabled": self.memory_validation.memory_validation_enabled,
                "validation_mode": self.memory_validation.validation_mode.value,
                "contradiction_threshold": self.memory_validation.contradiction_threshold,
                "confidence_threshold": self.memory_validation.confidence_threshold,
            },
            "performance": {
                "performance_monitoring_enabled": self.performance.performance_monitoring_enabled,
                "auto_performance_optimization": self.performance.auto_performance_optimization,
                "optimization_trigger_threshold": self.performance.optimization_trigger_threshold,
            },
            "integration": {
                "publish_cognitive_events": self.integration.publish_cognitive_events,
                "hierarchical_coordination": self.integration.hierarchical_coordination,
                "graceful_degradation": self.integration.graceful_degradation,
            },
            "cognitive_resource_limits": self.cognitive_resource_limits,
            "emergency_mode_triggers": self.emergency_mode_triggers,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "CognitiveConfig":
        """Create configuration from dictionary."""
        config = cls(agent_id=config_dict.get("agent_id", ""))

        # Apply configuration values
        if "cognitive_mode" in config_dict:
            config.cognitive_mode = CognitiveMode(config_dict["cognitive_mode"])

        # Apply reflection config
        if "reflection" in config_dict:
            refl_config = config_dict["reflection"]
            config.reflection.reflection_interval = refl_config.get(
                "reflection_interval", config.reflection.reflection_interval
            )
            config.reflection.performance_degradation_threshold = refl_config.get(
                "performance_degradation_threshold",
                config.reflection.performance_degradation_threshold,
            )

        # Apply other configurations similarly...

        return config

    @classmethod
    def create_development_config(cls, agent_id: str) -> "CognitiveConfig":
        """Create configuration optimized for development and testing."""
        config = cls(agent_id=agent_id, cognitive_mode=CognitiveMode.DEBUG)

        # Fast iterations for development
        config.reflection.reflection_interval = 1  # Daily reflection
        config.reflection.min_reflection_interval_hours = 1  # Allow frequent reflection
        config.strategic_planning.plan_review_interval = 3  # Review plans every 3 days

        # Comprehensive logging
        config.integration.comprehensive_logging = True
        config.integration.performance_profiling = True
        config.integration.trace_cognitive_decisions = True

        # Relaxed thresholds for testing
        config.memory_validation.contradiction_threshold = 0.6
        config.reflection.performance_degradation_threshold = 0.3

        return config

    @classmethod
    def create_production_config(cls, agent_id: str) -> "CognitiveConfig":
        """Create configuration optimized for production use."""
        config = cls(agent_id=agent_id, cognitive_mode=CognitiveMode.ENHANCED)

        # Balanced performance and accuracy
        config.reflection.reflection_interval = 7  # Weekly reflection
        config.strategic_planning.strategic_planning_horizon = 90  # Quarterly planning

        # Production-appropriate validation
        config.memory_validation.validation_mode = ValidationMode.ADVISORY
        config.memory_validation.contradiction_threshold = 0.8

        # Performance monitoring
        config.performance.performance_monitoring_enabled = True
        config.performance.auto_performance_optimization = True

        # Robust error handling
        config.integration.graceful_degradation = True
        config.integration.auto_recovery_enabled = True

        return config

    @classmethod
    def create_research_config(cls, agent_id: str) -> "CognitiveConfig":
        """Create configuration optimized for research and experimentation."""
        config = cls(agent_id=agent_id, cognitive_mode=CognitiveMode.EXPERIMENTAL)

        # Frequent reflection for research insights
        config.reflection.reflection_interval = 3  # Every 3 days
        config.reflection.analysis_lookback_days = 14  # Longer analysis window

        # Aggressive validation for research quality
        config.memory_validation.validation_mode = ValidationMode.BLOCKING
        config.memory_validation.contradiction_threshold = 0.9

        # Comprehensive data collection
        config.performance.collect_cognitive_metrics = True
        config.performance.historical_metric_retention_days = 90

        # Advanced features
        config.strategic_planning.auto_objective_generation = True
        config.memory_validation.pattern_recognition_enabled = True

        return config


# Predefined configuration templates
COGNITIVE_CONFIG_TEMPLATES = {
    "development": CognitiveConfig.create_development_config,
    "production": CognitiveConfig.create_production_config,
    "research": CognitiveConfig.create_research_config,
}


def get_cognitive_config(template: str, agent_id: str) -> CognitiveConfig:
    """
    Get a cognitive configuration using a predefined template.

    Args:
        template: Template name ("development", "production", "research")
        agent_id: Unique identifier for the agent

    Returns:
        CognitiveConfig instance configured for the specified template
    """
    if template not in COGNITIVE_CONFIG_TEMPLATES:
        raise ValueError(
            f"Unknown template: {template}. Available: {list(COGNITIVE_CONFIG_TEMPLATES.keys())}"
        )

    config_factory = COGNITIVE_CONFIG_TEMPLATES[template]
    return config_factory(agent_id)


def validate_cognitive_config(config: CognitiveConfig) -> List[str]:
    """
    Validate a cognitive configuration and return any issues found.

    Args:
        config: CognitiveConfig to validate

    Returns:
        List of validation issues (empty if valid)
    """
    issues = []

    # Check critical thresholds
    if config.reflection.performance_degradation_threshold > 0.5:
        issues.append("Performance degradation threshold may be too high (>50%)")

    if config.memory_validation.contradiction_threshold < 0.5:
        issues.append("Contradiction threshold may be too strict (<50%)")

    # Check resource limits
    if config.cognitive_resource_limits["max_concurrent_reflections"] > 2:
        issues.append("Too many concurrent reflections may cause performance issues")

    # Check intervals
    if config.reflection.reflection_interval > 30:
        issues.append("Reflection interval may be too long (>30 days)")

    if config.strategic_planning.strategic_planning_horizon < 30:
        issues.append("Strategic planning horizon may be too short (<30 days)")

    return issues
