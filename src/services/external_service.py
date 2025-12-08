"""
External Service facade.

Re-exports the core external service integrations and managers.
"""
from fba_bench_core.services.external_service import (
    AmazonSellerCentralService,
    ExchangeRateService,
    ExternalService,
    ExternalServiceManager,
    ExternalServiceType,
    OpenAIService,
    RateLimiter,
    ServiceConfig,
    ServiceResponse,
    WeatherService,
    external_service_manager,
)

__all__ = [
    "AmazonSellerCentralService",
    "ExchangeRateService",
    "ExternalService",
    "ExternalServiceManager",
    "ExternalServiceType",
    "OpenAIService",
    "RateLimiter",
    "ServiceConfig",
    "ServiceResponse",
    "WeatherService",
    "external_service_manager",
]
