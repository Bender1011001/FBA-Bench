import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
import tiktoken

from llm_interface.llm_config import LLMConfig  # Imported LLMConfig
from llm_interface.contract import BaseLLMClient, LLMClientError

logger = logging.getLogger(__name__)

# Best-effort .env loader so OPENROUTER_API_KEY in .env becomes visible to os.getenv()
try:
    from dotenv import load_dotenv  # type: ignore

    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False


class OpenRouterClient(BaseLLMClient):
    """
    LLM client for OpenRouter API, adhering to BaseLLMClient interface.
    Uses httpx for asynchronous requests and tiktoken for token counting.
    """

    def __init__(self, config: LLMConfig):  # Modified to accept LLMConfig
        # Resolve API key from environment variable name provided in config.api_key_env
        api_key_env_name = config.api_key_env
        if not api_key_env_name:
            raise ValueError(
                "OpenRouterClient requires LLMConfig.api_key_env to be set to the API key env var name (e.g., 'OPENROUTER_API_KEY')."
            )
        api_key_value = os.getenv(api_key_env_name)
        # If not found in process env, attempt to load from .env (local dev)
        if not api_key_value and _HAS_DOTENV:
            try:
                load_dotenv()
                api_key_value = os.getenv(api_key_env_name)
            except (OSError, AttributeError):
                pass
        if not api_key_value:
            raise ValueError(
                f"Environment variable '{api_key_env_name}' is not set or empty for OpenRouter API key."
            )
        # Sanitize key: remove accidental quotes/whitespace from .env
        api_key_value = api_key_value.strip()
        if (api_key_value.startswith('"') and api_key_value.endswith('"')) or (
            api_key_value.startswith("'") and api_key_value.endswith("'")
        ):
            api_key_value = api_key_value[1:-1].strip()

        super().__init__(
            config.model, api_key_value, config.base_url
        )  # Pass resolved API key to base
        self.config = config  # Store full config
        self.api_key_env_name = api_key_env_name
        self.api_key = api_key_value

        self.base_url = (
            config.base_url or "https://openrouter.ai/api/v1"
        )  # Use config base_url or default
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url, timeout=config.timeout
        )  # Use config timeout

        # Initialize tiktoken for token counting (compatible with OpenAI models)
        try:
            self.encoding = tiktoken.encoding_for_model(
                self.config.model
            )  # Use config.model
        except KeyError:
            logger.warning(
                f"Could not find tiktoken encoding for model '{self.config.model}'. Using 'cl100k_base' as fallback. Token counts might be inaccurate."
            )
            self.encoding = tiktoken.get_encoding("cl100k_base")

    async def aclose(self) -> None:  # Added aclose method for httpx.AsyncClient
        """Close the underlying HTTP client session."""
        await self.http_client.aclose()

    async def generate_response(
        self,
        prompt: str,
        # Default values now come from config, with optional overrides via kwargs or method parameters
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        response_format: Optional[
            Dict[str, str]
        ] = None,  # Default for structured output
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generates a structured response from the LLM based on the given prompt using OpenRouter API.

        Args:
            prompt: The formatted prompt string.
            temperature: Sampling temperature for the model.
            max_tokens: Maximum tokens to generate in the completion.
            response_format: Specifies the format of the response (e.g., {"type": "json_object"}).
            **kwargs: Additional parameters to pass to the OpenRouter API (e.g., top_p, frequency_penalty).

        Returns:
            A dictionary containing the LLM's raw response, similar to OpenAI's chat completions format.

        Raises:
            LLMClientError: If there is an issue communicating with the LLM API or receiving a valid response.
        """
        # OpenRouter recommends providing site URL and title for better routing/analytics.
        # These should be passed externally or configured centrally.
        # For now, keeping as environment variables (or can be added to LLMConfig if desired).
        referer = kwargs.pop(
            "referer", "http://localhost:3000"
        )  # Allow override for site URL (local dev default)
        app_title = kwargs.pop(
            "app_title", "FBA-Bench Dev"
        )  # Allow override for app title (local dev)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": referer,
            "X-Title": app_title,
            "X-Request-Id": kwargs.pop(
                "request_id", ""
            ),  # Optional: for tracing requests
            "Content-Type": "application/json",  # Explicitly set content type
        }

        # OpenRouter API expects messages array for chat completions
        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": (
                temperature if temperature is not None else self.config.temperature
            ),
            "top_p": top_p if top_p is not None else self.config.top_p,
            "frequency_penalty": (
                frequency_penalty
                if frequency_penalty is not None
                else self.config.frequency_penalty
            ),
            "presence_penalty": (
                presence_penalty
                if presence_penalty is not None
                else self.config.presence_penalty
            ),
            **kwargs,
        }

        # Only include max_tokens if explicitly set (allows "no limit" by omission).
        mt = max_tokens if max_tokens is not None else self.config.max_tokens
        if mt is not None:
            payload["max_tokens"] = int(mt)

        # Fix #86: Only include response_format if explicitly provided
        if response_format is not None:
            payload["response_format"] = response_format

        # Log Level based control for payload details
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Calling OpenRouter API for model {self.config.model} with payload: {json.dumps(payload, indent=2)}"
            )

        try:
            response = await self.http_client.post(
                self.base_url + "/chat/completions",  # Use base_url from config
                headers=headers,
                json=payload,
                timeout=self.config.timeout,  # Use config timeout for individual requests as well (may be None)
            )
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            try:
                response_data = response.json()
            except ValueError as e:
                # OpenRouter can occasionally return a truncated/non-JSON body (network/proxy issues).
                body = ""
                try:
                    body = response.text
                except Exception:
                    body = "<unreadable body>"
                snippet = body[:2000]
                logger.error(
                    "Failed to decode OpenRouter JSON response: %s; body_snippet=%r",
                    e,
                    snippet,
                )
                raise LLMClientError(
                    f"OpenRouter returned a non-JSON response (status {response.status_code}).",
                    original_exception=e,
                    status_code=response.status_code,
                )

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"Received response from OpenRouter: {json.dumps(response_data, indent=2)}"
                )

            # Basic validation of response structure, allowing for non-strict OpenAI-like responses
            if not response_data.get("choices") or not isinstance(
                response_data["choices"], list
            ):
                # This could be a valid response from a non-OpenAI-compatible model
                logger.warning(
                    f"OpenRouter response missing 'choices' field or not a list, but returning raw response. Response: {response_data}"
                )
                return response_data  # Return raw response if not conforming to expected structure
            if not response_data["choices"][0].get("message") or not response_data[
                "choices"
            ][0]["message"].get("content"):
                logger.warning(
                    f"OpenRouter response missing message content in choices, but returning raw response. Response: {response_data}"
                )
                return response_data  # Return raw response if not conforming to expected structure

            return response_data

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error connecting to OpenRouter API: {e.response.status_code} - {e.response.text}"
            )
            raise LLMClientError(
                f"OpenRouter API returned an HTTP error: {e.response.status_code} - {e.response.text}",
                original_exception=e,
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error(f"Network error connecting to OpenRouter API: {e}")
            raise LLMClientError(
                f"Network error connecting to OpenRouter API: {e}", original_exception=e
            )
        except (TypeError, AttributeError, RuntimeError, KeyError, ValueError) as e:
            logger.error(
                f"An unexpected error occurred during OpenRouter API call: {e}",
                exc_info=True,
            )
            raise LLMClientError(
                f"An unexpected error occurred during OpenRouter API call: {e}",
                original_exception=e,
            )

    async def get_token_count(self, text: str) -> int:
        """
        Calculates the token count for a given text using tiktoken.
        """
        # tiktoken requires encoding text, not messages.
        # For actual prompt/completion token calculation, typically the OpenAI API returns usage info.
        # This method is for client-side estimation if needed, like for preprompt components.
        return len(self.encoding.encode(text))
