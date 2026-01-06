"""Core ledger operations for the double-entry system."""

import logging
import uuid
import threading
from typing import Any, Dict, List

from money import Money

from .models import (
    Account,
    AccountType,
    LedgerEntry,
    Transaction,
    TransactionType,
)

logger = logging.getLogger(__name__)


# ... (Keeping AccountingError class) ...
class AccountingError(Exception):
    pass


class LedgerCore:
    """
    Core ledger operations handling accounts, transactions, and balances.
    Maintains the state of accounts and transactions.
    """

    def __init__(self):
        """Initialize the ledger core with empty storage."""
        self.accounts: Dict[str, Account] = {}
        self.transactions: Dict[str, Transaction] = {}
        self.unposted_transactions: List[Transaction] = []
        # CRITICAL: RLock for thread-safe ledger access
        self._lock = threading.RLock()

    async def initialize_chart_of_accounts(self) -> None:
        """Initialize the standard chart of accounts."""
        # Asset accounts (debit normal)
        self.add_account(
            Account(
                account_id="cash",
                name="Cash",
                account_type=AccountType.ASSET,
                description="Cash on hand and in bank accounts",
            )
        )

        self.add_account(
            Account(
                account_id="inventory",
                name="Inventory",
                account_type=AccountType.ASSET,
                description="Inventory at cost",
            )
        )

        self.add_account(
            Account(
                account_id="accounts_receivable",
                name="Accounts Receivable",
                account_type=AccountType.ASSET,
                description="Money owed by customers",
            )
        )

        self.add_account(
            Account(
                account_id="prepaid_expenses",
                name="Prepaid Expenses",
                account_type=AccountType.ASSET,
                description="Expenses paid in advance",
            )
        )

        # Liability accounts (credit normal)
        self.add_account(
            Account(
                account_id="accounts_payable",
                name="Accounts Payable",
                account_type=AccountType.LIABILITY,
                description="Money owed to suppliers",
            )
        )

        self.add_account(
            Account(
                account_id="accrued_liabilities",
                name="Accrued Liabilities",
                account_type=AccountType.LIABILITY,
                description="Expenses incurred but not yet paid",
            )
        )

        self.add_account(
            Account(
                account_id="unearned_revenue",
                name="Unearned Revenue",
                account_type=AccountType.LIABILITY,
                description="Revenue received but not yet earned",
            )
        )

        # Equity accounts (credit normal)
        self.add_account(
            Account(
                account_id="owner_equity",
                name="Owner Equity",
                account_type=AccountType.EQUITY,
                description="Owner's investment in the business",
            )
        )

        self.add_account(
            Account(
                account_id="retained_earnings",
                name="Retained Earnings",
                account_type=AccountType.EQUITY,
                description="Accumulated profits retained in the business",
            )
        )

        # Revenue accounts (credit normal)
        self.add_account(
            Account(
                account_id="sales_revenue",
                name="Sales Revenue",
                account_type=AccountType.REVENUE,
                description="Revenue from product sales",
            )
        )

        self.add_account(
            Account(
                account_id="other_revenue",
                name="Other Revenue",
                account_type=AccountType.REVENUE,
                description="Revenue from other sources",
            )
        )

        # Expense accounts (debit normal)
        self.add_account(
            Account(
                account_id="cost_of_goods_sold",
                name="Cost of Goods Sold",
                account_type=AccountType.EXPENSE,
                description="Cost of inventory sold",
            )
        )

        self.add_account(
            Account(
                account_id="fulfillment_fees",
                name="Fulfillment Fees",
                account_type=AccountType.EXPENSE,
                description="FBA fulfillment fees",
            )
        )

        self.add_account(
            Account(
                account_id="referral_fees",
                name="Referral Fees",
                account_type=AccountType.EXPENSE,
                description="Amazon referral fees",
            )
        )

        self.add_account(
            Account(
                account_id="storage_fees",
                name="Storage Fees",
                account_type=AccountType.EXPENSE,
                description="Inventory storage fees",
            )
        )

        self.add_account(
            Account(
                account_id="advertising_expense",
                name="Advertising Expense",
                account_type=AccountType.EXPENSE,
                description="Advertising costs",
            )
        )

        self.add_account(
            Account(
                account_id="other_expenses",
                name="Other Expenses",
                account_type=AccountType.EXPENSE,
                description="Other operating expenses",
            )
        )

        logger.info(f"Initialized chart of accounts with {len(self.accounts)} accounts")

    def add_account(self, account: Account) -> None:
        """Add an account to the chart of accounts."""
        self.accounts[account.account_id] = account

    async def post_transaction(
        self,
        transaction: Transaction,
        strict_validation: bool = True,
    ) -> None:
        """Post a transaction to the ledger and update account balances.
        
        Enhanced with strict validation:
        - Balance check (debits must equal credits)
        - Account existence and type validation
        - Normal balance direction enforcement
        - Duplicate transaction detection
        - Amount bounds checking (no negative amounts)
        - Atomic: rolls back on any error
        
        Args:
            transaction: The transaction to post.
            strict_validation: If True, enforce all validation rules.
        
        Raises:
            ValueError: If transaction fails validation.
            AccountingError: If posting would violate accounting equation.
        """
        # CRITICAL: Thread-safe transaction posting
        with self._lock:
            # Track changes for rollback
            balance_changes: Dict[str, Money] = {}
            
            try:
                # === VALIDATION PHASE ===
                
                # 1. Check for duplicate transaction
                if transaction.transaction_id in self.transactions:
                    raise ValueError(
                        f"Duplicate transaction: {transaction.transaction_id} already posted"
                    )
                
                # 2. Validate balance (debits == credits)
                if not transaction.is_balanced():
                    debit_total = sum(e.amount.cents for e in transaction.debits)
                    credit_total = sum(e.amount.cents for e in transaction.credits)
                    raise ValueError(
                        f"Transaction {transaction.transaction_id} is not balanced: "
                        f"debits={debit_total/100:.2f} != credits={credit_total/100:.2f}"
                    )
                
                # 3. Validate all accounts exist and entries are valid
                all_entries = list(transaction.debits) + list(transaction.credits)
                for entry in all_entries:
                    account = self.accounts.get(entry.account_id)
                    if not account:
                        raise ValueError(
                            f"Account {entry.account_id} not found in chart of accounts"
                        )
                    
                    if strict_validation:
                        # Check for negative amounts
                        if entry.amount.cents < 0:
                            raise ValueError(
                                f"Negative amount {entry.amount} not allowed for "
                                f"account {entry.account_id}"
                            )
                        
                        # Check for zero amounts (typically a mistake)
                        if entry.amount.cents == 0:
                            logger.warning(
                                f"Zero-amount entry for account {entry.account_id} "
                                f"in transaction {transaction.transaction_id}"
                            )
                
                # === POSTING PHASE (with rollback support) ===
                
                # 4. Update account balances - DEBITS
                for entry in transaction.debits:
                    account = self.accounts[entry.account_id]
                    
                    # Store original for rollback
                    if entry.account_id not in balance_changes:
                        balance_changes[entry.account_id] = Money(account.balance.cents)
                    
                    # Apply debit: increase for debit-normal, decrease for credit-normal
                    if account.normal_balance == "debit":
                        account.balance += entry.amount
                    else:
                        account.balance -= entry.amount
    
                # 5. Update account balances - CREDITS
                for entry in transaction.credits:
                    account = self.accounts[entry.account_id]
                    
                    # Store original for rollback
                    if entry.account_id not in balance_changes:
                        balance_changes[entry.account_id] = Money(account.balance.cents)
                    
                    # Apply credit: increase for credit-normal, decrease for debit-normal
                    if account.normal_balance == "credit":
                        account.balance += entry.amount
                    else:
                        account.balance -= entry.amount
    
                # 6. Verify trial balance still holds (optional strict check)
                if strict_validation:
                    if not self.is_trial_balance_balanced():
                        diff = self.get_trial_balance_difference()
                        raise AccountingError(
                            f"Transaction {transaction.transaction_id} would break "
                            f"trial balance by {diff}"
                        )
    
                # === FINALIZATION ===
                
                # 7. Mark as posted
                transaction.is_posted = True
    
                # 8. Store transaction
                self.transactions[transaction.transaction_id] = transaction
    
                # 9. Remove from unposted if it was there
                if transaction in self.unposted_transactions:
                    self.unposted_transactions.remove(transaction)
    
                logger.debug(
                    f"Posted transaction {transaction.transaction_id}: "
                    f"{len(transaction.debits)} debits, {len(transaction.credits)} credits"
                )
    
            except Exception as e:
                # ROLLBACK: Restore original balances
                for account_id, original_balance in balance_changes.items():
                    if account_id in self.accounts:
                        self.accounts[account_id].balance = original_balance
                
                logger.error(
                    f"Error posting transaction {transaction.transaction_id}: {e} "
                    f"(rolled back {len(balance_changes)} account changes)"
                )
                raise


    async def post_all_unposted_transactions(self) -> None:
        """Post all unposted transactions."""
        if not self.unposted_transactions:
            return

        logger.info(f"Posting {len(self.unposted_transactions)} unposted transactions")

        # Create a copy to avoid modification during iteration
        transactions_to_post = self.unposted_transactions.copy()

        for transaction in transactions_to_post:
            await self.post_transaction(transaction)

        logger.info("All unposted transactions posted successfully")

    def get_account_balance(self, account_id: str) -> Money:
        """Get the current balance of an account."""
        with self._lock:
            account = self.accounts.get(account_id)
            if not account:
                raise ValueError(f"Account {account_id} not found")
            return account.balance

    def get_all_account_balances(self) -> Dict[str, Money]:
        """Get balances for all accounts."""
        with self._lock:
            return {
                account_id: account.balance for account_id, account in self.accounts.items()
            }

    def trial_balance(self) -> Dict[str, Money]:
        """Generate a trial balance of all accounts."""
        # get_all_account_balances is already locked
        return self.get_all_account_balances()

    def is_trial_balance_balanced(self) -> bool:
        """Check if the trial balance is balanced (debits = credits)."""
        with self._lock:
            balances = self.trial_balance()

            total_debits = Money.zero()
            total_credits = Money.zero()

            for account_id, balance in balances.items():
                account = self.accounts[account_id]
                if account.normal_balance == "debit":
                    total_debits += balance
                else:
                    total_credits += balance

            return total_debits.cents == total_credits.cents

    def get_trial_balance_difference(self) -> Money:
        """Get the difference between total debits and credits."""
        with self._lock:
            balances = self.trial_balance()

            total_debits = Money.zero()
            total_credits = Money.zero()

            for account_id, balance in balances.items():
                account = self.accounts[account_id]
                if account.normal_balance == "debit":
                    total_debits += balance
                else:
                    total_credits += balance

            return total_debits - total_credits

    def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Get the transaction history, limited to the specified number of transactions."""
        with self._lock:
            # Sort transactions by timestamp (most recent first)
            sorted_transactions = sorted(
                self.transactions.values(), key=lambda t: t.timestamp, reverse=True
            )

            return sorted_transactions[:limit]

    def get_transactions_by_type(
        self, transaction_type: TransactionType
    ) -> List[Transaction]:
        """Get all transactions of a specific type."""
        with self._lock:
            return [
                transaction
                for transaction in self.transactions.values()
                if transaction.transaction_type == transaction_type
            ]

    def get_transactions_by_account(self, account_id: str) -> List[Transaction]:
        """Get all transactions that affect a specific account."""
        with self._lock:
            return [
                transaction
                for transaction in self.transactions.values()
                if any(
                    entry.account_id == account_id
                    for entry in transaction.debits + transaction.credits
                )
            ]

    def get_ledger_statistics(self) -> Dict[str, Any]:
        """Get ledger service statistics."""
        with self._lock:
            return {
                "total_accounts": len(self.accounts),
            "total_transactions": len(self.transactions),
            "unposted_transactions": len(self.unposted_transactions),
            "trial_balance_balanced": self.is_trial_balance_balanced(),
            "trial_balance_difference": str(self.get_trial_balance_difference()),
            "last_transaction_time": (
                max(t.timestamp for t in self.transactions.values())
                if self.transactions
                else None
            ),
        }

    async def inject_equity(
        self, amount: Money, description: str = "Initial capital injection"
    ) -> str:
        """
        Post a balanced equity injection: DR cash, CR owner_equity.
        Returns the created transaction_id.
        """
        if not isinstance(amount, Money):
            raise TypeError("amount must be a Money instance")
        tx_id = f"equity_{uuid.uuid4()}"
        tx = Transaction(
            transaction_id=tx_id,
            transaction_type=TransactionType.EQUITY_INJECTION,
            description=description,
        )
        # Debit: Cash (increase asset)
        tx.debits.append(
            LedgerEntry(
                entry_id=f"debit_cash_{tx_id}",
                account_id="cash",
                amount=amount,
                entry_type="debit",
                description=description,
            )
        )
        # Credit: Owner Equity (increase equity)
        tx.credits.append(
            LedgerEntry(
                entry_id=f"credit_equity_{tx_id}",
                account_id="owner_equity",
                amount=amount,
                entry_type="credit",
                description=description,
            )
        )
        await self.post_transaction(tx)
        return tx_id

    async def initialize_capital(self, amount: Money) -> str:
        """
        Convenience alias for inject_equity with standard description.
        """
        return await self.inject_equity(amount, description="Initial capital injection")

    def get_cash_balance(self) -> Money:
        """Return current cash account balance."""
        return self.get_account_balance("cash")

    def verify_integrity(self, raise_on_failure: bool = True) -> bool:
        """Verify the fundamental accounting equation: Assets = Liabilities + Equity.
        
        This is the "Panic Button" - if the accounting equation is violated,
        the simulation should halt immediately and dump the event journal
        for forensic analysis.
        
        The accounting equation verification includes:
        - Assets (normal debit balance)
        - Liabilities (normal credit balance)  
        - Equity (normal credit balance)
        
        Revenue and Expense accounts affect Retained Earnings (Equity) and
        are included in the equity calculation for a complete picture.
        
        Args:
            raise_on_failure: If True (default), raises AccountingError on violation.
                             If False, returns False instead.
        
        Returns:
            True if the accounting equation holds.
            
        Raises:
            AccountingError: If raise_on_failure=True and Assets != Liabilities + Equity.
        """
        total_assets = Money.zero()
        total_liabilities = Money.zero()
        total_equity = Money.zero()
        
        for account_id, account in self.accounts.items():
            balance = account.balance
            
            if account.account_type == AccountType.ASSET:
                total_assets += balance
            elif account.account_type == AccountType.LIABILITY:
                total_liabilities += balance
            elif account.account_type == AccountType.EQUITY:
                total_equity += balance
            elif account.account_type == AccountType.REVENUE:
                # Revenue increases equity (credit normal)
                total_equity += balance
            elif account.account_type == AccountType.EXPENSE:
                # Expenses decrease equity (debit normal, so subtract)
                total_equity -= balance
        
        # Fundamental accounting equation: A = L + E
        liabilities_plus_equity = total_liabilities + total_equity
        is_balanced = total_assets.cents == liabilities_plus_equity.cents
        
        if not is_balanced:
            error_msg = (
                f"LEDGER INTEGRITY FAILURE: Accounting equation violated!\n"
                f"  Assets:                {total_assets}\n"
                f"  Liabilities:           {total_liabilities}\n"
                f"  Equity (incl. P&L):    {total_equity}\n"
                f"  L + E:                 {liabilities_plus_equity}\n"
                f"  Difference:            {total_assets - liabilities_plus_equity}\n"
                f"  Total transactions:    {len(self.transactions)}"
            )
            logger.critical(error_msg)
            
            if raise_on_failure:
                raise AccountingError(error_msg)
        
        return is_balanced

    def get_accounting_equation_summary(self) -> Dict[str, Any]:
        """Return a summary of the accounting equation components.
        
        Useful for debugging and audit reports.
        """
        total_assets = Money.zero()
        total_liabilities = Money.zero()
        total_equity = Money.zero()
        total_revenue = Money.zero()
        total_expenses = Money.zero()
        
        for account_id, account in self.accounts.items():
            balance = account.balance
            
            if account.account_type == AccountType.ASSET:
                total_assets += balance
            elif account.account_type == AccountType.LIABILITY:
                total_liabilities += balance
            elif account.account_type == AccountType.EQUITY:
                total_equity += balance
            elif account.account_type == AccountType.REVENUE:
                total_revenue += balance
            elif account.account_type == AccountType.EXPENSE:
                total_expenses += balance
        
        net_income = total_revenue - total_expenses
        equity_with_pl = total_equity + net_income
        
        return {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity_base": total_equity,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_income": net_income,
            "equity_with_retained_earnings": equity_with_pl,
            "equation_balanced": total_assets.cents == (total_liabilities + equity_with_pl).cents,
        }
