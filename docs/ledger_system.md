# Double-Entry Ledger System

## Overview

FBA-Bench distinguishes itself from other "roleplay" based simulations by enforcing **strict financial fidelity**. At the core of the simulation lies a professional-grade Double-Entry Ledger that adheres to Generally Accepted Accounting Principles (GAAP).

Unlike systems that simply track "points" or "money" as a single variable, our ledger ensures that every penny is accounted for through balanced debits and credits.

## Core Features

### 1. The "Panic Button" (Integrity Verification)

The system continuously verifies the fundamental accounting equation:

$$ \text{Assets} = \text{Liabilities} + \text{Equity} $$

If this equation is ever violated—even by a fraction of a cent—the ledger’s `verify_integrity(...)` check can be used as a "Panic Button".

*   **Behavior**: Callers can treat integrity failure as a hard stop (the ledger logs a critical error and can raise `AccountingError`).
*   **Forensics**: The critical log includes a full accounting equation breakdown and transaction counts for debugging.
*   **Why it matters**: This guarantees that the simulation results are mathematically impossible to "hallucinate." Profit is not an opinion; it is a derived fact from balanced transactions.

### 2. Atomic Transactions & Concurrency

The ledger handles high-frequency trading and automated agents through strict concurrency controls.

*   **Atomic Locking**: The `post_transaction` method uses `asyncio.Lock` to serialize all writes.
*   **All-or-Nothing**: Transactions are atomic. If *any* part of a transaction fails validation (e.g., negative balance in a strict account, unequal debits/credits), the entire transaction is rolled back, ensuring the ledger never enters an invalid state.

### 3. Chart of Accounts

The system initializes with a standard Chart of Accounts structure:

*   **Assets** (Debit Normal): Cash, Inventory, Accounts Receivable, Prepaid Expenses.
*   **Liabilities** (Credit Normal): Accounts Payable, Accrued Liabilities, Unearned Revenue.
*   **Equity** (Credit Normal): Owner Equity, Retained Earnings.
*   **Revenue** (Credit Normal): Sales Revenue, Other Revenue.
*   **Expenses** (Debit Normal): Cost of Goods Sold, Fulfillment Fees, Advertising, etc.

## Technical Implementation

The implementation acts as a source of truth for the entire simulation state.

### Key Methods

*   `verify_integrity()`: The watchdog ensuring mathematical correctness.
*   `post_transaction(transaction)`: The gatekeeper for all state changes. Performs zero-sum validation ($\Sigma \text{Debits} - \Sigma \text{Credits} = 0$).
*   `initialize_chart_of_accounts()`: Sets up the GAAP-compliant account structure.

Implementation references:
- `src/services/ledger/core.py`
- `src/services/ledger/models.py`
- `src/services/ledger/validation.py`

## Integration

Agents do not "update their balance." They submit legal **Transactions**. The ledger determines the resulting balance. This separation of concerns prevents agents from hallucinating wealth or bypassing costs.
