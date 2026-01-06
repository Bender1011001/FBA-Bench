"""Utility functions for ledger analysis and accounting calculations."""

import hashlib
import json
import warnings
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Protocol, Set, Tuple, Union

from money import Money


class LedgerLike(Protocol):
    """Minimal protocol describing the ledger used by these utilities."""

    async def trial_balance(self) -> Mapping[str, Union[Money, Decimal, float, int]]:
        ...

    entries: Sequence[Any]  # sequence of txns with attributes used by hash_ledger_slice


# Define account classifications as sets
ASSET_ACCOUNTS: Set[str] = {
    "Cash",
    "Inventory",
    "Accounts Receivable",
    "Prepaid Expenses",
}

LIABILITY_ACCOUNTS: Set[str] = {
    "Accounts Payable",
    "Accrued Liabilities",
    "Notes Payable",
}

EQUITY_ACCOUNTS: Set[str] = {
    "Equity",
    "Retained Earnings",
}

REVENUE_ACCOUNTS: Set[str] = {
    "Revenue",
    "Sales",
    "Interest Income",
}

EXPENSE_ACCOUNTS: Set[str] = {
    "COGS",
    "Fees",
    "Operating Expenses",
    "Interest Expense",
}

# Derived groupings for normal balance conventions
DEBIT_NORMAL_ACCOUNTS: Set[str] = ASSET_ACCOUNTS.union(EXPENSE_ACCOUNTS)
CREDIT_NORMAL_ACCOUNTS: Set[str] = LIABILITY_ACCOUNTS.union(EQUITY_ACCOUNTS).union(REVENUE_ACCOUNTS)


def _balance_to_decimal(balance: Union[int, float, Decimal, Money]) -> Decimal:
    """
    Convert balance to Decimal for calculations.
    Prefer Money or Decimal to avoid floating-point inaccuracies.
    """
    if isinstance(balance, Money):
        return balance.to_decimal()
    if isinstance(balance, Decimal):
        return balance
    if isinstance(balance, int):
        return Decimal(balance)
    # Handle float for backward compatibility (discouraged)
    warnings.warn(
        "Using float for monetary calculations can introduce precision errors. "
        "Prefer Money or Decimal.",
        DeprecationWarning,
        stacklevel=2,
    )
    return Decimal(str(balance))


def _to_cents(value: Union[int, float, Decimal, Money]) -> int:
    """
    Convert a monetary value to integer cents deterministically.
    Accepts Money (uses .cents), Decimal, int, or float (float discouraged).
    """
    if isinstance(value, Money):
        return int(value.cents)
    if isinstance(value, Decimal):
        quant = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return int((quant * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if isinstance(value, int):
        # Treat integer as dollars
        return int(Decimal(value) * 100)
    # Float fallback via Decimal(str(...))
    warnings.warn(
        "hashing from float cost_per_unit coerces via Decimal(str(x)); ensure Decimal/Money for precision.",
        DeprecationWarning,
        stacklevel=2,
    )
    quant = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((quant * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _canonicalize_for_json(obj: Any) -> Any:
    """
    Canonicalize Python objects (including tuples) into JSON-serializable
    structures with deterministic ordering where applicable.
    """
    if isinstance(obj, tuple):
        return [_canonicalize_for_json(x) for x in obj]
    if isinstance(obj, list):
        return [_canonicalize_for_json(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _canonicalize_for_json(v) for k, v in obj.items()}
    return obj


async def balance_sheet(ledger: LedgerLike) -> Dict[str, Decimal]:
    """
    Generate a per-account balance sheet presentation.
    Assets (debit-normal) are presented as signed Decimals (contra accounts may be negative).
    Liabilities and Equity (credit-normal) are presented as positive values (absolute).
    Revenue and Expense accounts are excluded from the balance sheet.
    """
    balances: Dict[str, Decimal] = {}
    trial_balances = await ledger.trial_balance()
    for account, balance in trial_balances.items():
        decimal_balance = _balance_to_decimal(balance)
        if account in ASSET_ACCOUNTS:
            # For asset accounts (debit-normal), use the value as-is
            balances[account] = decimal_balance
        elif account in LIABILITY_ACCOUNTS or account in EQUITY_ACCOUNTS:
            # For liability and equity accounts (credit-normal), ensure positive presentation
            balances[account] = abs(decimal_balance)
    return balances


async def balance_sheet_from_ledger(ledger: LedgerLike) -> Dict[str, Decimal]:
    """Deprecated: use balance_sheet(ledger) instead. This function will be removed in version 4.0.0."""
    warnings.warn(
        "balance_sheet_from_ledger is deprecated and will be removed in version 4.0.0. Use balance_sheet instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return await balance_sheet(ledger)


async def income_statement(
    ledger: LedgerLike, start_tick: int = 0, end_tick: Optional[int] = None
) -> Dict[str, Decimal]:
    """
    Generate income statement with revenue and expense classification.
    Note: start_tick and end_tick are reserved for period filtering when supported by the ledger.
    """
    statement: Dict[str, Decimal] = {}
    trial_balances = await ledger.trial_balance()

    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    for account, balance in trial_balances.items():
        decimal_balance = _balance_to_decimal(balance)
        if account in REVENUE_ACCOUNTS:
            # Revenue accounts normally have credit balances, but stored as negative in our system
            # Convert to positive for income statement presentation
            amount = abs(decimal_balance)
            statement[account] = amount
            total_revenue += amount
        elif account in EXPENSE_ACCOUNTS:
            # Expense accounts normally have debit balances, stored as positive in our system
            # Use as-is for income statement presentation
            amount = abs(decimal_balance)
            statement[account] = amount
            total_expenses += amount

    statement["Total Revenue"] = total_revenue
    statement["Total Expenses"] = total_expenses
    statement["Net Income"] = total_revenue - total_expenses
    return statement


async def income_statement_from_ledger(
    ledger: LedgerLike, start_tick: int = 0, end_tick: Optional[int] = None
) -> Dict[str, Decimal]:
    """Deprecated: use income_statement(ledger, start_tick, end_tick) instead. This function will be removed in version 4.0.0."""
    warnings.warn(
        "income_statement_from_ledger is deprecated and will be removed in version 4.0.0. Use income_statement instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return await income_statement(ledger, start_tick, end_tick)


async def trial_balance(ledger: LedgerLike, tick: Optional[int] = None) -> Tuple[Decimal, Decimal]:
    """Calculate trial balance returning (total_debits, total_credits)."""
    balances = await ledger.trial_balance()

    total_debits = Decimal("0")
    total_credits = Decimal("0")

    for account, balance in balances.items():
        decimal_balance = _balance_to_decimal(balance)

        if account in CREDIT_NORMAL_ACCOUNTS:
            # For credit-normal accounts: positive = credit, negative = debit
            if decimal_balance >= 0:
                total_credits += decimal_balance
            else:
                total_debits += -decimal_balance
        else:
            # Debit-normal accounts: positive = debit, negative = credit
            if decimal_balance >= 0:
                total_debits += decimal_balance
            else:
                total_credits += -decimal_balance

    return total_debits, total_credits


def accounting_identity_gap(bs: Dict[str, Decimal]) -> Decimal:
    """Calculate the gap in the accounting identity A = L + E."""
    assets = sum(v for k, v in bs.items() if k in ASSET_ACCOUNTS)
    liabilities = sum(v for k, v in bs.items() if k in LIABILITY_ACCOUNTS)
    equity = sum(v for k, v in bs.items() if k in EQUITY_ACCOUNTS)

    return assets - (liabilities + equity)


def equity_delta_ex_owner(
    bs_start: Dict[str, Decimal],
    bs_end: Dict[str, Decimal],
    owner_contrib: Decimal,
    owner_dist: Decimal,
) -> Decimal:
    """Calculate equity change excluding owner contributions/distributions."""
    equity_start = sum(v for k, v in bs_start.items() if k in EQUITY_ACCOUNTS)
    equity_end = sum(v for k, v in bs_end.items() if k in EQUITY_ACCOUNTS)

    return (equity_end - equity_start) - (owner_contrib - owner_dist)


def hash_ledger_slice(ledger, start_tick: int, end_tick: Optional[int] = None) -> str:
    """Generate hash of ledger entries for specified tick range."""
    transactions = [
        {
            "description": txn.description,
            "debits": [(e.account, str(e.amount), e.timestamp.isoformat()) for e in txn.debits],
            "credits": [(e.account, str(e.amount), e.timestamp.isoformat()) for e in txn.credits],
        }
        for txn in ledger.entries
        if txn.tick >= start_tick and (end_tick is None or txn.tick <= end_tick)
    ]

    # Sort for deterministic hashing
    transactions.sort(
        key=lambda x: (x["description"], *(d[0] for d in x["debits"]))
    )  # Include debit accounts in sort for more determinism

    hash_data = json.dumps(transactions, sort_keys=True)
    return hashlib.sha256(hash_data.encode()).hexdigest()[:16]


def hash_rng_state(rng) -> str:
    """Generate robust hash of RNG state for determinism checking."""
    state = rng.getstate()
    canonical = _canonicalize_for_json(state)
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def hash_inventory_state(inventory_manager) -> str:
    """Generate hash of inventory state for drift detection."""
    inventory_data = []

    for sku, batches in inventory_manager._batches.items():
        for batch in batches:
            cents = _to_cents(batch.cost_per_unit)
            batch_data = (sku, int(batch.quantity), int(cents))
            inventory_data.append(batch_data)

    # Sort for deterministic hashing
    inventory_data.sort()

    hash_data = json.dumps(inventory_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(hash_data.encode("utf-8")).hexdigest()[:16]
