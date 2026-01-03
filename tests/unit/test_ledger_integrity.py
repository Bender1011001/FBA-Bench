"""Tests for ledger integrity verification - the 'Panic Button'.

These tests verify that the fundamental accounting equation (A = L + E) is
properly enforced and that violations are caught and reported.
"""

import pytest
from money import Money

from fba_bench_core.services.ledger import (
    Account,
    AccountType,
    AccountingError,
    DoubleEntryLedgerService,
    LedgerEntry,
    Transaction,
    TransactionType,
)
from fba_bench_core.services.ledger.core import LedgerCore


class TestLedgerIntegrity:
    """Tests for verify_integrity() method."""

    @pytest.fixture
    def ledger_core(self):
        """Create a fresh LedgerCore with chart of accounts."""
        core = LedgerCore()
        # Use sync initialization for tests
        import asyncio
        asyncio.get_event_loop().run_until_complete(core.initialize_chart_of_accounts())
        return core

    @pytest.fixture
    def ledger_service(self):
        """Create a fresh DoubleEntryLedgerService."""
        return DoubleEntryLedgerService(config={})

    def test_verify_integrity_passes_on_balanced_ledger(self, ledger_core):
        """A newly initialized ledger should pass integrity check."""
        assert ledger_core.verify_integrity() is True

    def test_verify_integrity_passes_after_balanced_transaction(self, ledger_core):
        """Integrity should pass after posting balanced transactions."""
        import asyncio
        
        # Create a balanced transaction: inject equity
        tx = Transaction(
            transaction_id="test-equity-001",
            transaction_type=TransactionType.EQUITY_INJECTION,
            description="Test capital injection",
        )
        tx.debits.append(
            LedgerEntry(
                entry_id="debit-cash-001",
                account_id="cash",
                amount=Money.from_dollars("10000"),
                entry_type="debit",
                description="Initial capital",
            )
        )
        tx.credits.append(
            LedgerEntry(
                entry_id="credit-equity-001",
                account_id="owner_equity",
                amount=Money.from_dollars("10000"),
                entry_type="credit",
                description="Initial capital",
            )
        )
        
        asyncio.get_event_loop().run_until_complete(
            ledger_core.post_transaction(tx)
        )
        
        assert ledger_core.verify_integrity() is True

    def test_verify_integrity_fails_on_manual_imbalance(self, ledger_core):
        """Manually corrupting an account balance should trigger failure."""
        import asyncio
        
        # First inject some capital to have non-zero balances
        asyncio.get_event_loop().run_until_complete(
            ledger_core.inject_equity(Money.from_dollars("5000"))
        )
        
        # Manually corrupt the cash balance (simulating a bug)
        cash_account = ledger_core.accounts.get("cash")
        original_balance = cash_account.balance
        cash_account.balance = Money.from_dollars("9999.99")  # Corrupt it!
        
        # Should fail with raise_on_failure=False
        assert ledger_core.verify_integrity(raise_on_failure=False) is False
        
        # Should raise AccountingError by default
        with pytest.raises(AccountingError) as exc_info:
            ledger_core.verify_integrity()
        
        assert "LEDGER INTEGRITY FAILURE" in str(exc_info.value)
        assert "Accounting equation violated" in str(exc_info.value)
        
        # Restore balance
        cash_account.balance = original_balance

    def test_verify_integrity_includes_revenue_and_expenses(self, ledger_core):
        """Revenue and expenses should be factored into equity for verification."""
        import asyncio
        
        # Inject capital first
        asyncio.get_event_loop().run_until_complete(
            ledger_core.inject_equity(Money.from_dollars("1000"))
        )
        
        # Create a sale transaction
        # DR Cash 100, CR Sales Revenue 100
        tx = Transaction(
            transaction_id="test-sale-001",
            transaction_type=TransactionType.SALE,
            description="Test sale",
        )
        tx.debits.append(
            LedgerEntry(
                entry_id="debit-cash-sale",
                account_id="cash",
                amount=Money.from_dollars("100"),
                entry_type="debit",
            )
        )
        tx.credits.append(
            LedgerEntry(
                entry_id="credit-revenue-sale",
                account_id="sales_revenue",
                amount=Money.from_dollars("100"),
                entry_type="credit",
            )
        )
        
        asyncio.get_event_loop().run_until_complete(
            ledger_core.post_transaction(tx)
        )
        
        # Should still pass - revenue is included in equity calculation
        assert ledger_core.verify_integrity() is True
        
        # Summary should show revenue
        summary = ledger_core.get_accounting_equation_summary()
        assert summary["total_revenue"].cents == 10000  # $100 in cents
        assert summary["equation_balanced"] is True

    def test_get_accounting_equation_summary(self, ledger_core):
        """Summary should correctly break down all account types."""
        import asyncio
        
        # Inject capital
        asyncio.get_event_loop().run_until_complete(
            ledger_core.inject_equity(Money.from_dollars("5000"))
        )
        
        summary = ledger_core.get_accounting_equation_summary()
        
        assert "total_assets" in summary
        assert "total_liabilities" in summary
        assert "total_equity_base" in summary
        assert "total_revenue" in summary
        assert "total_expenses" in summary
        assert "net_income" in summary
        assert "equity_with_retained_earnings" in summary
        assert "equation_balanced" in summary
        
        # Check equation is balanced
        assert summary["equation_balanced"] is True

    def test_service_verify_integrity_proxy(self, ledger_service):
        """DoubleEntryLedgerService should expose verify_integrity()."""
        # Should pass with fresh ledger (no transactions yet)
        assert ledger_service.verify_integrity() is True
        
        # Summary should also work
        summary = ledger_service.get_accounting_equation_summary()
        assert isinstance(summary, dict)
        assert "equation_balanced" in summary


class TestAccountingErrorException:
    """Tests for the AccountingError exception class."""

    def test_accounting_error_is_exception(self):
        """AccountingError should be a proper Exception subclass."""
        assert issubclass(AccountingError, Exception)

    def test_accounting_error_message(self):
        """AccountingError should preserve its message."""
        error = AccountingError("Test error message")
        assert str(error) == "Test error message"

    def test_accounting_error_can_be_caught(self):
        """AccountingError should be catchable."""
        try:
            raise AccountingError("Deliberate test error")
        except AccountingError as e:
            assert "Deliberate test error" in str(e)
        else:
            pytest.fail("AccountingError was not raised")
