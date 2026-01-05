"""
WorldStore service for FBA-Bench v3 multi-agent platform.

Provides centralized, authoritative state management with command arbitration
and conflict resolution. All canonical market state is managed here.
"""

import logging
from typing import Any, Dict, List, Optional

from money import Money

from fba_events.bus import EventBus
from fba_events.inventory import InventoryUpdate
from fba_events.pricing import SetPriceCommand
from fba_events.time_events import TickEvent

from .arbitration import CommandArbitrator
from .events import (
    handle_inventory_update,
    handle_tick_event_for_snapshot,
    save_state_snapshot,
)
from .factory import get_world_store, set_world_store
from .models import CommandArbitrationResult, ProductState, SimpleArbitrationResult
from .persistence import InMemoryStorageBackend, JsonFileStorageBackend, PersistenceBackend
from .state import WorldStateManager

logger = logging.getLogger(__name__)


class WorldStore:
    """
    Centralized, authoritative state management service.

    The WorldStore is the single source of truth for all canonical market state.
    It processes commands from agents, arbitrates conflicts, and publishes
    authoritative state updates that all other services must respect.

    Key Responsibilities:
    - Maintain canonical product state (prices, inventory, etc.)
    - Process SetPriceCommand events from agents
    - Arbitrate conflicts when multiple agents target the same resource
    - Publish ProductPriceUpdated events for state changes, and WorldStateSnapshotEvent
    - Ensure data consistency and integrity
    - Integrate with a persistence backend for long-horizon simulations.

    Multi-Agent Principles:
    - No service except WorldStore can modify canonical state
    - All agent actions flow through command-arbitration-event pattern
    - Conflict resolution is transparent and auditable
    - State changes are atomic and immediately propagated
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        storage_backend: Optional[PersistenceBackend] = None,
    ):
        """
        Initialize WorldStore with empty state.

        Args:
            event_bus: EventBus instance for pub/sub communication
            storage_backend: Optional backend for persisting state snapshots.
                            If None, defaults to InMemoryStorageBackend.
        """
        # Use provided bus or a new in-memory bus
        self.event_bus = event_bus or EventBus()
        self.storage_backend = (
            storage_backend if storage_backend is not None else InMemoryStorageBackend()
        )

        # Composed components
        self.state_manager = WorldStateManager()
        self.arbitrator = CommandArbitrator(self.event_bus, self.state_manager)
        self.snapshots_saved = 0

        logger.info("WorldStore initialized - ready for multi-agent command processing")

    async def start(self):
        """Start the WorldStore service, subscribe to events, and initialize storage."""
        # Subscribe to events
        await self.event_bus.subscribe(
            SetPriceCommand, self.arbitrator.handle_set_price_command
        )
        await self.event_bus.subscribe(InventoryUpdate, self._handle_inventory_update)
        await self.event_bus.subscribe(TickEvent, self._handle_tick_event)

        if self.storage_backend:
            await self.storage_backend.initialize()
            loaded_state = await self.storage_backend.load_latest_state()
            if loaded_state:
                self.state_manager.load_state_from_dict(loaded_state)
                logger.info(
                    f"WorldStore loaded state from persistence backend. Current products: {len(self.state_manager.get_all_product_states())}"
                )
            else:
                logger.info("No existing state found in persistence backend.")

        logger.info(
            "WorldStore started - subscribed to SetPriceCommand, InventoryUpdate, TickEvent events"
        )

    async def stop(self):
        """Stop the WorldStore service and shut down storage backend."""
        if self.storage_backend:
            await self.storage_backend.shutdown()
        logger.info("WorldStore stopped")

    async def _handle_inventory_update(self, event: InventoryUpdate):
        """Handle InventoryUpdate events."""
        await handle_inventory_update(self.state_manager, event)

    async def _handle_tick_event(self, event: TickEvent):
        """Handles TickEvents: clear per-tick tracking and trigger periodic state snapshots."""
        # Clear per-tick command tracking at the beginning of each new tick
        self.arbitrator.reset_tick_state()

        # Periodically persist snapshots
        self.snapshots_saved = await handle_tick_event_for_snapshot(
            self.storage_backend,
            self.event_bus,
            self.state_manager,
            self.snapshots_saved,
            event,
        )

    # State Query Interface (delegated to state_manager)

    def get_product_price(self, asin: str) -> Optional[Money]:
        """Get canonical price for a product."""
        return self.state_manager.get_product_price(asin)

    def get_product_state(self, asin: str) -> Optional[ProductState]:
        """Get complete product state."""
        return self.state_manager.get_product_state(asin)

    def get_all_product_states(self) -> Dict[str, ProductState]:
        """Get all product states (read-only copy)."""
        return self.state_manager.get_all_product_states()

    def get_product_inventory_quantity(self, asin: str) -> int:
        """Get current inventory quantity for a product."""
        return self.state_manager.get_product_inventory_quantity(asin)

    def get_product_cost_basis(self, asin: str) -> Money:
        """Get current cost basis for a product."""
        return self.state_manager.get_product_cost_basis(asin)

    # Supplier catalog helpers (delegated)

    def set_supplier_catalog(self, catalog: List[Dict[str, Any]]) -> None:
        """Store supplier catalog in the world store for downstream services."""
        self.state_manager.set_supplier_catalog(catalog)

    def get_supplier_catalog(self) -> Dict[str, Any]:
        """Return the supplier catalog keyed by supplier_id."""
        return self.state_manager.get_supplier_catalog()

    def get_supplier_lead_time(self, supplier_id: str) -> Optional[int]:
        """
        Return the lead_time (in ticks) for a supplier if present in the catalog.
        """
        return self.state_manager.get_supplier_lead_time(supplier_id)

    # Marketing visibility helpers (delegated)

    def get_marketing_visibility(self, asin: str) -> float:
        """
        Return current marketing visibility multiplier for an ASIN.
        1.0 = neutral baseline, >1.0 increases demand proportionally.
        """
        return self.state_manager.get_marketing_visibility(asin)

    def set_marketing_visibility(self, asin: str, visibility: float) -> None:
        """
        Set marketing visibility multiplier for an ASIN in canonical state.
        Bounds value to [0.1, 5.0] and updates metadata.
        """
        self.state_manager.set_marketing_visibility(asin, visibility)

    # Reputation helpers (delegated)

    def get_reputation_score(self, asin: str) -> float:
        """
        Return current customer reputation score for an ASIN in [0.0, 1.0].
        Defaults to 0.7 when unknown.
        """
        return self.state_manager.get_reputation_score(asin)

    def set_reputation_score(self, asin: str, score: float) -> None:
        """
        Set reputation score for an ASIN, clamped to [0.0, 1.0].
        Creates product stub if needed.
        """
        self.state_manager.set_reputation_score(asin, score)

    # Command arbitration (delegated)

    def arbitrate_commands(
        self, commands: List[Dict[str, Any]]
    ) -> SimpleArbitrationResult:
        """
        Back-compat simple arbitration for dict-based commands.
        """
        return self.arbitrator.arbitrate_commands(commands)

    # Direct state mutation helpers for tests/fixtures (delegated)

    def set_product_state(self, product_id: str, state: ProductState) -> None:
        """
        Back-compat helper used by tests to inject a ProductState directly.
        """
        self.state_manager.set_product_state(product_id, state)

    # Administrative Interface (delegated or composed)

    def initialize_product(
        self,
        asin: str,
        initial_price: Money,
        initial_inventory: int = 0,
        initial_cost_basis: Money = Money.zero(),
    ) -> bool:
        """
        Initialize a product with starting state.
        """
        return self.state_manager.initialize_product(
            asin, initial_price, initial_inventory, initial_cost_basis
        )

    async def save_state_snapshot(self, tick: Optional[int] = None) -> Optional[str]:
        """
        Saves a snapshot of the current WorldStore state using the configured backend.
        Publishes a WorldStateSnapshotEvent if successful.
        """
        snapshot_id = await save_state_snapshot(
            self.storage_backend, self.event_bus, self.state_manager, tick
        )
        if snapshot_id:
            self.snapshots_saved += 1
        return snapshot_id

    async def load_state_snapshot(self, snapshot_id: Optional[str] = None) -> bool:
        """
        Loads a world state snapshot from the configured backend.
        If snapshot_id is None, loads the latest state.
        Returns True on success, False on failure.
        """
        if not self.storage_backend:
            logger.warning(
                "No storage backend configured for WorldStore, cannot load snapshot."
            )
            return False

        loaded_data = None
        if snapshot_id:
            loaded_data = await self.storage_backend.load_state_by_id(snapshot_id)
        else:
            loaded_data = await self.storage_backend.load_latest_state()

        if loaded_data:
            self.state_manager.load_state_from_dict(loaded_data)
            logger.info(
                f"WorldStore state loaded successfully from snapshot {snapshot_id or 'latest'}. "
                f"Current products: {len(self.state_manager.get_all_product_states())}"
            )
            return True
        logger.warning(
            f"Failed to load WorldStore state snapshot {snapshot_id or 'latest'}."
        )
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get WorldStore operational statistics."""
        arb_stats = self.arbitrator.get_statistics()
        arb_stats["products_managed"] = len(self.state_manager.get_all_product_states())
        arb_stats["snapshots_saved"] = self.snapshots_saved
        return arb_stats

    def reset_state(self):
        """Reset all state - used for testing."""
        self.state_manager.reset_state()
        self.arbitrator.reset()
        self.snapshots_saved = 0
        logger.info("WorldStore state reset")


__all__ = [
    "WorldStore",
    "get_world_store",
    "set_world_store",
    # Storage backend classes
    "PersistenceBackend",
    "InMemoryStorageBackend",
    "JsonFileStorageBackend",
    # Model classes
    "CommandArbitrationResult",
    "ProductState",
    "SimpleArbitrationResult",
]
