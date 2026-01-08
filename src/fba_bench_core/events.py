from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from fba_bench_core.models.sales_result import SalesResult
from fba_bench_core.money import Money


class Event(BaseModel):
    """Base model for all events, providing a timestamp and event ID."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_name: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True  # Allow canonical Money in derived events
    )


class SaleProcessedEvent(Event):
    """Fired when a sale has been successfully processed."""

    event_name: str = "sale.processed"
    payload: SalesResult


class TrustScoreCalculationRequested(Event):
    """Fired to request a trust score recalculation for an entity."""

    event_name: str = "trust_score.calculation.requested"
    entity_id: str = Field(
        ...,
        description="The ID of the entity (e.g., seller) whose score should be updated.",
    )
    # Use the canonical Money type for financial data in events
    sale_value: Money = Field(
        ..., description="The value of the transaction that triggered this request."
    )
