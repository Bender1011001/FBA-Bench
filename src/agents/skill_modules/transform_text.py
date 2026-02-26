from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from pydantic import ConfigDict, Field, ValidationError

from .base import Skill, SkillExecutionError, SkillInputModel, SkillOutputModel

try:
    from fba_bench.core.logging import setup_logging  # type: ignore
except Exception:  # pragma: no cover
    setup_logging = None  # type: ignore

if setup_logging:
    try:
        setup_logging()
    except Exception:
        pass

logger = logging.getLogger(__name__)


def _dedupe_whitespace(s: str) -> str:
    # Collapse runs of whitespace to a single space and trim
    return re.sub(r"\s+", " ", s).strip()


# Map operation name to callable
_OPERATION_FUNCS = {
    "lower": str.lower,
    "upper": str.upper,
    "strip": str.strip,
    "title": str.title,
    "dedupe_whitespace": _dedupe_whitespace,
}


class TransformTextInput(SkillInputModel):
    text: str = Field(..., description="Source text to transform", min_length=0)
    operations: List[str] = Field(
        ...,
        description="List of operations to apply in order. Supported: lower, upper, strip, dedupe_whitespace, title",
        min_length=1,
        json_schema_extra={"example": ["strip", "lower", "dedupe_whitespace", "title"]},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "  Hello   WORLD ",
                    "operations": ["strip", "lower", "dedupe_whitespace", "title"],
                }
            ]
        }
    )


class TransformTextOutput(SkillOutputModel):
    text: str = Field(..., description="Transformed text result")

    model_config = ConfigDict(json_schema_extra={"examples": [{"text": "Hello World"}]})


class TransformTextSkill(Skill):
    """
    Deterministic text transformation pipeline.

    Supported operations:
    - lower
    - upper
    - strip
    - dedupe_whitespace
    - title
    """

    name = "transform_text"
    description = "Apply deterministic text transformations in sequence."
    input_model = TransformTextInput
    output_model = TransformTextOutput

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = self.input_model.model_validate(params)
        except ValidationError as e:
            raise SkillExecutionError(f"Invalid input: {e}") from e

        result = data.text
        for op_name in data.operations:
            func = _OPERATION_FUNCS.get(op_name)
            if func is None:
                raise SkillExecutionError(f"Unknown operation: {op_name}")
            try:
                result = func(result)  # type: ignore[operator]
            except Exception as e:
                raise SkillExecutionError(f"Operation '{op_name}' failed: {e}") from e

        out = self.output_model(text=result)
        return out.model_dump()
