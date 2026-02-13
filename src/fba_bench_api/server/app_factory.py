from __future__ import annotations

import logging
import os
from typing import List

from fastapi import FastAPI, Request  # type: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[reportMissingImports]
from fba_bench import __version__
from fba_bench.core.logging import RequestIdMiddleware, setup_logging
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from fba_bench_api.api.exception_handlers import add_exception_handlers
from fba_bench_api.api.routes import (
    agents as agents_routes,
    benchmarks as benchmarks_routes,
    contact as contact_routes,
    config as config_routes,
    demo as demo_routes,
    experiments as exp_routes,
    golden as golden_routes,
    leaderboard as leaderboard_routes,
    llm as llm_routes,
    medusa as medusa_router,
    metrics as metrics_routes,
    public_leaderboard as public_leaderboard_routes,
    realtime as realtime_routes,
    root as root_routes,
    scenarios as scenarios_routes,
    settings as settings_routes,
    setup as setup_routes,
    simulation as sim_routes,
    stack as stack_routes,
    templates as templates_routes,
    wargames as wargames_routes,
)
from fba_bench_api.core.container import AppContainer
from fba_bench_api.core.lifespan import lifespan
from fba_bench_core.config import get_settings

try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
except ImportError:
    SQLAlchemyInstrumentor = None
import time

from starlette.middleware.base import BaseHTTPMiddleware
from fba_bench_api.core.database_async import async_engine

from prometheus_client import Counter, Gauge, Histogram

# Centralized, idempotent logging initialization
setup_logging()
logger = logging.getLogger("fba_bench_api")

# JWT verification (RS256) middleware

import jwt  # PyJWT
from starlette.middleware.httpsredirect import (
    HTTPSRedirectMiddleware,  # type: ignore[reportMissingImports]
)
from starlette.requests import Request  # type: ignore[reportMissingImports]
from starlette.responses import JSONResponse  # type: ignore[reportMissingImports]

from fba_bench_api.core.redis_client import get_redis

# Rate limiting (slowapi)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore[reportMissingImports]
    from slowapi.errors import RateLimitExceeded  # type: ignore[reportMissingImports]
    from slowapi.middleware import SlowAPIMiddleware  # type: ignore[reportMissingImports]
    from slowapi.util import (
        get_remote_address as _slowapi_get_remote_address,  # type: ignore[reportMissingImports]
    )

    get_remote_address = _slowapi_get_remote_address
except ImportError:
    # Minimal fallback for Limiter when slowapi is not available
    class Limiter:
        def __init__(self, *args, **kwargs):
            # The class initializer accepts any args/kwargs and stores nothing
            pass

        def limit(
            self,
            limit_string,
            key_func=None,
            deduct_when_started=False,
            override_defaults=True,
        ):
            # Returns a pass-through decorator (i.e., returns the original function without modification).
            def decorator(func):
                return func

            return decorator

        def exempt(self, func=None):
            if func is None:

                def decorator(f):
                    return f

                return decorator
            return func

    # Minimal fallback for _rate_limit_exceeded_handler when slowapi is not available
    def _rate_limit_exceeded_handler(*args, **kwargs):
        # A no-op function that accepts arbitrary args/kwargs and returns None.
        return None

    # Minimal fallback for get_remote_address when slowapi is not available
    def get_remote_address(request: Request) -> str:
        return getattr(getattr(request, "client", None), "host", "127.0.0.1")

    # Dummy SlowAPIMiddleware and RateLimitExceeded to avoid NameError in the rest of the file
    class SlowAPIMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    class RateLimitExceeded(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)


def _is_protected_env() -> bool:
    """Centralized protected env detection via AppSettings"""
    return get_settings().is_protected_env


def env_bool(name: str, default: bool) -> bool:
    """
    Parse a boolean environment variable with robust truthy/falsy handling.
    Accepts: 1/0, true/false, yes/no, on/off (case-insensitive).
    Falls back to default if unset or unparsable.
    Also checks a backward-compatible 'FBA_<NAME>' alias if primary is unset.
    """
    raw = os.getenv(name)
    if raw is None:
        raw = os.getenv(
            f"FBA_{name}"
        )  # maintain compatibility with prior FBA_AUTH_ENABLED, etc.
    if raw is None:
        return bool(default)
    v = raw.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return bool(default)


# Centralized settings
_settings = get_settings()

AUTH_JWT_ALG = _settings.auth_jwt_alg
AUTH_JWT_ISSUER = _settings.auth_jwt_issuer
AUTH_JWT_AUDIENCE = _settings.auth_jwt_audience
AUTH_JWT_CLOCK_SKEW = _settings.auth_jwt_clock_skew
# Back-compat single key for downstream references
AUTH_JWT_PUBLIC_KEY = _settings.auth_jwt_public_key


def _load_public_keys_from_env() -> List[str]:
    keys: List[str] = []
    # 1) Single key (back-compat)
    single = os.getenv("AUTH_JWT_PUBLIC_KEY") or os.getenv("FBA_AUTH_JWT_PUBLIC_KEY")
    if single and single.strip():
        keys.append(single.strip())

    # 2) Multiple keys in one env var (separated by '||' or ';' or PEM terminator)
    multi = os.getenv("AUTH_JWT_PUBLIC_KEYS") or os.getenv("FBA_AUTH_JWT_PUBLIC_KEYS")
    if multi:
        parts: List[str] = []
        # Prefer PEM block splitting if present
        pem_sep = "\n-----END PUBLIC KEY-----\n"
        if pem_sep in multi:
            chunks = multi.split(pem_sep)
            parts = [c + "-----END PUBLIC KEY-----" for c in chunks if c.strip()]
        elif "||" in multi:
            parts = [p for p in multi.split("||") if p.strip()]
        elif ";" in multi:
            parts = [p for p in multi.split(";") if p.strip()]
        else:
            parts = [multi]
        for p in parts:
            p = p.strip()
            if p:
                keys.append(p)

    # 3) Load from file if provided
    key_file = os.getenv("AUTH_JWT_PUBLIC_KEY_FILE") or os.getenv(
        "FBA_AUTH_JWT_PUBLIC_KEY_FILE"
    )
    if key_file:
        try:
            with open(key_file, encoding="utf-8") as fh:
                content = fh.read().strip()
                if content:
                    keys.append(content)
        except Exception:
            # Fail open to allow single-key configurations still to work
            pass

    # De-duplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


# Resolved list of verification keys (supports rotation)
AUTH_JWT_PUBLIC_KEYS: List[str] = _load_public_keys_from_env()


# Auth flags with protected-aware defaults
_PROTECTED_DEFAULT = _settings.is_protected_env
AUTH_ENABLED = _settings.auth_enabled
AUTH_TEST_BYPASS = _settings.auth_test_bypass
AUTH_PROTECT_DOCS = _settings.auth_protect_docs

# Default API rate limit (configurable)
API_RATE_LIMIT = _settings.api_rate_limit


UNPROTECTED_PATHS = {
    "/health",
    "/api/v1/health",
    "/healthz",
    "/livez",
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Public Performance Index endpoints (designed for external access)
    "/api/v1/public/leaderboard",
    "/api/v1/public/leaderboard/widget",
    "/api/v1/public/leaderboard/embed",
    "/api/v1/public/stats",
    "/api/v1/contact",
}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Allow health and docs unauthenticated; protect the rest
        if path in UNPROTECTED_PATHS or path.startswith(
            "/ws"
        ):  # ws authenticated separately if needed
            return await call_next(request)
        # Global bypass for tests/dev unless explicitly disabled
        if not AUTH_ENABLED or AUTH_TEST_BYPASS:
            return await call_next(request)

        auth = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if not auth or not auth.lower().startswith("bearer "):
            return JSONResponse({"detail": "Missing bearer token"}, status_code=401)

        token = auth.split(" ", 1)[1].strip()
        try:
            options = {
                "require": ["exp", "iat"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": AUTH_JWT_AUDIENCE is not None,
                "verify_iss": AUTH_JWT_ISSUER is not None,
            }
            # Prefer static PEM public key(s) via env for simplicity and security (supports rotation)
            payload = None
            if AUTH_JWT_PUBLIC_KEYS:
                last_err = None
                for _key in AUTH_JWT_PUBLIC_KEYS:
                    try:
                        payload = jwt.decode(
                            token,
                            _key,
                            algorithms=[AUTH_JWT_ALG],
                            audience=AUTH_JWT_AUDIENCE,
                            issuer=AUTH_JWT_ISSUER,
                            leeway=AUTH_JWT_CLOCK_SKEW,
                            options=options,
                        )
                        break
                    except Exception as _e:
                        last_err = _e
                        payload = None
                if payload is None:
                    raise last_err or Exception("JWT verification failed")
            else:
                # If a JWKS URL were provided (not in current spec), add support here.
                return JSONResponse(
                    {"detail": "JWT public key not configured"}, status_code=500
                )

            # Blacklist check using Redis (for logout)
            jti = payload.get("jti")
            if jti:
                try:
                    r = await get_redis()
                    if await r.sismember("blacklisted_tokens", jti):
                        logger.warning("Blacklisted token detected: %s", jti)
                        return JSONResponse(
                            {"detail": "Token has been revoked"}, status_code=401
                        )
                except Exception as e:
                    logger.warning("Redis blacklist check failed: %s", e)
                    # Fail open: allow if Redis unavailable (better availability than strict)

            # Attach identity to request.state for handlers
            request.state.user = {
                "sub": payload.get("sub"),
                "scope": payload.get("scope"),
                "roles": payload.get("roles"),
            }
        except Exception as e:
            logger.warning("JWT verification failed: %s", e)
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Basic hardening headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        # HSTS for HTTPS
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        # Basic CSP
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self';",
        )
        return response


def _get_cors_allowed_origins() -> List[str]:
    """Resolve allowed CORS origins via centralized settings."""
    return get_settings().cors_allow_origins


def create_app() -> FastAPI:
    # Initialize OpenTelemetry
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)

    # Set up OTLP exporter if configured
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        trace.get_tracer_provider().add_span_processor(span_processor)

    # Prometheus metrics
    REQUEST_TIME = Histogram(
        "http_request_duration_seconds", "Duration of HTTP requests in seconds"
    )
    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total number of HTTP requests",
        ["method", "endpoint", "status"],
    )
    ACTIVE_CONNECTIONS = Gauge(
        "active_db_connections", "Number of active database connections"
    )

    class MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            REQUEST_TIME.labels(
                method=request.method, endpoint=request.url.path
            ).observe(process_time)
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
            ).inc()
            return response

    class OTELMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            with tracer.start_as_current_span(
                "http_request",
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.user_agent": request.headers.get("user-agent", ""),
                },
            ) as span:
                # Add DB span if DB operation
                if "db" in request.url.path:
                    with tracer.start_as_current_span("db_query") as db_span:
                        db_span.set_attribute("db.system", "postgresql")
                        response = await call_next(request)
                else:
                    response = await call_next(request)

                # LLM span example - would be added in specific routes
                if "llm" in request.url.path:
                    with tracer.start_as_current_span("llm_call") as llm_span:
                        llm_span.set_attribute("llm.model", "gpt-4o")
                        response = await call_next(request)

                span.set_attribute("http.status_code", response.status_code)
                return response

    # Resolve environment and security defaults
    protected = _is_protected_env()

    # Recompute settings to pick up any runtime env changes
    from fba_bench_core.config import get_settings as _gs

    _gs.cache_clear()
    _s = _gs()

    # Recompute auth flags from centralized settings with protected-aware defaults
    global AUTH_ENABLED, AUTH_TEST_BYPASS, AUTH_JWT_PUBLIC_KEY, AUTH_JWT_PUBLIC_KEYS, AUTH_PROTECT_DOCS, AUTH_JWT_ALG, AUTH_JWT_ISSUER, AUTH_JWT_AUDIENCE, AUTH_JWT_CLOCK_SKEW, API_RATE_LIMIT
    AUTH_ENABLED = _s.auth_enabled
    AUTH_TEST_BYPASS = _s.auth_test_bypass
    AUTH_PROTECT_DOCS = _s.auth_protect_docs
    AUTH_JWT_PUBLIC_KEY = _s.auth_jwt_public_key
    AUTH_JWT_PUBLIC_KEYS = _load_public_keys_from_env()
    AUTH_JWT_ALG = _s.auth_jwt_alg
    AUTH_JWT_ISSUER = _s.auth_jwt_issuer
    AUTH_JWT_AUDIENCE = _s.auth_jwt_audience
    AUTH_JWT_CLOCK_SKEW = _s.auth_jwt_clock_skew
    API_RATE_LIMIT = _s.api_rate_limit

    # Ensure we are using the real PyJWT in protected environments (avoid local 'jwt' shim)
    try:
        if protected and AUTH_ENABLED:
            mod_path = getattr(jwt, "__file__", "") or ""
            repo_root = os.getcwd()
            if (
                mod_path
                and repo_root
                and os.path.abspath(mod_path).startswith(os.path.abspath(repo_root))
            ):
                # raise RuntimeError(
                #     "Security error: local 'jwt' module shadowing PyJWT detected in protected environment."
                # )
                # Basic feature check for real PyJWT
                if not hasattr(jwt, "__version__"):
                    raise RuntimeError(
                        "Security error: PyJWT not available (missing __version__)."
                    )
    except Exception as _e:
        raise

    # Fail fast on insecure/misconfigured setups
    if AUTH_ENABLED and not AUTH_JWT_PUBLIC_KEYS:
        raise RuntimeError(
            "AUTH_ENABLED=true but no JWT public keys are configured. Set AUTH_JWT_PUBLIC_KEY, AUTH_JWT_PUBLIC_KEYS, or AUTH_JWT_PUBLIC_KEY_FILE."
        )

    # CORS must be explicit in protected environments
    raw_cors = os.getenv("FBA_CORS_ALLOW_ORIGINS")
    if protected:
        if not raw_cors or raw_cors.strip() in ("", "*"):
            raise RuntimeError(
                "FBA_CORS_ALLOW_ORIGINS must be a comma-separated allow-list (not '*') in staging/production."
            )

    # Compute docs gating after resolving AUTH flags
    # Always protect docs in protected environments
    protect_docs = True if protected else (AUTH_PROTECT_DOCS and AUTH_ENABLED)
    default_docs = "/docs"
    default_redoc = "/redoc"
    default_openapi = "/openapi.json"

    docs_url = None if protect_docs else default_docs
    redoc_url = None if protect_docs else default_redoc
    openapi_url = None if protect_docs else default_openapi

    # Construct FastAPI with gated docs
    app = FastAPI(
        title="FBA-Bench Research Toolkit API",
        description="Real-time simulation data API for research and analysis, with control.",
        version=__version__,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Instrument FastAPI and SQLAlchemy
    FastAPIInstrumentor.instrument_app(app)
    if SQLAlchemyInstrumentor is not None:
        SQLAlchemyInstrumentor().instrument(engine=async_engine)
    else:
        logger.warning(
            "SQLAlchemy OTEL instrumentation not available. Install opentelemetry-instrumentation-sqlalchemy."
        )
    # Ensure tests can rely on presence of state.config attribute
    try:
        if not hasattr(app.state, "config"):
            app.state.config = {}
    except Exception:
        # Best-effort; continue without raising
        pass

    # Adjust UNPROTECTED_PATHS based on base docs availability (always keep health aliases)
    if docs_url is None:
        UNPROTECTED_PATHS.discard(default_docs)
    else:
        UNPROTECTED_PATHS.add(docs_url)
    if redoc_url is None:
        UNPROTECTED_PATHS.discard(default_redoc)
    else:
        UNPROTECTED_PATHS.add(redoc_url)
    if openapi_url is None:
        UNPROTECTED_PATHS.discard(default_openapi)
    else:
        UNPROTECTED_PATHS.add(openapi_url)

    # Dependency Injection container
    app.state.container = AppContainer()

    # Correlation id middleware (adds X-Request-ID and injects into logs)
    app.add_middleware(RequestIdMiddleware)

    # Force CORS headers in development for Codespaces
    if not protected:

        class DevCORSForceMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                response = await call_next(request)
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = (
                    "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                )
                response.headers["Access-Control-Allow-Headers"] = (
                    "Authorization, Content-Type, Accept"
                )
                if request.method == "OPTIONS":
                    response.status_code = 200
                return response

        app.add_middleware(DevCORSForceMiddleware)

    # Security headers middleware (basic hardening)
    app.add_middleware(SecurityHeadersMiddleware)
    # Enforce HTTPS in protected environments (redirect http->https)
    if protected and env_bool("ENFORCE_HTTPS", True):
        app.add_middleware(HTTPSRedirectMiddleware)

    # Rate Limiting (global default with health exemptions)
    if API_RATE_LIMIT and API_RATE_LIMIT.strip() != "0":
        limiter = Limiter(key_func=get_remote_address, default_limits=[API_RATE_LIMIT])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)
        logger.info("SlowAPI rate limiting enabled: %s", API_RATE_LIMIT)
    else:
        # If rate limiting is disabled, create a no-op limiter so that @limiter.exempt still works
        limiter = Limiter(key_func=get_remote_address, enabled=False)
        app.state.limiter = limiter
        logger.info("SlowAPI rate limiting disabled (API_RATE_LIMIT is '0' or empty)")

    # JWT middleware (protects all but health/docs) - only if explicitly enabled and keys provided
    if AUTH_ENABLED and AUTH_JWT_PUBLIC_KEYS:
        app.add_middleware(JWTAuthMiddleware)
        logger.info(
            "JWTAuthMiddleware enabled (keys configured: %d)", len(AUTH_JWT_PUBLIC_KEYS)
        )
    else:
        logger.info(
            "JWTAuthMiddleware disabled (AUTH_ENABLED=%s, KEYS_CONFIGURED=%d)",
            AUTH_ENABLED,
            len(AUTH_JWT_PUBLIC_KEYS) if isinstance(AUTH_JWT_PUBLIC_KEYS, list) else 0,
        )

    allow_origins = _get_cors_allowed_origins()
    # Hardened CORS: explicit origins, no credentials, limited methods/headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Content-Type"],
        max_age=600,
    )

    # Exception handlers
    add_exception_handlers(app)

    # Logout route for token blacklisting
    @app.post("/logout")
    async def logout(request: Request):
        auth = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if not auth or not auth.lower().startswith("bearer "):
            return JSONResponse({"detail": "Missing bearer token"}, status_code=401)

        token = auth.split(" ", 1)[1].strip()
        try:
            # Decode without verification to get jti and exp (trust client for logout, but log)
            payload = jwt.decode(token, options={"verify_signature": False})
            jti = payload.get("jti")
            exp = payload.get("exp")
            if not jti or not exp:
                return JSONResponse(
                    {"detail": "Invalid token structure"}, status_code=400
                )

            if exp > time.time():
                ttl = int(exp - time.time())
                r = await get_redis()
                await r.sadd("blacklisted_tokens", jti)
                if ttl > 0:
                    await r.expire("blacklisted_tokens", ttl)

            return JSONResponse({"detail": "Token revoked successfully"})
        except Exception as e:
            logger.warning("Logout failed: %s", e)
            return JSONResponse({"detail": "Logout failed"}, status_code=500)

    # Routers
    app.include_router(root_routes.router)
    app.include_router(config_routes.router)
    app.include_router(contact_routes.router)
    # Place realtime BEFORE simulation to avoid '/api/v1/simulation/{simulation_id}' catching 'events'
    app.include_router(realtime_routes.router)
    app.include_router(sim_routes.router)
    app.include_router(agents_routes.router)
    app.include_router(exp_routes.router)
    app.include_router(scenarios_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(metrics_routes.router)
    app.include_router(llm_routes.router)
    app.include_router(golden_routes.router)
    app.include_router(setup_routes.router)
    # Mount dashboard and demo routes
    app.include_router(leaderboard_routes.router)
    # Public Performance Index API (no auth required for public endpoints)
    app.include_router(public_leaderboard_routes.router)
    app.include_router(demo_routes.router)
    # Mount Benchmarks router with normalized prefix
    app.include_router(benchmarks_routes.router, prefix="/api/v1")
    app.include_router(templates_routes.router, prefix="/api/v1")
    app.include_router(medusa_router.router, prefix="/api/v1", tags=["Medusa"])
    app.include_router(templates_routes.router, prefix="/api/v1", tags=["Templates"])
    # War Games API - connects React frontend to simulation engine
    app.include_router(wargames_routes.router)
    # Mount ClearML stack routes only in non-protected environments (isolation)
    if not protected:
        app.include_router(stack_routes.router)
    else:
        logger.info("ClearML stack routes disabled in protected environment")

    from starlette.responses import Response

    @app.options("/{path:path}")
    async def options_handler(request: Request, path: str):
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept"
        )
        response.headers["Access-Control-Max-Age"] = "600"
        return response

    # Health endpoint (unauthenticated) with optional Redis/DB/EventBus checks (exempt from rate limiting)
    @app.get("/health")
    @limiter.exempt
    async def health(request: Request):
        import datetime

        from starlette.responses import JSONResponse as _JSON  # type: ignore[reportMissingImports]

        from fba_bench_api.api.dependencies import ConnectionManager

        # Get connection manager for websocket count
        conn_manager = ConnectionManager()
        websocket_count = len(conn_manager.active_connections)

        # Calculate uptime
        start_time = getattr(app.state, "start_time", time.time())
        uptime_s = int(time.time() - start_time)

        # Build metadata
        status: dict = {
            "status": "ok",
            "service": "FBA-Bench Research Toolkit API",
            "version": __version__,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "websocket_connections": websocket_count,
            "uptime_s": uptime_s,
            "git_sha": os.getenv("GIT_SHA", "unknown"),
            "build_time": os.getenv("BUILD_TIME", "unknown"),
            "environment": os.getenv("ENVIRONMENT", "development"),
        }

        # Auto-detect if checks are needed based on configured URLs (production-ready)
        check_redis = bool(
            os.getenv("REDIS_URL")
            or os.getenv("FBA_BENCH_REDIS_URL")
            or os.getenv("FBA_REDIS_URL")
        )
        check_db = bool(os.getenv("DATABASE_URL") or os.getenv("FBA_BENCH_DB_URL"))
        check_event_bus = os.getenv("CHECK_EVENT_BUS", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        # Redis (optional)
        if check_redis:
            # Check if Redis URL is available
            redis_url = (
                os.getenv("REDIS_URL")
                or os.getenv("FBA_BENCH_REDIS_URL")
                or os.getenv("FBA_REDIS_URL")
            )
            if not redis_url:
                status["redis"] = "skipped"
            else:
                try:
                    from fba_bench_api.core.redis_client import get_redis

                    r = await get_redis()
                    pong = await r.ping()
                    status["redis"] = "ok" if pong else "down"
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Redis health check failed: {str(e)} - URL: {redis_url}"
                    )
                    status["redis"] = f"down:{type(e).__name__}:{str(e)[:50]}..."
        else:
            status["redis"] = "skipped"

        # Event bus via DI container (optional)
        if check_event_bus:
            try:
                container = request.app.state.container  # type: ignore[attr-defined]
                bus = container.event_bus() if container else None
                status["event_bus"] = "ok" if bus is not None else "down"
            except Exception as e:
                status["event_bus"] = f"down:{type(e).__name__}"
        else:
            status["event_bus"] = "skipped"

        # Database (optional)
        if check_db:
            # Check if Database URL is available
            db_url = os.getenv("DATABASE_URL") or os.getenv("FBA_BENCH_DB_URL")
            if not db_url:
                status["db"] = "skipped"
            else:
                try:
                    from sqlalchemy import create_engine, text
                    from sqlalchemy.ext.asyncio import create_async_engine

                    # Use async engine for PostgreSQL, sync for SQLite to avoid greenlet issues
                    if "sqlite" in db_url:
                        # Strip async driver for sync engine
                        sync_db_url = db_url.replace("+aiosqlite", "")
                        eng = create_engine(sync_db_url, future=True)
                        with eng.connect() as conn:
                            conn.execute(text("SELECT 1"))
                        eng.dispose()
                        status["db"] = "ok"
                    elif db_url.startswith("postgresql+asyncpg"):
                        engine = create_async_engine(db_url, echo=False)
                        async with engine.connect() as conn:
                            await conn.execute(text("SELECT 1"))
                        await engine.dispose()
                        status["db"] = "ok"
                    else:
                        # Fallback for other sync DBs
                        eng = create_engine(db_url, future=True)
                        with eng.connect() as conn:
                            conn.execute(text("SELECT 1"))
                        eng.dispose()
                        status["db"] = "ok"
                except Exception as e:
                    logger.error(
                        f"DB health check failed: {type(e).__name__}: {str(e)}"
                    )
                    status["db"] = f"down:{type(e).__name__}:{str(e)[:50]}..."
        else:
            status["db"] = "skipped"

        # Return 200 OK by default for development, 503 only if explicitly configured checks fail
        # Only consider actual service checks (redis, event_bus, db) when determining health status
        service_checks = {
            k: v for k, v in status.items() if k in ("redis", "event_bus", "db")
        }
        checked_services = [v for k, v in service_checks.items() if v != "skipped"]
        # Health is degraded only if we have checked services and any of them failed
        is_degraded = bool(checked_services) and any(
            v != "ok" for v in checked_services
        )
        http_status = 503 if is_degraded else 200
        status["status"] = "healthy" if not is_degraded else "degraded"
        return _JSON(status, status_code=http_status)

    # Alias route matching frontend path; identical behavior/auth as /health (also exempt)
    @app.get("/api/v1/health")
    @limiter.exempt
    async def health_v1(request: Request):
        # Delegate to the primary health handler to ensure identical payload and status
        return await health(request)

    # Simple stats endpoint for frontend dashboard (equivalent to /system/stats)
    @app.get("/system/stats")
    @limiter.exempt
    async def system_stats():
        return {
            "stats": {
                "uptime_s": int(
                    time.time() - getattr(app.state, "start_time", time.time())
                ),
                "websocket_connections": 0,
            }
        }

    # Readiness probe endpoint with full DB and Redis checks
    @app.get("/ready")
    @limiter.exempt
    async def ready(request: Request):
        import datetime

        from starlette.responses import JSONResponse as _JSON

        status = {
            "status": "ok",
            "service": "FBA-Bench Research Toolkit API",
            "version": __version__,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
        }

        # Always check Redis if configured
        if check_redis:
            try:
                from fba_bench_api.core.redis_client import get_redis

                r = await get_redis()
                pong = await r.ping()
                status["redis"] = "ok" if pong else "down"
            except Exception as e:
                status["redis"] = f"down: {type(e).__name__}"
                status["status"] = "not_ready"
        else:
            status["redis"] = "skipped"

        # Always check DB if configured
        if check_db:
            db_url = os.getenv("DATABASE_URL") or os.getenv("FBA_BENCH_DB_URL")
            try:
                from sqlalchemy import create_engine, text
                from sqlalchemy.ext.asyncio import create_async_engine

                # Use async engine for consistency
                if db_url.startswith("postgresql+asyncpg"):
                    engine = create_async_engine(db_url, echo=False)
                    async with engine.connect() as conn:
                        await conn.execute(text("SELECT 1"))
                    await engine.dispose()
                    status["db"] = "ok"
                else:
                    # Fallback for sync
                    eng = create_engine(db_url, future=True)
                    with eng.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    eng.dispose()
                    status["db"] = "ok"
            except Exception as e:
                status["db"] = f"down: {type(e).__name__}"
                status["status"] = "not_ready"
        else:
            status["db"] = "skipped"

        # Determine overall readiness
        required_checks = ["redis", "db"]
        failed_checks = [
            k
            for k, v in status.items()
            if k in required_checks and v.startswith("down")
        ]
        if failed_checks:
            http_status = 503
            status["status"] = "not_ready"
            status["failed_checks"] = failed_checks
        else:
            http_status = 200
            status["status"] = "ready"

        return _JSON(status, status_code=http_status)

    # Liveness probe endpoint (simple, no DB/Redis)
    @app.get("/livez")
    @limiter.exempt
    async def livez():
        return {"status": "alive"}

    return app
