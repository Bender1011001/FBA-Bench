#!/usr/bin/env python3
"""
Minimal script to verify coverage thresholds.
Parses coverage.xml and enforces overall >=80% and per-file thresholds for critical modules.
Exits non-zero on violation with a clear report.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_coverage_xml(xml_path: Path) -> dict:
    """Parse coverage.xml and return coverage data."""
    if not xml_path.exists():
        raise FileNotFoundError(f"Coverage XML not found: {xml_path}")
    
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Overall coverage
    overall_line_rate = float(root.attrib.get("line-rate", "0"))
    overall_coverage = overall_line_rate * 100
    
    # Per-file coverage
    file_coverages = {}
    for package in root.findall(".//{http://cobertura.sourceforge.net/xml/coverage-04/coverage}package"):
        for file_elem in package.findall(".//{http://cobertura.sourceforge.net/xml/coverage-04/coverage}class"):
            filename = file_elem.attrib.get("filename", "")
            if filename:
                line_rate = float(file_elem.attrib.get("line-rate", "0"))
                file_coverages[filename] = line_rate * 100
    
    return {
        "overall": overall_coverage,
        "files": file_coverages
    }

def check_thresholds(coverage_data: dict) -> tuple[bool, list[str]]:
    """Check thresholds and return (passed, messages)."""
    messages = []
    passed = True
    
    # Overall threshold
    if coverage_data["overall"] < 80.0:
        passed = False
        messages.append(
            f"❌ Overall coverage {coverage_data['overall']:.1f}% < 80.0% threshold"
        )
    else:
        messages.append(
            f"✅ Overall coverage {coverage_data['overall']:.1f}% >= 80.0%"
        )
    
    # Per-file thresholds
    critical_files = {
        "src/fba_bench_core/simulation_orchestrator.py": 90.0,
        "src/fba_bench_core/metrics.py": 90.0,
    }
    
    for file_path, threshold in critical_files.items():
        if file_path in coverage_data["files"]:
            file_cov = coverage_data["files"][file_path]
            if file_cov < threshold:
                passed = False
                messages.append(
                    f"❌ {file_path} coverage {file_cov:.1f}% < {threshold}% threshold"
                )
            else:
                messages.append(
                    f"✅ {file_path} coverage {file_cov:.1f}% >= {threshold}%"
                )
        else:
            passed = False
            messages.append(
                f"❌ Coverage data missing for critical file: {file_path}"
            )
    
    return passed, messages

def main():
    # Assume coverage.xml is in current dir; adjust if needed
    xml_path = Path("coverage.xml")
    
    try:
        coverage_data = parse_coverage_xml(xml_path)
        passed, messages = check_thresholds(coverage_data)
        
        print("Coverage Threshold Verification Report:")
        for msg in messages:
            print(msg)
        
        if passed:
            print("\n✅ All coverage thresholds met.")
            sys.exit(0)
        else:
            print("\n❌ Coverage thresholds violated. Fix tests or adjust scope.")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Failed to verify coverage: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
