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

    referer = os.getenv("OPENROUTER_REFERER", "https://github.com/fba-bench/fba-bench-enterprise")
    title = os.getenv("OPENROUTER_TITLE", "FBA-Bench")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title
    return headers


def _parse_usage_and_cost_from_headers(h: "aiohttp.typedefs.LooseHeaders") -> Dict[str, Union[int, float]]:
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

    prompt_tokens = _get_int("x-usage-prompt-tokens") or _get_int("openrouter-usage-prompt-tokens")
    completion_tokens = _get_int("x-usage-completion-tokens") or _get_int("openrouter-usage-completion-tokens")
    total_tokens = (
        _get_int("x-usage-total-tokens")
        or _get_int("openrouter-usage-total-tokens")
        or (prompt_tokens + completion_tokens)
    )
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
    out = dict(fallback)
    out.update({k: v for k, v in primary.items() if v})
    out.setdefault("prompt_tokens", 0)
    out.setdefault("completion_tokens", 0)
    out.setdefault("total_tokens", out["prompt_tokens"] + out["completion_tokens"])
    out.setdefault("cost", 0.0)
    return out


# ---- Client ------------------------------------------------------------------

class OpenRouterClient:
    """
    Async client for OpenRouter API v1.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        initial_backoff_ms: int = 1000,
        max_connections: int = 10,
    ):
        self.api_key = api_key
        # Fix #106: Strip trailing slash to ensure clean URL construction later
        self.base_url = base_url.rstrip("/")
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
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

                body_text = await resp.text()
                detail = f"status={resp.status} reason={resp.reason} url={resp.url} body={body_text[:1024]}"
                logger.warning(f"OpenRouter non-2xx: {detail}")

                retryable = resp.status in (429, 500, 502, 503, 504)
                if retryable and attempt < self.max_retries:
                    wait = (backoff_ms / 1000.0) * (1.0 + random.uniform(0.0, 0.25))
                    logger.info(f"Retrying in {wait:.2f}s (attempt {attempt+1}/{self.max_retries})")
                    await asyncio.sleep(wait)
                    backoff_ms *= 2
                    continue

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

        # Fix #106: Clean URL construction (base_url is already stripped)
        url = f"{self.base_url}/chat/completions"
        resp = await self._request_with_retries("POST", url, json=payload)

        # Fix #107: Remove content_type=None to enforce correct content type validation
        data = await resp.json()

        try:
            choice0 = data["choices"][0]
            msg = choice0.get("message") or choice0.get("delta") or {}
            content = msg.get("content")
            if content is None:
                content = choice0.get("text", "")
        except Exception as e:
            logger.error(f"Malformed response structure: {e!r} | data keys: {list(data.keys())}")
            raise

        json_usage = data.get("usage") or {}
        primary_usage = {
            "prompt_tokens": json_usage.get("prompt_tokens", 0),
            "completion_tokens": json_usage.get("completion_tokens", 0),
            "total_tokens": json_usage.get("total_tokens", 0),
            "cost": 0.0,
        }

        header_usage = _parse_usage_and_cost_from_headers(resp.headers)
        merged = _merge_usage(primary_usage, header_usage)

        if not merged.get("cost"):
            total_tokens = merged.get("total_tokens", 0)
            merged["cost"] = (total_tokens / 1000.0) * 0.002

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

    async def get_token_count(self, text: str) -> int:
        """
        Fix #108: CPU-bound token counting run in thread to avoid blocking event loop.
        """
        # Note: tiktoken is not included here as this class relies on API for usage,
        # but if we needed local estimation:
        import tiktoken
        def _count():
            try:
                # Use a common encoding if model specific one fails or is unavailable
                enc = tiktoken.encoding_for_model("gpt-4")
                return len(enc.encode(text))
            except Exception:
                # Fallback to a rough estimate if tiktoken fails
                return len(text) // 4
        
        return await asyncio.to_thread(_count)
