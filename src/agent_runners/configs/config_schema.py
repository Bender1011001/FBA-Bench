"""
Configuration schema and validation for agent runner frameworks.

Provides structured configuration with validation, defaults, and
framework-specific schema definitions.
"""

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class Framework(Enum):
    """Supported agent frameworks."""

    DIY = "diy"
    CREWAI = "crewai"
    LANGCHAIN = "langchain"


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def __post_init__(self):
        if self.temperature < 0.0 or self.temperature > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")


@dataclass
class MemoryConfig:
    """Configuration for agent memory systems."""

    type: str = "buffer"  # buffer, summary, none
    window_size: int = 10
    max_tokens: Optional[int] = None

    def __post_init__(self):
        if self.type not in ["buffer", "summary", "none"]:
            raise ValueError("Memory type must be 'buffer', 'summary', or 'none'")
        if self.window_size < 1:
            raise ValueError("Window size must be positive")


@dataclass
class AgentConfig:
    """Configuration for individual agent behavior."""

    agent_type: str = "advanced"
    target_asin: str = "B0DEFAULT"
    strategy: str = "profit_maximizer"
    price_sensitivity: float = 0.1
    reaction_speed: int = 1
    min_price_cents: int = 500
    max_price_cents: int = 5000

    def __post_init__(self):
        if self.price_sensitivity < 0.0 or self.price_sensitivity > 1.0:
            raise ValueError("Price sensitivity must be between 0.0 and 1.0")
        if self.reaction_speed < 1:
            raise ValueError("Reaction speed must be positive")
        if self.min_price_cents >= self.max_price_cents:
            raise ValueError("Min price must be less than max price")


@dataclass
class CrewConfig:
    """Configuration for CrewAI crew setup."""

    process: str = "sequential"  # sequential, hierarchical
    crew_size: int = 4
    roles: List[str] = field(
        default_factory=lambda: [
            "pricing_specialist",
            "inventory_manager",
            "market_analyst",
            "strategy_coordinator",
        ]
    )
    collaboration_mode: str = "sequential"
    allow_delegation: bool = True

    def __post_init__(self):
        if self.process not in ["sequential", "hierarchical"]:
            raise ValueError("Process must be 'sequential' or 'hierarchical'")
        if self.crew_size < 1:
            raise ValueError("Crew size must be positive")


@dataclass
class AgentRunnerConfig:
    """
    Unified configuration for agent runners across all frameworks.

    This provides a structured way to configure agents with validation,
    defaults, and framework-specific sections.
    """

    # Core identification
    agent_id: str
    framework: str

    # Framework-specific configurations
    llm_config: Optional[LLMConfig] = None
    memory_config: Optional[MemoryConfig] = None
    agent_config: Optional[AgentConfig] = None
    crew_config: Optional[CrewConfig] = None

    # General settings
    verbose: bool = False
    max_iterations: int = 5
    timeout_seconds: int = 30

    # Custom configurations
    custom_tools: List[Any] = field(default_factory=list)
    custom_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.agent_id:
            raise ValueError("Agent ID cannot be empty")

        try:
            Framework(self.framework)
        except ValueError:
            valid_frameworks = [f.value for f in Framework]
            raise ValueError(
                f"Invalid framework: {self.framework}. Valid: {valid_frameworks}"
            )

        # Set defaults based on framework
        self._set_framework_defaults()

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access for backward compatibility with tests."""
        if hasattr(self, key):
            return getattr(self, key)
        # Check in nested agent_config for DIY-style fields
        if self.agent_config and hasattr(self.agent_config, key):
            return getattr(self.agent_config, key)
        if key in self.custom_config:
            return self.custom_config[key]
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Allow 'in' operator for backward compatibility."""
        if hasattr(self, key):
            return True
        if self.agent_config and hasattr(self.agent_config, key):
            return True
        return key in self.custom_config

    def _set_framework_defaults(self):
        """Set framework-specific defaults."""
        if self.framework == Framework.DIY.value:
            if self.agent_config is None:
                self.agent_config = AgentConfig()

        elif self.framework == Framework.CREWAI.value:
            if self.llm_config is None:
                self.llm_config = LLMConfig()
            if self.crew_config is None:
                self.crew_config = CrewConfig()

        elif self.framework == Framework.LANGCHAIN.value:
            if self.llm_config is None:
                self.llm_config = LLMConfig()
            if self.memory_config is None:
                self.memory_config = MemoryConfig()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    def to_yaml(self) -> str:
        """Convert configuration to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False)

    def to_json(self) -> str:
        """Convert configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRunnerConfig":
        """Create configuration from dictionary with robust field filtering."""
        import inspect

        def _filter_kwargs(target_cls, d: Dict[str, Any]) -> Dict[str, Any]:
            if not d or not isinstance(d, dict):
                return {}
            sig = inspect.signature(target_cls)
            return {k: v for k, v in d.items() if k in sig.parameters}

        # Extract nested configurations
        llm_config = None
        if data.get("llm_config"):
            llm_config = LLMConfig(**_filter_kwargs(LLMConfig, data["llm_config"]))

        memory_config = None
        if data.get("memory_config"):
            memory_config = MemoryConfig(
                **_filter_kwargs(MemoryConfig, data["memory_config"])
            )

        agent_config = None
        if data.get("agent_config"):
            # Special case for DIY bots that might put extra fields in agent_config
            agent_config_data = data["agent_config"]
            if isinstance(agent_config_data, dict):
                agent_config = AgentConfig(
                    **_filter_kwargs(AgentConfig, agent_config_data)
                )

        crew_config = None
        if data.get("crew_config"):
            crew_config = CrewConfig(**_filter_kwargs(CrewConfig, data["crew_config"]))

        # Create main config
        main_kwargs = _filter_kwargs(cls, data)
        main_kwargs["llm_config"] = llm_config
        main_kwargs["memory_config"] = memory_config
        main_kwargs["agent_config"] = agent_config
        main_kwargs["crew_config"] = crew_config

        return cls(**main_kwargs)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "AgentRunnerConfig":
        """Create configuration from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_str: str) -> "AgentRunnerConfig":
        """Create configuration from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def validate_config(
    config: Union[Dict[str, Any], AgentRunnerConfig]
) -> AgentRunnerConfig:
    """
    Validate and normalize configuration.

    Args:
        config: Configuration as dictionary or AgentRunnerConfig

    Returns:
        Validated AgentRunnerConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    if isinstance(config, dict):
        return AgentRunnerConfig.from_dict(config)
    elif isinstance(config, AgentRunnerConfig):
        return config
    else:
        raise ValueError(f"Invalid config type: {type(config)}")


def load_config_from_file(file_path: Union[str, Path]) -> AgentRunnerConfig:
    """
    Load configuration from YAML or JSON file.

    Args:
        file_path: Path to configuration file

    Returns:
        Loaded AgentRunnerConfig instance

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path) as f:
        content = f.read()

    if file_path.suffix.lower() in [".yaml", ".yml"]:
        return AgentRunnerConfig.from_yaml(content)
    elif file_path.suffix.lower() == ".json":
        return AgentRunnerConfig.from_json(content)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def create_default_config(framework: str, agent_id: str) -> AgentRunnerConfig:
    """
    Create a default configuration for a framework.

    Args:
        framework: Framework name
        agent_id: Agent identifier

    Returns:
        Default configuration for the framework
    """
    return AgentRunnerConfig(agent_id=agent_id, framework=framework)


def merge_configs(
    base_config: AgentRunnerConfig, override_config: Dict[str, Any]
) -> AgentRunnerConfig:
    """
    Merge a base configuration with override values.

    Args:
        base_config: Base configuration
        override_config: Values to override

    Returns:
        Merged configuration
    """
    base_dict = base_config.to_dict()

    # Deep merge dictionaries
    def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged_dict = deep_merge(base_dict, override_config)
    return AgentRunnerConfig.from_dict(merged_dict)


class ConfigBuilder:
    """Builder pattern for creating agent configurations."""

    def __init__(self, agent_id: str, framework: str):
        self.config = create_default_config(framework, agent_id)

    def with_llm(
        self,
        provider: str,
        model: str,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
    ) -> "ConfigBuilder":
        """Configure LLM settings."""
        self.config.llm_config = LLMConfig(
            provider=provider, model=model, temperature=temperature, api_key=api_key
        )
        return self

    def with_memory(self, memory_type: str, window_size: int = 10) -> "ConfigBuilder":
        """Configure memory settings."""
        self.config.memory_config = MemoryConfig(
            type=memory_type, window_size=window_size
        )
        return self

    def with_agent_settings(
        self,
        strategy: str,
        price_sensitivity: float = 0.1,
        target_asin: str = "B0DEFAULT",
    ) -> "ConfigBuilder":
        """Configure agent behavior settings."""
        if self.config.agent_config is None:
            self.config.agent_config = AgentConfig()

        self.config.agent_config.strategy = strategy
        self.config.agent_config.price_sensitivity = price_sensitivity
        self.config.agent_config.target_asin = target_asin
        return self

    def with_crew_settings(
        self, process: str = "sequential", crew_size: int = 4
    ) -> "ConfigBuilder":
        """Configure CrewAI settings."""
        if self.config.crew_config is None:
            self.config.crew_config = CrewConfig()

        self.config.crew_config.process = process
        self.config.crew_config.crew_size = crew_size
        return self

    def with_custom_config(self, **kwargs) -> "ConfigBuilder":
        """Add custom configuration options."""
        self.config.custom_config.update(kwargs)
        return self

    def build(self) -> AgentRunnerConfig:
        """Build the final configuration."""
        return validate_config(self.config)


def create_config_builder(agent_id: str, framework: str) -> ConfigBuilder:
    """Convenience function to create a configuration builder."""
    return ConfigBuilder(agent_id, framework)
