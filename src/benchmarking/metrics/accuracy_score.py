from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

try:
    # Pydantic v2
    from pydantic import BaseModel, Field, ValidationError
except Exception:  # pragma: no cover

    class BaseModel:  # type: ignore
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self, *_, **__):
            return self.__dict__

    def Field(*_, **__):  # type: ignore
        return None


from .registry import register_metric

logger = logging.getLogger(__name__)


# -----------------------------
# Schemas
# -----------------------------
class AccuracyInput(BaseModel):
    output: Any = Field(description="Model/scenario output; may be str or structured")

    # Optional: allow evaluating nested field by context.path (dot-notation)
    class Config:
        frozen = False


class AccuracyContext(BaseModel):
    expected_output: Any = Field(description="Reference answer, str or structured")
    mode: str = Field(default="exact", description="exact|overlap")
    field_path: Optional[str] = Field(
        default=None,
        description="Optional dot-path to extract from outputs for comparison",
    )
    tokenizer: str = Field(
        default="simple", description="simple tokenizer for overlap mode"
    )
    case_insensitive: bool = Field(default=True)
    strip_punctuation: bool = Field(default=True)

    class Config:
        frozen = False


class AccuracyOutput(BaseModel):
    accuracy: float = Field(ge=0.0, le=1.0)
    mode: str

    def as_dict(self) -> Dict[str, Any]:
        return {"accuracy": float(self.accuracy), "mode": str(self.mode)}


# -----------------------------
# Helpers
# -----------------------------
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _to_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (str, bytes)):
        return x.decode("utf-8", errors="ignore") if isinstance(x, bytes) else x
    return str(x)


def _extract_by_path(obj: Any, path: Optional[str]) -> Any:
    if not path or not isinstance(obj, dict):
        return obj
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _tokenize_simple(
    s: str, case_insensitive: bool, strip_punctuation: bool
) -> List[str]:
    if strip_punctuation:
        s = _PUNCT_RE.sub(" ", s)
    if case_insensitive:
        s = s.lower()
    return [t for t in s.split() if t]


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter / union) if union > 0 else 0.0


# -----------------------------
# Metric implementation
# -----------------------------
def evaluate(
    run: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Accuracy metric.

    Inputs:
      - run.output (string or structured)
      - context.expected_output (string or structured)
      - context.mode: "exact" or "overlap" (default "exact")
      - context.field_path: dot-path to extract a nested field from run.output
      - context.case_insensitive, context.strip_punctuation for string normalization

    Output:
      {"accuracy": float in [0,1], "mode": "exact"|"overlap"}
    """
    try:
        if not isinstance(run, dict):
            return {"accuracy": 0.0, "mode": "exact", "error": "invalid_run_type"}

        output = run.get("output")
        try:
            inp = AccuracyInput(output=output)  # type: ignore
        except ValidationError as ve:
            logger.error(f"accuracy_score: invalid input: {ve}")
            return {
                "accuracy": 0.0,
                "mode": "exact",
                "error": "validation_error",
                "reason": "invalid_input",
            }

        ctx = AccuracyContext(**(context or {}))  # type: ignore

        # Allow evaluating nested path for structured outputs
        eff_out = _extract_by_path(inp.output, ctx.field_path)
        eff_exp = _extract_by_path(ctx.expected_output, ctx.field_path)

        # Exact mode: deep equality for dict/list else string equality (normalized if case_insensitive)
        mode = ctx.mode.lower().strip()  # pylint: disable=no-member
        if mode == "exact":
            if isinstance(eff_out, (dict, list)) or isinstance(eff_exp, (dict, list)):
                acc = 1.0 if eff_out == eff_exp else 0.0
            else:
                a = _to_text(eff_out)
                b = _to_text(eff_exp)
                if ctx.case_insensitive:
                    a, b = a.lower(), b.lower()
                acc = 1.0 if a == b else 0.0
            return AccuracyOutput(accuracy=acc, mode="exact").as_dict()

        # Overlap mode: Jaccard token set overlap
        a = _to_text(eff_out)
        b = _to_text(eff_exp)
        toks_a = set(_tokenize_simple(a, ctx.case_insensitive, ctx.strip_punctuation))
        toks_b = set(_tokenize_simple(b, ctx.case_insensitive, ctx.strip_punctuation))
        acc = _jaccard(toks_a, toks_b)
        # clip
        acc = min(1.0, max(0.0, acc))
        return AccuracyOutput(accuracy=acc, mode="overlap").as_dict()

    except Exception as e:
        logger.exception("accuracy_score metric failed")
        return {
            "accuracy": 0.0,
            "mode": "exact",
            "error": "exception",
            "reason": str(e),
        }


# -----------------------------
# Registry auto-registration
# -----------------------------
register_metric("accuracy_score", evaluate)
