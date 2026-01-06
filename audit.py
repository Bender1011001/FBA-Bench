"""
Audit infrastructure for FBA-bench simulation tracking and verification.

This module provides comprehensive audit tracking for simulation runs to ensure
reproducibility and enable golden snapshot testing. The audit system tracks:

1. Configuration hashes - Detect changes in simulation parameters
2. Code hashes - Detect changes in the codebase (via Git SHA or file hashing)
3. Fee schedule hashes - Detect changes in fee calculations
4. Per-tick state hashes - Ensure deterministic execution
5. Financial statement integrity - Validate accounting identities

REPRODUCIBILITY IMPROVEMENTS (v2025.1):
- External configuration discovery (env + config dirs) merged deterministically into config hash
- Baseline hash validation against golden_masters/audit_baselines.json
- Hash-based simulation cache (opt-in) with integrity validation
- Hash rotation strategy via config/hash_rotation.json to preserve comparability across planned changes

TODO ITEMS (remaining):
- Implement semantic/AST-level code change detection for richer diffs
"""

import glob
import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from money import Money

from ledger_utils import (
    balance_sheet_from_ledger,
    hash_inventory_state,
    hash_ledger_slice,
    hash_rng_state,
    income_statement_from_ledger,
    trial_balance,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickAudit:
    """Immutable audit record for a single simulation tick."""

    day: int
    assets: Decimal
    liabilities: Decimal
    equity: Decimal
    debit_sum: Decimal
    credit_sum: Decimal
    equity_change_from_profit: Decimal
    net_income_to_date: Decimal
    owner_contributions_to_date: Decimal
    owner_distributions_to_date: Decimal
    inventory_units_by_sku: Dict[str, int]
    inventory_hash: str  # SHA256 over (sku, qty, unit_cost_cents) tuples
    rng_state_hash: str
    ledger_tick_hash: str  # hash of all postings at this tick


@dataclass(frozen=True)
class RunAudit:
    """Immutable audit record for a complete simulation run."""

    seed: int
    days: int
    config_hash: str
    code_hash: str
    git_tree_hash: str  # New field for Git tree hash
    fee_schedule_hash: str  # Hash of fee configuration
    initial_equity: Decimal  # Equity before any simulation days
    ticks: List[TickAudit]
    final_balance_sheet: Dict[str, Decimal]
    final_income_statement: Dict[str, Decimal]
    final_ledger_hash: str  # hash over whole run
    violations: List[str]  # filled by the harness if discovered


async def run_and_audit(sim, days: int) -> RunAudit:
    """Runs the simulation and produces an immutable audit structure suitable for golden snapshots."""
    # Precompute immutable signatures for baseline validation and optional caching
    pre_config_hash = _generate_config_hash(sim)
    pre_code_hash = _generate_code_hash()
    pre_git_tree_hash = _generate_git_tree_hash()
    pre_fee_schedule_hash = _generate_fee_schedule_hash(getattr(sim, "fees", None))

    # Attempt deterministic cache read if enabled (opt-in)
    cached = _maybe_load_cached_run(
        sim, days, pre_config_hash, pre_code_hash, pre_git_tree_hash, pre_fee_schedule_hash
    )
    if cached is not None:
        # Validate against baseline and return cached result if acceptable
        violations = _validate_against_baseline(
            pre_config_hash, pre_code_hash, pre_git_tree_hash, pre_fee_schedule_hash
        )
        merged_violations = list({*cached.violations, *violations})
        if merged_violations != cached.violations:
            cached = RunAudit(
                seed=cached.seed,
                days=cached.days,
                config_hash=cached.config_hash,
                code_hash=cached.code_hash,
                git_tree_hash=cached.git_tree_hash,
                fee_schedule_hash=cached.fee_schedule_hash,
                initial_equity=cached.initial_equity,
                ticks=cached.ticks,
                final_balance_sheet=cached.final_balance_sheet,
                final_income_statement=cached.final_income_statement,
                final_ledger_hash=cached.final_ledger_hash,
                violations=merged_violations,
            )
        return cached

    # Store initial state
    initial_equity = await _get_equity_from_ledger(sim.ledger)
    owner_contributions = Decimal("10000.00")  # Initial seed capital
    owner_distributions = Decimal("0.00")

    ticks: List[TickAudit] = []
    violations: List[str] = []

    for day in range(days):
        pre_tick_equity = await _get_equity_from_ledger(sim.ledger)
        sim.tick_day()

        balance_sheet = await balance_sheet_from_ledger(sim.ledger)
        trial_balance_result = await trial_balance(sim.ledger)

        assets = sum(v for k, v in balance_sheet.items() if k in ["Cash", "Inventory"])
        liabilities = sum(v for k, v in balance_sheet.items() if k.startswith("Liability"))

        debit_sum = trial_balance_result[0]
        credit_sum = trial_balance_result[1]

        income_statement = await income_statement_from_ledger(sim.ledger, 0, day + 1)
        net_income_to_date = income_statement.get("Net Income", Decimal("0"))

        initial_equity_balance = balance_sheet.get("Equity", Decimal("0"))
        closing_equity = initial_equity_balance + net_income_to_date

        equity_change_from_profit = closing_equity - pre_tick_equity

        inventory_units = {}
        for sku in sim.products.keys():
            inventory_units[sku] = sim.inventory.quantity(sku)

        inventory_hash = hash_inventory_state(sim.inventory)
        rng_state_hash = hash_rng_state(sim.rng)
        ledger_tick_hash = hash_ledger_slice(sim.ledger, day, day + 1)

        tick_audit = TickAudit(
            day=day + 1,
            assets=assets,
            liabilities=liabilities,
            equity=closing_equity,
            debit_sum=debit_sum,
            credit_sum=credit_sum,
            equity_change_from_profit=equity_change_from_profit,
            net_income_to_date=net_income_to_date,
            owner_contributions_to_date=owner_contributions,
            owner_distributions_to_date=owner_distributions,
            inventory_units_by_sku=inventory_units,
            inventory_hash=inventory_hash,
            rng_state_hash=rng_state_hash,
            ledger_tick_hash=ledger_tick_hash,
        )

        ticks.append(tick_audit)

        if abs(debit_sum - credit_sum) > Decimal("0.01"):
            violations.append(
                f"Day {day + 1}: Trial balance violation - debits {debit_sum} != credits {credit_sum}"
            )

        if abs(assets - (liabilities + closing_equity)) > Decimal("0.01"):
            violations.append(
                f"Day {day + 1}: Accounting identity violation - A={assets} != L+E={liabilities + closing_equity}"
            )

    final_balance_sheet = await balance_sheet_from_ledger(sim.ledger)
    final_income_statement = await income_statement_from_ledger(sim.ledger, 0, days)
    final_ledger_hash = hash_ledger_slice(sim.ledger, 0, days)

    config_hash = pre_config_hash
    code_hash = pre_code_hash
    git_tree_hash = pre_git_tree_hash
    fee_schedule_hash = pre_fee_schedule_hash

    violations.extend(
        _validate_against_baseline(config_hash, code_hash, git_tree_hash, fee_schedule_hash)
    )

    result = RunAudit(
        seed=sim.rng.getstate()[1][0],
        days=days,
        config_hash=config_hash,
        code_hash=code_hash,
        git_tree_hash=git_tree_hash,
        fee_schedule_hash=fee_schedule_hash,
        initial_equity=initial_equity,
        ticks=ticks,
        final_balance_sheet=final_balance_sheet,
        final_income_statement=final_income_statement,
        final_ledger_hash=final_ledger_hash,
        violations=violations,
    )

    _maybe_write_cached_run(sim, result)

    return result


async def _get_equity_from_ledger(ledger) -> Decimal:
    """Extract equity balance from ledger."""
    balance = await ledger.get_account_balance("Equity")
    if isinstance(balance, Money):
        return balance.to_decimal()
    else:
        # Handle float/int for backward compatibility
        return Decimal(str(balance))


def _generate_config_hash(sim=None) -> str:
    """
    Generate hash of current configuration, including simulation parameters, environment variables,
    and discovered external config files from well-known locations.

    Discovery order (merged deterministically):
    1) Explicit env var FBA_CONFIG_PATH (file or directory; if dir, scan *.yaml|*.yml|*.json)
    2) Local working dir files: config.json, simulation_config.json, fba_config.json, sweep.yaml
    3) Config dirs: config/, configs/, config/environments/, configs/environments/ (scan recursively for *.yaml|*.yml|*.json)
    """
    config_data: Dict[str, Any] = {}

    if sim is not None:
        if hasattr(sim, "fees") and hasattr(sim.fees, "config"):
            config_data["fee_config"] = sim.fees.config
        elif hasattr(sim, "fees") and hasattr(sim.fees, "fee_rates"):
            config_data["fee_rates"] = sim.fees.fee_rates

        if hasattr(sim, "products"):
            product_summary = {}
            for sku, product in sim.products.items():
                product_summary[sku] = {
                    "category": getattr(product, "category", "unknown"),
                    "weight_oz": getattr(product, "weight_oz", 0),
                    "dimensions": getattr(product, "dimensions_inches", [0, 0, 0]),
                }
            config_data["products"] = product_summary

        if hasattr(sim, "config"):
            config_data["sim_config"] = sim.config

    config_data["environment_variables"] = dict(os.environ)

    discovered_configs = _discover_external_configs()
    for key in sorted(discovered_configs.keys()):
        config_data[key] = discovered_configs[key]

    if not config_data:
        config_data = {
            "version": "fba_bench_v3",
            "timestamp": "static_for_reproducibility",
            "note": "No dynamic configuration or environment variables found - using static hash",
        }

    config_json = json.dumps(config_data, sort_keys=True, default=str)
    return hashlib.sha256(config_json.encode()).hexdigest()[:16]


def _generate_code_hash() -> str:
    """Generate hash of current codebase state using git tree or file fallback."""
    git_hash = _generate_git_tree_hash()
    if git_hash != "no_git_hash":
        return git_hash

    # Fallback to hashing all relevant files
    return _generate_file_tree_hash()


def _hash_working_tree_changes() -> str:
    """Hash uncommitted changes in working tree."""
    try:
        # Get diff of working tree
        result = subprocess.run(
            ["git", "diff", "--no-color"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=10,
        )
        if result.returncode == 0:
            diff_content = result.stdout
            return hashlib.sha256(diff_content.encode()).hexdigest()[:16]  # Truncate for brevity
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Failed to get git diff for working tree changes: {e}")
    return "no_diff_hash"


def _generate_file_digest(file_path: Path) -> str:
    """Generate SHA256 digest of a file's content upto 16 characters."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
    except OSError:
        return "file_read_error"
    return hasher.hexdigest()[:16]


def _generate_file_tree_hash(base_path: Path = Path.cwd()) -> str:
    """Generate a hash of all relevant files in the directory tree (except .git, artifacts, frontend)."""
    hasher = hashlib.sha256()
    filepaths = []

    # Define directories and file patterns to exclude
    exclude_dirs = {
        ".git",
        "artifacts",
        "frontend",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".vscode",
    }
    exclude_file_patterns = {"*.pyc", "*~$*", ".DS_Store"}  # Add more as needed

    for root, dirs, files in os.walk(base_path):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            # Filter out excluded file patterns
            if any(glob.fnmatch.fnmatch(file, pattern) for pattern in exclude_file_patterns):
                continue

            # Only consider relevant source code and config files
            if file.endswith((".py", ".yaml", ".yml", ".md", ".txt", ".json", ".sh")):
                full_path = Path(root) / file
                filepaths.append(full_path)

    # Sort filepaths for deterministic order across different OS/environments
    filepaths.sort()

    for file_path in filepaths:
        # Include relative path and file content hash
        hasher.update(
            file_path.relative_to(base_path).as_posix().encode()
        )  # Use as_posix for consistent path separators
        hasher.update(_generate_file_digest(file_path).encode())

    return hasher.hexdigest()[:16]


def _generate_git_tree_hash() -> str:
    """
    Generate a hash representing the current state of the Git repository.
    Includes the commit hash and, if present, a hash of uncommitted changes.
    Applies hash rotation mapping if configured.
    """
    try:
        commit_hash_res = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path.cwd(), timeout=10
        )
        commit_hash = commit_hash_res.stdout.strip() if commit_hash_res.returncode == 0 else ""

        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=10,
        )
        if status_res.returncode == 0 and status_res.stdout.strip():
            diff_hash = _hash_working_tree_changes()
            raw = f"{commit_hash}-dirty-{diff_hash}"
        else:
            raw = commit_hash
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        raw = "no_git_hash"

    return _apply_hash_rotation(raw)


def _generate_fee_schedule_hash(fee_engine) -> str:
    """
    Generate hash of fee schedule configuration for reproducibility.

    This ensures that fee changes are detected in audit comparisons.
    Attempts to extract comprehensive fee configuration from the fee engine.

    Args:
        fee_engine: Fee calculation service instance

    Returns:
        SHA256 hash (first 16 characters) of fee configuration
    """
    fee_data = {}

    # Extract fee metadata if available
    if hasattr(fee_engine, "fee_metadata"):
        fee_data["fee_metadata"] = fee_engine.fee_metadata

    # Extract fee rates if available
    if hasattr(fee_engine, "fee_rates"):
        # Convert Money objects to serializable format
        fee_rates = {}
        for key, value in fee_engine.fee_rates.items():
            if hasattr(value, "cents"):  # Money object
                fee_rates[key] = {"cents": value.cents, "type": "Money"}
            else:
                fee_rates[key] = value
        fee_data["fee_rates"] = fee_rates

    # Extract category rates if available
    if hasattr(fee_engine, "category_referral_rates"):
        fee_data["category_referral_rates"] = fee_engine.category_referral_rates

    # Extract size tiers if available
    if hasattr(fee_engine, "size_tiers"):
        fee_data["size_tiers"] = fee_engine.size_tiers

    # Extract storage rates if available
    if hasattr(fee_engine, "storage_rates"):
        storage_rates = {}
        for key, value in fee_engine.storage_rates.items():
            if hasattr(value, "cents"):  # Money object
                storage_rates[key] = {"cents": value.cents, "type": "Money"}
            else:
                storage_rates[key] = value
        fee_data["storage_rates"] = storage_rates

    # Extract config if available
    if hasattr(fee_engine, "config"):
        fee_data["config"] = fee_engine.config

    # If no fee data found, create a descriptive placeholder
    if not fee_data:
        fee_data = {
            "note": "No fee configuration extracted from fee_engine",
            "fee_engine_type": type(fee_engine).__name__ if fee_engine else "None",
            "available_attributes": dir(fee_engine) if fee_engine else [],
        }

    # Create deterministic hash
    fee_json = json.dumps(fee_data, sort_keys=True, default=str)
    return hashlib.sha256(fee_json.encode()).hexdigest()[:16]


# ---------------------------
# Extended helpers: config discovery, baselines, cache, rotation
# ---------------------------


def _discover_external_configs() -> Dict[str, Any]:
    """
    Discover external configuration files from:
    - Env var FBA_CONFIG_PATH (file or directory)
    - Local files: config.json, simulation_config.json, fba_config.json, sweep.yaml
    - Directories: config/, configs/, config/environments/, configs/environments/
    Returns a dict mapping "source_path" -> parsed content.
    """
    discovered: Dict[str, Any] = {}

    def _load_file(path: Path) -> Optional[Any]:
        try:
            if path.suffix.lower() in (".yaml", ".yml"):
                import yaml  # type: ignore

                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f)
            elif path.suffix.lower() in (".json",):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            else:
                return None
        except (OSError, ValueError, ImportError) as e:
            logger.warning(f"Failed to load config file {path}: {e}")
            return None

    def _scan_dir(dir_path: Path) -> None:
        if not dir_path.exists() or not dir_path.is_dir():
            return
        for root, _, files in os.walk(dir_path):
            for fname in files:
                p = Path(root) / fname
                if p.suffix.lower() in (".yaml", ".yml", ".json"):
                    content = _load_file(p)
                    if content is not None:
                        # Use POSIX style for consistency in hash order
                        key = (
                            str(p.relative_to(Path.cwd()).as_posix())
                            if p.is_absolute()
                            else str(p.as_posix())
                        )
                        discovered[key] = content

    # 1) Env var
    env_path = os.getenv("FBA_CONFIG_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            content = _load_file(p)
            if content is not None:
                discovered[str(p)] = content
        elif p.is_dir():
            _scan_dir(p)

    # 2) Local files
    for local in ["config.json", "simulation_config.json", "fba_config.json", "sweep.yaml"]:
        p = Path(local)
        if p.exists() and p.is_file():
            content = _load_file(p)
            if content is not None:
                discovered[str(p)] = content

    # 3) Config dirs
    for d in ["config", "configs", "config/environments", "configs/environments"]:
        _scan_dir(Path(d))

    return discovered


def _apply_hash_rotation(hash_value: str) -> str:
    """
    Apply a rotation mapping if config/hash_rotation.json exists.
    The mapping is { "old_hash": "new_hash", ... }.
    """
    try:
        rotation_file = Path("config/hash_rotation.json")
        if rotation_file.exists():
            with open(rotation_file, encoding="utf-8") as f:
                mapping = json.load(f)
            return mapping.get(hash_value, hash_value)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Hash rotation mapping load failed: {e}")
    return hash_value


def _validate_against_baseline(
    config_hash: str, code_hash: str, git_tree_hash: str, fee_hash: str
) -> List[str]:
    """
    Compare current hashes against stored baselines in golden_masters/audit_baselines.json.
    Returns a list of violation messages (empty if all match or no baseline file).
    Supports hash rotation mapping.
    """
    violations: List[str] = []
    baseline_file = Path("golden_masters/audit_baselines.json")
    if not baseline_file.exists():
        return violations

    try:
        with open(baseline_file, encoding="utf-8") as f:
            baseline = json.load(f)
        # Apply rotation to current values before comparison
        cur = {
            "config_hash": _apply_hash_rotation(config_hash),
            "code_hash": _apply_hash_rotation(code_hash),
            "git_tree_hash": _apply_hash_rotation(git_tree_hash),
            "fee_schedule_hash": _apply_hash_rotation(fee_hash),
        }
        for k, v in cur.items():
            expected = baseline.get(k)
            if expected and v != expected:
                violations.append(f"Baseline mismatch for {k}: expected {expected}, got {v}")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to validate against baseline: {e}")

    return violations


def _cache_enabled(mode: str = "readwrite") -> bool:
    """
    Returns True if simulation cache is enabled.
    Modes:
      - readwrite: read and write cache (FBA_ENABLE_SIM_CACHE true and not disabled)
      - writeonly: only write cache (FBA_ENABLE_SIM_CACHE true and FBA_SIM_CACHE_MODE=writeonly)
    """
    if os.getenv("FBA_DISABLE_SIM_CACHE", "").lower() == "true":
        return False
    enabled = os.getenv("FBA_ENABLE_SIM_CACHE", "").lower() == "true"
    if not enabled:
        return False
    sim_mode = os.getenv("FBA_SIM_CACHE_MODE", "readwrite").lower()
    if mode == "writeonly":
        return sim_mode in ("writeonly", "readwrite")
    return sim_mode == "readwrite"


def _build_cache_key(
    sim, days: int, config_hash: str, code_hash: str, git_tree_hash: str, fee_hash: str
) -> str:
    """
    Deterministic cache key based on tier, scenario id/name if available, and hashes.
    """
    tier = None
    scenario = None
    try:
        if hasattr(sim, "config"):
            if isinstance(sim.config, dict):
                tier = sim.config.get("tier")
                scenario = sim.config.get("scenario_name") or sim.config.get("scenario_id")
            else:
                tier = getattr(sim.config, "tier", None)
                scenario = getattr(sim.config, "scenario_name", None) or getattr(
                    sim.config, "scenario_id", None
                )
    except AttributeError:
        pass
    payload = {
        "tier": tier or "unknown",
        "scenario": scenario or "unknown",
        "days": days,
        "config_hash": config_hash,
        "code_hash": code_hash,
        "git_tree_hash": git_tree_hash,
        "fee_hash": fee_hash,
    }
    s = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()


def _cache_dir() -> Path:
    p = Path("config_storage/simulations")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _serialize_run(audit: RunAudit) -> Dict[str, Any]:
    return {
        "seed": audit.seed,
        "days": audit.days,
        "config_hash": audit.config_hash,
        "code_hash": audit.code_hash,
        "git_tree_hash": audit.git_tree_hash,
        "fee_schedule_hash": audit.fee_schedule_hash,
        "initial_equity": str(audit.initial_equity),
        "ticks": [
            {
                "day": t.day,
                "assets": str(t.assets),
                "liabilities": str(t.liabilities),
                "equity": str(t.equity),
                "debit_sum": str(t.debit_sum),
                "credit_sum": str(t.credit_sum),
                "equity_change_from_profit": str(t.equity_change_from_profit),
                "net_income_to_date": str(t.net_income_to_date),
                "owner_contributions_to_date": str(t.owner_contributions_to_date),
                "owner_distributions_to_date": str(t.owner_distributions_to_date),
                "inventory_units_by_sku": t.inventory_units_by_sku,
                "inventory_hash": t.inventory_hash,
                "rng_state_hash": t.rng_state_hash,
                "ledger_tick_hash": t.ledger_tick_hash,
            }
            for t in audit.ticks
        ],
        "final_balance_sheet": {k: str(v) for k, v in audit.final_balance_sheet.items()},
        "final_income_statement": {k: str(v) for k, v in audit.final_income_statement.items()},
        "final_ledger_hash": audit.final_ledger_hash,
        "violations": audit.violations,
    }


def _deserialize_run(payload: Dict[str, Any]) -> RunAudit:
    ticks = [
        TickAudit(
            day=it["day"],
            assets=Decimal(it["assets"]),
            liabilities=Decimal(it["liabilities"]),
            equity=Decimal(it["equity"]),
            debit_sum=Decimal(it["debit_sum"]),
            credit_sum=Decimal(it["credit_sum"]),
            equity_change_from_profit=Decimal(it["equity_change_from_profit"]),
            net_income_to_date=Decimal(it["net_income_to_date"]),
            owner_contributions_to_date=Decimal(it["owner_contributions_to_date"]),
            owner_distributions_to_date=Decimal(it["owner_distributions_to_date"]),
            inventory_units_by_sku=it["inventory_units_by_sku"],
            inventory_hash=it["inventory_hash"],
            rng_state_hash=it["rng_state_hash"],
            ledger_tick_hash=it["ledger_tick_hash"],
        )
        for it in payload.get("ticks", [])
    ]
    return RunAudit(
        seed=payload["seed"],
        days=payload["days"],
        config_hash=payload["config_hash"],
        code_hash=payload["code_hash"],
        git_tree_hash=payload["git_tree_hash"],
        fee_schedule_hash=payload["fee_schedule_hash"],
        initial_equity=Decimal(payload["initial_equity"]),
        ticks=ticks,
        final_balance_sheet={k: Decimal(v) for k, v in payload["final_balance_sheet"].items()},
        final_income_statement={
            k: Decimal(v) for k, v in payload["final_income_statement"].items()
        },
        final_ledger_hash=payload["final_ledger_hash"],
        violations=payload.get("violations", []),
    )


def _maybe_load_cached_run(
    sim, days: int, config_hash: str, code_hash: str, git_tree_hash: str, fee_hash: str
) -> Optional[RunAudit]:
    """
    If cache is enabled for reads, attempt to load a cached RunAudit from disk and validate integrity.
    """
    if not _cache_enabled("readwrite"):
        return None
    try:
        key = _build_cache_key(sim, days, config_hash, code_hash, git_tree_hash, fee_hash)
        cache_path = _cache_dir() / f"{key}.json"
        if not cache_path.exists():
            return None
        with open(cache_path, encoding="utf-8") as f:
            payload = json.load(f)
        # Integrity checks
        if (
            payload.get("config_hash") != config_hash
            or payload.get("code_hash") != code_hash
            or payload.get("git_tree_hash") != git_tree_hash
            or payload.get("fee_schedule_hash") != fee_hash
            or payload.get("days") != days
        ):
            logger.warning("Cached run integrity check failed; ignoring cache.")
            return None
        return _deserialize_run(payload)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read simulation cache: {e}")
        return None


def _maybe_write_cached_run(sim, audit: RunAudit) -> None:
    """
    If cache is enabled for write, persist the RunAudit to disk atomically.
    """
    if not _cache_enabled("writeonly"):
        return
    try:
        key = _build_cache_key(
            sim,
            audit.days,
            audit.config_hash,
            audit.code_hash,
            audit.git_tree_hash,
            audit.fee_schedule_hash,
        )
        cache_path = _cache_dir() / f"{key}.json"
        tmp_path = cache_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_serialize_run(audit), f, sort_keys=True)
        os.replace(tmp_path, cache_path)
    except OSError as e:
        logger.warning(f"Failed to write simulation cache: {e}")
