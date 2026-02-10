"""
Configuration classes for Language Model (LLM) interfaces in FBA-Bench.

This module defines the `LLMConfig` dataclass, which is used to specify
the configuration parameters for interacting with various LLM providers and models.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse


@dataclass
class LLMConfig:
    """
    Configuration for an LLM provider and model.
    """

    provider: str  # e.g., "openai", "openrouter", "google"
    model: str  # e.g., "gpt-4o-mini", "google/gemini-flash-2.5"
    api_key_env: Optional[str] = None  # Environment variable name for API key
    base_url: Optional[str] = None  # Custom base URL for API endpoint
    temperature: float = 0.7  # Creativity/randomness of output
    # If None, the client should omit max_tokens and let the provider/model decide.
    max_tokens: Optional[int] = 1024  # Maximum tokens in the response
    top_p: float = 1.0  # Nucleus sampling parameter
    frequency_penalty: float = 0.0  # Penalty for new tokens based on their frequency
    presence_penalty: float = (
        0.0  # Penalty for new tokens based on whether they appear in the text so far
    )
    # If None, the client may disable network timeouts (not recommended for most usage).
    timeout: Optional[float] = 60  # Request timeout in seconds
    max_retries: int = 3  # Maximum number of retries for failed requests

    # Provider-specific parameters that don't fit into generic fields
    custom_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Validate configuration values early to surface misconfiguration fast.
        """
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("provider must be a non-empty string")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        if not (0.0 <= float(self.temperature) <= 2.0):
            raise ValueError("temperature must be within [0.0, 2.0]")
        if self.max_tokens is not None and int(self.max_tokens) <= 0:
            raise ValueError("max_tokens must be > 0 when set")
        if not (0.0 <= self.top_p <= 1.0):
            raise ValueError("top_p must be within [0.0, 1.0]")
        if not (-2.0 <= self.frequency_penalty <= 2.0):
            raise ValueError("frequency_penalty must be within [-2.0, 2.0]")
        if not (-2.0 <= self.presence_penalty <= 2.0):
            raise ValueError("presence_penalty must be within [-2.0, 2.0]")
        if self.timeout is not None and float(self.timeout) <= 0:
            raise ValueError("timeout must be > 0 when set")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        if self.base_url:
            parsed = urlparse(self.base_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"Invalid base_url: {self.base_url}")

        # Do not enforce API key presence here: some clients support loading from .env or
        # other late-binding mechanisms. The client should raise a clear error if it
        # cannot resolve credentials at call time.
