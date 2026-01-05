"""Event handling for the double-entry ledger service."""

import logging
from typing import Any, Dict, Optional

from money import Money

from fba_events.bus import EventBus
from fba_events.sales import SaleOccurred

from .core import LedgerCore
from .models import (
    LedgerEntry,
    Transaction,
    TransactionType,
)
from .statements import StatementsGenerator

logger = logging.getLogger(__name__)


class EventsHandler:
    """
    Handles event subscriptions and processing for ledger updates.
    """

    def __init__(
        self,
        ledger_core: LedgerCore,
        statements_generator: StatementsGenerator,
        config: Optional[Dict] = None,
    ):
        """Initialize with dependencies for transaction handling and statements."""
        self.ledger_core = ledger_core
        self.statements_generator = statements_generator
        self.config = config or {}
        self.event_bus: Optional[EventBus] = None

    async def start(self, event_bus: EventBus) -> None:
        """Start the event handler and subscribe to events."""
        self.event_bus = event_bus

        # Subscribe to relevant events
        await self.event_bus.subscribe(SaleOccurred, self._handle_sale_occurred)

        # Optional startup capital injection from config for greenfield scenarios
        try:
            init_dollars: Optional[float] = None
            if self.config.get("initial_capital_dollars") is not None:
                init_dollars = float(self.config.get("initial_capital_dollars"))
            elif self.config.get("starting_cash_dollars") is not None:
                # Reuse existing key used elsewhere in the project if provided
                init_dollars = float(self.config.get("starting_cash_dollars"))
            if init_dollars and init_dollars > 0:
                await self.ledger_core.inject_equity(
                    Money.from_dollars(f"{init_dollars:.2f}"),
                    description="Initial capital injection (config)",
                )
                logger.info(
                    f"Initialized starting capital via equity injection: ${init_dollars:.2f}"
                )
        except Exception as e:
            logger.warning(f"Failed to initialize starting capital: {e}", exc_info=True)

        logger.info("EventsHandler started and subscribed to events")

    async def stop(self) -> None:
        """Stop the event handler and post any remaining unposted transactions."""
        # Post any remaining unposted transactions
        if self.ledger_core.unposted_transactions:
            logger.info(
                f"Posting {len(self.ledger_core.unposted_transactions)} unposted transactions"
            )
            await self.ledger_core.post_all_unposted_transactions()

        logger.info("EventsHandler stopped")

    async def _handle_sale_occurred(self, event: SaleOccurred) -> None:
        """Handle SaleOccurred events by creating appropriate ledger entries with fee breakdown."""
        try:
            # Compute net receivable
            net_receivable = event.total_revenue - event.total_fees

            # Create transaction for the sale including fees and COGS
            transaction = Transaction(
                transaction_id=f"sale_{event.event_id}",
                transaction_type=TransactionType.SALE,
                description=f"Sale of ASIN {event.asin}",
                metadata={
                    "event_id": event.event_id,
                    "asin": event.asin,
                    "units_sold": event.units_sold,
                    "units_demanded": event.units_demanded,
                    "unit_price": event.unit_price,
                    "total_revenue": event.total_revenue,
                    "total_fees": event.total_fees,
                    "total_profit": event.total_profit,
                    "cost_basis": event.cost_basis,
                    "fee_breakdown": {
                        k: str(v) for k, v in (event.fee_breakdown or {}).items()
                    },
                },
            )

            # Debit: Accounts Receivable for net proceeds (increase asset)
            transaction.debits.append(
                LedgerEntry(
                    entry_id=f"ar_{event.event_id}",
                    account_id="accounts_receivable",
                    amount=net_receivable,
                    entry_type="debit",
                    description="Net receivable from sale (gross revenue less fees)",
                )
            )

            # Debit: Cost of Goods Sold (increase expense)
            if event.cost_basis.cents != 0:
                transaction.debits.append(
                    LedgerEntry(
                        entry_id=f"cogs_{event.event_id}",
                        account_id="cost_of_goods_sold",
                        amount=event.cost_basis,
                        entry_type="debit",
                        description="Cost of goods sold",
                    )
                )

            # Debit: Fee expenses by type (increase expenses)
            fee_account_map = {
                "referral": "referral_fees",
                "fba": "fulfillment_fees",
                "storage": "storage_fees",
                "advertising": "advertising_expense",
            }
            debited_fees_total = Money.zero()
            if event.total_fees.cents != 0:
                # Apply detailed breakdown if available
                if getattr(event, "fee_breakdown", None):
                    for fee_type, amount in event.fee_breakdown.items():
                        if amount.cents == 0:
                            continue
                        expense_account = fee_account_map.get(
                            fee_type.lower(), "other_expenses"
                        )
                        transaction.debits.append(
                            LedgerEntry(
                                entry_id=f"fee_{fee_type}_{event.event_id}",
                                account_id=expense_account,
                                amount=amount,
                                entry_type="debit",
                                description=f"{fee_type} fee expense",
                            )
                        )
                        debited_fees_total += amount
                    # Adjust for any residual rounding differences
                    residual = event.total_fees - debited_fees_total
                    if residual.cents != 0:
                        transaction.debits.append(
                            LedgerEntry(
                                entry_id=f"fee_residual_{event.event_id}",
                                account_id="other_expenses",
                                amount=residual,
                                entry_type="debit",
                                description="Residual fee adjustment",
                            )
                        )
                else:
                    # No breakdown provided, book all fees to other_expenses
                    transaction.debits.append(
                        LedgerEntry(
                            entry_id=f"fee_other_{event.event_id}",
                            account_id="other_expenses",
                            amount=event.total_fees,
                            entry_type="debit",
                            description="Aggregated fees expense",
                        )
                    )

            # Credit: Sales Revenue (increase revenue) for gross revenue
            if event.total_revenue.cents != 0:
                transaction.credits.append(
                    LedgerEntry(
                        entry_id=f"rev_{event.event_id}",
                        account_id="sales_revenue",
                        amount=event.total_revenue,
                        entry_type="credit",
                        description="Revenue from product sale (gross)",
                    )
                )

            # Credit: Inventory (decrease asset) for cost basis
            if event.cost_basis.cents != 0:
                transaction.credits.append(
                    LedgerEntry(
                        entry_id=f"inv_{event.event_id}",
                        account_id="inventory",
                        amount=event.cost_basis,
                        entry_type="credit",
                        description="Inventory reduction",
                    )
                )

            # Add to unposted transactions and immediately post to update balances
            self.ledger_core.unposted_transactions.append(transaction)
            await self.ledger_core.post_transaction(transaction)

            # Invalidate financial statement cache
            self.statements_generator.invalidate_cache()

            logger.debug(
                f"Created sale transaction {transaction.transaction_id} for {event.total_revenue} with fees {event.total_fees}"
            )

        except Exception as e:
            logger.error(f"Error handling SaleOccurred event {event.event_id}: {e}")
            raise

    async def _handle_inventory_adjusted(self, event: Any) -> None:
        """Handle InventoryAdjusted events by creating appropriate ledger entries."""
        try:
            # Create transaction for the inventory adjustment
            transaction = Transaction(
                transaction_id=f"inv_adj_{event.event_id}",
                transaction_type=TransactionType.INVENTORY_ADJUSTMENT,
                description=f"Inventory adjustment for {event.product_id}",
                metadata={
                    "event_id": event.event_id,
                    "product_id": event.product_id,
                    "adjustment_type": event.adjustment_type,
                    "quantity_change": event.quantity_change,
                    "cost_change": event.cost_change,
                },
            )

            if event.adjustment_type == "write_up":
                # Debit: Inventory (increase asset)
                transaction.debits.append(
                    LedgerEntry(
                        entry_id=f"inv_up_{event.event_id}",
                        account_id="inventory",
                        amount=event.cost_change,
                        entry_type="debit",
                        description="Inventory write-up",
                    )
                )

                # Credit: Other Revenue (increase revenue)
                transaction.credits.append(
                    LedgerEntry(
                        entry_id=f"rev_adj_{event.event_id}",
                        account_id="other_revenue",
                        amount=event.cost_change,
                        entry_type="credit",
                        description="Revenue from inventory adjustment",
                    )
                )

            elif event.adjustment_type == "write_down":
                # Debit: Other Expenses (increase expense)
                transaction.debits.append(
                    LedgerEntry(
                        entry_id=f"exp_adj_{event.event_id}",
                        account_id="other_expenses",
                        amount=event.cost_change,
                        entry_type="debit",
                        description="Expense from inventory write-down",
                    )
                )

                # Credit: Inventory (decrease asset)
                transaction.credits.append(
                    LedgerEntry(
                        entry_id=f"inv_down_{event.event_id}",
                        account_id="inventory",
                        amount=event.cost_change,
                        entry_type="credit",
                        description="Inventory write-down",
                    )
                )

            # Add to unposted transactions (note: not posted immediately, per original)
            self.ledger_core.unposted_transactions.append(transaction)

            logger.debug(
                f"Created inventory adjustment transaction {transaction.transaction_id}"
            )

        except Exception as e:
            logger.error(
                f"Error handling InventoryAdjusted event {event.event_id}: {e}"
            )
            raise
