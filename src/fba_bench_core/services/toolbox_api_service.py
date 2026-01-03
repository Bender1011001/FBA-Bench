from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from money import Money
from services.toolbox_schemas import (
    LaunchProductRequest,
    LaunchProductResponse,
    ObserveRequest,
    ObserveResponse,
    SetPriceRequest,
    SetPriceResponse,
)

from fba_bench_core.event_bus import EventBus
from fba_events import WorldStateSnapshotEvent
from fba_events.pricing import ProductPriceUpdated, SetPriceCommand

# mypy: ignore-errors


class ToolboxAPIService:
    """
    Lightweight in-memory Toolbox API facade with schema-validated methods and EventBus integration.

    Responsibilities:
    - Maintain a cache of latest product snapshot metrics per ASIN
    - Provide observe() for reading cached metrics
    - Provide set_price() which publishes SetPriceCommand onto the EventBus
    - Provide launch_product() to register a new product internally (no event publishing yet)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._event_bus: Optional[EventBus] = None
        # Cache structure per ASIN:
        # {
        #   "price": Money,
        #   "inventory": int,
        #   "bsr": int,
        #   "conversion_rate": float,
        #   "timestamp": datetime
        # }
        self._product_cache: Dict[str, Dict[str, Any]] = {}
        # Internal registry for launched products
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._is_running: bool = False

    async def start(self, event_bus: EventBus) -> None:
        """
        Start service by wiring to the EventBus subscriptions.
        """
        if self._is_running:
            return
        self._event_bus = event_bus
        await self._event_bus.subscribe(
            WorldStateSnapshotEvent, self._on_world_snapshot
        )
        await self._event_bus.subscribe(ProductPriceUpdated, self._on_price_updated)
        self._is_running = True

    async def stop(self) -> None:
        """
        No-op stop. The EventBus manages handler lifecycle internally.
        """
        self._is_running = False

    # --------------------
    # Event Handlers
    # --------------------
    async def _on_world_snapshot(self, event: WorldStateSnapshotEvent) -> None:
        """
        Update product cache from WorldStateSnapshotEvent summary_metrics.

        Expected structure:
        summary_metrics = {
            "products": {
                asin: {
                    "price_cents": int,
                    "inventory": int,
                    "bsr": int,
                    "conversion_rate": float
                },
                ...
            }
        }
        """
        try:
            products = {}
            if isinstance(event.summary_metrics, dict):
                products = event.summary_metrics.get("products", {}) or {}
            if not isinstance(products, dict):
                return

            for asin, pdata in products.items():
                if not isinstance(pdata, dict):
                    continue
                price_cents = pdata.get("price_cents")
                price = (
                    Money(int(price_cents)) if isinstance(price_cents, int) else None
                )
                inventory = pdata.get("inventory")
                bsr = pdata.get("bsr")
                conversion_rate = pdata.get("conversion_rate")

                # Compose record, preserving any previous known values if absent
                prev = self._product_cache.get(asin, {})
                record = {
                    "price": price if isinstance(price, Money) else prev.get("price"),
                    "inventory": (
                        int(inventory)
                        if isinstance(inventory, int)
                        else prev.get("inventory")
                    ),
                    "bsr": int(bsr) if isinstance(bsr, int) else prev.get("bsr"),
                    "conversion_rate": (
                        float(conversion_rate)
                        if conversion_rate is not None
                        else prev.get("conversion_rate")
                    ),
                    "timestamp": event.timestamp or datetime.now(timezone.utc),
                }
                self._product_cache[asin] = record
        except (TypeError, AttributeError, ValueError, KeyError):
            # Cache updates must never crash the bus
            pass

    async def _on_price_updated(self, event: ProductPriceUpdated) -> None:
        """
        Update in-memory cache for an ASIN's price when ProductPriceUpdated arrives.
        """
        try:
            prev = self._product_cache.get(event.asin, {})
            self._product_cache[event.asin] = {
                **prev,
                "price": event.new_price,
                "timestamp": event.timestamp or datetime.now(timezone.utc),
            }
        except (TypeError, AttributeError, KeyError):
            pass

    # --------------------
    # Public API
    # --------------------
    def observe(self, req: ObserveRequest) -> ObserveResponse:
        """
        Returns the cached observation for the requested asin. If not present, found=False.
        """
        asin = req.asin
        now = datetime.now(timezone.utc)
        cached = self._product_cache.get(asin)
        if not cached:
            return ObserveResponse(
                asin=asin,
                found=False,
                price=None,
                inventory=None,
                bsr=None,
                conversion_rate=None,
                timestamp=now,
            )

        # Return everything we have; 'fields' in req is currently advisory for future filtering
        return ObserveResponse(
            asin=asin,
            found=True,
            price=cached.get("price"),
            inventory=cached.get("inventory"),
            bsr=cached.get("bsr"),
            conversion_rate=cached.get("conversion_rate"),
            timestamp=cached.get("timestamp") or now,
        )

    def set_price(self, req: SetPriceRequest) -> SetPriceResponse:
        """
        Publish SetPriceCommand asynchronously and return accepted=True with command_id.
        """
        if not self._event_bus:
            raise RuntimeError("ToolboxAPIService not started - EventBus not set")

        # Create command event
        command = SetPriceCommand(
            event_id=self._uuid4_str(),
            timestamp=datetime.now(timezone.utc),
            agent_id=req.agent_id,
            asin=req.asin,
            new_price=req.new_price,
            reason=req.reason,
        )

        # Publish without blocking caller
        asyncio.create_task(self._event_bus.publish(command))

        return SetPriceResponse(
            accepted=True,
            command_id=command.event_id,
            asin=req.asin,
            new_price=req.new_price,
            details="SetPriceCommand published",
        )

    def launch_product(self, req: LaunchProductRequest) -> LaunchProductResponse:
        """
        Register a product locally for deterministic behavior. No event publish for now.
        """
        asin = req.asin
        self._registry[asin] = {
            "initial_price": req.initial_price,
            "initial_inventory": req.initial_inventory,
            "category": req.category,
            "dimensions_inches": req.dimensions_inches,
            "weight_oz": req.weight_oz,
            "registered_at": datetime.now(timezone.utc),
        }
        # Also seed cache for immediate observability
        self._product_cache.setdefault(asin, {})
        self._product_cache[asin].update(
            {
                "price": req.initial_price,
                "inventory": req.initial_inventory,
                "timestamp": datetime.now(timezone.utc),
            }
        )
        return LaunchProductResponse(
            accepted=True,
            asin=asin,
            message="Product registered successfully",
        )

    # --------------------
    # Testing/Introspection helpers
    # --------------------
    def get_registered(self, asin: str) -> Optional[Dict[str, Any]]:
        return self._registry.get(asin)

    # --------------------
    # Utils
    # --------------------
    @staticmethod
    def _uuid4_str() -> str:
        # Local import to avoid overhead until needed
        import uuid

        return str(uuid.uuid4())
