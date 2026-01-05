"""OpenRouter LLM Client wrapper for baseline_bots integration."""
import logging
from typing import Any, Dict, Optional

from infrastructure.openrouter_client import OpenRouterClient as InfraClient
from llm_interface.config import LLMConfig

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """
    Wrapper for infrastructure.OpenRouterClient to provide interface expected by OpenRouterBot.
    Handles authentication, retries, and response formatting for OpenRouter API.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize OpenRouter client with configuration.

        Args:
            config: LLMConfig with provider="openrouter", model, and auth details
        """
        self.config = config
        self.api_key = config.get_api_key()
        self.model = config.model
        self.base_url = config.base_url or "https://openrouter.ai/api/v1"
        self._client: Optional[InfraClient] = None

    async def generate_response(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate LLM response via OpenRouter API.

        Args:
            prompt: The user prompt
            temperature: Override config temperature (default: use config)
            max_tokens: Override config max_tokens (default: use config)
            top_p: Override config top_p (default: use config)

        Returns:
            Dict with OpenAI-like structure: {"choices": [{"message": {"content": "..."}}], "usage": {...}}

        Raises:
            Exception: On API errors after retries
        """
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        top = top_p if top_p is not None else self.config.top_p

        # Use context manager for session management
        async with InfraClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout_seconds=60.0,
            max_retries=3,
        ) as client:
            result = await client.chat_completions(
                model=self.model,
                prompt=prompt,
                max_tokens=tokens,
                temperature=temp,
            )

            # Convert infrastructure client result to OpenAI-like format
            return {
                "choices": [
                    {
                        "message": {
                            "content": result.get("content", ""),
                            "role": "assistant",
                        },
                        "finish_reason": "stop",
                        "index": 0,
                    }
                ],
                "usage": result.get("usage", {}),
                "model": self.model,
                "cost": result.get("cost", 0.0),
            }
