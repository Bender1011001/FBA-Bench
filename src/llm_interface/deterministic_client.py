# src/llm_interface/deterministic_client.py
import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from reproducibility.llm_cache import LLMResponseCache

from llm_interface.contract import BaseLLMClient, LLMClientError

logger = logging.getLogger(__name__)


class OperationMode(Enum):
    """Operating modes for the deterministic client."""

    DETERMINISTIC = "deterministic"  # Only use cached responses
    STOCHASTIC = "stochastic"  # Use live LLM calls, optionally cache
    HYBRID = "hybrid"  # Use cache when available, fallback to live


@dataclass
class ResponseMetadata:
    """Metadata for LLM response tracking."""

    model: str
    temperature: float
    timestamp: str
    mode: str
    cache_hit: bool
    response_time_ms: float
    prompt_hash: str
    validation_passed: bool
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "timestamp": self.timestamp,
            "mode": self.mode,
            "cache_hit": self.cache_hit,
            "response_time_ms": self.response_time_ms,
            "prompt_hash": self.prompt_hash,
            "validation_passed": self.validation_passed,
            "fallback_used": self.fallback_used,
        }


@dataclass
class ValidationSchema:
    """Schema for response format validation."""

    required_fields: list
    field_types: Dict[str, type]
    min_content_length: int = 1
    max_content_length: int = 100000

    def validate(self, response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate response against schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check required fields
            for field in self.required_fields:
                if field not in response:
                    return False, f"Missing required field: {field}"

            # Check field types
            for field, expected_type in self.field_types.items():
                if field in response and not isinstance(response[field], expected_type):
                    return (
                        False,
                        f"Field {field} has wrong type: expected {expected_type}, got {type(response[field])}",
                    )

            # Check content length if choices exist
            if response.get("choices"):
                content = response["choices"][0].get("message", {}).get("content", "")
                if len(content) < self.min_content_length:
                    return (
                        False,
                        f"Content too short: {len(content)} < {self.min_content_length}",
                    )
                if len(content) > self.max_content_length:
                    return (
                        False,
                        f"Content too long: {len(content)} > {self.max_content_length}",
                    )

            return True, None

        except Exception as e:
            return False, f"Validation error: {e}"


class DeterministicLLMClient(BaseLLMClient):
    """
    Deterministic LLM client that wraps existing LLM clients with caching
    and mode switching for reproducible simulation runs.

    Supports three operating modes:
    - DETERMINISTIC: Only cached responses, fails on cache miss
    - STOCHASTIC: Live LLM calls, optionally records responses
    - HYBRID: Cache first, fallback to live calls
    """

    # Issue 97: Modified schema to be more permissive. 'usage' is optional now.
    DEFAULT_SCHEMA = ValidationSchema(
        required_fields=["choices"],
        field_types={"choices": list} # Removed "usage": dict as strictly required
    )

    def __init__(
        self,
        underlying_client: BaseLLMClient,
        cache: Optional[LLMResponseCache] = None,
        mode: OperationMode = OperationMode.HYBRID,
        enable_validation: bool = True,
        validation_schema: Optional[ValidationSchema] = None,
        fallback_temperature: float = 0.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize deterministic LLM client.

        Args:
            underlying_client: The actual LLM client to wrap
            cache: LLM response cache instance
            mode: Operating mode for the client
            enable_validation: Whether to validate responses
            validation_schema: Custom validation schema
            fallback_temperature: Temperature to use for fallback calls
            max_retries: Maximum retry attempts for failed calls
            retry_delay: Delay between retries in seconds
        """
        super().__init__(
            model_name=getattr(underlying_client, "model_name", "unknown"),
            api_key=getattr(underlying_client, "api_key", None),
            base_url=getattr(underlying_client, "base_url", None),
        )

        self.underlying_client = underlying_client
        self.cache = cache or LLMResponseCache()
        self.mode = mode
        self.enable_validation = enable_validation
        self.validation_schema = validation_schema or self.DEFAULT_SCHEMA
        self.fallback_temperature = fallback_temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # State for auto-export
        self._export_path = None

        # Statistics tracking
        self._total_calls = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._validation_failures = 0
        self._fallback_calls = 0

        logger.info(f"DeterministicLLMClient initialized in {mode.value} mode")

    def __del__(self):
        """Ensure cache is exported if recording was active."""
        if self._export_path and self.cache._recording_mode:
            try:
                self.cache.export_cache(self._export_path)
                logger.info(f"Auto-exported cache to {self._export_path} on shutdown.")
            except Exception as e:
                logger.error(f"Failed to auto-export cache on shutdown: {e}")

    def set_deterministic_mode(self, enabled: bool, cache_file: Optional[str] = None):
        """
        Switch to deterministic mode.

        Args:
            enabled: Whether to enable deterministic mode
            cache_file: Optional cache file to use
        """
        if enabled:
            self.mode = OperationMode.DETERMINISTIC
            self.cache.set_deterministic_mode(True)
            if cache_file:
                # Load cache from file if specified
                self.cache.import_cache(cache_file, merge=False)
        else:
            self.mode = OperationMode.HYBRID
            self.cache.set_deterministic_mode(False)

        logger.info(f"Switched to {'deterministic' if enabled else 'hybrid'} mode")

    def record_responses(self, enabled: bool, cache_file: Optional[str] = None):
        """
        Enable response recording mode.

        Args:
            enabled: Whether to enable recording
            cache_file: Optional cache file to save to
        """
        self.cache.set_recording_mode(enabled)
        
        if enabled and cache_file:
            self._export_path = cache_file # Store path for auto-export on disable/del
        elif not enabled and self._export_path:
            # Export now on disable
            try:
                self.cache.export_cache(self._export_path)
                logger.info(f"Exported cache to {self._export_path} upon disabling recording.")
            except Exception as e:
                logger.error(f"Failed to export cache: {e}")

        logger.info(f"Response recording: {'enabled' if enabled else 'disabled'}")

    def validate_response_format(
        self,
        response: Dict[str, Any],
        expected_schema: Optional[ValidationSchema] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate response format against expected schema.

        Args:
            response: LLM response to validate
            expected_schema: Schema to validate against

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.enable_validation:
            return True, None

        schema = expected_schema or self.validation_schema
        return schema.validate(response)

    async def call_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make deterministic LLM call with caching and validation.

        Args:
            prompt: Input prompt
            model: Model name (overrides default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            LLM response with metadata

        Raises:
            LLMClientError: On validation or deterministic mode failures
        """
        start_time = time.time()
        self._total_calls += 1

        # Use provided model or default
        model_name = model or self.model_name

        # Generate cache key
        cache_params = {
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        prompt_hash = self.cache.generate_prompt_hash(prompt, **cache_params)

        logger.debug(
            f"LLM call for hash: {prompt_hash[:16]}... (mode: {self.mode.value})"
        )

        # Try cache first if not in pure stochastic mode
        cached_response = None
        cache_hit = False

        if self.mode != OperationMode.STOCHASTIC:
            try:
                cached_response = self.cache.get_cached_response(prompt_hash)
            except ValueError:
                # Deterministic cache miss from cache layer
                cached_response = None

            if cached_response:
                # Validate cached response BEFORE counting as a hit
                is_valid, error = self.validate_response_format(cached_response)
                if not is_valid:
                    logger.warning(f"Cached response validation failed: {error}")
                    self._validation_failures += 1
                    cached_response = None # Invalidate it
                    
                    if self.mode == OperationMode.DETERMINISTIC:
                        # Strict mode: Invalid cache is a fatal error
                        raise LLMClientError(f"Deterministic mode failure: Invalid cached response for {prompt_hash[:8]}")
                else:
                    # Only increment hits if valid
                    cache_hit = True
                    self._cache_hits += 1
            else:
                self._cache_misses += 1
                if self.mode == OperationMode.DETERMINISTIC:
                     raise LLMClientError(f"Deterministic mode failure: Cache miss for {prompt_hash[:8]}")

        # Make live call if needed
        live_response = None
        fallback_used = False

        if not cached_response:
            # Ensure we are NOT in deterministic mode if we got here
            if self.mode == OperationMode.DETERMINISTIC:
                 raise LLMClientError(f"Deterministic mode failure: Cache miss or invalid cache for {prompt_hash[:8]}")

            # Make live LLM call with retries
            live_response = await self._make_live_call_with_retry(
                prompt, model_name, temperature, max_tokens, **kwargs
            )

            # Validate live response
            is_valid, error = self.validate_response_format(live_response)
            if not is_valid:
                self._validation_failures += 1

                # Try fallback with different temperature
                if self.fallback_temperature != temperature:
                    logger.warning(
                        f"Response validation failed, trying fallback: {error}"
                    )
                    fallback_used = True
                    self._fallback_calls += 1

                    live_response = await self._make_live_call_with_retry(
                        prompt,
                        model_name,
                        self.fallback_temperature,
                        max_tokens,
                        **kwargs,
                    )

                    is_valid, error = self.validate_response_format(live_response)
                    if not is_valid:
                        raise LLMClientError(
                            f"Response validation failed even with fallback: {error}"
                        )
                else:
                    raise LLMClientError(f"Response validation failed: {error}")

            # Cache the response for future determinism
            if self.cache._recording_mode or self.mode in (
                OperationMode.HYBRID,
                OperationMode.DETERMINISTIC, # Should not reach here strictly, but good practice
            ):
                metadata = {
                    "model": model_name,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs,
                }
                try:
                    self.cache.cache_response(prompt_hash, live_response, metadata)
                except Exception as e:
                    logger.warning(
                        f"Failed to cache live LLM response for hash {prompt_hash[:16]}...: {e}"
                    )

        # Prepare final response
        final_response = cached_response or live_response
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Add metadata to response
        response_metadata = ResponseMetadata(
            model=model_name,
            temperature=temperature,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=self.mode.value,
            cache_hit=cache_hit,
            response_time_ms=response_time,
            prompt_hash=prompt_hash,
            validation_passed=True,  # If we got here, validation passed
            fallback_used=fallback_used,
        )

        # Add metadata to response without modifying original
        enhanced_response = dict(final_response)
        enhanced_response["_fba_metadata"] = response_metadata.to_dict()

        logger.debug(
            f"LLM call completed in {response_time:.1f}ms (cache_hit: {cache_hit})"
        )

        return enhanced_response

    async def _make_live_call_with_retry(
        self, prompt: str, model: str, temperature: float, max_tokens: int, **kwargs
    ) -> Dict[str, Any]:
        """
        Make live LLM call with retry logic.

        Args:
            prompt: Input prompt
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            LLM response

        Raises:
            LLMClientError: If all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Live LLM call attempt {attempt + 1}/{self.max_retries}")

                response = await self.underlying_client.generate_response(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                return response

            except Exception as e:
                last_exception = e
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(
                        self.retry_delay * (2**attempt)
                    )  # Exponential backoff

        # All retries failed
        raise LLMClientError(
            f"All {self.max_retries} LLM call attempts failed",
            original_exception=last_exception,
        )

    async def generate_response(
        self, prompt: str, temperature: float = 0.0, max_tokens: int = 1000, **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response (BaseLLMClient interface implementation).

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            LLM response
        """
        return await self.call_llm(
            prompt=prompt, temperature=temperature, max_tokens=max_tokens, **kwargs
        )

    async def get_token_count(self, text: str) -> int:
        """
        Get token count (BaseLLMClient interface implementation).

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return await self.underlying_client.get_token_count(text)

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache and client statistics.

        Returns:
            Statistics dictionary
        """
        cache_stats = self.cache.get_cache_statistics()

        return {
            "mode": self.mode.value,
            "total_calls": self._total_calls,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "validation_failures": self._validation_failures,
            "fallback_calls": self._fallback_calls,
            "cache_statistics": {
                "total_requests": cache_stats.total_requests,
                "cache_hits": cache_stats.cache_hits,
                "cache_misses": cache_stats.cache_misses,
                "cache_size": cache_stats.cache_size,
                "hit_ratio": cache_stats.hit_ratio,
                "last_access": cache_stats.last_access,
            },
        }

    def reset_statistics(self):
        """Reset client statistics."""
        self._total_calls = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._validation_failures = 0
        self._fallback_calls = 0

        logger.info("Client statistics reset")

    def set_validation_schema(self, schema: ValidationSchema):
        """Set custom validation schema."""
        self.validation_schema = schema
        logger.info("Custom validation schema applied")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the client and underlying systems.

        Returns:
            Health status dictionary
        """
        try:
            # Check cache health
            cache_valid, cache_errors = self.cache.validate_cache_integrity()

            # Check mode consistency
            mode_consistent = True
            mode_errors = []

            if (
                self.mode == OperationMode.DETERMINISTIC
                and not self.cache._deterministic_mode
            ):
                mode_consistent = False
                mode_errors.append("Client in deterministic mode but cache is not")

            return {
                "status": "healthy" if cache_valid and mode_consistent else "unhealthy",
                "mode": self.mode.value,
                "cache_valid": cache_valid,
                "cache_errors": cache_errors,
                "mode_consistent": mode_consistent,
                "mode_errors": mode_errors,
                "underlying_client": self.underlying_client.__class__.__name__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Factory functions for common configurations


def create_deterministic_client(
    underlying_client: BaseLLMClient, cache_file: str = "llm_responses.cache"
) -> DeterministicLLMClient:
    """
    Create client configured for deterministic mode.

    Args:
        underlying_client: The actual LLM client
        cache_file: Cache file path

    Returns:
        Configured deterministic client
    """
    cache = LLMResponseCache(cache_file=cache_file, enable_validation=True)
    client = DeterministicLLMClient(
        underlying_client=underlying_client,
        cache=cache,
        mode=OperationMode.DETERMINISTIC,
        enable_validation=True,
    )

    client.set_deterministic_mode(True, cache_file)
    return client


def create_recording_client(
    underlying_client: BaseLLMClient, cache_file: str = "llm_responses.cache"
) -> DeterministicLLMClient:
    """
    Create client configured for response recording.

    Args:
        underlying_client: The actual LLM client
        cache_file: Cache file path

    Returns:
        Configured recording client
    """
    cache = LLMResponseCache(cache_file=cache_file, enable_validation=True)
    client = DeterministicLLMClient(
        underlying_client=underlying_client,
        cache=cache,
        mode=OperationMode.STOCHASTIC,
        enable_validation=True,
    )

    client.record_responses(True, cache_file)
    return client


def create_hybrid_client(
    underlying_client: BaseLLMClient, cache_file: str = "llm_responses.cache"
) -> DeterministicLLMClient:
    """
    Create client configured for hybrid mode.

    Args:
        underlying_client: The actual LLM client
        cache_file: Cache file path

    Returns:
        Configured hybrid client
    """
    cache = LLMResponseCache(cache_file=cache_file, enable_validation=True)
    return DeterministicLLMClient(
        underlying_client=underlying_client,
        cache=cache,
        mode=OperationMode.HYBRID,
        enable_validation=True,
    )
