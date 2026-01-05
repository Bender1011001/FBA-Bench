"""Financial statement generation for the double-entry ledger."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from money import Money

from .core import LedgerCore
from .models import AccountType, FinancialStatement

logger = logging.getLogger(__name__)


class StatementsGenerator:
    """
    Handles generation of financial statements from ledger data.
    """

    def __init__(self, ledger_core: LedgerCore):
        """Initialize with reference to ledger core for data access."""
        self.ledger_core = ledger_core
        self.balance_sheet_cache: Optional[FinancialStatement] = None
        self.income_statement_cache: Optional[FinancialStatement] = None

    def generate_balance_sheet(self, force_refresh: bool = False) -> FinancialStatement:
        """Generate a balance sheet statement."""
        if self.balance_sheet_cache and not force_refresh:
            return self.balance_sheet_cache

        # Ensure all transactions are posted (log warning if unposted exist)
        if self.ledger_core.unposted_transactions:
            logger.warning(
                "Unposted transactions exist. Posting them before generating balance sheet."
            )

        # Calculate account balances
        balances = self.ledger_core.get_all_account_balances()

        # Prepare balance sheet data
        balance_sheet_data = {"assets": {}, "liabilities": {}, "equity": {}}

        total_assets = Money.zero()
        total_liabilities = Money.zero()
        total_equity = Money.zero()

        for account_id, balance in balances.items():
            account = self.ledger_core.accounts[account_id]

            if account.account_type == AccountType.ASSET:
                balance_sheet_data["assets"][account_id] = {
                    "name": account.name,
                    "balance": balance,
                    "description": account.description,
                }
                total_assets += balance

            elif account.account_type == AccountType.LIABILITY:
                balance_sheet_data["liabilities"][account_id] = {
                    "name": account.name,
                    "balance": balance,
                    "description": account.description,
                }
                total_liabilities += balance

            elif account.account_type == AccountType.EQUITY:
                balance_sheet_data["equity"][account_id] = {
                    "name": account.name,
                    "balance": balance,
                    "description": account.description,
                }
                total_equity += balance

        # Add totals
        balance_sheet_data["total_assets"] = total_assets
        balance_sheet_data["total_liabilities"] = total_liabilities
        balance_sheet_data["total_equity"] = total_equity

        # Check accounting identity
        balance_sheet_data["accounting_identity_valid"] = (
            total_assets.cents == (total_liabilities + total_equity).cents
        )
        balance_sheet_data["identity_difference"] = total_assets - (
            total_liabilities + total_equity
        )

        # Create financial statement
        balance_sheet = FinancialStatement(
            statement_type="balance_sheet",
            period_start=datetime.min,  # Since beginning of time
            period_end=datetime.now(),
            data=balance_sheet_data,
        )

        # Cache the result
        self.balance_sheet_cache = balance_sheet

        return balance_sheet

    def generate_income_statement(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> FinancialStatement:
        """Generate an income statement for the specified period."""
        if self.income_statement_cache and not force_refresh:
            return self.income_statement_cache

        # For now, we'll generate a simple income statement from current balances
        # In a full implementation, this would filter transactions by date

        # Get account balances
        balances = self.ledger_core.get_all_account_balances()

        # Prepare income statement data
        income_statement_data = {"revenue": {}, "expenses": {}}

        total_revenue = Money.zero()
        total_expenses = Money.zero()

        for account_id, balance in balances.items():
            account = self.ledger_core.accounts[account_id]

            if account.account_type == AccountType.REVENUE:
                income_statement_data["revenue"][account_id] = {
                    "name": account.name,
                    "balance": balance,
                    "description": account.description,
                }
                total_revenue += balance

            elif account.account_type == AccountType.EXPENSE:
                income_statement_data["expenses"][account_id] = {
                    "name": account.name,
                    "balance": balance,
                    "description": account.description,
                }
                total_expenses += balance

        # Calculate totals and net income
        income_statement_data["total_revenue"] = total_revenue
        income_statement_data["total_expenses"] = total_expenses
        income_statement_data["net_income"] = total_revenue - total_expenses

        # Create financial statement
        income_statement = FinancialStatement(
            statement_type="income_statement",
            period_start=period_start or datetime.min,
            period_end=period_end or datetime.now(),
            data=income_statement_data,
        )

        # Cache the result
        self.income_statement_cache = income_statement

        return income_statement

    def invalidate_cache(self) -> None:
        """Invalidate all financial statement caches."""
        self.balance_sheet_cache = None
        self.income_statement_cache = None

    def get_financial_position(self) -> Dict[str, Any]:
        """Get the current financial position for audit purposes."""
        balance_sheet = self.generate_balance_sheet()
        income_statement = self.generate_income_statement()

        return {
            "timestamp": datetime.now(),
            "cash": self.ledger_core.get_cash_balance(),
            "inventory_value": self.ledger_core.get_account_balance("inventory"),
            "accounts_receivable": self.ledger_core.get_account_balance(
                "accounts_receivable"
            ),
            "total_assets": balance_sheet.data["total_assets"],
            "accounts_payable": self.ledger_core.get_account_balance(
                "accounts_payable"
            ),
            "accrued_liabilities": self.ledger_core.get_account_balance(
                "accrued_liabilities"
            ),
            "total_liabilities": balance_sheet.data["total_liabilities"],
            "retained_earnings": self.ledger_core.get_account_balance(
                "retained_earnings"
            ),
            "current_period_profit": income_statement.data["net_income"],
            "total_equity": balance_sheet.data["total_equity"],
            "accounting_identity_valid": balance_sheet.data[
                "accounting_identity_valid"
            ],
            "identity_difference": balance_sheet.data["identity_difference"],
        }
