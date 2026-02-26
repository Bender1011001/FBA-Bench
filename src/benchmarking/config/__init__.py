"""
Configuration management for benchmarking.

This module provides comprehensive configuration management for FBA-Bench,
including schema validation, environment-specific settings, and configuration templates.

DEPRECATED: The legacy schema-based configuration system is deprecated and will be removed in a future version.
Please use the Pydantic-based configuration models (e.g., PydanticBenchmarkConfig) instead.
"""

import warnings

# Issue a deprecation warning when importing from the legacy schema system
warnings.warn(
    "The legacy schema-based configuration system in 'benchmarking.config' is deprecated and will be removed in a future version. "
    "Please use the Pydantic-based configuration models (e.g., PydanticBenchmarkConfig) instead.",
    DeprecationWarning,
    stacklevel=2,
)


from .manager import ConfigurationManager, ConfigurationProfile, config_manager  # noqa: E402
from .pydantic_config import (  # Builders and managers; Enums  # Builders and managers; Enums  # Builders and managers; Enums  # Builders and managers; Enums  # noqa: E402
    AgentCapability,  # Builders and managers; Enums
    AgentConfig as PydanticAgentConfig,
    BaseConfig as PydanticBaseConfig,  # Configuration models
    BenchmarkConfig as PydanticBenchmarkConfig,
    ConfigBuilder,  # Builders and managers; Enums
    ConfigProfile as PydanticConfigProfile,
    ConfigTemplate,  # Builders and managers; Enums
    ConfigurationManager as PydanticConfigurationManager,
    CrewConfig as PydanticCrewConfig,
    EnvironmentConfig,
    EnvironmentType,
    ExecutionConfig as PydanticExecutionConfig,
    FrameworkType,  # Builders and managers; Enums
    LLMConfig as PydanticLLMConfig,
    LLMProvider,
    LogLevel,
    MemoryConfig as PydanticMemoryConfig,
    MetricsCollectionConfig as PydanticMetricsConfig,
    MetricType,  # Builders and managers; Enums
    ScenarioConfig as PydanticScenarioConfig,
    ScenarioType,  # Builders and managers; Enums
    UnifiedAgentRunnerConfig as PydanticUnifiedAgentRunnerConfig,
    config_manager as pydantic_config_manager,  # Global instance
)

__all__ = [
    # Primary Pydantic configuration (canonical)
    "EnvironmentType",
    "LogLevel",
    "FrameworkType",
    "LLMProvider",
    "MetricType",
    "ScenarioType",
    "PydanticBaseConfig",
    "PydanticLLMConfig",
    "AgentCapability",
    "PydanticAgentConfig",
    "PydanticMemoryConfig",
    "PydanticCrewConfig",
    "PydanticExecutionConfig",
    "PydanticMetricsConfig",
    "PydanticScenarioConfig",
    "PydanticBenchmarkConfig",
    "EnvironmentConfig",
    "ConfigTemplate",
    "PydanticConfigProfile",
    "PydanticUnifiedAgentRunnerConfig",
    "ConfigBuilder",
    "PydanticConfigurationManager",
    "pydantic_config_manager",
    # Manager interfaces
    "ConfigurationProfile",
    "ConfigurationManager",
    "config_manager",
]
