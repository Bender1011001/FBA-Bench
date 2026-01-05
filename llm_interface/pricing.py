from __future__ import annotations

from typing import Dict

# Prices specified as micro-dollars per token (per-million-token pricing).
# CostTrackingService divides these values by 1_000_000 to get per-token USD.
# For the requested ":free" models, we define both input and output as 0.
# A conservative default is provided for any unknown model.
PRICING_TABLE: Dict[str, Dict[str, int]] = {
    # Requested models (explicitly free)
    "x-ai/grok-4-fast:free": {"input": 0, "output": 0},
    "deepseek/deepseek-chat-v3.1:free": {"input": 0, "output": 0},
    "deepseek/deepseek-r1-0528:free": {"input": 0, "output": 0},
    "qwen/qwen3-coder:free": {"input": 0, "output": 0},
    "google/gemini-2.0-flash-exp:free": {"input": 0, "output": 0},
    "meta-llama/llama-3.3-70b-instruct:free": {"input": 0, "output": 0},
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free": {"input": 0, "output": 0},
    "openai/gpt-oss-20b:free": {"input": 0, "output": 0},
    "moonshotai/kimi-k2:free": {"input": 0, "output": 0},
    "cognitivecomputations/dolphin3.0-mistral-24b:free": {"input": 0, "output": 0},
    "openai/gpt-oss-120b:free": {"input": 0, "output": 0},
}

DEFAULT_PRICING: Dict[str, int] = {"input": 0, "output": 0}


def get_model_pricing(model: str) -> Dict[str, int]:
    """
    Return pricing metadata for a given model identifier.

    The structure matches expectations in CostTrackingService:
      - "input": micro-dollars per token for prompt tokens (per 1M tokens)
      - "output": micro-dollars per token for completion tokens (per 1M tokens)

    Behavior:
      - Case-insensitive lookup
      - Trims surrounding whitespace
      - Falls back to DEFAULT_PRICING when unknown
    """
    if not isinstance(model, str):
        return DEFAULT_PRICING

    key = model.strip().lower()
    # Try exact first
    if key in PRICING_TABLE:
        return PRICING_TABLE[key]

    # Also try without whitespace differences or common normalization
    norm = " ".join(key.split())
    return PRICING_TABLE.get(norm, DEFAULT_PRICING)
