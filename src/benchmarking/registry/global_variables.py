"""
Global Registry Variables for FBA-Bench.

This module provides a centralized way to define and access global variables
and constants used throughout the FBA-Bench system.
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EnvironmentType(str, Enum):
    """Environment types for the application."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log levels for the application."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class SystemPaths:
    """System paths configuration."""

    # Base paths
    project_root: Path = field(default_factory=lambda: Path.cwd())
    config_dir: Path = field(default_factory=lambda: Path.cwd() / "config")
    data_dir: Path = field(default_factory=lambda: Path.cwd() / "data")
    logs_dir: Path = field(default_factory=lambda: Path.cwd() / "logs")
    temp_dir: Path = field(default_factory=lambda: Path.cwd() / "temp")

    # Subdirectories
    scenarios_dir: Path = field(default_factory=lambda: Path.cwd() / "scenarios")
    agents_dir: Path = field(default_factory=lambda: Path.cwd() / "agents")
    metrics_dir: Path = field(default_factory=lambda: Path.cwd() / "metrics")
    results_dir: Path = field(default_factory=lambda: Path.cwd() / "results")

    def __post_init__(self):
        """Ensure all paths are created."""
        for path_attr in [
            "config_dir",
            "data_dir",
            "logs_dir",
            "temp_dir",
            "scenarios_dir",
            "agents_dir",
            "metrics_dir",
            "results_dir",
        ]:
            path = getattr(self, path_attr)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)


@dataclass
class SystemConfig:
    """System configuration variables."""

    # Environment
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT
    debug: bool = False
    testing: bool = False

    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None

    # Performance
    max_workers: int = 4
    timeout_seconds: int = 300
    memory_limit_mb: int = 1024

    # Security
    enable_auth: bool = False
    api_key: Optional[str] = None

    # Features
    enable_metrics: bool = True
    enable_monitoring: bool = True
    enable_caching: bool = True
    enable_profiling: bool = False

    # External services
    external_api_timeout: int = 30
    external_api_retries: int = 3

    def __post_init__(self):
        """Validate and adjust configuration based on environment."""
        # Override values based on environment variables
        self.environment = EnvironmentType(os.getenv("FBA_ENV", self.environment.value))
        self.debug = os.getenv("FBA_DEBUG", str(self.debug)).lower() == "true"
        self.testing = os.getenv("FBA_TESTING", str(self.testing)).lower() == "true"

        # Set log level based on environment
        if self.environment == EnvironmentType.PRODUCTION:
            self.log_level = LogLevel.WARNING
        elif self.environment == EnvironmentType.DEVELOPMENT:
            self.log_level = LogLevel.DEBUG

        # Adjust performance settings based on environment
        if self.environment == EnvironmentType.PRODUCTION:
            self.max_workers = min(self.max_workers, 8)
            self.memory_limit_mb = min(self.memory_limit_mb, 2048)
        elif self.environment == EnvironmentType.DEVELOPMENT:
            self.max_workers = min(self.max_workers, 2)
            self.memory_limit_mb = min(self.memory_limit_mb, 512)


@dataclass
class BenchmarkDefaults:
    """Default values for benchmark configurations."""

    # Default scenario settings
    default_scenario_duration: int = 100
    default_scenario_ticks_per_second: int = 1
    default_max_agents: int = 10

    # Default agent settings
    default_agent_timeout: int = 30
    default_agent_retries: int = 3
    default_agent_memory_size: int = 100

    # Default metrics settings
    default_metrics_interval: int = 10
    default_metrics_history_size: int = 1000

    # Default execution settings
    default_parallel_execution: bool = True
    default_save_results: bool = True
    default_save_intermediate: bool = False

    # Default output settings
    default_output_format: str = "json"
    default_output_precision: int = 2


@dataclass
class APISettings:
    """API configuration settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # API settings
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    cors_methods: List[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"]
    )
    cors_headers: List[str] = field(default_factory=lambda: ["*"])

    # Rate limiting
    enable_rate_limit: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Authentication
    enable_auth: bool = False
    auth_secret_key: Optional[str] = None
    auth_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 30

    # Documentation
    enable_docs: bool = True
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"


@dataclass
class DatabaseSettings:
    """Database configuration settings."""

    # Database type
    db_type: str = "sqlite"

    # Connection settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "fba_bench"
    db_user: str = "fba_user"
    db_password: Optional[str] = None

    # SQLite specific
    sqlite_path: str = "data/fba_bench.db"

    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    def get_connection_string(self) -> str:
        """Get the database connection string."""
        if self.db_type.lower() == "sqlite":
            return f"sqlite:///{self.sqlite_path}"
        elif self.db_type.lower() == "postgresql":
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        elif self.db_type.lower() == "mysql":
            return f"mysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")


@dataclass
class CacheSettings:
    """Cache configuration settings."""

    # Cache type
    cache_type: str = "memory"

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # Cache settings
    default_ttl: int = 3600  # 1 hour
    max_size: int = 1000
    key_prefix: str = "fba_bench:"

    # Cache invalidation
    enable_auto_invalidation: bool = True
    invalidation_check_interval: int = 60  # seconds


@dataclass
class MonitoringSettings:
    """Monitoring and metrics configuration settings."""

    # Metrics collection
    enable_metrics: bool = True
    metrics_interval: int = 10  # seconds
    metrics_retention_days: int = 30

    # Health checks
    enable_health_checks: bool = True
    health_check_interval: int = 30  # seconds

    # Performance monitoring
    enable_performance_monitoring: bool = True
    profiling_enabled: bool = False
    profiling_sample_rate: float = 0.1  # 10% of requests

    # Alerting
    enable_alerting: bool = False
    alert_webhook_url: Optional[str] = None
    alert_email_recipients: List[str] = field(default_factory=list)

    # Export settings
    metrics_export_format: str = "json"
    metrics_export_interval: int = 60  # seconds
    metrics_export_path: str = "data/metrics"


class GlobalVariables:
    """
    Global variables and constants for FBA-Bench.

    This class provides a centralized way to access global variables
    and configuration settings throughout the application.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(GlobalVariables, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize global variables."""
        if getattr(self, "_initialized", False):
            return

        # Initialize configuration objects
        self.paths = SystemPaths()
        self.system = SystemConfig()
        self.benchmark_defaults = BenchmarkDefaults()
        self.api = APISettings()
        self.database = DatabaseSettings()
        self.cache = CacheSettings()
        self.monitoring = MonitoringSettings()

        # Application metadata
        self.app_name = "FBA-Bench"
        self.app_version = "1.0.0"
        self.app_description = "Functional Benchmarking Application for AI Agents"

        # Runtime state
        self.start_time = None
        self.shutdown_requested = False

        # Feature flags
        self.feature_flags = {
            "enable_experimental_features": False,
            "enable_beta_agents": False,
            "enable_advanced_metrics": False,
            "enable_real_time_monitoring": False,
        }

        self._initialized = True
        logger.info("GlobalVariables initialized")

    def initialize_from_environment(self) -> None:
        """Initialize variables from environment variables."""
        # System configuration
        self.system.environment = EnvironmentType(
            os.getenv("FBA_ENV", self.system.environment.value)
        )
        self.system.debug = (
            os.getenv("FBA_DEBUG", str(self.system.debug)).lower() == "true"
        )
        self.system.testing = (
            os.getenv("FBA_TESTING", str(self.system.testing)).lower() == "true"
        )
        self.system.log_level = LogLevel(
            os.getenv("FBA_LOG_LEVEL", self.system.log_level.value)
        )

        # API settings
        self.api.host = os.getenv("FBA_API_HOST", self.api.host)
        self.api.port = int(os.getenv("FBA_API_PORT", self.api.port))
        self.api.workers = int(os.getenv("FBA_API_WORKERS", self.api.workers))

        # Database settings
        self.database.db_type = os.getenv("FBA_DB_TYPE", self.database.db_type)
        self.database.db_host = os.getenv("FBA_DB_HOST", self.database.db_host)
        self.database.db_port = int(os.getenv("FBA_DB_PORT", self.database.db_port))
        self.database.db_name = os.getenv("FBA_DB_NAME", self.database.db_name)
        self.database.db_user = os.getenv("FBA_DB_USER", self.database.db_user)
        self.database.db_password = os.getenv(
            "FBA_DB_PASSWORD", self.database.db_password
        )

        # Redis settings
        self.cache.redis_host = os.getenv("FBA_REDIS_HOST", self.cache.redis_host)
        self.cache.redis_port = int(os.getenv("FBA_REDIS_PORT", self.cache.redis_port))
        self.cache.redis_db = int(os.getenv("FBA_REDIS_DB", self.cache.redis_db))
        self.cache.redis_password = os.getenv(
            "FBA_REDIS_PASSWORD", self.cache.redis_password
        )

        # Feature flags
        self.feature_flags["enable_experimental_features"] = (
            os.getenv("FBA_ENABLE_EXPERIMENTAL", "false").lower() == "true"
        )
        self.feature_flags["enable_beta_agents"] = (
            os.getenv("FBA_ENABLE_BETA_AGENTS", "false").lower() == "true"
        )
        self.feature_flags["enable_advanced_metrics"] = (
            os.getenv("FBA_ENABLE_ADVANCED_METRICS", "false").lower() == "true"
        )
        self.feature_flags["enable_real_time_monitoring"] = (
            os.getenv("FBA_ENABLE_REAL_TIME_MONITORING", "false").lower() == "true"
        )

        logger.info("GlobalVariables initialized from environment")

    def get_config_dict(self) -> Dict[str, Any]:
        """
        Get a dictionary representation of all configuration.

        Returns:
            Dictionary containing all configuration values
        """
        return {
            "paths": {
                "project_root": str(self.paths.project_root),
                "config_dir": str(self.paths.config_dir),
                "data_dir": str(self.paths.data_dir),
                "logs_dir": str(self.paths.logs_dir),
                "temp_dir": str(self.paths.temp_dir),
                "scenarios_dir": str(self.paths.scenarios_dir),
                "agents_dir": str(self.paths.agents_dir),
                "metrics_dir": str(self.paths.metrics_dir),
                "results_dir": str(self.paths.results_dir),
            },
            "system": {
                "environment": self.system.environment.value,
                "debug": self.system.debug,
                "testing": self.system.testing,
                "log_level": self.system.log_level.value,
                "log_format": self.system.log_format,
                "log_file": self.system.log_file,
                "max_workers": self.system.max_workers,
                "timeout_seconds": self.system.timeout_seconds,
                "memory_limit_mb": self.system.memory_limit_mb,
                "enable_auth": self.system.enable_auth,
                "api_key": "***" if self.system.api_key else None,
                "enable_metrics": self.system.enable_metrics,
                "enable_monitoring": self.system.enable_monitoring,
                "enable_caching": self.system.enable_caching,
                "enable_profiling": self.system.enable_profiling,
                "external_api_timeout": self.system.external_api_timeout,
                "external_api_retries": self.system.external_api_retries,
            },
            "benchmark_defaults": {
                "default_scenario_duration": self.benchmark_defaults.default_scenario_duration,
                "default_scenario_ticks_per_second": self.benchmark_defaults.default_scenario_ticks_per_second,
                "default_max_agents": self.benchmark_defaults.default_max_agents,
                "default_agent_timeout": self.benchmark_defaults.default_agent_timeout,
                "default_agent_retries": self.benchmark_defaults.default_agent_retries,
                "default_agent_memory_size": self.benchmark_defaults.default_agent_memory_size,
                "default_metrics_interval": self.benchmark_defaults.default_metrics_interval,
                "default_metrics_history_size": self.benchmark_defaults.default_metrics_history_size,
                "default_parallel_execution": self.benchmark_defaults.default_parallel_execution,
                "default_save_results": self.benchmark_defaults.default_save_results,
                "default_save_intermediate": self.benchmark_defaults.default_save_intermediate,
                "default_output_format": self.benchmark_defaults.default_output_format,
                "default_output_precision": self.benchmark_defaults.default_output_precision,
            },
            "api": {
                "host": self.api.host,
                "port": self.api.port,
                "workers": self.api.workers,
                "api_prefix": self.api.api_prefix,
                "cors_origins": self.api.cors_origins,
                "cors_methods": self.api.cors_methods,
                "cors_headers": self.api.cors_headers,
                "enable_rate_limit": self.api.enable_rate_limit,
                "rate_limit_requests": self.api.rate_limit_requests,
                "rate_limit_window": self.api.rate_limit_window,
                "enable_auth": self.api.enable_auth,
                "auth_algorithm": self.api.auth_algorithm,
                "auth_access_token_expire_minutes": self.api.auth_access_token_expire_minutes,
                "enable_docs": self.api.enable_docs,
                "docs_url": self.api.docs_url,
                "redoc_url": self.api.redoc_url,
            },
            "database": {
                "db_type": self.database.db_type,
                "db_host": self.database.db_host,
                "db_port": self.database.db_port,
                "db_name": self.database.db_name,
                "db_user": self.database.db_user,
                "db_password": "***" if self.database.db_password else None,
                "sqlite_path": self.database.sqlite_path,
                "pool_size": self.database.pool_size,
                "max_overflow": self.database.max_overflow,
                "pool_timeout": self.database.pool_timeout,
                "pool_recycle": self.database.pool_recycle,
            },
            "cache": {
                "cache_type": self.cache.cache_type,
                "redis_host": self.cache.redis_host,
                "redis_port": self.cache.redis_port,
                "redis_db": self.cache.redis_db,
                "redis_password": "***" if self.cache.redis_password else None,
                "default_ttl": self.cache.default_ttl,
                "max_size": self.cache.max_size,
                "key_prefix": self.cache.key_prefix,
                "enable_auto_invalidation": self.cache.enable_auto_invalidation,
                "invalidation_check_interval": self.cache.invalidation_check_interval,
            },
            "monitoring": {
                "enable_metrics": self.monitoring.enable_metrics,
                "metrics_interval": self.monitoring.metrics_interval,
                "metrics_retention_days": self.monitoring.metrics_retention_days,
                "enable_health_checks": self.monitoring.enable_health_checks,
                "health_check_interval": self.monitoring.health_check_interval,
                "enable_performance_monitoring": self.monitoring.enable_performance_monitoring,
                "profiling_enabled": self.monitoring.profiling_enabled,
                "profiling_sample_rate": self.monitoring.profiling_sample_rate,
                "enable_alerting": self.monitoring.enable_alerting,
                "alert_webhook_url": self.monitoring.alert_webhook_url,
                "alert_email_recipients": self.monitoring.alert_email_recipients,
                "metrics_export_format": self.monitoring.metrics_export_format,
                "metrics_export_interval": self.monitoring.metrics_export_interval,
                "metrics_export_path": self.monitoring.metrics_export_path,
            },
            "app_metadata": {
                "app_name": self.app_name,
                "app_version": self.app_version,
                "app_description": self.app_description,
            },
            "feature_flags": self.feature_flags.copy(),
        }

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.system.environment == EnvironmentType.DEVELOPMENT

    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.system.environment == EnvironmentType.TESTING or self.system.testing

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.system.environment == EnvironmentType.PRODUCTION

    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature_name: Name of the feature

        Returns:
            True if the feature is enabled
        """
        return self.feature_flags.get(feature_name, False)

    def enable_feature(self, feature_name: str) -> None:
        """
        Enable a feature.

        Args:
            feature_name: Name of the feature to enable
        """
        self.feature_flags[feature_name] = True
        logger.info(f"Enabled feature: {feature_name}")

    def disable_feature(self, feature_name: str) -> None:
        """
        Disable a feature.

        Args:
            feature_name: Name of the feature to disable
        """
        self.feature_flags[feature_name] = False
        logger.info(f"Disabled feature: {feature_name}")

    def request_shutdown(self) -> None:
        """Request application shutdown."""
        self.shutdown_requested = True
        logger.info("Shutdown requested")

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_requested


# Global instance of the variables
global_variables = GlobalVariables()
