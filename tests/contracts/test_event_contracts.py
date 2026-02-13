from decimal import Decimal
from uuid import UUID

from fba_bench_core.events import SaleProcessedEvent, TrustScoreCalculationRequested
from fba_bench_core.models.sales_result import SalesResult
from fba_bench_core.money import Money


def test_sale_processed_event_contract():
    """
    Validates the structure and types of the SaleProcessedEvent.
    This test acts as a contract for consumers of this event.
    """
    # 1. ARRANGE: Create a valid sample payload
    sample_sale = SalesResult(
        product_id=UUID("12345678-1234-5678-1234-567812345678"),
        quantity_sold=5,
        total_revenue=Money(amount="250.75", currency="CAD"),
    )

    # 2. ACT: Create the event
    event = SaleProcessedEvent(payload=sample_sale)

    # 3. ASSERT: Verify the structure, types, and default values
    assert isinstance(event.event_id, UUID)
    assert event.event_name == "sale.processed"
    assert event.payload == sample_sale
    assert event.payload.total_revenue.currency == "CAD"

    # Verify serialization/deserialization (ensures it's JSON-friendly)
    event_dict = event.dict()
    rehydrated_event = SaleProcessedEvent(**event_dict)
    assert rehydrated_event == event


def test_trust_score_calculation_requested_event_contract():
    """
    Validates the structure and types of the TrustScoreCalculationRequested event.
    """
    # 1. ARRANGE
    event_data = {
        "entity_id": "seller_abc_123",
        "sale_value": Money(amount="99.99", currency="USD"),
    }

    # 2. ACT
    event = TrustScoreCalculationRequested(**event_data)

    # 3. ASSERT
    assert event.event_name == "trust_score.calculation.requested"
    assert event.entity_id == "seller_abc_123"
    assert event.sale_value.amount == Decimal("99.99")

    event_dict = event.dict()
    rehydrated_event = TrustScoreCalculationRequested(**event_dict)
    assert rehydrated_event == event
