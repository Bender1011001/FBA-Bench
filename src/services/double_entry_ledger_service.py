"""
Double Entry Ledger Service facade.

Re-exports the core ledger service and financial models.
"""
from fba_bench_core.services.double_entry_ledger_service import (
    Account,
    AccountType,
    DoubleEntryLedgerService,
    FinancialStatement,
    LedgerEntry,
    Transaction,
    TransactionType,
)

__all__ = [
    "Account",
    "AccountType",
    "DoubleEntryLedgerService",
    "FinancialStatement",
    "LedgerEntry",
    "Transaction",
    "TransactionType",
]
