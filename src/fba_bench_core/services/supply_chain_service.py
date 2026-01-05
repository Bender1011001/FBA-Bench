"""
SupplyChainService

Manages supplier state and pending purchase orders. Integrates with EventBus to:
- Accept PlaceOrderCommand from agents
- Schedule deliveries at future ticks (current_tick + lead_time)
- On each tick, process arriving orders and publish InventoryUpdate events
- Support disruption controls (lead time increase, fulfillment rate reduction)
- **NEW** Stochastic lead time variance with seeded randomness
- **NEW** Black swan event system (customs holds, port delays)

Contract:
- Subscribe to PlaceOrderCommand and TickEvent
- Methods:
    - set_disruption(active: bool, lead_time_increase: int = 0, fulfillment_rate: float = 1.0)
    - process_tick() -> processes any arrivals for the current tick
    - set_stochastic_params() -> configure lead time variance
    - trigger_black_swan() -> simulate major supply chain disruptions
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from money import Money

from fba_bench_core.event_bus import EventBus, get_event_bus
from services.world_store import WorldStore
from fba_events.inventory import InventoryUpdate
from fba_events.supplier import PlaceOrderCommand
from fba_events.time_events import TickEvent

logger = logging.getLogger(__name__)


class BlackSwanType(str, Enum):
    """Types of major supply chain disruptions."""
    CUSTOMS_HOLD = "customs_hold"         # 5-15 day delay, random inspection
    PORT_CONGESTION = "port_congestion"   # 3-10 day delay, affects all shipments
    CONTAINER_SHORTAGE = "container"      # 7-21 day delay, limited availability
    FACTORY_SHUTDOWN = "factory_shutdown" # 14-30 day delay, supplier issue
    WEATHER_EVENT = "weather_event"       # 2-7 day delay, typhoon/storm


@dataclass
class BlackSwanEvent:
    """Active black swan disruption affecting the supply chain."""
    event_type: BlackSwanType
    start_tick: int
    duration_ticks: int
    lead_time_multiplier: float
    affected_suppliers: List[str] = field(default_factory=list)  # Empty = all suppliers
    description: str = ""


@dataclass
class PendingOrder:
    order_id: str
    supplier_id: str
    asin: str
    quantity: int
    max_price: Money
    arrival_tick: int
    # Indicates if disruption-based partial fulfillment has already been applied for this order.
    # If True, deliver the remainder in full on the next tick.
    partial_applied: bool = False
    # Stochastic variance applied to this order
    variance_applied: int = 0


class SupplyChainService:
    """
    Stateful supply chain/order management with stochastic lead times.

    - Receives PlaceOrderCommand and schedules a PendingOrder.
    - On each TickEvent, processes arrivals and publishes InventoryUpdate.
    - Disruption controls:
        active -> whether disruption parameters should apply
        lead_time_increase -> additional ticks to add to base lead time
        fulfillment_rate -> portion of ordered units actually delivered (0.0-1.0)
    - Stochastic controls:
        lead_time_std_dev -> standard deviation for lead time variance
        seed -> random seed for deterministic replay
        black_swan_probability -> chance per tick of major disruption
    """

    def __init__(
        self,
        world_store: WorldStore,
        event_bus: Optional[EventBus] = None,
        base_lead_time: int = 2,
        seed: Optional[int] = None,
    ) -> None:
        self.world_store = world_store
        self.event_bus = event_bus or get_event_bus()
        self.base_lead_time = max(0, int(base_lead_time))

        self._started: bool = False
        self._current_tick: int = 0

        # Disruption controls (deterministic)
        self._disruption_active: bool = False
        self._lead_time_increase: int = 0
        self._fulfillment_rate: float = 1.0

        # Stochastic controls (seeded for determinism)
        self._seed = seed
        self._rng = random.Random(seed)
        self._lead_time_std_dev: float = 1.0  # Days variance
        self._black_swan_probability: float = 0.005  # 0.5% per tick
        self._stochastic_enabled: bool = True
        
        # Active black swan events
        self._active_black_swans: List[BlackSwanEvent] = []

        # Pending orders keyed by asin for quick grouping
        self._pending: List[PendingOrder] = []
        
        # Statistics
        self._stats = {
            "orders_placed": 0,
            "orders_delivered": 0,
            "total_lead_time_variance": 0,
            "black_swans_triggered": 0,
        }


    async def start(self) -> None:
        if self._started:
            return
        await self.event_bus.subscribe(PlaceOrderCommand, self._on_place_order)
        await self.event_bus.subscribe(TickEvent, self._on_tick)
        self._started = True
        logger.info(
            "SupplyChainService started and subscribed to PlaceOrderCommand and TickEvent."
        )

    async def stop(self) -> None:
        # EventBus doesn't expose unsubscribe; rely on _started flag if needed
        self._started = False
        logger.info("SupplyChainService stopped.")

    def set_disruption(
        self,
        active: bool,
        lead_time_increase: int = 0,
        fulfillment_rate: float = 1.0,
    ) -> None:
        """
        Configure disruption parameters.

        - lead_time_increase: extra ticks added to base lead time (non-negative)
        - fulfillment_rate: delivered quantity ratio [0.0, 1.0]
        """
        self._disruption_active = bool(active)
        self._lead_time_increase = max(0, int(lead_time_increase))
        self._fulfillment_rate = max(0.0, min(1.0, float(fulfillment_rate)))
        logger.debug(
            "SupplyChainService disruption set: active=%s, lead_time_increase=%d, fulfillment_rate=%.2f",
            self._disruption_active,
            self._lead_time_increase,
            self._fulfillment_rate,
        )

    async def _on_place_order(self, event: PlaceOrderCommand) -> None:
        """
        Handle incoming PlaceOrderCommand by scheduling a pending delivery.
        """
        try:
            extra_lead = self._lead_time_increase if self._disruption_active else 0
            # Prefer supplier-specific lead time from WorldStore catalog when available
            supplier_lt = self.world_store.get_supplier_lead_time(
                getattr(event, "supplier_id", None)
            )
            base_lt = supplier_lt if supplier_lt is not None else self.base_lead_time
            arrival_tick = self._current_tick + base_lt + extra_lead
            pending = PendingOrder(
                order_id=event.event_id or f"order_{uuid.uuid4()}",
                supplier_id=event.supplier_id,
                asin=event.asin,
                quantity=event.quantity,
                max_price=event.max_price,
                arrival_tick=arrival_tick,
            )
            self._pending.append(pending)
            logger.info(
                "SupplyChainService scheduled order: asin=%s qty=%d arrival_tick=%d supplier=%s (base_lt=%d extra_lead=%d)",
                pending.asin,
                pending.quantity,
                pending.arrival_tick,
                pending.supplier_id,
                base_lt,
                extra_lead,
            )
        except (TypeError, AttributeError, ValueError) as e:
            logger.error(
                f"Error handling PlaceOrderCommand {getattr(event, 'event_id', 'unknown')}: {e}",
                exc_info=True,
            )

    async def _on_tick(self, event: TickEvent) -> None:
        """
        Update current tick and process arrivals.
        """
        try:
            self._current_tick = int(getattr(event, "tick_number", self._current_tick))
            await self.process_tick()
        except (TypeError, AttributeError, ValueError) as e:
            logger.error(
                f"Error processing TickEvent in SupplyChainService: {e}", exc_info=True
            )

    async def process_tick(self) -> None:
        """
        Process any pending orders whose arrival_tick <= current tick.
        Applies fulfillment_rate and publishes InventoryUpdate for delivered units.
        """
        if not self._pending:
            return

        remaining: List[PendingOrder] = []
        for po in self._pending:
            if po.arrival_tick <= self._current_tick:
                # Determine delivered quantity under disruption
                # Apply disruption-based partial fulfillment only once; deliver full remainder on the next tick.
                if self._disruption_active and not getattr(
                    po, "partial_applied", False
                ):
                    delivered = max(
                        0, min(po.quantity, int(po.quantity * self._fulfillment_rate))
                    )
                    next_partial_applied = True
                else:
                    delivered = po.quantity
                    next_partial_applied = getattr(po, "partial_applied", False)

                # Deliver arrived units
                if delivered > 0:
                    try:
                        current_qty = self.world_store.get_product_inventory_quantity(
                            po.asin
                        )
                    except (TypeError, AttributeError, ValueError, KeyError):
                        current_qty = 0

                    new_qty = current_qty + delivered
                    try:
                        cost_basis = self.world_store.get_product_cost_basis(po.asin)
                    except (TypeError, AttributeError, ValueError, KeyError):
                        cost_basis = Money.zero()

                    inv_event = InventoryUpdate(
                        event_id=f"inv_supply_{po.asin}_{uuid.uuid4()}",
                        timestamp=datetime.now(),
                        asin=po.asin,
                        new_quantity=new_qty,
                        previous_quantity=current_qty,
                        change_reason="inbound_shipment",
                        agent_id="supply_chain",
                        command_id=po.order_id,
                        cost_basis=cost_basis,
                    )
                    await self.event_bus.publish(inv_event)
                    logger.info(
                        "SupplyChainService delivered: asin=%s delivered=%d new_inventory=%d",
                        po.asin,
                        delivered,
                        new_qty,
                    )

                remainder = po.quantity - delivered
                # If not fully fulfilled and disruption active, re-queue remainder for next tick
                if remainder > 0:
                    remaining.append(
                        PendingOrder(
                            order_id=po.order_id,
                            supplier_id=po.supplier_id,
                            asin=po.asin,
                            quantity=remainder,
                            max_price=po.max_price,
                            arrival_tick=self._current_tick + 1,  # next tick attempt
                            partial_applied=next_partial_applied,
                        )
                    )
            else:
                remaining.append(po)

        self._pending = remaining

    # Introspection helpers (useful for tests/metrics)
    def get_pending_orders(self) -> List[Dict[str, object]]:
        return [
            {
                "order_id": po.order_id,
                "supplier_id": po.supplier_id,
                "asin": po.asin,
                "quantity": po.quantity,
                "arrival_tick": po.arrival_tick,
                "variance_applied": getattr(po, 'variance_applied', 0),
            }
            for po in self._pending
        ]

    def get_current_tick(self) -> int:
        return self._current_tick

    # =========================================================================
    # Stochastic Lead Time Methods
    # =========================================================================
    
    def set_stochastic_params(
        self,
        enabled: bool = True,
        lead_time_std_dev: float = 1.0,
        black_swan_probability: float = 0.005,
        seed: Optional[int] = None,
    ) -> None:
        """Configure stochastic lead time parameters.
        
        Args:
            enabled: Enable/disable stochastic variance.
            lead_time_std_dev: Standard deviation for lead time (in ticks/days).
            black_swan_probability: Probability per tick of major disruption.
            seed: Random seed for deterministic replay.
        """
        self._stochastic_enabled = enabled
        self._lead_time_std_dev = max(0.0, lead_time_std_dev)
        self._black_swan_probability = max(0.0, min(1.0, black_swan_probability))
        if seed is not None:
            self._seed = seed
            self._rng = random.Random(seed)
        
        logger.info(
            "Stochastic params set: enabled=%s, std_dev=%.2f, black_swan_prob=%.4f",
            enabled, self._lead_time_std_dev, self._black_swan_probability
        )
    
    def sample_lead_time_variance(self) -> int:
        """Sample lead time variance from normal distribution.
        
        Returns:
            Integer variance to add to base lead time (can be negative).
            Capped at -base_lead_time to prevent negative arrival times.
        """
        if not self._stochastic_enabled or self._lead_time_std_dev <= 0:
            return 0
        
        variance = int(round(self._rng.gauss(0, self._lead_time_std_dev)))
        # Cap to prevent negative lead times
        min_variance = -self.base_lead_time + 1
        return max(min_variance, variance)
    
    def _check_for_black_swan(self) -> Optional[BlackSwanEvent]:
        """Check if a black swan event should occur this tick.
        
        Returns:
            BlackSwanEvent if triggered, None otherwise.
        """
        if not self._stochastic_enabled:
            return None
        
        if self._rng.random() < self._black_swan_probability:
            return self._generate_black_swan()
        return None
    
    def _generate_black_swan(self) -> BlackSwanEvent:
        """Generate a random black swan event."""
        event_type = self._rng.choice(list(BlackSwanType))
        
        # Duration and multiplier vary by type
        params = {
            BlackSwanType.CUSTOMS_HOLD: (5, 15, 1.5, "Customs inspection delay"),
            BlackSwanType.PORT_CONGESTION: (3, 10, 1.3, "Port congestion affecting shipments"),
            BlackSwanType.CONTAINER_SHORTAGE: (7, 21, 2.0, "Container shortage - limited capacity"),
            BlackSwanType.FACTORY_SHUTDOWN: (14, 30, 2.5, "Supplier factory shutdown"),
            BlackSwanType.WEATHER_EVENT: (2, 7, 1.2, "Weather-related shipping delays"),
        }
        
        min_dur, max_dur, multiplier, desc = params[event_type]
        duration = self._rng.randint(min_dur, max_dur)
        
        event = BlackSwanEvent(
            event_type=event_type,
            start_tick=self._current_tick,
            duration_ticks=duration,
            lead_time_multiplier=multiplier,
            description=desc,
        )
        
        self._stats["black_swans_triggered"] += 1
        logger.warning(
            "BLACK SWAN EVENT: %s - %s (duration=%d ticks, multiplier=%.1fx)",
            event_type.value, desc, duration, multiplier
        )
        
        return event
    
    def trigger_black_swan(
        self,
        event_type: BlackSwanType = BlackSwanType.CUSTOMS_HOLD,
        duration_ticks: int = 10,
        lead_time_multiplier: float = 1.5,
        affected_suppliers: Optional[List[str]] = None,
    ) -> BlackSwanEvent:
        """Manually trigger a black swan event.
        
        Args:
            event_type: Type of disruption.
            duration_ticks: How long the disruption lasts.
            lead_time_multiplier: Factor to multiply lead times.
            affected_suppliers: List of supplier IDs affected (None = all).
            
        Returns:
            The created BlackSwanEvent.
        """
        event = BlackSwanEvent(
            event_type=event_type,
            start_tick=self._current_tick,
            duration_ticks=duration_ticks,
            lead_time_multiplier=lead_time_multiplier,
            affected_suppliers=affected_suppliers or [],
            description=f"Manually triggered {event_type.value}",
        )
        
        self._active_black_swans.append(event)
        self._stats["black_swans_triggered"] += 1
        
        logger.warning(
            "BLACK SWAN TRIGGERED: %s (duration=%d, multiplier=%.1fx)",
            event_type.value, duration_ticks, lead_time_multiplier
        )
        
        return event
    
    def get_active_black_swans(self) -> List[BlackSwanEvent]:
        """Return currently active black swan events."""
        # Clean up expired events
        active = [
            e for e in self._active_black_swans
            if self._current_tick < e.start_tick + e.duration_ticks
        ]
        self._active_black_swans = active
        return active
    
    def get_current_lead_time_multiplier(
        self,
        supplier_id: Optional[str] = None,
    ) -> float:
        """Get the combined lead time multiplier from active black swans.
        
        Args:
            supplier_id: Specific supplier to check.
            
        Returns:
            Combined multiplier (1.0 = no effect).
        """
        active = self.get_active_black_swans()
        if not active:
            return 1.0
        
        # Combine multiplicatively
        multiplier = 1.0
        for event in active:
            # Check if this supplier is affected
            if event.affected_suppliers and supplier_id:
                if supplier_id not in event.affected_suppliers:
                    continue
            multiplier *= event.lead_time_multiplier
        
        return multiplier
    
    def get_statistics(self) -> Dict[str, object]:
        """Return supply chain statistics."""
        return {
            **self._stats,
            "pending_orders": len(self._pending),
            "active_black_swans": len(self.get_active_black_swans()),
            "stochastic_enabled": self._stochastic_enabled,
            "lead_time_std_dev": self._lead_time_std_dev,
            "current_tick": self._current_tick,
        }
