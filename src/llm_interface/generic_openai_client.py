import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx
import tiktoken
from services.cost_tracking_service import CostTrackingService

from llm_interface.contract import BaseLLMClient, LLMClientError

logger = logging.getLogger(__name__)


class GenericOpenAIClient(BaseLLMClient):
    """
    Generic OpenAI-compatible LLM client.
    """

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str],
        base_url: Optional[str],
        cost_tracker: Optional[CostTrackingService] = None,
    ):
        super().__init__(model_name, api_key, base_url)
        if not base_url:
            raise ValueError(
                "GenericOpenAIClient requires a base_url for the OpenAI-compatible endpoint."
            )
        if not api_key:
            raise ValueError("GenericOpenAIClient requires an API key.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
        self.cost_tracker = cost_tracker

        try:
            self.encoding = tiktoken.encoding_for_model(self.model_name)
        except KeyError:
            logger.warning(
                f"Could not find tiktoken encoding for model '{self.model_name}'. "
                "Using 'cl100k_base' as fallback."
            )
            self.encoding = tiktoken.get_encoding("cl100k_base")

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        referer = os.getenv("OPENAI_COMPAT_SITE_URL", "https://fba-bench.com")
        app_title = os.getenv("OPENAI_COMPAT_APP_TITLE", "FBA-Bench")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": referer,
            "X-Title": app_title,
            "Content-Type": "application/json",
        }
        req_id = kwargs.pop("request_id", None)
        if req_id:
            headers["X-Request-Id"] = req_id

        messages = [{"role": "user", "content": prompt}]

        wants_completion_tokens = str(self.model_name).lower().startswith(
            ("gpt-5", "gpt-4.1", "o4", "o4-mini")
        ) or bool(kwargs.pop("use_max_completion_tokens", False))
        token_key = "max_completion_tokens" if wants_completion_tokens else "max_tokens"

        if wants_completion_tokens:
            kwargs.pop("max_tokens", None)

        effective_temperature = kwargs.pop("temperature", temperature)
        if wants_completion_tokens:
            effective_temperature = 1

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": effective_temperature,
            token_key: max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        payload.update(kwargs)

        try:
            response = await self.http_client.post(
                "/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("choices") or not isinstance(
                response_data["choices"], list
            ):
                raise LLMClientError(
                    f"Response missing 'choices' list: {response_data}"
                )

            first_choice = response_data["choices"][0]
            if (
                not first_choice.get("message")
                or "content" not in first_choice["message"]
            ):
                raise LLMClientError(
                    f"Response missing message object in choices: {response_data}"
                )

            if self.cost_tracker and response_data.get("usage"):
                self.cost_tracker.record_usage(
                    model=self.model_name, usage=response_data["usage"]
                )

            return response_data

        except httpx.HTTPStatusError as e:
            raise LLMClientError(
                f"OpenAI-compatible API returned an HTTP error: {e.response.status_code} - {e.response.text}",
                original_exception=e,
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise LLMClientError(
                f"Network error connecting to OpenAI-compatible API: {e}",
                original_exception=e,
            )
        except Exception as e:
            raise LLMClientError(
                f"Unexpected error during OpenAI-compatible API call: {e}",
                original_exception=e,
            )

    async def get_token_count(self, text: str) -> int:
        """
        Fix #109: Run tiktoken on a separate thread to avoid blocking the event loop.
        """
        return await asyncio.to_thread(lambda: len(self.encoding.encode(text)))
