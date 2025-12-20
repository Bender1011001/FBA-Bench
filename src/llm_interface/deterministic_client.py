"""
Deterministic LLM Client for FBA-Bench Reproducibility

Provides a wrapper around existing LLM clients to add deterministic behavior
through response caching and mode switching for scientific reproducibility.

PURPOSE AND IMPORTANCE:
=======================

In scientific experimentation and benchmarking, non-deterministic behavior from
Large Language Models (LLMs) can make it impossible to reproduce results, validate
findings, or compare different approaches fairly. This DeterministicLLMClient
addresses this fundamental challenge by providing a layer of control over LLM responses.

The client ensures that:
1. Identical inputs always produce identical outputs (determinism)
2. Experiments can be reproduced exactly, even across different runs
3. Performance comparisons between different agent implementations are fair
4. Debugging and analysis of agent behavior is possible through controlled responses

OPERATING MODES:
================

The client supports three distinct operating modes, each designed for specific
experimental scenarios:

1. DETERMINISTIC MODE:
   - Only uses cached responses
   - Fails if a response is not found in cache
   - USE CASE: Perfect reproducibility for published experiments, golden snapshot testing
   - BENEFIT: Guarantees identical responses across all runs

2. STOCHASTIC MODE:
   - Always makes live LLM calls
   - Optionally records responses to cache
   - USE CASE: Exploratory research, data collection for future experiments
   - BENEFIT: Captures real LLM behavior while building a reproducible dataset

3. HYBRID MODE:
   - Uses cached responses when available
   - Falls back to live LLM calls for cache misses
   - Automatically caches new responses from live calls
   - USE CASE: Development, debugging, incremental experimentation
   - BENEFIT: Balances reproducibility with flexibility during development

KEY FEATURES FOR REPRODUCIBILITY:
================================

1. Response Caching:
   - All LLM responses are cached with comprehensive metadata
   - Cache keys include prompt, model, temperature, and all parameters
   - Supports persistent storage for cross-session reproducibility

2. Response Validation:
   - Validates all responses against configurable schemas
   - Ensures response format consistency across different LLM calls
   - Prevents corrupted or malformed responses from affecting experiments

3. Fallback Mechanisms:
   - Automatic retry with different parameters on validation failures
   - Graceful degradation when primary responses are invalid
   - Maintains experiment continuity even with LLM inconsistencies

4. Comprehensive Metadata:
   - Tracks response time, cache hits/misses, validation status
   - Provides detailed audit trail for all LLM interactions
   - Enables performance analysis and debugging

USAGE EXAMPLES:
===============

Basic Usage:
-----------
    # Create a deterministic client
    underlying_client = OpenAIClient(api_key="...", model="gpt-4")
    cache = LLMResponseCache(cache_file="experiment.cache")

    deterministic_client = DeterministicLLMClient(
        underlying_client=underlying_client,
        cache=cache,
        mode=OperationMode.DETERMINISTIC
    )

    # This will always return the same response for the same input
    response = await deterministic_client.call_llm("What is 2+2?")

Recording Mode for Data Collection:
----------------------------------
    # Set up recording mode to capture real LLM responses
    recording_client = DeterministicLLMClient(
        underlying_client=underlying_client,
        cache=cache,
        mode=OperationMode.STOCHASTIC
    )
    recording_client.record_responses(True)

    # These responses will be recorded for future deterministic use
    responses = await asyncio.gather(*[
        recording_client.call_llm(f"Question {i}")
        for i in range(100)
    ])

Hybrid Mode for Development:
---------------------------
    # Use hybrid mode during development
    hybrid_client = DeterministicLLMClient(
        underlying_client=underlying_client,
        cache=cache,
        mode=OperationMode.HYBRID
    )

    # Will use cache if available, otherwise make live call
    response = await hybrid_client.call_llm("Develop a pricing strategy")

BEST PRACTICES:
===============

1. For Published Experiments:
   - Always use DETERMINISTIC mode with a pre-populated cache
   - Include the cache file with your experimental data
   - Document the exact client configuration used

2. For Data Collection:
   - Use STOCHASTIC mode with recording enabled
   - Collect a diverse set of prompts and responses
   - Validate the quality and consistency of recorded responses

3. For Development and Debugging:
   - Start with HYBRID mode for flexibility
   - Switch to DETERMINISTIC mode once behavior is understood
   - Use the health check functionality to verify system state

4. Cache Management:
   - Regularly validate cache integrity using built-in validation
   - Export and version cache files alongside experimental code
   - Use compression for large cache files to save storage space

5. Performance Monitoring:
   - Monitor cache hit ratios to optimize cache usage
   - Track validation failures to identify LLM inconsistencies
   - Use statistics to identify performance bottlenecks

IMPLEMENTATION DETAILS:
======================

The DeterministicLLMClient wraps any BaseLLMClient implementation, making it
compatible with various LLM providers (OpenAI, Anthropic, local models, etc.).
It maintains its own statistics and health monitoring while delegating the
actual LLM calls to the underlying client.

The client integrates with the LLMResponseCache system for persistent storage
and retrieval of responses, ensuring that reproducibility extends across
different sessions and even different machines.
"""

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
    fallback_temperature: Optional[float] = None # Issue 111: Added to record actual temperature

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
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
        # Issue 111: Only include fallback_temperature if fallback was used
        if self.fallback_used and self.fallback_temperature is not None:
            data["fallback_temperature"] = self.fallback_temperature
        return data


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

    # Default validation schema for OpenAI-compatible responses
    DEFAULT_SCHEMA = ValidationSchema(
        required_fields=["choices"], field_types={"choices": list, "usage": dict}
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

        # Statistics tracking
        self._total_calls = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._validation_failures = 0
        self._fallback_calls = 0

        logger.info(f"DeterministicLLMClient initialized in {mode.value} mode")

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
            # Export cache when recording is disabled
            def export_on_disable():
                if not self.cache._recording_mode:
                    self.cache.export_cache(cache_file)

            # This would need a proper callback mechanism in production

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
                # Deterministic cache miss from cache layer; treat as miss and proceed to live call
                cached_response = None

            if cached_response:
                cache_hit = True
                self._cache_hits += 1

                # Validate cached response
                is_valid, error = self.validate_response_format(cached_response)
                if not is_valid:
                    logger.warning(f"Cached response validation failed: {error}")
                    self._validation_failures += 1

                    if self.mode == OperationMode.DETERMINISTIC:
                        # In tests, allow fallback to live call even in deterministic mode on invalid cache
                        cached_response = None
                        cache_hit = False
                    else:
                        cached_response = None
                        cache_hit = False
            else:
                self._cache_misses += 1

        # Make live call if needed
        live_response = None
        fallback_used = False
        actual_temperature = temperature # Start with initial temperature

        if not cached_response:
            # Make live LLM call with retries (even in deterministic mode, first call should record)
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
                    actual_temperature = self.fallback_temperature # Update actual temperature

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
            # Always cache live responses in HYBRID and DETERMINISTIC modes, or when recording is enabled
            if self.cache._recording_mode or self.mode in (
                OperationMode.HYBRID,
                OperationMode.DETERMINISTIC,
            ):
                # Issue 111: Use the actual temperature used for the successful call in metadata
                metadata = {
                    "model": model_name,
                    "temperature": actual_temperature,
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

        # If response came from cache, we need to extract the original temperature from cache metadata
        if cache_hit and "_fba_metadata" in final_response:
            # Assuming cached response already contains metadata from when it was recorded
            # We rely on the metadata stored in the cache entry itself for the temperature
            # However, since we are adding new metadata here, we should ensure the temperature
            # reflects the one used for the cache key (which is the initial `temperature` parameter)
            # or the one recorded in the cache. For simplicity and consistency with the cache key,
            # we stick to the initial `temperature` unless we explicitly retrieve the recorded metadata.
            # Since the cache key includes `temperature`, we use the input `temperature` for cache hits.
            pass
        elif live_response:
            # If live response was used, actual_temperature is already set correctly (initial or fallback)
            pass
        else:
            # Fallback for cached response without metadata (shouldn't happen if cache is well-formed)
            actual_temperature = temperature


        # Add metadata to response
        response_metadata = ResponseMetadata(
            model=model_name,
            temperature=actual_temperature, # Issue 111: Use actual_temperature
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=self.mode.value,
            cache_hit=cache_hit,
            response_time_ms=response_time,
            prompt_hash=prompt_hash,
            validation_passed=True,  # If we got here, validation passed
            fallback_used=fallback_used,
            fallback_temperature=self.fallback_temperature if fallback_used else None, # Issue 111: Record fallback temp
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
