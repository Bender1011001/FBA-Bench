"""Typed Chart of Accounts for GAAP-Compliant Financial Simulation.

This module defines the physics of money in the FBA simulation. All financial
transactions MUST reference accounts defined here - string-based account IDs
are forbidden for type safety.

The chart follows standard GAAP classification:
- Assets (1xxx): Debit normal balance
- Liabilities (2xxx): Credit normal balance
- Equity (3xxx): Credit normal balance
- Revenue (4xxx): Credit normal balance
- Expenses (5xxx, 6xxx): Debit normal balance

Usage:
    from fba_bench_core.domain.finance.chart_of_accounts import Account, AccountType
    
    # Reference accounts by enum
    cash = Account.CASH
    print(f"Account: {cash.code} - {cash.name} ({cash.account_type.value})")
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class AccountType(str, Enum):
    """GAAP account type classification.
    
    Determines the normal balance direction:
    - ASSET, EXPENSE: Debit normal (increases on debit)
    - LIABILITY, EQUITY, REVENUE: Credit normal (increases on credit)
    """
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"
    
    @property
    def normal_balance(self) -> str:
        """Return the normal balance direction for this account type."""
        if self in (AccountType.ASSET, AccountType.EXPENSE):
            return "debit"
        return "credit"
    
    @property
    def increases_on_debit(self) -> bool:
        """Whether debits increase this account type."""
        return self in (AccountType.ASSET, AccountType.EXPENSE)


class AccountInfo(NamedTuple):
    """Account metadata tuple for enum values."""
    code: str
    name: str
    account_type: AccountType


class Account(Enum):
    """Typed Chart of Accounts for FBA Simulation.
    
    Each account has:
    - code: Numeric account code (for sorting and grouping)
    - name: Human-readable account name
    - account_type: GAAP classification (ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE)
    
    Accounts are organized by type:
    - 1000-1999: Assets
    - 2000-2999: Liabilities
    - 3000-3999: Equity
    - 4000-4999: Revenue
    - 5000-5999: Cost of Goods Sold
    - 6000-6999: Operating Expenses
    """
    
    # =========================================================================
    # ASSETS (1xxx) - Debit normal balance
    # =========================================================================
    
    # Cash & Equivalents
    CASH = AccountInfo("1000", "Cash on Hand", AccountType.ASSET)
    BANK_ACCOUNT = AccountInfo("1010", "Bank Account", AccountType.ASSET)
    ACCOUNTS_RECEIVABLE = AccountInfo("1100", "Accounts Receivable", AccountType.ASSET)
    
    # Inventory Assets
    INVENTORY_ON_HAND = AccountInfo("1200", "Inventory On Hand", AccountType.ASSET)
    INVENTORY_IN_TRANSIT = AccountInfo("1210", "Inventory In Transit", AccountType.ASSET)
    INVENTORY_FBA_WAREHOUSE = AccountInfo("1220", "Inventory at FBA Warehouse", AccountType.ASSET)
    INVENTORY_RESERVE = AccountInfo("1230", "Inventory Reserve (Damaged/Returns)", AccountType.ASSET)
    
    # Prepaid & Other Assets
    PREPAID_EXPENSES = AccountInfo("1300", "Prepaid Expenses", AccountType.ASSET)
    PREPAID_ADVERTISING = AccountInfo("1310", "Prepaid Advertising", AccountType.ASSET)
    DEPOSITS = AccountInfo("1400", "Deposits", AccountType.ASSET)
    
    # =========================================================================
    # LIABILITIES (2xxx) - Credit normal balance
    # =========================================================================
    
    ACCOUNTS_PAYABLE = AccountInfo("2000", "Accounts Payable", AccountType.LIABILITY)
    ACCRUED_LIABILITIES = AccountInfo("2100", "Accrued Liabilities", AccountType.LIABILITY)
    UNEARNED_REVENUE = AccountInfo("2200", "Unearned Revenue", AccountType.LIABILITY)
    SALES_TAX_PAYABLE = AccountInfo("2300", "Sales Tax Payable", AccountType.LIABILITY)
    AMAZON_SETTLEMENT_DUE = AccountInfo("2400", "Amazon Settlement Due", AccountType.LIABILITY)
    
    # =========================================================================
    # EQUITY (3xxx) - Credit normal balance
    # =========================================================================
    
    STARTING_CAPITAL = AccountInfo("3000", "Starting Capital", AccountType.EQUITY)
    OWNER_EQUITY = AccountInfo("3100", "Owner's Equity", AccountType.EQUITY)
    RETAINED_EARNINGS = AccountInfo("3200", "Retained Earnings", AccountType.EQUITY)
    OWNER_DRAWS = AccountInfo("3300", "Owner's Draws", AccountType.EQUITY)  # Contra-equity
    
    # =========================================================================
    # REVENUE (4xxx) - Credit normal balance
    # =========================================================================
    
    SALES_REVENUE = AccountInfo("4000", "Gross Sales Revenue", AccountType.REVENUE)
    SALES_RETURNS = AccountInfo("4100", "Sales Returns & Allowances", AccountType.REVENUE)  # Contra-revenue
    SHIPPING_REVENUE = AccountInfo("4200", "Shipping Revenue", AccountType.REVENUE)
    OTHER_INCOME = AccountInfo("4900", "Other Income", AccountType.REVENUE)
    
    # =========================================================================
    # COST OF GOODS SOLD (5xxx) - Debit normal balance
    # =========================================================================
    
    COGS = AccountInfo("5000", "Cost of Goods Sold", AccountType.EXPENSE)
    COGS_PRODUCT_COST = AccountInfo("5100", "Product Cost", AccountType.EXPENSE)
    COGS_FREIGHT_IN = AccountInfo("5200", "Inbound Freight", AccountType.EXPENSE)
    COGS_CUSTOMS_DUTIES = AccountInfo("5300", "Customs & Duties", AccountType.EXPENSE)
    COGS_BREAKAGE = AccountInfo("5400", "Breakage & Damage", AccountType.EXPENSE)
    
    # =========================================================================
    # OPERATING EXPENSES (6xxx) - Debit normal balance
    # =========================================================================
    
    # Amazon Fees
    FBA_FULFILLMENT_FEES = AccountInfo("6100", "FBA Fulfillment Fees", AccountType.EXPENSE)
    FBA_REFERRAL_FEES = AccountInfo("6110", "Referral Fees", AccountType.EXPENSE)
    FBA_STORAGE_FEES = AccountInfo("6120", "FBA Storage Fees", AccountType.EXPENSE)
    FBA_STORAGE_FEES_AGED = AccountInfo("6121", "Aged Inventory Storage Fees", AccountType.EXPENSE)
    FBA_REMOVAL_FEES = AccountInfo("6130", "FBA Removal Fees", AccountType.EXPENSE)
    FBA_LONG_TERM_STORAGE = AccountInfo("6140", "Long-Term Storage Fees", AccountType.EXPENSE)
    
    # Marketing & Advertising
    AD_SPEND_PPC = AccountInfo("6200", "PPC Advertising", AccountType.EXPENSE)
    AD_SPEND_SPONSORED_BRANDS = AccountInfo("6210", "Sponsored Brands", AccountType.EXPENSE)
    AD_SPEND_SPONSORED_DISPLAY = AccountInfo("6220", "Sponsored Display", AccountType.EXPENSE)
    AD_SPEND_DSP = AccountInfo("6230", "DSP Advertising", AccountType.EXPENSE)
    
    # Operations
    SOFTWARE_TOOLS = AccountInfo("6300", "Software & Tools", AccountType.EXPENSE)
    PROFESSIONAL_SERVICES = AccountInfo("6310", "Professional Services", AccountType.EXPENSE)
    SUPPLIES = AccountInfo("6320", "Supplies", AccountType.EXPENSE)
    INSURANCE = AccountInfo("6400", "Insurance", AccountType.EXPENSE)
    
    # Other Expenses
    PAYMENT_PROCESSING = AccountInfo("6500", "Payment Processing Fees", AccountType.EXPENSE)
    CHARGEBACKS = AccountInfo("6510", "Chargebacks & Disputes", AccountType.EXPENSE)
    REFUNDS_GIVEN = AccountInfo("6520", "Refunds Issued", AccountType.EXPENSE)
    OTHER_EXPENSES = AccountInfo("6900", "Other Operating Expenses", AccountType.EXPENSE)
    
    # -------------------------------------------------------------------------
    # Accessor Properties
    # -------------------------------------------------------------------------
    
    @property
    def code(self) -> str:
        """Return the numeric account code."""
        return self.value.code
    
    @property
    def name(self) -> str:
        """Return the human-readable account name."""
        return self.value.name
    
    @property
    def account_type(self) -> AccountType:
        """Return the GAAP account type classification."""
        return self.value.account_type
    
    @property
    def normal_balance(self) -> str:
        """Return the normal balance direction (debit or credit)."""
        return self.account_type.normal_balance
    
    @property
    def increases_on_debit(self) -> bool:
        """Whether debits increase this account."""
        return self.account_type.increases_on_debit
    
    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_by_code(cls, code: str) -> "Account":
        """Look up an account by its numeric code.
        
        Args:
            code: The account code (e.g., "1000", "5000")
            
        Returns:
            The matching Account enum member.
            
        Raises:
            ValueError: If no account matches the code.
        """
        for account in cls:
            if account.code == code:
                return account
        raise ValueError(f"No account found with code: {code}")
    
    @classmethod
    def get_by_type(cls, account_type: AccountType) -> list["Account"]:
        """Return all accounts of a given type.
        
        Args:
            account_type: The account type to filter by.
            
        Returns:
            List of accounts matching the type.
        """
        return [acct for acct in cls if acct.account_type == account_type]
    
    @classmethod
    def get_assets(cls) -> list["Account"]:
        """Return all asset accounts."""
        return cls.get_by_type(AccountType.ASSET)
    
    @classmethod
    def get_liabilities(cls) -> list["Account"]:
        """Return all liability accounts."""
        return cls.get_by_type(AccountType.LIABILITY)
    
    @classmethod
    def get_equity(cls) -> list["Account"]:
        """Return all equity accounts."""
        return cls.get_by_type(AccountType.EQUITY)
    
    @classmethod
    def get_revenue(cls) -> list["Account"]:
        """Return all revenue accounts."""
        return cls.get_by_type(AccountType.REVENUE)
    
    @classmethod
    def get_expenses(cls) -> list["Account"]:
        """Return all expense accounts (including COGS)."""
        return cls.get_by_type(AccountType.EXPENSE)


# =============================================================================
# Account Code Ranges (for validation)
# =============================================================================

ACCOUNT_CODE_RANGES = {
    AccountType.ASSET: ("1000", "1999"),
    AccountType.LIABILITY: ("2000", "2999"),
    AccountType.EQUITY: ("3000", "3999"),
    AccountType.REVENUE: ("4000", "4999"),
    AccountType.EXPENSE: ("5000", "6999"),
}


def validate_account_code(account: Account) -> bool:
    """Validate that an account's code is in the correct range for its type."""
    code = int(account.code)
    min_code, max_code = ACCOUNT_CODE_RANGES[account.account_type]
    return int(min_code) <= code <= int(max_code)


# Validate all accounts on module load
for _account in Account:
    assert validate_account_code(_account), (
        f"Account {_account.name} ({_account.code}) is not in valid range "
        f"for type {_account.account_type.value}"
    )
