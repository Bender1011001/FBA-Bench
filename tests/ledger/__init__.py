"""Test-local shim for ledger package, re-exporting from real fba_bench_core.services.ledger.

This allows 'from ledger import Account' etc. to succeed by proxying to the production implementation.
No modifications to behavior; purely for import neutralization during test collection.
"""

# Re-export all public symbols from the real ledger package
from services.ledger import (
    Account,
    AccountType,
    DoubleEntryLedgerService,
    FinancialStatement,
    LedgerEntry,
    Transaction,
    TransactionType,
    # Include any other public exports as needed
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
