from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # YAML overlay becomes a no-op if PyYAML is missing

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _truthy(v: Optional[str], default: bool = False) -> bool:
    if v is None:
        return default
    s = v.strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _get_env_first(keys: List[str], default: Optional[str] = None) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


class AppSettings(BaseSettings):
    """
    Centralized configuration for FBA-Bench.

    Priority (lowest to highest):
    - Built-in defaults
    - YAML overlay from FBA_CONFIG_PATH (if provided)
    - Environment variables
    """

    # Environment (development|staging|production), best-effort auto-detection
    environment: str = Field(
        default_factory=lambda: _get_env_first(
            ["ENVIRONMENT", "APP_ENV", "ENV"], "development"
        )
        or "development"
    )

    # API
    api_rate_limit: str = Field(default="100/minute", validation_alias="API_RATE_LIMIT")

    # Contact / Messaging (website -> backend)
    contact_to_email: Optional[str] = Field(
        default=None, validation_alias="CONTACT_TO_EMAIL"
    )
    contact_fallback_email: Optional[str] = Field(
        default=None, validation_alias="CONTACT_FALLBACK_EMAIL"
    )

    # Email (SMTP)
    smtp_host: Optional[str] = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_from: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("SMTP_FROM", "EMAIL_FROM")
    )
    smtp_use_tls_raw: Optional[str] = Field(
        default=None, validation_alias="SMTP_USE_TLS"
    )

    # CORS
    cors_allow_origins_raw: Optional[str] = Field(
        default=None, validation_alias="FBA_CORS_ALLOW_ORIGINS"
    )

    # Auth
    auth_enabled_raw: Optional[str] = Field(
        default=None, validation_alias="AUTH_ENABLED"
    )
    auth_test_bypass_raw: Optional[str] = Field(
        default=None, validation_alias="AUTH_TEST_BYPASS"
    )
    auth_protect_docs_raw: Optional[str] = Field(
        default=None, validation_alias="AUTH_PROTECT_DOCS"
    )

    auth_jwt_alg: str = Field(default="RS256", validation_alias="AUTH_JWT_ALG")
    auth_jwt_public_key: Optional[str] = Field(
        default=None, validation_alias="AUTH_JWT_PUBLIC_KEY"
    )
    auth_jwt_issuer: Optional[str] = Field(
        default=None, validation_alias="AUTH_JWT_ISSUER"
    )
    auth_jwt_audience: Optional[str] = Field(
        default=None, validation_alias="AUTH_JWT_AUDIENCE"
    )
    auth_jwt_clock_skew: int = Field(default=60, validation_alias="AUTH_JWT_CLOCK_SKEW")

    # Redis / Database (for future centralization)
    redis_url_fba: Optional[str] = Field(
        default=None, validation_alias="FBA_BENCH_REDIS_URL"
    )
    redis_url_compat: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    db_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    db_url_fba: Optional[str] = Field(default=None, validation_alias="FBA_BENCH_DB_URL")

    # Logging
    logging_level: Optional[str] = Field(default=None, validation_alias="FBA_LOG_LEVEL")
    logging_format: Optional[str] = Field(
        default=None, validation_alias="FBA_LOG_FORMAT"
    )
    logging_file: Optional[str] = Field(default=None, validation_alias="FBA_LOG_FILE")
    logging_include_tracebacks_raw: Optional[str] = Field(
        default=None, validation_alias="FBA_LOG_INCLUDE_TRACEBACKS"
    )

    # ClearML / CLI
    clearml_web_host: str = Field(
        default="https://app.clear.ml", validation_alias="CLEARML_WEB_HOST"
    )
    clearml_local_ui: str = Field(
        default="http://localhost:8080", validation_alias="FBA_BENCH_CLEARML_LOCAL_UI"
    )
    clearml_web_port: int = Field(
        default=8080, validation_alias="FBA_BENCH_CLEARML_WEB_PORT"
    )
    clearml_file_port: int = Field(
        default=8081, validation_alias="FBA_BENCH_CLEARML_FILE_PORT"
    )
    clearml_api_port: int = Field(
        default=8008, validation_alias="FBA_BENCH_CLEARML_API_PORT"
    )
    clearml_compose_filename: str = Field(
        default="docker-compose.clearml.yml",
        validation_alias="FBA_BENCH_CLEARML_COMPOSE",
    )
    repo_root_hint: Optional[str] = Field(
        default=None, validation_alias="FBA_BENCH_ROOT"
    )

    model_config = SettingsConfigDict(extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Inject a YAML overlay source (if FBA_CONFIG_PATH is set) before environment variables,
        so that env vars still override YAML. Preserve .env support (dotenv_settings).
        """

        def yaml_source() -> Dict[str, Any]:
            path = os.getenv("FBA_CONFIG_PATH")
            if not path or not yaml:
                return {}
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except (OSError, yaml.YAMLError):
                return {}
            if not isinstance(data, dict):
                return {}

            # Map supported YAML keys to flat settings fields
            mapped: Dict[str, Any] = {}

            # api.rate_limit -> API_RATE_LIMIT
            api = data.get("api")
            if isinstance(api, dict):
                if isinstance(api.get("rate_limit"), str):
                    mapped["API_RATE_LIMIT"] = api["rate_limit"]

            # cors.allow_origins -> FBA_CORS_ALLOW_ORIGINS (comma-separated)
            cors = data.get("cors")
            if isinstance(cors, dict):
                ao = cors.get("allow_origins")
                if isinstance(ao, list):
                    mapped["FBA_CORS_ALLOW_ORIGINS"] = ",".join(
                        [str(x) for x in ao if str(x).strip()]
                    )

            # auth.*
            auth = data.get("auth")
            if isinstance(auth, dict):
                if "enabled" in auth:
                    mapped["AUTH_ENABLED"] = str(bool(auth.get("enabled"))).lower()
                if "test_bypass" in auth:
                    mapped["AUTH_TEST_BYPASS"] = str(
                        bool(auth.get("test_bypass"))
                    ).lower()
                if "protect_docs" in auth:
                    mapped["AUTH_PROTECT_DOCS"] = str(
                        bool(auth.get("protect_docs"))
                    ).lower()
                if "jwt_alg" in auth and isinstance(auth.get("jwt_alg"), str):
                    mapped["AUTH_JWT_ALG"] = auth["jwt_alg"]
                if "jwt_public_key" in auth and isinstance(
                    auth.get("jwt_public_key"), str
                ):
                    mapped["AUTH_JWT_PUBLIC_KEY"] = auth["jwt_public_key"]
                if "jwt_issuer" in auth and isinstance(auth.get("jwt_issuer"), str):
                    mapped["AUTH_JWT_ISSUER"] = auth["jwt_issuer"]
                if "jwt_audience" in auth and isinstance(auth.get("jwt_audience"), str):
                    mapped["AUTH_JWT_AUDIENCE"] = auth["jwt_audience"]
                if "jwt_clock_skew" in auth:
                    try:
                        mapped["AUTH_JWT_CLOCK_SKEW"] = int(auth["jwt_clock_skew"])
                    except (ValueError, TypeError):
                        pass

            # redis.url / database.url convenience
            redis = data.get("redis")
            if isinstance(redis, dict):
                if isinstance(redis.get("url"), str):
                    mapped["FBA_BENCH_REDIS_URL"] = redis["url"]
            db = data.get("database")
            if isinstance(db, dict):
                if isinstance(db.get("url"), str):
                    mapped["DATABASE_URL"] = db["url"]

            # logging.*
            logging_cfg = data.get("logging")
            if isinstance(logging_cfg, dict):
                if isinstance(logging_cfg.get("level"), str):
                    mapped["FBA_LOG_LEVEL"] = logging_cfg["level"]
                if isinstance(logging_cfg.get("format"), str):
                    mapped["FBA_LOG_FORMAT"] = logging_cfg["format"]
                if isinstance(logging_cfg.get("file"), str):
                    mapped["FBA_LOG_FILE"] = logging_cfg["file"]
                if "include_tracebacks" in logging_cfg:
                    mapped["FBA_LOG_INCLUDE_TRACEBACKS"] = str(
                        bool(logging_cfg.get("include_tracebacks"))
                    ).lower()

            # clearml.*
            clearml = data.get("clearml")
            if isinstance(clearml, dict):
                if isinstance(clearml.get("web_host"), str):
                    mapped["CLEARML_WEB_HOST"] = clearml["web_host"]
                if isinstance(clearml.get("local_ui"), str):
                    mapped["FBA_BENCH_CLEARML_LOCAL_UI"] = clearml["local_ui"]
                if "web_port" in clearml:
                    try:
                        mapped["FBA_BENCH_CLEARML_WEB_PORT"] = int(clearml["web_port"])
                    except (ValueError, TypeError):
                        pass
                if "file_port" in clearml:
                    try:
                        mapped["FBA_BENCH_CLEARML_FILE_PORT"] = int(
                            clearml["file_port"]
                        )
                    except (ValueError, TypeError):
                        pass
                if "api_port" in clearml:
                    try:
                        mapped["FBA_BENCH_CLEARML_API_PORT"] = int(clearml["api_port"])
                    except (ValueError, TypeError):
                        pass
                if isinstance(clearml.get("compose_filename"), str):
                    mapped["FBA_BENCH_CLEARML_COMPOSE"] = clearml["compose_filename"]
                if isinstance(clearml.get("root_hint"), str):
                    mapped["FBA_BENCH_ROOT"] = clearml["root_hint"]

            # environment
            if isinstance(data.get("environment"), str):
                mapped["ENVIRONMENT"] = str(data["environment"])

            return mapped

        # Precedence (highest -> lowest) achieved by source order here:
        # init kwargs > env vars > .env > YAML overlay > file secrets > defaults
        # Ensure env vars override YAML by placing env before YAML.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_source,
            file_secret_settings,
        )

    # --------- Derived helpers ---------

    @property
    def is_protected_env(self) -> bool:
        v = (self.environment or "development").strip().lower()
        return v in ("production", "prod", "staging")

    @property
    def cors_allow_origins(self) -> List[str]:
        raw = (self.cors_allow_origins_raw or "").strip()
        if raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            if items:
                return items
        # Defaults: local dev origins if not explicitly configured
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]

    @property
    def auth_enabled(self) -> bool:
        # If explicitly provided, honor it; else default by environment
        if self.auth_enabled_raw is not None:
            return _truthy(self.auth_enabled_raw, default=self.is_protected_env)
        return self.is_protected_env

    @property
    def auth_test_bypass(self) -> bool:
        if self.auth_test_bypass_raw is not None:
            return _truthy(self.auth_test_bypass_raw, default=not self.is_protected_env)
        return not self.is_protected_env

    @property
    def auth_protect_docs(self) -> bool:
        if self.auth_protect_docs_raw is not None:
            return _truthy(self.auth_protect_docs_raw, default=self.is_protected_env)
        return self.is_protected_env

    @property
    def logging_include_tracebacks(self) -> bool:
        return _truthy(self.logging_include_tracebacks_raw, default=True)

    @property
    def smtp_use_tls(self) -> bool:
        return _truthy(self.smtp_use_tls_raw, default=True)

    @property
    def contact_reply_to(self) -> Optional[str]:
        v = (self.contact_to_email or "").strip()
        return v or None

    @property
    def contact_fallback(self) -> Optional[str]:
        v = (self.contact_fallback_email or self.contact_to_email or "").strip()
        return v or None

    @property
    def preferred_redis_url(self) -> Optional[str]:
        # Prefer FBA_BENCH_REDIS_URL over REDIS_URL
        return self.redis_url_fba or self.redis_url_compat

    @property
    def preferred_db_url(self) -> Optional[str]:
        # Prefer FBA_BENCH_DB_URL over legacy DATABASE_URL for clarity/namespace consistency
        return self.db_url_fba or self.db_url


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Cached settings accessor. Re-evaluate by calling get_settings.cache_clear() if needed.
    """
    return AppSettings()
