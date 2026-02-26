"""
Reproducibility Configuration System for FBA-Bench

Centralized configuration management for all reproducibility features,
providing a unified interface for controlling deterministic behavior.
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from reproducibility.simulation_modes import SimulationMode

logger = logging.getLogger(__name__)


class CacheCompressionLevel(Enum):
    """Cache compression levels."""

    NONE = "none"
    FAST = "fast"
    BALANCED = "balanced"
    MAX = "max"


class ValidationLevel(Enum):
    """Validation strictness levels."""

    DISABLED = "disabled"
    BASIC = "basic"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class LLMCacheConfig:
    """Configuration for LLM response caching."""

    enabled: bool = True
    cache_file: str = "llm_responses.cache"
    enable_validation: bool = True
    enable_compression: bool = True
    compression_level: CacheCompressionLevel = CacheCompressionLevel.BALANCED
    max_memory_entries: int = 10000
    cache_dir: Optional[str] = None
    allow_cache_misses: bool = False
    auto_export_interval_hours: int = 24

    def validate(self) -> List[str]:
        """Validate LLM cache configuration."""
        issues = []

        if self.max_memory_entries < 100:
            issues.append(
                "max_memory_entries should be at least 100 for reasonable performance"
            )

        if self.auto_export_interval_hours < 1:
            issues.append("auto_export_interval_hours should be at least 1")

        return issues


@dataclass
class SeedManagementConfig:
    """Configuration for seed management."""

    enabled: bool = True
    master_seed: Optional[int] = None
    component_isolation: bool = True
    thread_safety: bool = True
    audit_enabled: bool = True
    audit_trail_size: int = 10000
    export_audit_trail: bool = False
    audit_export_file: Optional[str] = None
    validate_determinism: bool = True
    strict_validation: bool = False

    def validate(self) -> List[str]:
        """Validate seed management configuration."""
        issues = []

        if self.enabled and self.master_seed is None:
            issues.append("master_seed must be set when seed management is enabled")

        if self.master_seed is not None and (
            self.master_seed < 0 or self.master_seed > 2**32 - 1
        ):
            issues.append("master_seed must be between 0 and 2^32 - 1")

        if self.audit_trail_size < 1000:
            issues.append(
                "audit_trail_size should be at least 1000 for meaningful tracking"
            )

        return issues


@dataclass
class GoldenMasterConfig:
    """Configuration for golden master testing."""

    enabled: bool = True
    storage_dir: str = "golden_masters"
    enable_compression: bool = True
    enable_validation: bool = True
    numeric_tolerance: float = 1e-10
    event_tolerance: int = 0
    timestamp_tolerance_ms: float = 1.0
    floating_point_epsilon: float = 1e-12
    ignore_fields: List[str] = field(
        default_factory=lambda: ["timestamp", "last_update"]
    )
    ignore_patterns: List[str] = field(default_factory=lambda: ["_metadata", "_debug"])
    auto_baseline_recording: bool = False
    baseline_retention_days: int = 30

    def validate(self) -> List[str]:
        """Validate golden master configuration."""
        issues = []

        if self.numeric_tolerance < 0:
            issues.append("numeric_tolerance must be non-negative")

        if self.event_tolerance < 0:
            issues.append("event_tolerance must be non-negative")

        if self.timestamp_tolerance_ms < 0:
            issues.append("timestamp_tolerance_ms must be non-negative")

        if self.baseline_retention_days < 1:
            issues.append("baseline_retention_days should be at least 1")

        return issues


@dataclass
class EventSnapshotConfig:
    """Configuration for event snapshot recording."""

    enabled: bool = True
    enable_validation: bool = True
    enable_compression: bool = True
    auto_snapshot_interval: Optional[int] = None  # ticks
    snapshot_on_error: bool = True
    max_snapshot_size_mb: int = 100
    retention_count: int = 10
    export_format: str = "parquet"  # parquet, json, csv
    include_metadata: bool = True

    def validate(self) -> List[str]:
        """Validate event snapshot configuration."""
        issues = []

        if self.max_snapshot_size_mb < 1:
            issues.append("max_snapshot_size_mb should be at least 1")

        if self.retention_count < 1:
            issues.append("retention_count should be at least 1")

        if self.export_format not in ["parquet", "json", "csv"]:
            issues.append("export_format must be one of: parquet, json, csv")

        return issues


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring."""

    monitor_determinism_overhead: bool = True
    profile_cache_performance: bool = True
    profile_seed_operations: bool = True
    profile_validation_time: bool = True
    max_profile_data_points: int = 10000
    performance_alert_threshold_ms: float = 1000.0
    enable_performance_logging: bool = False

    def validate(self) -> List[str]:
        """Validate performance configuration."""
        issues = []

        if self.max_profile_data_points < 100:
            issues.append("max_profile_data_points should be at least 100")

        if self.performance_alert_threshold_ms < 0:
            issues.append("performance_alert_threshold_ms must be non-negative")

        return issues


@dataclass
class ReproducibilityConfig:
    """
    Master configuration for all reproducibility features in FBA-Bench.

    This serves as the central configuration point for coordinating
    deterministic behavior across all system components.
    """

    # Core settings
    simulation_mode: SimulationMode = SimulationMode.DETERMINISTIC
    validation_level: ValidationLevel = ValidationLevel.STRICT
    debug_mode: bool = False

    # Component configurations
    llm_cache: LLMCacheConfig = field(default_factory=LLMCacheConfig)
    seed_management: SeedManagementConfig = field(default_factory=SeedManagementConfig)
    golden_master: GoldenMasterConfig = field(default_factory=GoldenMasterConfig)
    event_snapshot: EventSnapshotConfig = field(default_factory=EventSnapshotConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    # Global settings
    output_dir: str = "reproducibility_output"
    log_level: str = "INFO"
    enable_detailed_logging: bool = False
    fail_fast_on_validation_error: bool = True

    # Research mode specific
    research_mode_config: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: str = "1.0"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.now(timezone.utc).isoformat()
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now

    def validate(self) -> List[str]:
        """
        Validate the entire configuration for consistency and correctness.

        Returns:
            List of validation issues found
        """
        issues = []

        # Validate component configurations
        issues.extend([f"LLM Cache: {issue}" for issue in self.llm_cache.validate()])
        issues.extend(
            [f"Seed Management: {issue}" for issue in self.seed_management.validate()]
        )
        issues.extend(
            [f"Golden Master: {issue}" for issue in self.golden_master.validate()]
        )
        issues.extend(
            [f"Event Snapshot: {issue}" for issue in self.event_snapshot.validate()]
        )
        issues.extend(
            [f"Performance: {issue}" for issue in self.performance.validate()]
        )

        # Cross-component validation
        if self.simulation_mode == SimulationMode.DETERMINISTIC:
            if not self.llm_cache.enabled:
                issues.append("Deterministic mode requires LLM cache to be enabled")
            if not self.seed_management.enabled:
                issues.append(
                    "Deterministic mode requires seed management to be enabled"
                )
            if self.llm_cache.allow_cache_misses:
                issues.append("Deterministic mode should not allow cache misses")

        # Validation level consistency
        if self.validation_level == ValidationLevel.DISABLED:
            if self.fail_fast_on_validation_error:
                issues.append(
                    "Cannot fail fast on validation errors when validation is disabled"
                )

        # Directory validation
        if not self.output_dir:
            issues.append("output_dir cannot be empty")

        # Log level validation
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            issues.append(f"log_level must be one of: {valid_log_levels}")

        return issues

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""

        def convert_value(value):
            # Handle dataclasses strictly
            if is_dataclass(value):
                result = asdict(value)  # type: ignore[arg-type]
                # Convert enums to their values
                for k, v in list(result.items()):
                    if isinstance(v, Enum):
                        result[k] = v.value
                    elif is_dataclass(v):
                        result[k] = convert_value(v)
                return result
            elif isinstance(value, Enum):
                return value.value
            elif isinstance(value, list):
                return [convert_value(item) for item in value]
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            else:
                return value

        return convert_value(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReproducibilityConfig":
        """Create configuration from dictionary."""
        # Convert enum strings back to enums
        if "simulation_mode" in data and isinstance(data["simulation_mode"], str):
            data["simulation_mode"] = SimulationMode(data["simulation_mode"])

        if "validation_level" in data and isinstance(data["validation_level"], str):
            data["validation_level"] = ValidationLevel(data["validation_level"])

        # Handle nested configurations
        nested_configs = {
            "llm_cache": LLMCacheConfig,
            "seed_management": SeedManagementConfig,
            "golden_master": GoldenMasterConfig,
            "event_snapshot": EventSnapshotConfig,
            "performance": PerformanceConfig,
        }

        for key, config_class in nested_configs.items():
            if key in data and isinstance(data[key], dict):
                # Convert enum strings in nested configs
                nested_data = data[key].copy()

                if key == "llm_cache" and "compression_level" in nested_data:
                    if isinstance(nested_data["compression_level"], str):
                        nested_data["compression_level"] = CacheCompressionLevel(
                            nested_data["compression_level"]
                        )

                data[key] = config_class(**nested_data)

        return cls(**data)

    def save_to_file(self, filepath: Union[str, Path]) -> bool:
        """
        Save configuration to file.

        Args:
            filepath: Path to save configuration file

        Returns:
            True if successful, False otherwise
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            config_dict = self.to_dict()

            # Determine format from extension
            if filepath.suffix.lower() == ".json":
                with open(filepath, "w") as f:
                    json.dump(config_dict, f, indent=2, separators=(",", ": "))
            elif filepath.suffix.lower() in [".yaml", ".yml"]:
                with open(filepath, "w") as f:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            else:
                # Default to JSON
                with open(filepath.with_suffix(".json"), "w") as f:
                    json.dump(config_dict, f, indent=2, separators=(",", ": "))

            logger.info(f"Configuration saved to: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration to {filepath}: {e}")
            return False

    @classmethod
    def load_from_file(
        cls, filepath: Union[str, Path]
    ) -> Optional["ReproducibilityConfig"]:
        """
        Load configuration from file.

        Args:
            filepath: Path to configuration file

        Returns:
            Loaded configuration or None if failed
        """
        try:
            filepath = Path(filepath)

            if not filepath.exists():
                logger.error(f"Configuration file not found: {filepath}")
                return None

            # Determine format from extension
            if filepath.suffix.lower() == ".json":
                with open(filepath) as f:
                    data = json.load(f)
            elif filepath.suffix.lower() in [".yaml", ".yml"]:
                with open(filepath) as f:
                    data = yaml.safe_load(f)
            else:
                logger.error(
                    f"Unsupported configuration file format: {filepath.suffix}"
                )
                return None

            config = cls.from_dict(data)
            logger.info(f"Configuration loaded from: {filepath}")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration from {filepath}: {e}")
            return None

    def create_directories(self) -> bool:
        """
        Create all necessary directories for reproducibility operations.

        Returns:
            True if successful, False otherwise
        """
        try:
            directories = [
                self.output_dir,
                self.golden_master.storage_dir,
            ]

            # Add LLM cache directory if specified
            if self.llm_cache.cache_dir:
                directories.append(self.llm_cache.cache_dir)

            for directory in directories:
                Path(directory).mkdir(parents=True, exist_ok=True)

            logger.info("All reproducibility directories created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create directories: {e}")
            return False

    def apply_logging_config(self):
        """Apply logging configuration."""
        try:
            # Set log level
            numeric_level = getattr(logging, self.log_level.upper(), logging.INFO)
            logger.setLevel(numeric_level)

            # Configure detailed logging if enabled
            if self.enable_detailed_logging:
                # Add file handler for detailed logs
                log_file = Path(self.output_dir) / "reproducibility.log"
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(logging.DEBUG)

                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                file_handler.setFormatter(formatter)

                # Add to all reproducibility loggers
                for logger_name in [
                    "reproducibility.sim_seed",
                    "reproducibility.llm_cache",
                    "reproducibility.golden_master",
                    "reproducibility.simulation_modes",
                    "llm_interface.deterministic_client",
                ]:
                    specific_logger = logging.getLogger(logger_name)
                    specific_logger.addHandler(file_handler)

            logger.info(
                f"Logging configured: level={self.log_level}, detailed={self.enable_detailed_logging}"
            )

        except Exception as e:
            logger.error(f"Failed to apply logging configuration: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the configuration."""
        validation_issues = self.validate()

        return {
            "simulation_mode": self.simulation_mode.value,
            "validation_level": self.validation_level.value,
            "is_valid": len(validation_issues) == 0,
            "validation_issues_count": len(validation_issues),
            "components_enabled": {
                "llm_cache": self.llm_cache.enabled,
                "seed_management": self.seed_management.enabled,
                "golden_master": self.golden_master.enabled,
                "event_snapshot": self.event_snapshot.enabled,
                "performance_monitoring": self.performance.monitor_determinism_overhead,
            },
            "debug_mode": self.debug_mode,
            "fail_fast": self.fail_fast_on_validation_error,
            "version": self.version,
            "updated_at": self.updated_at,
        }


# Predefined configurations for common use cases


def create_deterministic_config(
    master_seed: int = 42, cache_file: str = "llm_responses.cache"
) -> ReproducibilityConfig:
    """
    Create configuration optimized for deterministic reproducibility.

    Args:
        master_seed: Master seed for deterministic behavior
        cache_file: LLM cache file path

    Returns:
        Configured ReproducibilityConfig
    """
    return ReproducibilityConfig(
        simulation_mode=SimulationMode.DETERMINISTIC,
        validation_level=ValidationLevel.STRICT,
        llm_cache=LLMCacheConfig(
            enabled=True,
            cache_file=cache_file,
            enable_validation=True,
            allow_cache_misses=False,
        ),
        seed_management=SeedManagementConfig(
            enabled=True,
            master_seed=master_seed,
            component_isolation=True,
            audit_enabled=True,
            strict_validation=True,
        ),
        golden_master=GoldenMasterConfig(
            enabled=True, enable_validation=True, numeric_tolerance=1e-12
        ),
        fail_fast_on_validation_error=True,
    )


def create_research_config(
    master_seed: int = 42, variability_probability: float = 0.1
) -> ReproducibilityConfig:
    """
    Create configuration for research mode with controlled variability.

    Args:
        master_seed: Master seed for controlled randomness
        variability_probability: Probability of injecting variability

    Returns:
        Configured ReproducibilityConfig
    """
    return ReproducibilityConfig(
        simulation_mode=SimulationMode.RESEARCH,
        validation_level=ValidationLevel.BASIC,
        llm_cache=LLMCacheConfig(enabled=True, allow_cache_misses=True),
        seed_management=SeedManagementConfig(
            enabled=True,
            master_seed=master_seed,
            component_isolation=True,
            strict_validation=False,
        ),
        research_mode_config={
            "controlled_randomness_probability": variability_probability,
            "variability_injection_points": ["market_events", "customer_behavior"],
        },
        fail_fast_on_validation_error=False,
    )


def create_performance_config() -> ReproducibilityConfig:
    """
    Create configuration optimized for performance monitoring.

    Returns:
        Configured ReproducibilityConfig
    """
    return ReproducibilityConfig(
        simulation_mode=SimulationMode.DETERMINISTIC,
        validation_level=ValidationLevel.BASIC,
        performance=PerformanceConfig(
            monitor_determinism_overhead=True,
            profile_cache_performance=True,
            profile_seed_operations=True,
            enable_performance_logging=True,
        ),
        enable_detailed_logging=True,
    )


def get_default_config() -> ReproducibilityConfig:
    """Get default reproducibility configuration."""
    return create_deterministic_config()


# Global configuration management
_global_config: Optional[ReproducibilityConfig] = None
_config_lock = threading.RLock()


def set_global_config(config: ReproducibilityConfig):
    """Set the global reproducibility configuration."""
    global _global_config

    with _config_lock:
        _global_config = config
        config.apply_logging_config()
        config.create_directories()

        logger.info(
            f"Global reproducibility configuration set: {config.simulation_mode.value} mode"
        )


def get_global_config() -> ReproducibilityConfig:
    """Get the global reproducibility configuration."""
    global _global_config

    with _config_lock:
        if _global_config is None:
            _global_config = get_default_config()
            _global_config.apply_logging_config()
            _global_config.create_directories()

        return _global_config


def load_config_from_env() -> ReproducibilityConfig:
    """
    Load configuration from environment variables and files.

    Returns:
        Loaded configuration
    """
    # Check for config file in environment
    config_file = os.getenv("REPRODUCIBILITY_CONFIG_FILE")
    if config_file and Path(config_file).exists():
        config = ReproducibilityConfig.load_from_file(config_file)
        if config:
            return config

    # Check for common config file locations
    for config_path in [
        "reproducibility_config.yaml",
        "reproducibility_config.json",
        "config/reproducibility.yaml",
        "config/reproducibility.json",
    ]:
        if Path(config_path).exists():
            config = ReproducibilityConfig.load_from_file(config_path)
            if config:
                return config

    # Override defaults with environment variables
    config = get_default_config()

    # Override from environment
    if os.getenv("SIMULATION_MODE"):
        try:
            config.simulation_mode = SimulationMode(os.getenv("SIMULATION_MODE"))
        except ValueError:
            logger.warning(f"Invalid SIMULATION_MODE: {os.getenv('SIMULATION_MODE')}")

    if os.getenv("MASTER_SEED"):
        try:
            config.seed_management.master_seed = int(os.getenv("MASTER_SEED"))  # type: ignore[arg-type]
        except ValueError:
            logger.warning(f"Invalid MASTER_SEED: {os.getenv('MASTER_SEED')}")

    if os.getenv("LLM_CACHE_FILE"):
        config.llm_cache.cache_file = os.getenv("LLM_CACHE_FILE")  # type: ignore[assignment]

    return config
