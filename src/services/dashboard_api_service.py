"""
DashboardAPIService - Real-time simulation state aggregator for research toolkit.

This service subscribes to all major events on the EventBus and maintains
a comprehensive, up-to-the-second JSON snapshot of the entire simulation state.
Provides the data foundation for all research tools and dashboards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from money import Money

from fba_bench_core.event_bus import EventBus
from fba_events.competitor import CompetitorPricesUpdated
from fba_events.pricing import ProductPriceUpdated, SetPriceCommand
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent
from fba_events.agent import AgentDecisionEvent


class DashboardAPIService:
    """
    Observer service that aggregates simulation state for research tools.

    Subscribes to all major EventBus events and maintains a comprehensive
    real-time snapshot of simulation state including:
    - Current tick and simulation time
    - Product pricing and inventory state
    - Competitor market landscape
    - Sales transaction history and analytics
    - Agent activity and command history
    - Financial performance metrics

    The service is read-only and cannot influence the simulation.
    """

    def __init__(
        self,
        event_bus: EventBus,
        audit_service: Optional[Any] = None,
        ledger_service: Optional[Any] = None,
        bsr_service: Optional[Any] = None,
        fee_aggregator: Optional[FeeMetricsAggregatorService] = None,
    ):
        """Initialize the dashboard API service."""
        self.event_bus = event_bus
        self.is_running = False

        # External metrics services (optional wiring; endpoints depend on these)
        self.audit_service = audit_service
        self.ledger_service = ledger_service
        self.bsr_service = bsr_service
        self.fee_aggregator = fee_aggregator

        # Core simulation state
        self.simulation_state = {
            # Time and ticks
            "current_tick": 0,
            "simulation_time": None,
            "last_update": None,
            "uptime_seconds": 0,
            "start_time": None,
            # Product state (canonical from WorldStore)
            "products": {},  # asin -> {price, last_updated, update_count}
            # Market competitive landscape
            "competitors": {},  # asin -> latest CompetitorState
            "market_summary": {},
            # Sales and financial data
            "sales_history": [],  # Recent SaleOccurred events
            "financial_summary": {
                "total_revenue": 0,
                "total_profit": 0,
                "total_fees": 0,
                "total_units_sold": 0,
                "total_transactions": 0,
                "average_order_value": 0,
                "profit_margin_pct": 0,
                "conversion_rate": 0,
            },
            # Agent activity tracking
            "agents": {},  # agent_id -> {command_count, last_command_time, strategy}
            "command_history": [],  # Recent SetPriceCommand events
            "command_stats": {
                "total_commands": 0,
                "accepted_commands": 0,
                "rejected_commands": 0,
                "acceptance_rate": 0,
            },
            # System health and performance
            "event_stats": {
                "events_processed": 0,
                "events_per_second": 0,
                "last_event_time": None,
            },
            # Debug and metadata
            "metadata": {
                "service_version": "1.0.0",
                "snapshot_generation": 0,
                "data_freshness_ms": 0,
            },
        }

        # Circular buffers for history (keep last N items)
        self.max_sales_history = 100
        self.max_command_history = 50
        self.events_processed_count = 0

    async def start(self) -> None:
        """Start the dashboard API service and subscribe to events."""
        if self.is_running:
            return

        print("🚀 Starting DashboardAPIService...")
        self.is_running = True
        self.simulation_state["start_time"] = datetime.now(timezone.utc).isoformat()

        # Subscribe to all major events (use class-based selectors for canonical EventBus)
        await self.event_bus.subscribe(TickEvent, self._handle_tick_event)
        await self.event_bus.subscribe(SaleOccurred, self._handle_sale_occurred)
        await self.event_bus.subscribe(
            CompetitorPricesUpdated, self._handle_competitor_prices_updated
        )
        await self.event_bus.subscribe(
            ProductPriceUpdated, self._handle_product_price_updated
        )
        await self.event_bus.subscribe(SetPriceCommand, self._handle_set_price_command)
        await self.event_bus.subscribe(AgentDecisionEvent, self._handle_agent_decision_event)

        # Start fee aggregator if provided (it subscribes to SaleOccurred itself)
        if self.fee_aggregator is not None:
            await self.fee_aggregator.start(self.event_bus)

        print("✅ DashboardAPIService started and subscribed to EventBus")

    async def stop(self) -> None:
        """Stop the dashboard API service."""
        if not self.is_running:
            return

        print("🛑 Stopping DashboardAPIService...")
        self.is_running = False
        print("✅ DashboardAPIService stopped")

    def get_simulation_snapshot(self) -> Dict[str, Any]:
        """
        Get complete simulation state snapshot.

        Returns:
            Comprehensive JSON-serializable simulation state
        """
        # Update metadata
        now = datetime.now(timezone.utc)
        self.simulation_state["last_update"] = now.isoformat()
        self.simulation_state["metadata"]["snapshot_generation"] += 1

        if self.simulation_state["start_time"]:
            start = datetime.fromisoformat(
                self.simulation_state["start_time"].replace("Z", "+00:00")
            )
            self.simulation_state["uptime_seconds"] = int((now - start).total_seconds())

        # Calculate events per second
        if self.simulation_state["uptime_seconds"] > 0:
            self.simulation_state["event_stats"]["events_per_second"] = round(
                self.events_processed_count / self.simulation_state["uptime_seconds"], 2
            )

        return dict(self.simulation_state)

    def get_recent_events(
        self, event_type: str = None, limit: int = 20, since_tick: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent events of specified type.

        Args:
            event_type: Filter by event type (e.g., 'sales', 'commands')
            limit: Maximum number of events to return
            since_tick: Only return events from this tick onwards (inclusive)

        Returns:
            List of recent events
        """
        if event_type == "sales":
            events = self.simulation_state["sales_history"]
        elif event_type == "commands":
            events = self.simulation_state["command_history"]
        else:
            # Return mix of recent events
            events = []
            events.extend(self.simulation_state["sales_history"])
            events.extend(self.simulation_state["command_history"])
            events = sorted(events, key=lambda x: x.get("timestamp", ""))

        # Apply tick filtering if specified
        if since_tick is not None:
            events = [
                event for event in events if event.get("tick_number", 0) >= since_tick
            ]

        # Apply limit
        return events[-limit:] if events else []

    async def _handle_tick_event(self, event: TickEvent) -> None:
        """Process TickEvent to update simulation time state."""
        self.simulation_state["current_tick"] = event.tick_number
        self.simulation_state["simulation_time"] = event.simulation_time.isoformat()
        self.events_processed_count += 1
        self.simulation_state["event_stats"][
            "events_processed"
        ] = self.events_processed_count
        self.simulation_state["event_stats"]["last_event_time"] = datetime.now(
            timezone.utc
        ).isoformat()

    async def _handle_sale_occurred(self, event: SaleOccurred) -> None:
        """Process SaleOccurred event to update financial state."""
        # Add to sales history
        sale_data = {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "tick_number": self.simulation_state["current_tick"],
            "asin": event.asin,
            "units_sold": event.units_sold,
            "units_demanded": event.units_demanded,
            "unit_price": str(event.unit_price),
            "total_revenue": str(event.total_revenue),
            "total_fees": str(event.total_fees),
            "total_profit": str(event.total_profit),
            "conversion_rate": round(event.conversion_rate, 3),
            "profit_margin_pct": round(event.get_profit_margin_percentage(), 2),
            "bsr_at_sale": event.bsr_at_sale,
            "trust_score_at_sale": round(event.trust_score_at_sale, 3),
        }

        self.simulation_state["sales_history"].append(sale_data)

        # Maintain circular buffer
        if len(self.simulation_state["sales_history"]) > self.max_sales_history:
            self.simulation_state["sales_history"] = self.simulation_state[
                "sales_history"
            ][-self.max_sales_history :]

        # Update financial summary
        financial = self.simulation_state["financial_summary"]
        financial["total_revenue"] += event.total_revenue.cents
        financial["total_profit"] += event.total_profit.cents
        financial["total_fees"] += event.total_fees.cents
        financial["total_units_sold"] += event.units_sold
        financial["total_transactions"] += 1

        # Calculate derived metrics
        if financial["total_transactions"] > 0:
            financial["average_order_value"] = (
                financial["total_revenue"] / financial["total_transactions"]
            )

        if financial["total_revenue"] > 0:
            financial["profit_margin_pct"] = round(
                (financial["total_profit"] / financial["total_revenue"]) * 100, 2
            )

        # Calculate overall conversion rate from recent sales
        if self.simulation_state["sales_history"]:
            recent_sales = self.simulation_state["sales_history"][-20:]  # Last 20 sales
            total_sold = sum(sale["units_sold"] for sale in recent_sales)
            total_demanded = sum(sale["units_demanded"] for sale in recent_sales)
            if total_demanded > 0:
                financial["conversion_rate"] = round(total_sold / total_demanded, 3)

        self.events_processed_count += 1
        self.simulation_state["event_stats"][
            "events_processed"
        ] = self.events_processed_count
        self.simulation_state["event_stats"]["last_event_time"] = datetime.now(
            timezone.utc
        ).isoformat()

    async def _handle_competitor_prices_updated(
        self, event: CompetitorPricesUpdated
    ) -> None:
        """Process CompetitorPricesUpdated event to update market landscape."""
        # Update competitor states
        for competitor in event.competitors:
            self.simulation_state["competitors"][competitor.asin] = {
                "asin": competitor.asin,
                "price": str(competitor.price),
                "bsr": competitor.bsr,
                "sales_velocity": competitor.sales_velocity,
                "last_updated": event.timestamp.isoformat(),
            }

        # Update market summary
        self.simulation_state["market_summary"] = dict(event.market_summary)

        # Add competitor analytics
        if event.competitors:
            prices = [comp.price.cents for comp in event.competitors]
            bsrs = [comp.bsr for comp in event.competitors]

            self.simulation_state["market_summary"].update(
                {
                    "competitor_count": len(event.competitors),
                    "avg_competitor_price_cents": sum(prices) // len(prices),
                    "min_competitor_price_cents": min(prices),
                    "max_competitor_price_cents": max(prices),
                    "avg_competitor_bsr": sum(bsrs) // len(bsrs),
                    "best_competitor_bsr": min(bsrs),
                    "worst_competitor_bsr": max(bsrs),
                }
            )

        self.events_processed_count += 1
        self.simulation_state["event_stats"][
            "events_processed"
        ] = self.events_processed_count
        self.simulation_state["event_stats"]["last_event_time"] = datetime.now(
            timezone.utc
        ).isoformat()

    async def _handle_product_price_updated(self, event: ProductPriceUpdated) -> None:
        """Process ProductPriceUpdated event to update canonical product state."""
        if event.asin not in self.simulation_state["products"]:
            self.simulation_state["products"][event.asin] = {
                "price": str(event.new_price),
                "previous_price": str(event.previous_price),
                "last_updated": event.timestamp.isoformat(),
                "update_count": 1,
                "price_change_pct": round(event.get_price_change_percentage(), 2),
                "last_agent": event.agent_id,
                "arbitration_notes": event.arbitration_notes,
            }
        else:
            product = self.simulation_state["products"][event.asin]
            product["previous_price"] = product["price"]
            product["price"] = str(event.new_price)
            product["last_updated"] = event.timestamp.isoformat()
            product["update_count"] += 1
            product["price_change_pct"] = round(event.get_price_change_percentage(), 2)
            product["last_agent"] = event.agent_id
            product["arbitration_notes"] = event.arbitration_notes

        self.events_processed_count += 1
        self.simulation_state["event_stats"][
            "events_processed"
        ] = self.events_processed_count
        self.simulation_state["event_stats"]["last_event_time"] = datetime.now(
            timezone.utc
        ).isoformat()

    async def _handle_set_price_command(self, event: SetPriceCommand) -> None:
        """Process SetPriceCommand to track agent activity."""
        # Add to command history
        command_data = {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "tick_number": self.simulation_state["current_tick"],
            "agent_id": event.agent_id,
            "asin": event.asin,
            "new_price": str(event.new_price),
            "reason": event.reason,
        }

        self.simulation_state["command_history"].append(command_data)

        # Maintain circular buffer
        if len(self.simulation_state["command_history"]) > self.max_command_history:
            self.simulation_state["command_history"] = self.simulation_state[
                "command_history"
            ][-self.max_command_history :]

        # Update agent tracking
        if event.agent_id not in self.simulation_state["agents"]:
            self.simulation_state["agents"][event.agent_id] = {
                "command_count": 1,
                "last_command_time": event.timestamp.isoformat(),
                "strategy": "unknown",  # Will be inferred from behavior
                "total_price_changes_cents": 0,
                "avg_price_change_pct": 0,
            }
        else:
            agent = self.simulation_state["agents"][event.agent_id]
            agent["command_count"] += 1
            agent["last_command_time"] = event.timestamp.isoformat()

        # Update command stats
        self.simulation_state["command_stats"]["total_commands"] += 1

        self.events_processed_count += 1
        self.simulation_state["event_stats"][
            "events_processed"
        ] = self.events_processed_count
        self.simulation_state["event_stats"]["last_event_time"] = datetime.now(
            timezone.utc
        ).isoformat()

    async def _handle_agent_decision_event(self, event: AgentDecisionEvent) -> None:
        """Process AgentDecisionEvent to track agent reasoning and logs."""
        # Ensure agent entry exists
        if event.agent_id not in self.simulation_state["agents"]:
            self.simulation_state["agents"][event.agent_id] = {
                "command_count": 0,
                "last_command_time": None,
                "strategy": "unknown",
                "total_price_changes_cents": 0,
                "avg_price_change_pct": 0,
                "last_reasoning": "",
                "recent_events": [],
                "financials": {"cash": 0.0, "inventory_value": 0.0, "net_profit": 0.0} # Placeholder
            }
        
        agent = self.simulation_state["agents"][event.agent_id]
        
        # Update reasoning and detailed stats
        agent["last_reasoning"] = event.reasoning
        agent["last_tool_calls"] = event.tool_calls
        agent["llm_usage"] = event.llm_usage
        
        # Add to recent events log for this agent
        log_entry = f"[{event.timestamp.strftime('%H:%M:%S')}] Decision: {event.reasoning[:70]}..."
        if "recent_events" not in agent:
            agent["recent_events"] = []
        agent["recent_events"].insert(0, log_entry)
        # Keep last 15 events per agent for richer history
        agent["recent_events"] = agent["recent_events"][:15]

        self.events_processed_count += 1
        self.simulation_state["event_stats"][
            "events_processed"
        ] = self.events_processed_count

    def _money_to_cents(self, money: Money) -> int:
        """Convert Money object to cents for JSON serialization."""
        return money.cents

    def _cents_to_money_str(self, cents: int) -> str:
        """Convert cents to Money string representation."""
        return str(Money(cents))

    # ----------------------- Metrics HTTP API -----------------------
    def build_app(self) -> FastAPI:
        """
        Build a minimal FastAPI app exposing metrics endpoints under /api/metrics.
        This uses the wired services (audit_service, ledger_service, bsr_service, fee_aggregator).
        """
        app = FastAPI(title="FBA-Bench Metrics API", version="1.0.0")

        @app.get("/api/metrics/audit")
        async def get_audit_metrics():
            if not self.audit_service:
                # Minimal consistent shape with audit disabled
                return {
                    "processed_transactions": 0,
                    "total_violations": 0,
                    "critical_violations": 0,
                    "total_revenue_audited": str(Money.zero()),
                    "total_fees_audited": str(Money.zero()),
                    "total_profit_audited": str(Money.zero()),
                    "current_position": {
                        "total_assets": str(Money.zero()),
                        "total_liabilities": str(Money.zero()),
                        "total_equity": str(Money.zero()),
                        "accounting_identity_valid": True,
                        "identity_difference": str(Money.zero()),
                    },
                    "audit_enabled": False,
                    "halt_on_violation": False,
                    "tolerance_cents": 0,
                }
            # Delegate to FinancialAuditService which already serializes Money to strings
            return self.audit_service.get_audit_statistics()

        @app.get("/api/metrics/ledger")
        async def get_ledger_metrics():
            if not self.ledger_service:
                now_iso = datetime.now(timezone.utc).isoformat()
                return {
                    "cash": str(Money.zero()),
                    "inventory_value": str(Money.zero()),
                    "accounts_receivable": str(Money.zero()),
                    "accounts_payable": str(Money.zero()),
                    "accrued_liabilities": str(Money.zero()),
                    "total_assets": str(Money.zero()),
                    "total_liabilities": str(Money.zero()),
                    "total_equity": str(Money.zero()),
                    "accounting_identity_valid": True,
                    "identity_difference": str(Money.zero()),
                    "timestamp": now_iso,
                }

            pos = self.ledger_service.get_financial_position()

            # Ensure Money -> strings, timestamp ISO
            def m(x: Any) -> str:
                return str(x) if isinstance(x, Money) else str(Money.zero())

            ts = pos.get("timestamp")
            ts_iso = (
                ts.isoformat()
                if hasattr(ts, "isoformat")
                else datetime.now(timezone.utc).isoformat()
            )

            return {
                "cash": m(pos.get("cash")),
                "inventory_value": m(pos.get("inventory_value")),
                "accounts_receivable": m(pos.get("accounts_receivable")),
                "accounts_payable": m(pos.get("accounts_payable")),
                "accrued_liabilities": m(pos.get("accrued_liabilities")),
                "total_assets": m(pos.get("total_assets")),
                "total_liabilities": m(pos.get("total_liabilities")),
                "total_equity": m(pos.get("total_equity")),
                "accounting_identity_valid": bool(
                    pos.get("accounting_identity_valid", True)
                ),
                "identity_difference": m(pos.get("identity_difference")),
                "timestamp": ts_iso,
            }

        @app.get("/api/metrics/bsr")
        async def get_bsr_metrics():
            now_iso = datetime.now(timezone.utc).isoformat()
            if not self.bsr_service:
                return {
                    "products": [],
                    "timestamp": now_iso,
                }

            # Build products list with numeric/null indices
            products = []
            for asin in getattr(self.bsr_service, "product_metrics", {}).keys():
                idx = self.bsr_service.get_product_indices(asin)

                def to_num(x):
                    if x is None:
                        return None
                    try:
                        return float(x)
                    except (TypeError, ValueError):
                        return None

                products.append(
                    {
                        "asin": asin,
                        "velocity_index": to_num(idx.get("velocity_index")),
                        "conversion_index": to_num(idx.get("conversion_index")),
                        "composite_index": to_num(idx.get("composite_index")),
                    }
                )

            market = self.bsr_service.get_market_metrics()
            market_ema_velocity = market.get("market_ema_velocity")
            market_ema_conversion = market.get("market_ema_conversion")
            competitor_count = market.get("competitor_count")

            resp = {
                "products": products,
                "timestamp": now_iso,
            }
            # Serialize EMAs to strings if present
            if market_ema_velocity is not None:
                resp["market_ema_velocity"] = str(market_ema_velocity)
            if market_ema_conversion is not None:
                resp["market_ema_conversion"] = str(market_ema_conversion)
            if competitor_count is not None:
                resp["competitor_count"] = int(competitor_count)

            return resp

        @app.get("/api/metrics/fees")
        async def get_fee_metrics():
            if self.fee_aggregator is None:
                return {}
            return self.fee_aggregator.get_summary_by_type()

        return app


class FeeMetricsAggregatorService:
    """
    Aggregates fees by type from SaleOccurred events.

    - Subscribes to SaleOccurred via EventBus
    - totals[fee_type] += amount (Money)
    - counts[fee_type] += 1
    - get_summary_by_type returns:
      { fee_type: { total_amount: "$x.xx", count: int, average_amount: "$y.yy" } }
    """

    def __init__(self):
        self._totals: Dict[str, Money] = {}
        self._counts: Dict[str, int] = {}
        self._is_running: bool = False
        self._event_bus: Optional[EventBus] = None

    async def start(self, event_bus: EventBus) -> None:
        """Subscribe to SaleOccurred events."""
        if self._is_running:
            return
        self._event_bus = event_bus
        await self._event_bus.subscribe(SaleOccurred, self._on_sale_occurred)
        self._is_running = True

    async def stop(self) -> None:
        """No unsubscribe available on EventBus; flip running flag."""
        self._is_running = False
        self._event_bus = None

    async def _on_sale_occurred(self, event: SaleOccurred) -> None:
        """Update fee totals and counts from SaleOccurred.fee_breakdown."""
        if not getattr(event, "fee_breakdown", None):
            return
        for fee_type, amount in event.fee_breakdown.items():
            if not isinstance(amount, Money):
                continue
            # Initialize structures
            if fee_type not in self._totals:
                self._totals[fee_type] = Money.zero()
                self._counts[fee_type] = 0
            # Aggregate totals and counts
            self._totals[fee_type] = self._totals[fee_type] + amount
            self._counts[fee_type] = int(self._counts[fee_type]) + 1

    def get_summary_by_type(self) -> Dict[str, Dict[str, Any]]:
        """Return fee summary by type with Money values serialized as strings."""
        summary: Dict[str, Dict[str, Any]] = {}
        for fee_type in sorted(
            set(list(self._totals.keys()) + list(self._counts.keys()))
        ):
            total = self._totals.get(fee_type, Money.zero())
            count = int(self._counts.get(fee_type, 0))
            avg = Money.zero() if count == 0 else Money(total.cents // count)
            summary[fee_type] = {
                "total_amount": str(total),
                "count": count,
                "average_amount": str(avg),
            }
        return summary

    def reset(self) -> None:
        """Clear all aggregates."""
        self._totals.clear()
        self._counts.clear()
