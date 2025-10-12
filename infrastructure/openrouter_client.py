import asyncio
import logging
import os
from typing import Dict, Optional, Any

import httpx

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """
    Async client for OpenRouter API v1.
    Supports chat completions with model slugs including :free variants.
    Handles retries for rate limits (429) with exponential backoff.
    Captures usage and cost from response if available.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        initial_backoff_ms: int = 1000,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", ""),  # Optional
            "X-Title": os.getenv("OPENROUTER_TITLE", "FBA-Bench"),  # Optional
        }
        self.session = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()

    async def chat_completions(
        self,
        model: str,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Send chat completion request to OpenRouter.

        Args:
            model: Model slug (e.g., "x-ai/grok-4-fast:free")
            prompt: User prompt string
            max_tokens: Optional max tokens limit (from budget enforcer)
            temperature: Sampling temperature

        Returns:
            Dict with 'content' (response text), 'usage' (tokens), 'cost' (estimated USD)

        Raises:
            aiohttp.ClientError: On API errors after retries
        """
        if not model:
            model = os.getenv("MODEL_SLUG", "openai/gpt-4o-mini")  # Fallback

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        backoff_ms = self.initial_backoff_ms
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.session.post("/chat/completions", json=payload)
                response.raise_for_status()

                data = response.json()

                # Extract response
                choice = data["choices"][0]
                content = choice["message"]["content"]

                # Capture usage if present
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

                # Estimate cost (OpenRouter provides this in some responses, fallback to model-specific)
                cost = data.get("cost", 0.0)  # If provided
                if not cost:
                    # Rough estimate: $0.002 / 1k tokens (adjust per model if needed)
                    cost = (total_tokens / 1000.0) * 0.002

                logger.info(
                    f"OpenRouter call succeeded: model={model}, tokens={total_tokens}, "
                    f"cost=${cost:.6f}"
                )

                return {
                    "content": content,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "cost": cost,
                }

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 429 and attempt < self.max_retries:
                    wait_time = backoff_ms / 1000.0
                    logger.warning(
                        f"Rate limit (429) on attempt {attempt + 1}/{self.max_retries}, waiting {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
                    backoff_ms *= 2
                    continue
                if status >= 500 and attempt < self.max_retries:
                    wait_time = backoff_ms / 1000.0
                    logger.warning(
                        f"Server error ({status}) on attempt {attempt + 1}, waiting {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
                    backoff_ms *= 2
                    continue
                logger.error(f"OpenRouter API error: {status} - {e}")
                raise

            except Exception as e:
                logger.error(f"Unexpected error in OpenRouter call: {e}")
                if attempt < self.max_retries:
                    wait_time = backoff_ms / 1000.0
                    await asyncio.sleep(wait_time)
                    backoff_ms *= 2
                    continue
                raise

        raise RuntimeError("Max retries exceeded for OpenRouter call")