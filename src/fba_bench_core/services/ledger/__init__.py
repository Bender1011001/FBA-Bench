"""Double-Entry Ledger Service package."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from money import Money

from fba_events.bus import EventBus

from .core import AccountingError, LedgerCore
from .events import EventsHandler
from .models import (
    Account,
    AccountType,
    FinancialStatement,
    LedgerEntry,
    Transaction,
    TransactionType,
)
from .statements import StatementsGenerator
from .utils import FEE_ACCOUNT_MAP
from .validation import LedgerValidator

logger = logging.getLogger(__name__)


class DoubleEntryLedgerService:
    """
    Double-Entry Ledger Service for FBA-Bench v3.

    Implements a complete double-entry accounting system with:
    - Chart of accounts management
    - Transaction recording and validation
    - Financial statement generation
    - Audit trail maintenance
    - Integration with event bus for real-time updates

    Critical Requirements:
    - Enforces double-entry rules (debits = credits)
    - Maintains proper account balances
    - Generates accurate financial statements
    - Provides audit trail for all transactions
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the double-entry ledger service."""
        self.config = config
        self.event_bus: Optional[EventBus] = None

        # Core components
        self.core = LedgerCore()
        self.statements = StatementsGenerator(self.core)
        self.validator = LedgerValidator()
        self.events = EventsHandler(self.core, self.statements, self.config)

        # Initialize chart of accounts
        self.core.initialize_chart_of_accounts()

        logger.info("DoubleEntryLedgerService initialized with chart of accounts")

    async def start(self, event_bus: EventBus) -> None:
        """Start the ledger service and subscribe to events."""
        await self.events.start(event_bus)

    async def stop(self) -> None:
        """Stop the ledger service."""
        await self.events.stop()

    async def post_transaction(self, transaction: Transaction) -> None:
        """Post a transaction to the ledger and update account balances."""
        # Validate before posting
        self.validator.validate_transaction(transaction, self.core.accounts)

        # Invalidate cache before posting (in case of changes)
        self.statements.invalidate_cache()

        await self.core.post_transaction(transaction)

    async def post_all_unposted_transactions(self) -> None:
        """Post all unposted transactions."""
        await self.core.post_all_unposted_transactions()

    def get_account_balance(self, account_id: str) -> Money:
        """Get the current balance of an account."""
        return self.core.get_account_balance(account_id)

    def get_all_account_balances(self) -> Dict[str, Money]:
        """Get balances for all accounts."""
        return self.core.get_all_account_balances()

    def trial_balance(self) -> Dict[str, Money]:
        """Generate a trial balance of all accounts."""
        return self.core.trial_balance()

    def is_trial_balance_balanced(self) -> bool:
        """Check if the trial balance is balanced (debits = credits)."""
        return self.core.is_trial_balance_balanced()

    def get_trial_balance_difference(self) -> Money:
        """Get the difference between total debits and credits."""
        return self.core.get_trial_balance_difference()

    def generate_balance_sheet(self, force_refresh: bool = False) -> FinancialStatement:
        """Generate a balance sheet statement."""
        return self.statements.generate_balance_sheet(force_refresh=force_refresh)

    def generate_income_statement(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> FinancialStatement:
        """Generate an income statement for the specified period."""
        return self.statements.generate_income_statement(
            period_start=period_start,
            period_end=period_end,
            force_refresh=force_refresh,
        )

    def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Get the transaction history, limited to the specified number of transactions."""
        return self.core.get_transaction_history(limit=limit)

    def get_transactions_by_type(
        self, transaction_type: TransactionType
    ) -> List[Transaction]:
        """Get all transactions of a specific type."""
        return self.core.get_transactions_by_type(transaction_type)

    def get_transactions_by_account(self, account_id: str) -> List[Transaction]:
        """Get all transactions that affect a specific account."""
        return self.core.get_transactions_by_account(account_id)

    def get_financial_position(self) -> Dict[str, Any]:
        """Get the current financial position for audit purposes."""
        return self.statements.get_financial_position()

    def get_ledger_statistics(self) -> Dict[str, Any]:
        """Get ledger service statistics."""
        return self.core.get_ledger_statistics()

    async def inject_equity(
        self, amount: Money, description: str = "Initial capital injection"
    ) -> str:
        """
        Post a balanced equity injection: DR cash, CR owner_equity.
        Returns the created transaction_id.
        """
        return await self.core.inject_equity(amount, description)

    async def initialize_capital(self, amount: Money) -> str:
        """
        Convenience alias for inject_equity with standard description.
        """
        return await self.core.initialize_capital(amount)

    def get_cash_balance(self) -> Money:
        """Return current cash account balance."""
        return self.core.get_cash_balance()

    def verify_integrity(self, raise_on_failure: bool = True) -> bool:
        """Verify the fundamental accounting equation: Assets = Liabilities + Equity.
        
        This is the 'Panic Button' - if violated, the simulation should halt.
        
        Args:
            raise_on_failure: If True, raises AccountingError on violation.
        
        Returns:
            True if the accounting equation holds.
            
        Raises:
            AccountingError: If raise_on_failure=True and equation is violated.
        """
        return self.core.verify_integrity(raise_on_failure=raise_on_failure)

    def get_accounting_equation_summary(self) -> Dict[str, Any]:
        """Return a summary of the accounting equation components for audit."""
        return self.core.get_accounting_equation_summary()
