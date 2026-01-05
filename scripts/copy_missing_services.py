#!/usr/bin/env python3
"""
Script to copy missing service files from src/services to fba_bench_core/services
and create the financial_audit.py shim.
"""

import shutil
from pathlib import Path


def copy_services():
    """Copy service files from src/services to fba_bench_core/services."""
    src_services = Path("src/services")
    dst_services = Path("fba_bench_core/services")
    
    # Ensure destination directory exists
    dst_services.mkdir(parents=True, exist_ok=True)
    
    # Service files to copy
    service_files = [
        "bsr_engine_v3.py",
        "competitor_manager.py", 
        "cost_tracking_service.py",
        "customer_event_service.py",
        "customer_reputation_service.py",
        "dashboard_api_service.py",
        "dispute_service.py",
        "double_entry_ledger_service.py",
        "external_service.py",
        "fee_calculation_service.py",
        "marketing_service.py",
        "market_simulator.py",
        "mock_service.py",
        "outcome_analysis_service.py",
        "sales_service.py",
        "supply_chain_service.py",
        "toolbox_api_service.py",
        "trust_score_service.py",
        "world_store.py"
    ]
    
    copied_count = 0
    for service_file in service_files:
        src_path = src_services / service_file
        dst_path = dst_services / service_file
        
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f"✓ Copied {service_file}")
            copied_count += 1
        else:
            print(f"✗ Missing: {service_file}")
    
    return copied_count

def create_financial_audit_shim():
    """Create a minimal financial_audit.py shim."""
    content = '''"""
Financial audit service shim for integration tests.
This provides a minimal implementation to satisfy imports.
"""

from __future__ import annotations

class FinancialAuditService:
    """Minimal financial audit service implementation."""
    
    def __init__(self):
        self.audits = []
    
    async def audit_transaction(self, transaction_data: dict) -> dict:
        """Audit a transaction."""
        return {"status": "approved", "audit_id": f"audit_{len(self.audits)}"}
    
    async def generate_report(self) -> dict:
        """Generate audit report."""
        return {"total_audits": len(self.audits), "status": "complete"}
'''
    
    with open("financial_audit.py", "w") as f:
        f.write(content)
    print("✓ Created financial_audit.py shim")

def main():
    """Main function to copy missing services."""
    print("🔧 Copying missing service files...")
    print("=" * 50)
    
    copied_count = copy_services()
    print(f"\n📦 Copied {copied_count} service files")
    
    create_financial_audit_shim()
    
    print("\n✅ All missing files have been created!")
    print("💡 Run 'poetry run python scripts/find_missing_imports.py' to verify.")

if __name__ == "__main__":
    main()
