"""
Event handling module for WorldStore.
Handles incoming events like inventory updates and tick events for snapshots.
"""

import logging
from datetime import datetime
from typing import Optional

from money import Money

from fba_events import WorldStateSnapshotEvent
from fba_events.bus import EventBus
from fba_events.inventory import InventoryUpdate
from fba_events.time_events import TickEvent

from .models import ProductState
from .persistence import PersistenceBackend
from .state import WorldStateManager

logger = logging.getLogger(__name__)


async def handle_inventory_update(
    state_manager: WorldStateManager, event: InventoryUpdate
) -> None:
    """
    Handle InventoryUpdate events to update canonical inventory state.
    """
    try:
        asin = event.asin
        # Enforce non-negative inventory at the canonical store level
        new_quantity = max(0, int(event.new_quantity))
        cost_basis = event.cost_basis

        if new_quantity != event.new_quantity:
            logger.warning(
                f"InventoryUpdate clamped negative quantity to zero for {asin} (requested={event.new_quantity})."
            )

        current_state = state_manager.get_product_state(asin)
        if current_state:
            current_state.inventory_quantity = new_quantity
            if cost_basis:
                current_state.cost_basis = cost_basis
            current_state.last_updated = datetime.now()
            logger.debug(
                f"Updated inventory for {asin}: new_quantity={new_quantity}, cost_basis={cost_basis}"
            )
        else:
            new_state = ProductState(
                asin=asin,
                price=Money.zero(),
                inventory_quantity=new_quantity,
                cost_basis=cost_basis if cost_basis else Money.zero(),
                last_updated=datetime.now(),
                last_agent_id="system_inventory",
                last_command_id=event.event_id,
                version=1,
            )
            state_manager.set_product_state(asin, new_state)
            logger.info(
                f"Initialized product state with inventory: asin={asin}, quantity={new_quantity}, cost={cost_basis}"
            )

    except (TypeError, AttributeError, ValueError) as e:
        logger.error(
            f"Error handling InventoryUpdate event {event.event_id}: {e}", exc_info=True
        )


async def handle_tick_event_for_snapshot(
    storage_backend: PersistenceBackend,
    event_bus: EventBus,
    state_manager: WorldStateManager,
    snapshots_saved: int,
    event: TickEvent,
) -> int:
    """
    Handles TickEvents: trigger periodic state snapshots.

    Note: Per-tick command clearing is handled in arbitration module.
    """
    # Periodically persist snapshots
    if event.tick_number % 100 == 0:  # Example: save every 100 ticks
        logger.info(f"Tick {event.tick_number}: Triggering WorldStore state snapshot.")
        snapshot_id = await save_state_snapshot(
            storage_backend, event_bus, state_manager, tick=event.tick_number
        )
        if snapshot_id:
            snapshots_saved += 1
    return snapshots_saved


async def save_state_snapshot(
    storage_backend: PersistenceBackend,
    event_bus: EventBus,
    state_manager: WorldStateManager,
    tick: Optional[int] = None,
) -> Optional[str]:
    """
    Saves a snapshot of the current WorldStore state using the configured backend.
    Publishes a WorldStateSnapshotEvent if successful.
    """
    if not storage_backend:
        logger.warning(
            "No storage backend configured for WorldStore, cannot save snapshot."
        )
        return None

    serializable_state = {
        asin: product_state.to_dict()
        for asin, product_state in state_manager.get_all_product_states().items()
    }

    timestamp = datetime.now()
    snapshot_id = await storage_backend.save_state(serializable_state, timestamp, tick)
    if not snapshot_id:
        return None

    snapshot_event = WorldStateSnapshotEvent(
        event_id=f"world_state_snapshot_{snapshot_id}",
        timestamp=timestamp,
        snapshot_id=snapshot_id,
        tick_number=tick,
        product_count=len(state_manager.get_all_product_states()),
        summary_metrics={"total_products": len(state_manager.get_all_product_states())},
    )
    await event_bus.publish(snapshot_event)
    logger.info(f"WorldStore state snapshot '{snapshot_id}' saved successfully.")
    return snapshot_id
