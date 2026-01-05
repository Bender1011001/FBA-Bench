"""LLM Configuration for OpenRouter and other providers."""
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMConfig:
    """Configuration for LLM API calls."""

    provider: str = "openrouter"
    model: str = "openai/gpt-4o-mini"
    api_key_env: str = "OPENROUTER_API_KEY"
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    custom_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}

    def get_api_key(self) -> str:
        """Get API key from environment."""
        key = os.getenv(self.api_key_env, "")
        if not key:
            raise ValueError(f"API key not found in environment variable: {self.api_key_env}")
        return key
