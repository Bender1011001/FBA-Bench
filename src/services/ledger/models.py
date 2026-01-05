"""Models for the double-entry ledger system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from money import Money


class AccountType(Enum):
    """Types of accounts in the double-entry system."""

    ASSET = "asset"  # Debit normal balance
    LIABILITY = "liability"  # Credit normal balance
    EQUITY = "equity"  # Credit normal balance
    REVENUE = "revenue"  # Credit normal balance
    EXPENSE = "expense"  # Debit normal balance


class TransactionType(Enum):
    """Types of transactions in the system."""

    SALE = "sale"
    FEE_PAYMENT = "fee_payment"
    INVENTORY_PURCHASE = "inventory_purchase"
    INVENTORY_ADJUSTMENT = "inventory_adjustment"
    CASH_DEPOSIT = "cash_deposit"
    CASH_WITHDRAWAL = "cash_withdrawal"
    EQUITY_INJECTION = "equity_injection"
    OWNER_DISTRIBUTION = "owner_distribution"
    ADJUSTING_ENTRY = "adjusting_entry"


@dataclass
class Account:
    """Account in the double-entry ledger system."""

    account_id: str
    name: str
    account_type: AccountType
    normal_balance: str = ""  # "debit" or "credit"
    balance: Money = field(default_factory=Money.zero)
    is_contra: bool = False  # Contra accounts have opposite normal balance
    description: str = ""
    parent_account: Optional[str] = None  # For hierarchical accounts

    def __post_init__(self):
        """Set normal balance based on account type."""
        if not self.normal_balance:
            if self.account_type in [AccountType.ASSET, AccountType.EXPENSE]:
                self.normal_balance = "debit"
            else:  # LIABILITY, EQUITY, REVENUE
                self.normal_balance = "credit"

        # Contra accounts flip the normal balance
        if self.is_contra:
            self.normal_balance = (
                "credit" if self.normal_balance == "debit" else "debit"
            )


@dataclass
class LedgerEntry:
    """Individual entry in a transaction (debit or credit)."""

    entry_id: str
    account_id: str
    amount: Money
    entry_type: str  # "debit" or "credit"
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transaction:
    """Complete transaction with balanced debits and credits."""

    transaction_id: str
    transaction_type: TransactionType
    description: str
    debits: List[LedgerEntry] = field(default_factory=list)
    credits: List[LedgerEntry] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_posted: bool = False

    def __post_init__(self):
        """Validate transaction balance."""
        if not self.is_balanced():
            raise ValueError(f"Transaction {self.transaction_id} is not balanced")

    def is_balanced(self) -> bool:
        """Check if total debits equal total credits."""
        total_debits = sum((entry.amount for entry in self.debits), Money.zero())
        total_credits = sum((entry.amount for entry in self.credits), Money.zero())
        return total_debits.cents == total_credits.cents

    def get_total_debits(self) -> Money:
        """Get total debit amount."""
        return sum((entry.amount for entry in self.debits), Money.zero())

    def get_total_credits(self) -> Money:
        """Get total credit amount."""
        return sum((entry.amount for entry in self.credits), Money.zero())


@dataclass
class FinancialStatement:
    """Financial statement data structure."""

    statement_type: str  # "balance_sheet", "income_statement", "cash_flow"
    period_start: datetime
    period_end: datetime
    data: Dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.now)
