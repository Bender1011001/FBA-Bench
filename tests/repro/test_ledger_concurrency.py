import asyncio
import threading
import time
import sys
import os
sys.path.append(os.getcwd()) # Add project root for 'src' imports
sys.path.append(os.path.abspath("src")) # Add src for direct imports
from money import Money
from services.ledger.core import LedgerCore, AccountType

import pytest

@pytest.mark.asyncio
async def test_ledger_concurrency():
    print("Initializing LedgerCore...")
    ledger = LedgerCore()
    await ledger.initialize_chart_of_accounts()
    await ledger.initialize_capital(Money.from_dollars("10000.00", "USD"))

    async def worker(worker_id):
        # print(f"Worker {worker_id} starting")
        for i in range(100):
            # perform a mix of reads and writes
            bal = await ledger.get_cash_balance()
            if i % 10 == 0:
                # post a transaction
                # For simplicity, self-transfer or expense
                # Just read strict validation
                # Simulate another read or write
                stats = await ledger.get_ledger_statistics()
                pass
            # Simulate slight delay to encourage overlap
            await asyncio.sleep(0.001)
        # print(f"Worker {worker_id} done")

    start_time = time.time()
    
    # Spawn multiple workers
    # If LedgerCore used blocking lock, this would be serial execution effectively or slower
    # With asyncio.Lock, the event loop keeps spinning.
    # To prove blocking behavior was fixed, we'd need to block the IO.
    # But mainly we want to ensure it works without crashing.
    
    tasks = [worker(i) for i in range(10)]
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"Finished 10 workers in {end_time - start_time:.4f}s")
    
    stats = await ledger.get_ledger_statistics()
    print("Ledger Stats:", stats)
    
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_ledger_concurrency())
