#!/usr/bin/env python3
# Ensure project root is on sys.path so imports like 'integration_tests' and 'financial_audit' resolve
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

"""
Diagnostic script to identify all missing imports in the integration test modules.
This will help identify which files need to be copied from the pre-split repository.
"""

import sys
from pathlib import Path


def test_import_with_fallback(module_path, fallback_module=None):
    """Test importing a module and capture any missing dependencies."""
    try:
        exec(f"import {module_path}")
        return True, None
    except ModuleNotFoundError as e:
        missing_module = str(e).split("'")[1]  # Extract module name from error
        return False, missing_module
    except Exception as e:
        return False, f"OTHER_ERROR: {str(e)}"

def find_all_missing_imports():
    """Systematically test all imports and collect missing modules."""
    print("🔍 Scanning for missing imports...")
    
    missing_modules = set()
    
    # Test integration_tests imports
    print("\n📦 Testing integration_tests imports...")
    try:
        import integration_tests
        print("✓ integration_tests imports successfully")
    except ModuleNotFoundError as e:
        missing_module = str(e).split("'")[1]
        missing_modules.add(missing_module)
        print(f"✗ integration_tests missing: {missing_module}")
    except Exception as e:
        print(f"✗ integration_tests error: {e}")
    
    # Test demo_scenarios imports
    print("\n📦 Testing demo_scenarios imports...")
    try:
        from integration_tests import demo_scenarios
        print("✓ demo_scenarios imports successfully")
    except ModuleNotFoundError as e:
        missing_module = str(e).split("'")[1]
        missing_modules.add(missing_module)
        print(f"✗ demo_scenarios missing: {missing_module}")
    except Exception as e:
        print(f"✗ demo_scenarios error: {e}")
    
    # Test individual service imports that are commonly missing
    print("\n📦 Testing individual service imports...")
    service_modules = [
        'fba_bench_core.services.fee_calculation_service',
        'fba_bench_core.services.world_store',
        'fba_bench_core.services.market_simulator',
        'fba_bench_core.services.supply_chain_service',
        'fba_bench_core.services.sales_service',
        'fba_bench_core.services.marketing_service',
        'fba_bench_core.services.customer_event_service',
        'fba_bench_core.services.customer_reputation_service',
        'fba_bench_core.services.trust_score_service',
        'fba_bench_core.services.dispute_service',
        'fba_bench_core.services.double_entry_ledger_service',
        'fba_bench_core.services.cost_tracking_service',
        'fba_bench_core.services.outcome_analysis_service',
        'fba_bench_core.services.competitor_manager',
        'fba_bench_core.services.bsr_engine_v3',
        'fba_bench_core.services.dashboard_api_service',
        'fba_bench_core.services.toolbox_api_service',
        'fba_bench_core.services.external_service',
        'fba_bench_core.services.mock_service',
        'financial_audit',
    ]
    
    for module in service_modules:
        success, missing = test_import_with_fallback(module)
        if not success:
            missing_modules.add(missing)
            print(f"✗ {module} missing: {missing}")
        else:
            print(f"✓ {module}")
    
    # Test src/services imports to see what's available there
    print("\n📦 Checking available src/services modules...")
    src_services_path = Path("src/services")
    if src_services_path.exists():
        available_services = []
        for py_file in src_services_path.glob("*.py"):
            if py_file.name != "__init__.py":
                available_services.append(py_file.stem)
        print(f"Available in src/services: {', '.join(available_services)}")
    
    return sorted(list(missing_modules))

def generate_copy_commands(missing_modules):
    """Generate copy commands for missing modules from the old repo."""
    print("\n📋 Suggested copy commands from C:\\Users\\admin\\Downloads\\fba:")
    
    for module in missing_modules:
        if module.startswith('fba_bench_core.services.'):
            service_name = module.replace('fba_bench_core.services.', '')
            print(f"copy C:\\Users\\admin\\Downloads\\fba\\fba_bench_core\\services\\{service_name}.py fba_bench_core\\services\\")
        elif module == 'financial_audit':
            print(f"copy C:\\Users\\admin\\Downloads\\fba\\{module}.py .")
        else:
            print(f"# Manual check needed for: {module}")

def main():
    """Main diagnostic function."""
    print("=" * 60)
    print("🔍 FBA-Bench Missing Import Diagnostic")
    print("=" * 60)
    
    missing_modules = find_all_missing_imports()
    
    if missing_modules:
        print(f"\n❌ Found {len(missing_modules)} missing modules:")
        for module in missing_modules:
            print(f"  - {module}")
        
        generate_copy_commands(missing_modules)
        
        print("\n💡 After copying the missing files, run this script again to verify.")
    else:
        print("\n✅ All imports successful!")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
