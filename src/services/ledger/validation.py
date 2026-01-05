"""Transaction validation and accounting rule enforcement for the ledger."""

import logging
from typing import Dict, List

from .models import LedgerEntry, Transaction

logger = logging.getLogger(__name__)


class LedgerValidator:
    """
    Validates transactions and accounting rules before posting.
    """

    def validate_transaction(
        self, transaction: Transaction, accounts: Dict[str, "Account"]
    ) -> None:
        """
        Validate a transaction before posting.

        Checks:
        - Transaction is balanced (debits == credits)
        - All referenced accounts exist
        - Amounts are positive
        """
        # Check if transaction is balanced
        if not transaction.is_balanced():
            raise ValueError(
                f"Transaction {transaction.transaction_id} is not balanced"
            )

        # Collect all account IDs
        account_ids = set()
        for entry in transaction.debits + transaction.credits:
            account_ids.add(entry.account_id)
            if entry.amount.cents <= 0:
                raise ValueError(
                    f"Transaction {transaction.transaction_id} has non-positive amount "
                    f"in entry {entry.entry_id}: {entry.amount}"
                )

        # Check all accounts exist
        for account_id in account_ids:
            if account_id not in accounts:
                raise ValueError(
                    f"Account {account_id} not found for transaction {transaction.transaction_id}"
                )

        logger.debug(f"Validated transaction {transaction.transaction_id}")

    def validate_account_normal_balance(
        self, account_id: str, entry_type: str, accounts: Dict[str, "Account"]
    ) -> None:
        """
        Validate that the entry type matches the account's normal balance.
        This is advisory - double-entry allows opposite entries for temporary imbalances.
        """
        account = accounts.get(account_id)
        if not account:
            return

        expected = account.normal_balance
        if entry_type != expected:
            logger.warning(
                f"Entry type '{entry_type}' does not match normal balance '{expected}' "
                f"for account '{account_id}' ({account.name})"
            )

    def validate_posting_amounts(
        self, debits: List[LedgerEntry], credits: List[LedgerEntry]
    ) -> None:
        """Validate that debit and credit amounts are positive and match totals."""
        total_debits = sum(entry.amount for entry in debits)
        total_credits = sum(entry.amount for entry in credits)

        if total_debits != total_credits:
            raise ValueError(
                f"Debit total {total_debits} does not match credit total {total_credits}"
            )

        for entry in debits + credits:
            if entry.amount.cents <= 0:
                raise ValueError(
                    f"Entry {entry.entry_id} has non-positive amount: {entry.amount}"
                )
