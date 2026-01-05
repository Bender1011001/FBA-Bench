"""
External Service Integration for FBA-Bench.

This module provides real, functional implementations for external dependencies,
allowing the system to integrate with actual external services and APIs.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

from benchmarking.registry.global_variables import global_variables

logger = logging.getLogger(__name__)


class ExternalServiceType(str, Enum):
    """Types of external services."""

    AMAZON_SELLER_CENTRAL = "amazon_seller_central"
    GOOGLE_ANALYTICS = "google_analytics"
    SHOPIFY = "shopify"
    FACEBOOK_MARKETPLACE = "facebook_marketplace"
    EBAY = "ebay"
    TWITTER = "twitter"
    REDDIT = "reddit"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    WEATHER_API = "weather_api"
    EXCHANGE_RATE_API = "exchange_rate_api"
    NEWS_API = "news_api"
    CUSTOM_API = "custom_api"


@dataclass
class ServiceConfig:
    """Configuration for external services."""

    service_type: ExternalServiceType
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit: int = 100  # requests per minute
    headers: Dict[str, str] = field(default_factory=dict)
    auth_method: str = "bearer"  # bearer, basic, custom
    custom_auth_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and prepare the configuration."""
        if not self.base_url:
            raise ValueError("base_url is required for service configuration")

        # Set default headers
        if not self.headers:
            self.headers = {
                "Content-Type": "application/json",
                "User-Agent": f"FBA-Bench/{global_variables.app_version}",
            }

        # Add authentication header if API key is provided
        if self.api_key:
            if self.auth_method == "bearer":
                self.headers["Authorization"] = f"Bearer {self.api_key}"
            elif self.auth_method == "basic":
                # Basic auth would be handled by the requests library
                pass
            elif self.auth_method == "custom":
                # Add custom authentication parameters
                for key, value in self.custom_auth_params.items():
                    self.headers[key] = value.format(api_key=self.api_key)


@dataclass
class ServiceResponse:
    """Response from an external service."""

    success: bool
    status_code: int
    data: Any
    headers: Dict[str, str]
    response_time: float
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "status_code": self.status_code,
            "data": self.data,
            "headers": self.headers,
            "response_time": self.response_time,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed.

        Returns:
            True if request is allowed, False otherwise
        """
        with self.lock:
            now = time.time()

            # Remove old requests
            self.requests = [
                req_time
                for req_time in self.requests
                if now - req_time < self.time_window
            ]

            # Check if we can make a new request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    def wait_for_slot(self) -> None:
        """Wait until a request slot is available."""
        while not self.is_allowed():
            time.sleep(0.1)


class ExternalService:
    """Base class for external services."""

    def __init__(self, config: ServiceConfig):
        """
        Initialize the external service.

        Args:
            config: Service configuration
        """
        self.config = config
        self.rate_limiter = RateLimiter(config.rate_limit)
        self.session = requests.Session()
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Set up session with default configuration
        self.session.headers.update(config.headers)
        self.session.timeout = config.timeout

        logger.info(f"Initialized external service: {config.service_type.value}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> ServiceResponse:
        """
        Make a request to the external service.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            ServiceResponse object
        """
        # Wait for rate limit
        self.rate_limiter.wait_for_slot()

        url = f"{self.config.base_url}{endpoint}"
        start_time = time.time()

        for attempt in range(self.config.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                response_time = time.time() - start_time

                # Check if response is successful
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError:
                        data = response.text

                    return ServiceResponse(
                        success=True,
                        status_code=response.status_code,
                        data=data,
                        headers=dict(response.headers),
                        response_time=response_time,
                    )
                else:
                    # Handle error responses
                    error_data = None
                    try:
                        error_data = response.json()
                    except ValueError:
                        error_data = response.text

                    return ServiceResponse(
                        success=False,
                        status_code=response.status_code,
                        data=error_data,
                        headers=dict(response.headers),
                        response_time=response_time,
                        error_message=f"HTTP {response.status_code}: {response.reason}",
                    )

            except requests.exceptions.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    return ServiceResponse(
                        success=False,
                        status_code=0,
                        data=None,
                        headers={},
                        response_time=time.time() - start_time,
                        error_message=f"Request failed: {e!s}",
                    )

                # Wait before retrying
                time.sleep(self.config.retry_delay * (2**attempt))

    def get(self, endpoint: str, params: Optional[Dict] = None) -> ServiceResponse:
        """Make a GET request."""
        return self._make_request("GET", endpoint, params=params)

    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> ServiceResponse:
        """Make a POST request."""
        if json_data:
            return self._make_request("POST", endpoint, json=json_data)
        else:
            return self._make_request("POST", endpoint, data=data)

    def put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> ServiceResponse:
        """Make a PUT request."""
        if json_data:
            return self._make_request("PUT", endpoint, json=json_data)
        else:
            return self._make_request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> ServiceResponse:
        """Make a DELETE request."""
        return self._make_request("DELETE", endpoint)

    def close(self) -> None:
        """Close the service connection."""
        self.session.close()
        self.executor.shutdown(wait=True)
        logger.info(f"Closed external service: {self.config.service_type.value}")


class AmazonSellerCentralService(ExternalService):
    """Service for Amazon Seller Central API integration."""

    def __init__(self, config: ServiceConfig):
        """Initialize Amazon Seller Central service."""
        super().__init__(config)
        self.access_token = None
        self.refresh_token = config.custom_auth_params.get("refresh_token")
        self.client_id = config.custom_auth_params.get("client_id")
        self.client_secret = config.custom_auth_params.get("client_secret")

        # Authenticate if credentials are provided
        if self.refresh_token and self.client_id and self.client_secret:
            self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Amazon Seller Central."""
        auth_url = "https://api.amazon.com/auth/o2/token"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = self._make_request("POST", auth_url, data=data)

        if response.success:
            self.access_token = response.data.get("access_token")
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            logger.info("Successfully authenticated with Amazon Seller Central")
        else:
            logger.error(
                f"Failed to authenticate with Amazon Seller Central: {response.error_message}"
            )

    def get_product_info(self, asin: str) -> ServiceResponse:
        """Get product information by ASIN."""
        endpoint = f"/products/v0/products/{asin}"
        return self.get(endpoint)

    def get_pricing(self, asin: str) -> ServiceResponse:
        """Get pricing information for a product."""
        endpoint = f"/products/v0/products/{asin}/offers"
        return self.get(endpoint)

    def get_sales_rank(self, asin: str) -> ServiceResponse:
        """Get sales rank for a product."""
        endpoint = f"/products/v0/products/{asin}/salesRank"
        return self.get(endpoint)

    def get_inventory_levels(self, asin: str) -> ServiceResponse:
        """Get inventory levels for a product."""
        endpoint = "/inventory/v1/summaries"
        params = {"sellerSkus": asin}
        return self.get(endpoint, params=params)

    def update_price(self, asin: str, price: float) -> ServiceResponse:
        """Update price for a product."""
        endpoint = f"/products/v0/products/{asin}/price"
        data = {"price": price, "currency": "USD"}
        return self.put(endpoint, json_data=data)


class OpenAIService(ExternalService):
    """Service for OpenAI API integration."""

    def __init__(self, config: ServiceConfig):
        """Initialize OpenAI service."""
        super().__init__(config)
        self.model = config.custom_auth_params.get("model", "gpt-4")

    def chat_completion(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> ServiceResponse:
        """
        Create a chat completion.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters

        Returns:
            ServiceResponse with completion result
        """
        endpoint = "/chat/completions"
        data = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }

        return self.post(endpoint, json_data=data)

    def embedding(
        self, text: str, model: str = "text-embedding-ada-002"
    ) -> ServiceResponse:
        """
        Create an embedding for text.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            ServiceResponse with embedding result
        """
        endpoint = "/embeddings"
        data = {"model": model, "input": text}

        return self.post(endpoint, json_data=data)

    def moderation(self, text: str) -> ServiceResponse:
        """
        Check text for policy violations.

        Args:
            text: Text to moderate

        Returns:
            ServiceResponse with moderation result
        """
        endpoint = "/moderations"
        data = {"input": text}

        return self.post(endpoint, json_data=data)


class WeatherService(ExternalService):
    """Service for weather API integration."""

    def __init__(self, config: ServiceConfig):
        """Initialize weather service."""
        super().__init__(config)
        self.api_key = config.api_key

    def get_current_weather(
        self, location: str, units: str = "metric"
    ) -> ServiceResponse:
        """
        Get current weather for a location.

        Args:
            location: Location name or coordinates
            units: Temperature units (metric, imperial)

        Returns:
            ServiceResponse with weather data
        """
        endpoint = "/current"
        params = {"q": location, "units": units, "appid": self.api_key}

        return self.get(endpoint, params=params)

    def get_forecast(
        self, location: str, days: int = 5, units: str = "metric"
    ) -> ServiceResponse:
        """
        Get weather forecast for a location.

        Args:
            location: Location name or coordinates
            days: Number of days to forecast
            units: Temperature units (metric, imperial)

        Returns:
            ServiceResponse with forecast data
        """
        endpoint = "/forecast"
        params = {
            "q": location,
            "cnt": days * 8,  # 8 forecasts per day (every 3 hours)
            "units": units,
            "appid": self.api_key,
        }

        return self.get(endpoint, params=params)


class ExchangeRateService(ExternalService):
    """Service for exchange rate API integration."""

    def __init__(self, config: ServiceConfig):
        """Initialize exchange rate service."""
        super().__init__(config)
        self.api_key = config.api_key

    def get_exchange_rate(
        self, from_currency: str, to_currency: str
    ) -> ServiceResponse:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            ServiceResponse with exchange rate data
        """
        endpoint = f"/pair/{from_currency}/{to_currency}"
        params = {"apikey": self.api_key}

        return self.get(endpoint, params=params)

    def get_historical_rates(self, base_currency: str, date: str) -> ServiceResponse:
        """
        Get historical exchange rates for a currency.

        Args:
            base_currency: Base currency code
            date: Date in YYYY-MM-DD format

        Returns:
            ServiceResponse with historical rates data
        """
        endpoint = f"/{date}"
        params = {"base": base_currency, "apikey": self.api_key}

        return self.get(endpoint, params=params)


class ExternalServiceManager:
    """Manager for external services."""

    def __init__(self):
        """Initialize the external service manager."""
        self.services: Dict[str, ExternalService] = {}
        self.service_configs: Dict[str, ServiceConfig] = {}
        self.lock = threading.Lock()

        logger.info("ExternalServiceManager initialized")

    def register_service(self, name: str, config: ServiceConfig) -> None:
        """
        Register an external service.

        Args:
            name: Service name
            config: Service configuration
        """
        with self.lock:
            if name in self.services:
                logger.warning(f"Service '{name}' already registered, replacing")
                self.services[name].close()

            # Create appropriate service instance
            if config.service_type == ExternalServiceType.AMAZON_SELLER_CENTRAL:
                service = AmazonSellerCentralService(config)
            elif config.service_type == ExternalServiceType.OPENAI:
                service = OpenAIService(config)
            elif config.service_type == ExternalServiceType.WEATHER_API:
                service = WeatherService(config)
            elif config.service_type == ExternalServiceType.EXCHANGE_RATE_API:
                service = ExchangeRateService(config)
            else:
                service = ExternalService(config)

            self.services[name] = service
            self.service_configs[name] = config

            logger.info(
                f"Registered external service: {name} ({config.service_type.value})"
            )

    def get_service(self, name: str) -> Optional[ExternalService]:
        """
        Get a registered service.

        Args:
            name: Service name

        Returns:
            ExternalService instance or None if not found
        """
        return self.services.get(name)

    def unregister_service(self, name: str) -> bool:
        """
        Unregister a service.

        Args:
            name: Service name

        Returns:
            True if successful, False if service not found
        """
        with self.lock:
            if name not in self.services:
                logger.warning(f"Service '{name}' not found for unregistration")
                return False

            self.services[name].close()
            del self.services[name]
            del self.service_configs[name]

            logger.info(f"Unregistered external service: {name}")
            return True

    def list_services(self) -> List[str]:
        """
        List all registered service names.

        Returns:
            List of service names
        """
        return list(self.services.keys())

    def get_service_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a service.

        Args:
            name: Service name

        Returns:
            Service information dictionary or None if not found
        """
        if name not in self.service_configs:
            return None

        config = self.service_configs[name]
        return {
            "name": name,
            "service_type": config.service_type.value,
            "base_url": config.base_url,
            "timeout": config.timeout,
            "max_retries": config.max_retries,
            "rate_limit": config.rate_limit,
            "has_api_key": config.api_key is not None,
        }

    def close_all(self) -> None:
        """Close all services."""
        with self.lock:
            for name, service in self.services.items():
                service.close()

            self.services.clear()
            self.service_configs.clear()

            logger.info("Closed all external services")

    def test_service(self, name: str) -> ServiceResponse:
        """
        Test a service by making a simple request.

        Args:
            name: Service name

        Returns:
            ServiceResponse with test result
        """
        service = self.get_service(name)
        if not service:
            return ServiceResponse(
                success=False,
                status_code=0,
                data=None,
                headers={},
                response_time=0,
                error_message=f"Service '{name}' not found",
            )

        # Try to make a simple request
        try:
            # Use a simple health check endpoint or root endpoint
            response = service.get("/")
            return response
        except Exception as e:
            return ServiceResponse(
                success=False,
                status_code=0,
                data=None,
                headers={},
                response_time=0,
                error_message=f"Service test failed: {e!s}",
            )


# Global instance of the external service manager
external_service_manager = ExternalServiceManager()
