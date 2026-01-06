"""
Production-Ready Service Implementation for FBA-Bench.

This module provides real implementations of external services for production use.
These services connect to actual APIs and handle authentication, rate limiting, and error handling.
"""

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from benchmarking.registry.global_variables import global_variables

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """Types of production services."""

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
    """Configuration for production services."""

    service_type: ServiceType
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit: int = 100  # requests per minute
    headers: Dict[str, str] = field(default_factory=dict)
    auth_method: str = "bearer"  # bearer, basic, custom, hmac, oauth
    custom_auth_params: Dict[str, Any] = field(default_factory=dict)
    response_timeout: float = 10.0  # Maximum time to wait for a response
    connection_timeout: float = 5.0  # Maximum time to establish a connection
    cache_enabled: bool = True
    cache_ttl: int = 300  # Cache time-to-live in seconds
    verify_ssl: bool = True
    cert_path: Optional[str] = None

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
                import base64

                auth_string = (
                    f"{self.custom_auth_params.get('username', '')}:{self.api_key}"
                )
                auth_bytes = auth_string.encode("utf-8")
                auth_header = base64.b64encode(auth_bytes).decode("utf-8")
                self.headers["Authorization"] = f"Basic {auth_header}"
            elif self.auth_method == "custom":
                # Add custom authentication parameters
                for key, value in self.custom_auth_params.items():
                    self.headers[key] = value.format(api_key=self.api_key)
            elif self.auth_method == "hmac":
                # HMAC authentication will be handled in the request
                pass


@dataclass
class ServiceResponse:
    """Response from a production service."""

    success: bool
    status_code: int
    data: Any
    headers: Dict[str, str]
    response_time: float
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    cached: bool = False

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
            "cached": self.cached,
        }


class RateLimiter:
    """Production-ready rate limiter for API requests."""

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


class ResponseCache:
    """Simple response cache for API requests."""

    def __init__(self, cache_dir: str = "./cache"):
        """
        Initialize response cache.

        Args:
            cache_dir: Directory to store cached responses
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.lock = threading.Lock()

    def _get_cache_key(
        self,
        url: str,
        method: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> str:
        """
        Generate a cache key for the request.

        Args:
            url: Request URL
            method: HTTP method
            params: Query parameters
            data: Request body data

        Returns:
            Cache key string
        """
        key_data = {
            "url": url,
            "method": method,
            "params": params or {},
            "data": data or {},
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_json.encode(), usedforsecurity=False).hexdigest()

    def get(
        self,
        url: str,
        method: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Get cached response if available and not expired.

        Args:
            url: Request URL
            method: HTTP method
            params: Query parameters
            data: Request body data

        Returns:
            Cached response data or None if not available
        """
        cache_key = self._get_cache_key(url, method, params, data)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached_data = json.load(f)

            # Check if cache is expired
            cache_time = datetime.fromisoformat(cached_data["timestamp"])
            if (datetime.now() - cache_time).total_seconds() > cached_data["ttl"]:
                cache_file.unlink()
                return None

            return cached_data

        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error reading cache: {e}")
            return None

    def set(
        self,
        url: str,
        method: str,
        response_data: Dict,
        ttl: int,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> None:
        """
        Cache a response.

        Args:
            url: Request URL
            method: HTTP method
            response_data: Response data to cache
            ttl: Time-to-live in seconds
            params: Query parameters
            data: Request body data
        """
        cache_key = self._get_cache_key(url, method, params, data)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_entry = {
                "timestamp": datetime.now().isoformat(),
                "ttl": ttl,
                "response": response_data,
            }

            with open(cache_file, "w") as f:
                json.dump(cache_entry, f)

        except (OSError, TypeError) as e:
            logger.error(f"Error writing cache: {e}")

    def clear(self) -> None:
        """Clear all cached responses."""
        with self.lock:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()


class ProductionService:
    """Base class for production services."""

    def __init__(self, config: ServiceConfig):
        """
        Initialize the production service.

        Args:
            config: Service configuration
        """
        self.config = config
        self.rate_limiter = RateLimiter(config.rate_limit)
        self.cache = ResponseCache() if config.cache_enabled else None
        self.session = requests.Session()

        # Configure session
        self.session.timeout = (config.connection_timeout, config.response_timeout)
        self.session.verify = config.verify_ssl

        if config.cert_path:
            self.session.cert = config.cert_path

        # Set default headers
        self.session.headers.update(config.headers)

        logger.info(f"Initialized production service: {config.service_type.value}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> ServiceResponse:
        """
        Make a real request to the service.

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

        # Check cache first if enabled
        if self.cache:
            params = kwargs.get("params", {})
            data = kwargs.get("json", {})
            cached_response = self.cache.get(url, method, params, data)

            if cached_response:
                logger.debug(f"Cache hit for {method} {url}")
                return ServiceResponse(
                    success=True,
                    status_code=200,
                    data=cached_response["response"],
                    headers={},
                    response_time=0.001,  # Very fast for cached responses
                    cached=True,
                )

        # Prepare request parameters
        request_kwargs = {
            "timeout": (self.config.connection_timeout, self.config.response_timeout),
            "verify": self.config.verify_ssl,
        }

        if "params" in kwargs:
            request_kwargs["params"] = kwargs["params"]

        if "json" in kwargs:
            request_kwargs["json"] = kwargs["json"]

        if "data" in kwargs:
            request_kwargs["data"] = kwargs["data"]

        if "headers" in kwargs:
            request_kwargs["headers"] = kwargs["headers"]

        # Handle HMAC authentication if configured
        if self.config.auth_method == "hmac" and self.config.api_key:
            self._add_hmac_authentication(method, url, request_kwargs)

        # Make the request with retries
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.request(method, url, **request_kwargs)

                # Process the response
                response_time = time.time() - start_time

                # Check if response is successful
                if response.status_code < 400:
                    response_data = self._parse_response(response)

                    # Cache the response if caching is enabled
                    if self.cache and self.config.cache_enabled:
                        self.cache.set(
                            url,
                            method,
                            response_data,
                            self.config.cache_ttl,
                            kwargs.get("params", {}),
                            kwargs.get("json", {}),
                        )

                    return ServiceResponse(
                        success=True,
                        status_code=response.status_code,
                        data=response_data,
                        headers=dict(response.headers),
                        response_time=response_time,
                    )
                else:
                    # Handle error responses
                    error_data = self._parse_response(response)
                    error_message = f"API error: {response.status_code}"

                    if isinstance(error_data, dict) and "error" in error_data:
                        error_message = error_data["error"]

                    return ServiceResponse(
                        success=False,
                        status_code=response.status_code,
                        data=error_data,
                        headers=dict(response.headers),
                        response_time=response_time,
                        error_message=error_message,
                    )

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")

                if attempt < self.config.max_retries:
                    # Wait before retrying
                    time.sleep(self.config.retry_delay * (2**attempt))
                else:
                    break

        # All attempts failed
        return ServiceResponse(
            success=False,
            status_code=0,
            data=None,
            headers={},
            response_time=time.time() - start_time,
            error_message=f"Request failed after {self.config.max_retries + 1} attempts: {last_exception}",
        )

    def _add_hmac_authentication(
        self, method: str, url: str, request_kwargs: Dict
    ) -> None:
        """
        Add HMAC authentication to the request.

        Args:
            method: HTTP method
            url: Request URL
            request_kwargs: Request parameters dictionary
        """
        # This is a simplified HMAC implementation
        # Real implementations would vary based on the specific API requirements

        api_key = self.config.api_key
        secret = self.config.custom_auth_params.get("secret", "")

        # Create a string to sign
        params = request_kwargs.get("params", {})
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))

        string_to_sign = f"{method.upper()}\n{url}\n{query_string}"

        # Create the signature
        signature = hmac.new(
            secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
        ).digest()

        # Add the signature to the headers
        request_kwargs.setdefault("headers", {})[
            "Authorization"
        ] = f"HMAC {api_key}:{base64.b64encode(signature).decode()}"

    def _parse_response(self, response: requests.Response) -> Any:
        """
        Parse the response data.

        Args:
            response: Response object

        Returns:
            Parsed response data
        """
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                return response.json()
            except ValueError:
                return response.text
        else:
            return response.text

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> ServiceResponse:
        """Make a GET request."""
        return self._make_request("GET", endpoint, params=params)

    def post(
        self, endpoint: str, json_data: Optional[Dict[str, Any]] = None
    ) -> ServiceResponse:
        """Make a POST request."""
        return self._make_request("POST", endpoint, json=json_data)

    def put(
        self, endpoint: str, json_data: Optional[Dict[str, Any]] = None
    ) -> ServiceResponse:
        """Make a PUT request."""
        return self._make_request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str) -> ServiceResponse:
        """Make a DELETE request."""
        return self._make_request("DELETE", endpoint)

    def close(self) -> None:
        """Close the service and release resources."""
        self.session.close()
        logger.info(f"Closed production service: {self.config.service_type.value}")


class AmazonSellerCentralService(ProductionService):
    """Service for Amazon Seller Central API integration."""

    def __init__(self, config: ServiceConfig):
        """Initialize Amazon Seller Central service with specific configuration."""
        super().__init__(config)

        # Amazon SP-API specific configuration
        self.region = config.custom_auth_params.get("region", "us-east-1")
        self.marketplace_id = config.custom_auth_params.get(
            "marketplace_id", "ATVPDKIKX0DER"
        )

        # Set up AWS Signature Version 4 authentication if needed
        if config.auth_method == "aws_sigv4":
            self.access_key = config.custom_auth_params.get("access_key")
            self.secret_key = config.custom_auth_params.get("secret_key")
            self.role_arn = config.custom_auth_params.get("role_arn")

    def get_product_offers(
        self, asin: str, marketplace_id: Optional[str] = None
    ) -> ServiceResponse:
        """
        Get product offers from Amazon.

        Args:
            asin: Amazon Standard Identification Number
            marketplace_id: Marketplace ID (defaults to configured marketplace)

        Returns:
            ServiceResponse with product offers data
        """
        endpoint = "/products/v0/offers"
        params = {
            "MarketplaceId": marketplace_id or self.marketplace_id,
            "ASIN": asin,
            "ItemCondition": "New",
            "CustomerContext": "FBA-Bench",
        }

        return self.get(endpoint, params=params)

    def get_product_sales_rank(
        self, asin: str, marketplace_id: Optional[str] = None
    ) -> ServiceResponse:
        """
        Get product sales rank from Amazon.

        Args:
            asin: Amazon Standard Identification Number
            marketplace_id: Marketplace ID (defaults to configured marketplace)

        Returns:
            ServiceResponse with sales rank data
        """
        endpoint = "/products/v0/salesRank"
        params = {"MarketplaceId": marketplace_id or self.marketplace_id, "ASIN": asin}

        return self.get(endpoint, params=params)

    def get_inventory_summaries(
        self, marketplace_id: Optional[str] = None
    ) -> ServiceResponse:
        """
        Get inventory summaries from Amazon.

        Args:
            marketplace_id: Marketplace ID (defaults to configured marketplace)

        Returns:
            ServiceResponse with inventory summaries data
        """
        endpoint = "/inventory/v1/summaries"
        params = {
            "MarketplaceId": marketplace_id or self.marketplace_id,
            "details": "true",
        }

        return self.get(endpoint, params=params)

    def get_orders(
        self, created_after: str, marketplace_id: Optional[str] = None
    ) -> ServiceResponse:
        """
        Get orders from Amazon.

        Args:
            created_after: ISO datetime string to get orders created after
            marketplace_id: Marketplace ID (defaults to configured marketplace)

        Returns:
            ServiceResponse with orders data
        """
        endpoint = "/orders/v0/orders"
        params = {
            "MarketplaceIds": marketplace_id or self.marketplace_id,
            "CreatedAfter": created_after,
            "OrderStatuses": "Pending,Unshipped,PartiallyShipped,Shipped,Canceled,Unfulfillable",
        }

        return self.get(endpoint, params=params)


class OpenAIService(ProductionService):
    """Service for OpenAI API integration."""

    def __init__(self, config: ServiceConfig):
        """Initialize OpenAI service with specific configuration."""
        super().__init__(config)

        # Set OpenAI specific headers
        self.session.headers.update({"OpenAI-Beta": "assistants=v2"})

    def chat_completion(
        self,
        messages: List[Dict],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> ServiceResponse:
        """
        Create a chat completion using OpenAI.

        Args:
            messages: List of message dictionaries with role and content
            model: Model to use for completion
            temperature: Temperature parameter for response randomness
            max_tokens: Maximum number of tokens to generate

        Returns:
            ServiceResponse with chat completion data
        """
        endpoint = "/chat/completions"
        json_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        return self.post(endpoint, json_data=json_data)

    def create_embedding(
        self, text: str, model: str = "text-embedding-ada-002"
    ) -> ServiceResponse:
        """
        Create an embedding for text using OpenAI.

        Args:
            text: Text to embed
            model: Model to use for embedding

        Returns:
            ServiceResponse with embedding data
        """
        endpoint = "/embeddings"
        json_data = {"model": model, "input": text}

        return self.post(endpoint, json_data=json_data)

    def moderate_text(self, text: str) -> ServiceResponse:
        """
        Moderate text using OpenAI.

        Args:
            text: Text to moderate

        Returns:
            ServiceResponse with moderation data
        """
        endpoint = "/moderations"
        json_data = {"input": text}

        return self.post(endpoint, json_data=json_data)


class WeatherService(ProductionService):
    """Service for weather API integration."""

    def get_current_weather(
        self, location: str, units: str = "metric"
    ) -> ServiceResponse:
        """
        Get current weather for a location.

        Args:
            location: Location name or coordinates
            units: Units for temperature (metric/imperial)

        Returns:
            ServiceResponse with current weather data
        """
        endpoint = "/current"
        params = {"q": location, "units": units}

        return self.get(endpoint, params=params)

    def get_weather_forecast(
        self, location: str, days: int = 5, units: str = "metric"
    ) -> ServiceResponse:
        """
        Get weather forecast for a location.

        Args:
            location: Location name or coordinates
            days: Number of days to forecast
            units: Units for temperature (metric/imperial)

        Returns:
            ServiceResponse with weather forecast data
        """
        endpoint = "/forecast"
        params = {
            "q": location,
            "units": units,
            "cnt": days * 8,  # 8 forecasts per day (every 3 hours)
        }

        return self.get(endpoint, params=params)


class ExchangeRateService(ProductionService):
    """Service for exchange rate API integration."""

    def get_exchange_rate(
        self, from_currency: str, to_currency: str
    ) -> ServiceResponse:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency code (e.g., USD)
            to_currency: Target currency code (e.g., EUR)

        Returns:
            ServiceResponse with exchange rate data
        """
        endpoint = f"/pair/{from_currency}/{to_currency}"

        return self.get(endpoint)

    def get_latest_rates(self, base_currency: str = "USD") -> ServiceResponse:
        """
        Get latest exchange rates for a base currency.

        Args:
            base_currency: Base currency code

        Returns:
            ServiceResponse with latest exchange rates
        """
        endpoint = "/latest"
        params = {"base": base_currency}

        return self.get(endpoint, params=params)

    def get_historical_rates(
        self, date: str, base_currency: str = "USD"
    ) -> ServiceResponse:
        """
        Get historical exchange rates for a date.

        Args:
            date: Date in YYYY-MM-DD format
            base_currency: Base currency code

        Returns:
            ServiceResponse with historical exchange rates
        """
        endpoint = f"/{date}"
        params = {"base": base_currency}

        return self.get(endpoint, params=params)


class ServiceManager:
    """Manager for production services."""

    def __init__(self):
        """Initialize the service manager."""
        self.services: Dict[str, ProductionService] = {}
        self.service_configs: Dict[str, ServiceConfig] = {}
        self.lock = threading.Lock()

        logger.info("ServiceManager initialized")

    def register_service(self, name: str, config: ServiceConfig) -> None:
        """
        Register a production service.

        Args:
            name: Service name
            config: Service configuration
        """
        with self.lock:
            if name in self.services:
                logger.warning(f"Service '{name}' already registered, replacing")
                self.services[name].close()

            # Create appropriate service instance based on type
            if config.service_type == ServiceType.AMAZON_SELLER_CENTRAL:
                self.services[name] = AmazonSellerCentralService(config)
            elif config.service_type == ServiceType.OPENAI:
                self.services[name] = OpenAIService(config)
            elif config.service_type == ServiceType.WEATHER_API:
                self.services[name] = WeatherService(config)
            elif config.service_type == ServiceType.EXCHANGE_RATE_API:
                self.services[name] = ExchangeRateService(config)
            else:
                # Default to generic production service
                self.services[name] = ProductionService(config)

            self.service_configs[name] = config

            logger.info(
                f"Registered production service: {name} ({config.service_type.value})"
            )

    def get_service(self, name: str) -> Optional[ProductionService]:
        """
        Get a registered service.

        Args:
            name: Service name

        Returns:
            ProductionService instance or None if not found
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

            logger.info(f"Unregistered production service: {name}")
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

            logger.info("Closed all production services")

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


# Global instance of the service manager
service_manager = ServiceManager()

# Backward-compatible alias (services/__init__.py imports MockService)
MockService = ProductionService
