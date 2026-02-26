import asyncio
from decimal import Decimal

from services.cost_tracking_service import CostTrackingService

from fba_events.bus import InMemoryEventBus as EventBus
from llm_interface.generic_openai_client import GenericOpenAIClient
from fba_bench_core.simulation_orchestrator import SimulationConfig, SimulationOrchestrator


async def test_cost_tracking():
    """
    End-to-end test for the LLM cost tracking subsystem.
    """
    print("Starting Cost Tracking Test...")

    # 1. Initialize EventBus and CostTrackingService
    event_bus = EventBus()
    await event_bus.start()
    cost_tracker = CostTrackingService(event_bus=event_bus)
    print("EventBus and CostTrackingService initialized.")

    # 2. Initialize SimulationOrchestrator with the cost_tracker
    sim_config = SimulationConfig(tick_interval_seconds=0.1, max_ticks=2)  # Short run for testing
    orchestrator = SimulationOrchestrator(config=sim_config, cost_tracker=cost_tracker)
    print("SimulationOrchestrator initialized.")

    # 3. Initialize GenericOpenAIClient with the cost_tracker
    # Use a dummy API key and base URL for testing, as we won't make a real API call
    # but will manually trigger the record_usage method.
    llm_client = GenericOpenAIClient(
        model_name="gpt-4o",
        api_key="test_key",
        base_url="http://localhost:8000/v1",  # Dummy base URL
        cost_tracker=cost_tracker,
    )
    print("GenericOpenAIClient initialized.")

    # 4. Simulate LLM usage by manually calling record_usage
    # This bypasses the actual API call and directly tests the cost tracking logic.
    print("Simulating LLM API call usage...")
    simulated_usage_1 = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    cost_tracker.record_usage(model="gpt-4o", usage=simulated_usage_1)
    print(f"Recorded usage 1: {simulated_usage_1}")

    simulated_usage_2 = {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
    cost_tracker.record_usage(model="gpt-4o", usage=simulated_usage_2)
    print(f"Recorded usage 2: {simulated_usage_2}")

    # 5. Check totals from CostTrackingService
    totals = cost_tracker.get_totals()
    print("\n--- CostTrackingService Totals ---")
    print(f"Total Prompt Tokens: {totals['total_prompt_tokens']}")
    print(f"Total Completion Tokens: {totals['total_completion_tokens']}")
    print(f"Total Cost: ${totals['total_cost']:.6f}")

    expected_prompt_tokens = 100 + 200
    expected_completion_tokens = 50 + 100
    # Pricing for gpt-4o: input $5.00, output $15.00 per 1M tokens
    expected_cost = (Decimal(expected_prompt_tokens) * Decimal("5.00") / Decimal("1000000")) + (
        Decimal(expected_completion_tokens) * Decimal("15.00") / Decimal("1000000")
    )

    assert (
        totals["total_prompt_tokens"] == expected_prompt_tokens
    ), f"Prompt tokens mismatch: {totals['total_prompt_tokens']} != {expected_prompt_tokens}"
    assert (
        totals["total_completion_tokens"] == expected_completion_tokens
    ), f"Completion tokens mismatch: {totals['total_completion_tokens']} != {expected_completion_tokens}"
    # Use Decimal for precise floating point comparison
    assert (
        Decimal(str(totals["total_cost"])) == expected_cost
    ), f"Cost mismatch: {totals['total_cost']} != {expected_cost}"
    print("CostTrackingService totals verified successfully.")

    # 6. Check SimulationOrchestrator status for cost data
    # The orchestrator itself doesn't store cost data, it retrieves it from the service.
    # We need to ensure the service passed to it is the one we're testing.
    status = orchestrator.get_status()
    print("\n--- SimulationOrchestrator Status ---")
    # The orchestrator's get_status was modified to call cost_tracker.get_totals()
    cost_data_from_orchestrator = status.get("cost_tracking")
    print(f"Cost data from orchestrator: {cost_data_from_orchestrator}")

    assert cost_data_from_orchestrator is not None, "Cost data not found in orchestrator status"
    assert cost_data_from_orchestrator["total_prompt_tokens"] == expected_prompt_tokens
    assert cost_data_from_orchestrator["total_completion_tokens"] == expected_completion_tokens
    assert cost_data_from_orchestrator["total_cost"] == float(expected_cost)
    print("SimulationOrchestrator cost data verified successfully.")

    # 7. Test reset functionality
    print("\nResetting CostTrackingService...")
    cost_tracker.reset()
    reset_totals = cost_tracker.get_totals()
    assert reset_totals["total_prompt_tokens"] == 0
    assert reset_totals["total_completion_tokens"] == 0
    assert reset_totals["total_cost"] == Decimal("0.0")
    print("CostTrackingService reset successfully.")

    await event_bus.stop()
    print("\nCost Tracking Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_cost_tracking())
