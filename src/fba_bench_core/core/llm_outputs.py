from __future__ import annotations

"""
Structured LLM output contracts for FBA-Bench agent runners.

These Pydantic models define the validated, strongly-typed results that LLM-backed
agents must return. Runners should instruct models to emit JSON that conforms to
FbaDecision.model_json_schema(), then parse/validate the response using
FbaDecision.model_validate_json().

Usage example (inside a runner):

    from fba_bench.core.llm_outputs import FbaDecision
    from pydantic import ValidationError

    schema = FbaDecision.model_json_schema()
    # Embed `schema` in the prompt and instruct JSON-only output

    llm_text = run_llm_and_get_text()
    try:
        decision = FbaDecision.model_validate_json(llm_text)
        return decision.model_dump()
    except ValidationError as e:
        logger.error("LLM output validation failed: %s", e)
        raise AgentRunnerDecisionError("Invalid LLM output") from e
"""

from typing import List, Optional  # noqa: E402

from pydantic import BaseModel, Field, field_validator  # noqa: E402


class PriceDecision(BaseModel):
    asin: str = Field(..., description="The product ASIN.")
    new_price: float = Field(
        ..., gt=0.0, description="The recommended new price in USD."
    )
    reasoning: str = Field(
        ..., min_length=1, description="The justification for this price."
    )

    @field_validator("asin")
    @classmethod
    def asin_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("asin must be a non-empty string")
        return v.strip()


class FbaDecision(BaseModel):
    pricing_decisions: List[PriceDecision] = Field(
        ..., description="A list of pricing decisions to execute."
    )
    meta: Optional[dict] = Field(
        default=None,
        description="Optional metadata about the decision, such as constraints applied or model confidence.",
    )

    def to_dict(self) -> dict:
        """
        Convenience method to produce a plain dict suitable for downstream usage.
        """
        return self.model_dump()

    def to_json(self) -> str:
        """
        Convenience method to produce a JSON string of the decision.
        """
        return self.model_dump_json()


# Additional canonical LLM output contracts used across the system.
# These models are intentionally generic and reusable. Validation utilities
# in fba_bench.core.llm_validation provide strict vs non-strict modes.
from typing import Any, Dict  # noqa: E402


class TaskPlan(BaseModel):
    """
    High-level task planning output from an LLM.

    Examples:
        {
            "objective": "Increase market share for ASIN B07XEXAMPLE",
            "steps": ["Analyze competitors", "Adjust price", "Monitor results"],
            "constraints": ["Budget <= $100", "Price >= cost_basis"],
            "metadata": {"priority": "high"}
        }
    """

    objective: str = Field(..., description="Primary objective of the plan.")
    steps: list[str] = Field(..., min_length=1, description="Ordered steps to execute.")
    constraints: Optional[list[str]] = Field(
        default=None, description="Optional constraints or guardrails."
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional additional metadata."
    )


class ToolCall(BaseModel):
    """
    A structured tool invocation request from an LLM.

    Examples:
        {
            "tool_name": "set_price",
            "arguments": {"asin": "B07XEXAMPLE", "price": 23.47},
            "id": "call-001"
        }
    """

    tool_name: str = Field(..., description="Name of the tool to invoke.")
    arguments: Dict[str, Any] = Field(..., description="Arguments for the tool.")
    id: Optional[str] = Field(
        default=None, description="Optional correlation identifier."
    )


class AgentResponse(BaseModel):
    """
    A general-purpose agent response envelope that can include natural language,
    optional citations, optional tool calls, and an optional plan.

    Examples:
        {
            "content": "Lowering price slightly to improve competitiveness.",
            "citations": ["https://example.com/market-report"],
            "tool_calls": [
                {"tool_name": "set_price", "arguments": {"asin": "B07XEXAMPLE", "price": 23.47}}
            ],
            "plan": {
                "objective": "Improve competitiveness",
                "steps": ["Analyze", "Adjust price", "Observe"],
                "constraints": ["Price > 0"]
            }
        }
    """

    content: str = Field(..., description="Primary content or summary.")
    citations: Optional[list[str]] = Field(
        default=None, description="Optional reference links."
    )
    tool_calls: Optional[list[ToolCall]] = Field(
        default=None, description="Optional list of tool calls to execute."
    )
    plan: Optional[TaskPlan] = Field(default=None, description="Optional task plan.")
