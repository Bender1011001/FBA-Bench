from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm", tags=["LLM"])


class LLMTestRequest(BaseModel):
    model: str = Field(
        ..., description="OpenRouter model id, e.g. deepseek/deepseek-chat-v3.1:free"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Optional prompt; defaults to a minimal JSON-returning ping to avoid long outputs",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=400, gt=0, le=8192)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)


class LLMTestResponse(BaseModel):
    ok: bool
    model: str
    content: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None


@router.post("/test", response_model=LLMTestResponse, status_code=status.HTTP_200_OK)
async def test_llm(req: LLMTestRequest) -> LLMTestResponse:
    """
    Minimal OpenRouter ping to verify free models and connectivity.
    Uses OPENROUTER_API_KEY from environment. Does not incur costs when using :free models.
    """
    # Validate API key presence via config (OpenRouterClient enforces it too)
    api_key_env = "OPENROUTER_API_KEY"
    if not os.getenv(api_key_env):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing environment variable {api_key_env}. Set your OpenRouter API key.",
        )

    # Enforce free-tier models only to prevent any accidental billing
    model_id = (req.model or "").strip()
    if ":free" not in model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only free-tier models are allowed via this endpoint. Use ids ending with ':free'.",
        )

    # Build client config
    cfg = LLMConfig(
        provider="openrouter",
        model=req.model,
        api_key_env=api_key_env,
        base_url=os.getenv("OPENROUTER_BASE_URL") or None,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        top_p=req.top_p,
        custom_params={},
    )

    client = OpenRouterClient(cfg)

    # Safe minimal JSON prompt by default to keep responses compact
    prompt = (
        req.prompt
        or 'Respond ONLY with a compact JSON object: {"ping": "pong", "ok": true}'
    )

    try:
        resp = await client.generate_response(
            prompt=prompt,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            top_p=req.top_p,
            response_format={"type": "json_object"},
            referer=os.getenv("OPENROUTER_REFERER", "https://fba-bench.local"),
            app_title=os.getenv("OPENROUTER_APP_TITLE", "FBA-Bench"),
        )
    except Exception as e:
        logger.error(
            "OpenRouter test failed for model %s: %s", req.model, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM call failed: {e!s}"
        )

    # Try to extract content content (OpenAI-like shape) but return raw always
    content: Optional[str] = None
    try:
        content = (
            resp.get("choices", [{}])[0].get("message", {}).get("content")  # type: ignore[assignment]
        )
    except Exception:
        content = None

    return LLMTestResponse(
        ok=True, model=req.model, content=content, raw=resp, message="LLM test ok"
    )


@router.get("/models", description="List supported LLM models for agents")
async def list_models():
    """
    Returns a list of supported LLM models.
    In the future, this could be fetched from OpenRouter or a dynamic configuration.
    """
    # Curated list of models known to work well with FBA-Bench
    return {
        "models": [
            {
                "id": "gpt-4o",
                "name": "GPT-4o (OpenAI)",
                "provider": "openrouter",
                "is_free": False,
            },
            {
                "id": "openai/gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "openrouter",
                "is_free": False,
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "provider": "openrouter",
                "is_free": False,
            },
            {
                "id": "google/gemini-2.0-flash-001",
                "name": "Gemini 2.0 Flash",
                "provider": "openrouter",
                "is_free": False,
            },
            {
                "id": "deepseek/deepseek-chat",
                "name": "DeepSeek V3",
                "provider": "openrouter",
                "is_free": False,
            },
            {
                "id": "deepseek/deepseek-chat-v3.1:free",
                "name": "DeepSeek V3 (Free)",
                "provider": "openrouter",
                "is_free": True,
            },
            {
                "id": "greedy-baseline",
                "name": "Greedy Baseline (No LLM)",
                "provider": "builtin",
                "is_free": True,
            },
            {
                "id": "human-manual",
                "name": "Human Strategy (Manual)",
                "provider": "user",
                "is_free": True,
            },
        ]
    }
