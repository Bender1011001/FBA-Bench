"""
Unified application settings for FBA-Bench (Phase 2: Structural Unification).

- Single source of truth for configuration under src/fba_bench_core/settings.py
- Pydantic v2 + pydantic-settings for robust, typed settings
- Precedence: Environment > YAML file (init) > defaults
  (achieved via settings_customise_sources so env overrides YAML)
- YAML path is provided via env var FBA_CONFIG (optional)

Usage:
    from fba_bench_core.settings import get_settings
    settings = get_settings()

    # Access nested sections
    settings.logging.level
    settings.paths.results_dir
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --------------------------
# Section models
# --------------------------


class AppSettings(BaseModel):
    env: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    version: str = "0.0.0"


class LoggingSettings(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"] = "INFO"
    json: bool = False
    destination: Literal["stdout", "stderr", "file"] = "stdout"
    filename: Optional[str] = None
    # Standard logging format; JSON formatting is enabled separately via python-json-logger if available
    format: str = "%(asctime)s %(levelname)s %(name)s - %(message)s"


class LLMSettings(BaseModel):
    provider: Optional[str] = None
    # Common provider keys; can be set via env (e.g., OPENAI_API_KEY) or YAML (llm.openai_api_key)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    rate_limit_rps: Optional[float] = None


class BenchmarkingSettings(BaseModel):
    default_parallelism: int = 1
    timeout_seconds: int = 1800  # 30 minutes default


class PathSettings(BaseModel):
    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    results_dir: Path = Field(default_factory=lambda: Path("results"))
    cache_dir: Path = Field(default_factory=lambda: Path(".cache"))


class FeatureFlags(BaseModel):
    enable_observability: bool = True
    enable_clearml: bool = False


class ClearMLSettings(BaseModel):
    # Cloud/web UI host for ClearML (used when not running local server)
    web_host: str = "https://app.clear.ml"
    # Local UI URL used when bringing up local ClearML via docker-compose
    local_ui: str = "http://localhost:8080"
    # Default ports for local ClearML stack
    web_port: int = 8080
    api_port: int = 8008
    file_port: int = 8081
    # Compose filename used by CLI to start local ClearML
    compose_filename: str = "docker-compose.clearml.yml"
    # Optional repository root hint (env: FBA_BENCH_ROOT) to help locate compose file
    repo_root_hint: Optional[str] = None


# --------------------------
# Root Settings
# --------------------------


class Settings(BaseSettings):
    """
    Root application settings.

    The precedence is customized to ensure:
      environment variables > init settings (YAML) > dotenv > file secrets
    """

    # Pydantic settings configuration (v2)
    model_config = SettingsConfigDict(
        env_prefix="FBA_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Sections
    app: AppSettings = AppSettings()
    logging: LoggingSettings = LoggingSettings()
    llm: LLMSettings = LLMSettings()
    benchmarking: BenchmarkingSettings = BenchmarkingSettings()
    paths: PathSettings = PathSettings()
    features: FeatureFlags = FeatureFlags()
    clearml: ClearMLSettings = ClearMLSettings()

    # Stored for introspection
    config_file: Optional[Path] = None

    # Back-compat root-level aliases for existing callers (e.g., CLI)
    @property
    def clearml_web_host(self) -> str:
        return self.clearml.web_host

    @property
    def clearml_local_ui(self) -> str:
        return self.clearml.local_ui

    @property
    def clearml_web_port(self) -> int:
        return self.clearml.web_port

    @property
    def clearml_api_port(self) -> int:
        return self.clearml.api_port

    @property
    def clearml_file_port(self) -> int:
        return self.clearml.file_port

    @property
    def clearml_compose_filename(self) -> str:
        return self.clearml.compose_filename

    @property
    def repo_root_hint(self) -> Optional[str]:
        return self.clearml.repo_root_hint

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Ensure env overrides YAML/init values
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)

    @model_validator(mode="after")
    def _normalize_paths(self) -> Settings:
        """
        Resolve relative paths against base_dir for consistency.
        """
        base = self.paths.base_dir
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()

        for attr in ("data_dir", "results_dir", "cache_dir"):
            p: Path = getattr(self.paths, attr)
            if not p.is_absolute():
                setattr(self.paths, attr, (base / p).resolve())
        return self


# --------------------------
# YAML loading helpers
# --------------------------


def _load_yaml_config(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        p = Path(path)
        if not p.is_file():
            return {}
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        # Do not raise during configuration bootstrap; prefer safe defaults
        return {}


# --------------------------
# Public accessor
# --------------------------


@lru_cache(maxsize=1)
def get_settings(config_path: Optional[str] = None) -> Settings:
    """
    Load Settings with precedence:
      1) Environment variables (FBA_*)
      2) YAML (if FBA_CONFIG env or config_path provided)
      3) Defaults

    The YAML file is passed as 'init settings' so env can override it.
    """
    # Determine config path: explicit arg has priority over env
    env_cfg = os.getenv("FBA_CONFIG")
    candidate = (
        Path(config_path) if config_path else (Path(env_cfg) if env_cfg else None)
    )

    yaml_data = _load_yaml_config(candidate)
    settings = Settings(**yaml_data, config_file=candidate)
    return settings
