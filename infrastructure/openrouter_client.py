import asyncio
import logging
import os
import random
from typing import Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ClientResponseError, ClientTimeout

logger = logging.getLogger(__name__)

# ---- Utility helpers ---------------------------------------------------------

def _build_default_headers(api_key: str) -> Dict[str, str]:
    if not api_key:
        raise ValueError("OpenRouter API key is required")

    # OpenRouter attribution headers (HTTP-Referer + X-Title)
    referer = os.getenv("OPENROUTER_REFERER", "https://github.com/fba-bench/fba-bench-enterprise")
    title = os.getenv("OPENROUTER_TITLE", "FBA-Bench")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Fixed: Use HTTP-Referer instead of Referer
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title
    return headers


def _parse_usage_and_cost_from_headers(h: "aiohttp.typedefs.LooseHeaders") -> Dict[str, Union[int, float]]:
    """
    OpenRouter often returns usage in headers. Handle the common variants.
    """
    lh = {k.lower(): v for k, v in h.items()}

    def _get_int(key: str) -> int:
        v = lh.get(key)
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0

    def _get_float(key: str) -> float:
        v = lh.get(key)
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    # Common header keys observed in the wild (case-insensitive)
    prompt_tokens = _get_int("x-usage-prompt-tokens") or _get_int("openrouter-usage-prompt-tokens")
    completion_tokens = _get_int("x-usage-completion-tokens") or _get_int("openrouter-usage-completion-tokens")
    total_tokens = (
        _get_int("x-usage-total-tokens")
        or _get_int("openrouter-usage-total-tokens")
        or (prompt_tokens + completion_tokens)
    )
    # Cost headers (OpenRouter sometimes exposes request cost)
    cost = (
        _get_float("x-usage-cost")
        or _get_float("x-request-cost")
        or _get_float("openrouter-usage-cost")
        or 0.0
    )

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
    }


def _merge_usage(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer primary values when present; otherwise take fallback."""
    out = dict(fallback)
    out.update({k: v for k, v in primary.items() if v})
    # Ensure integers/floats with sane defaults
    out.setdefault("prompt_tokens", 0)
    out.setdefault("completion_tokens", 0)
    out.setdefault("total_tokens", out["prompt_tokens"] + out["completion_tokens"])
    out.setdefault("cost", 0.0)
    return out


# ---- Client ------------------------------------------------------------------

class OpenRouterClient:
    """
    Async client for OpenRouter API v1.
    - Robust retries with exponential backoff + jitter for 429/5xx.
    - Proper attribution headers (HTTP-Referer, X-Title).
    - Extracts usage and cost from JSON and/or headers.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        initial_backoff_ms: int = 1000,
        max_connections: int = 10,
        fallback_cost_per_1k: float = 0.002,  # Configurable default
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.fallback_cost_per_1k = fallback_cost_per_1k
        self.session: Optional[aiohttp.ClientSession] = None
        self._connector = aiohttp.TCPConnector(limit=max_connections, enable_cleanup_closed=True)

    async def __aenter__(self):
        headers = _build_default_headers(self.api_key)
        self.session = aiohttp.ClientSession(headers=headers, timeout=self.timeout, connector=self._connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None
        # Explicitly close connector to ensure no leakage if session didn't own it fully or if closed early
        if self._connector and not self._connector.closed:
            await self._connector.close()

    async def _request_with_retries(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        if not self.session:
            raise RuntimeError("Client session not initialized. Use `async with OpenRouterClient(...)`.")

        backoff_ms = self.initial_backoff_ms
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = await self.session.request(method, url, **kwargs)
                if resp.status >= 200 and resp.status < 300:
                    return resp

                # Non-2xx: check if retryable
                # Fix #81: Only read truncated body to avoid memory issues with large error pages
                # We read up to 2KB to capture enough context without loading massive payloads
                raw_body = await resp.read()
                body_text = raw_body.decode(errors='replace')[:2048]
                if len(raw_body) > 2048:
                    body_text += "... (truncated)"

                detail = f"status={resp.status} reason={resp.reason} url={resp.url} body={body_text}"
                logger.warning(f"OpenRouter non-2xx: {detail}")

                retryable = resp.status in (429, 500, 502, 503, 504)
                if retryable and attempt < self.max_retries:
                    wait = (backoff_ms / 1000.0) * (1.0 + random.uniform(0.0, 0.25))
                    logger.info(f"Retrying in {wait:.2f}s (attempt {attempt+1}/{self.max_retries})")
                    await asyncio.sleep(wait)
                    backoff_ms *= 2
                    continue

                # Fix #82: Pass truncated body text to exception
                raise ClientResponseError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    message=body_text,
                    headers=resp.headers,
                )

            except (aiohttp.ClientConnectionError, aiohttp.ServerTimeoutError) as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = (backoff_ms / 1000.0) * (1.0 + random.uniform(0.0, 0.25))
                    logger.info(f"Transport error: {e!r}. Retrying in {wait:.2f}s")
                    await asyncio.sleep(wait)
                    backoff_ms *= 2
                    continue
                break
            except ClientResponseError as e:
                last_exc = e
                break
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = (backoff_ms / 1000.0) * (1.0 + random.uniform(0.0, 0.25))
                    logger.info(f"Unexpected error: {e!r}. Retrying in {wait:.2f}s")
                    await asyncio.sleep(wait)
                    backoff_ms *= 2
                    continue
                break

        # Exhausted
        if last_exc:
            raise last_exc
        raise RuntimeError("OpenRouter request failed with unknown error")

    async def chat_completions(
        self,
        model: Optional[str],
        prompt: Optional[str] = None,
        *,
        messages: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke the /chat/completions endpoint.

        Args:
            model: e.g. "x-ai/grok-4-fast:free"
            prompt: convenience param; if provided, wrapped into messages=[{"role":"user","content": prompt}]
            messages: full chat messages payload; takes precedence over `prompt` if provided
            max_tokens: optional cap
            temperature: float
            response_format: e.g. {"type": "json_object"} or {"type": "text"}
            extra: any additional OpenRouter/OpenAI-compatible params to merge into payload

        Returns:
            {
              "content": <str>,
              "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int},
              "cost": <float>,
              "raw": <raw JSON dict>
            }
        """
        if not model:
            model = os.getenv("MODEL_SLUG", "openai/gpt-4o-mini")

        if messages is None:
            if prompt is None:
                raise ValueError("Either `messages` or `prompt` must be provided.")
            messages = [{"role": "user", "content": prompt}]

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        if extra:
            payload.update(extra)

        url = f"{self.base_url}/chat/completions"
        resp = await self._request_with_retries("POST", url, json=payload)

        # Parse JSON body first
        data = await resp.json(content_type=None)

        # Extract message content (non-streaming)
        try:
            choice0 = data["choices"][0]
            # Handle both message and delta fields for completeness
            msg = choice0.get("message") or choice0.get("delta") or {}
            content = msg.get("content")
            if content is None:
                # Additional fallback for non-chat completions
                content = choice0.get("text", "")
        except Exception as e:
            logger.error(f"Malformed response structure: {e!r} | data keys: {list(data.keys())}")
            raise

        # Usage/cost from JSON (OpenAI-style)
        json_usage = data.get("usage") or {}
        primary_usage = {
            "prompt_tokens": json_usage.get("prompt_tokens", 0),
            "completion_tokens": json_usage.get("completion_tokens", 0),
            "total_tokens": json_usage.get("total_tokens", 0),
            "cost": 0.0,  # OpenRouter doesn't return cost in response body
        }

        # Merge with header-derived usage/cost
        header_usage = _parse_usage_and_cost_from_headers(resp.headers)
        merged = _merge_usage(primary_usage, header_usage)

        # If still no cost, provide conservative estimate (fallback)
        if not merged.get("cost"):
            total_tokens = merged.get("total_tokens", 0)
            # Fix #87: Use configurable cost model instead of hardcoded 0.002
            merged["cost"] = (total_tokens / 1000.0) * self.fallback_cost_per_1k

        logger.info(
            "OpenRouter call ok: model=%s, total_tokens=%s, cost=$%.6f",
            model, merged["total_tokens"], merged["cost"]
        )

        return {
            "content": content,
            "usage": {
                "prompt_tokens": merged["prompt_tokens"],
                "completion_tokens": merged["completion_tokens"],
                "total_tokens": merged["total_tokens"],
            },
            "cost": float(merged["cost"]),
            "raw": data,
        }
