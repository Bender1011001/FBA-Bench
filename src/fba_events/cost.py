from dataclasses import dataclass

from fba_bench_core.money import Money

from .base import BaseEvent


@dataclass
class LLMUsageReportedEvent(BaseEvent):
    """Event fired after an LLM API call is completed and costed."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    call_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost: float

    def to_summary_dict(self) -> dict:
        """Provides a summary dictionary for logging or UI display."""
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "call_cost": self.call_cost,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost": self.total_cost,
        }


@dataclass
class TokenUsageEvent(BaseEvent):
    """Normalized event representing token consumption and estimated cost for a single operation."""

    source_event_id: str
    source_event_type: str
    tokens_consumed: int
    estimated_cost_usd: Money

    def to_summary_dict(self) -> dict:
        return {
            "source_event_id": self.source_event_id,
            "source_event_type": self.source_event_type,
            "tokens_consumed": self.tokens_consumed,
            "estimated_cost_usd": self.estimated_cost_usd.to_float(),
        }


@dataclass
class ApiCostEvent(BaseEvent):
    """Normalized event representing direct API cost incurred by an operation."""

    source_event_id: str
    source_event_type: str
    cost_incurred: Money

    def to_summary_dict(self) -> dict:
        return {
            "source_event_id": self.source_event_id,
            "source_event_type": self.source_event_type,
            "cost_incurred": self.cost_incurred.to_float(),
        }


@dataclass
class PenaltyEvent(BaseEvent):
    """Penalty scoring event used by CostMetrics to adjust cost-based scores."""

    source_event_id: str
    source_event_type: str
    penalty_type: str
    penalty_value: float
    reason: str = ""

    def to_summary_dict(self) -> dict:
        return {
            "source_event_id": self.source_event_id,
            "source_event_type": self.source_event_type,
            "penalty_type": self.penalty_type,
            "penalty_value": self.penalty_value,
            "reason": self.reason,
        }


__all__ = [
    "LLMUsageReportedEvent",
    "TokenUsageEvent",
    "ApiCostEvent",
    "PenaltyEvent",
]
