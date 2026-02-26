from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fba_bench_core.money import Money  # For consistent Money->string defaults

# Import pattern consistent with realtime router to avoid circulars
from fba_bench_api.core.state import dashboard_service

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _money_str(x: Any) -> str:
    """
    Coerce value to Money string:
    - Money -> str(Money)
    - str   -> as-is (assume already money-like)
    - other -> "$0.00"
    """
    if isinstance(x, Money):
        return str(x)
    if isinstance(x, str) and x:
        return x
    return str(Money.zero())


# -------- Audit --------


def _audit_defaults() -> Dict[str, Any]:
    return {
        "processed_transactions": 0,
        "total_violations": 0,
        "critical_violations": 0,
        "total_revenue_audited": str(Money.zero()),
        "total_fees_audited": str(Money.zero()),
        "total_profit_audited": str(Money.zero()),
        "current_position": {
            "total_assets": str(Money.zero()),
            "total_liabilities": str(Money.zero()),
            "total_equity": str(Money.zero()),
            "accounting_identity_valid": True,
            "identity_difference": str(Money.zero()),
        },
        "audit_enabled": False,
        "halt_on_violation": False,
        "tolerance_cents": 0,
    }


@router.get("/audit")
async def get_audit() -> Dict[str, Any]:
    """
    GET /api/metrics/audit
    Returns live audit metrics if available, otherwise a stable default shape.
    """
    try:
        ds = dashboard_service
        audit = getattr(ds, "audit_service", None) if ds else None
        if not audit:
            return _audit_defaults()
        # Delegate to FinancialAuditService which serializes Money to strings
        return audit.get_audit_statistics()
    except Exception:
        return _audit_defaults()


# -------- Ledger --------


def _ledger_defaults() -> Dict[str, Any]:
    now_iso = _now_iso()
    return {
        "cash": str(Money.zero()),
        "inventory_value": str(Money.zero()),
        "accounts_receivable": str(Money.zero()),
        "accounts_payable": str(Money.zero()),
        "accrued_liabilities": str(Money.zero()),
        "total_assets": str(Money.zero()),
        "total_liabilities": str(Money.zero()),
        "total_equity": str(Money.zero()),
        "accounting_identity_valid": True,
        "identity_difference": str(Money.zero()),
        "timestamp": now_iso,
    }


@router.get("/ledger")
async def get_ledger() -> Dict[str, Any]:
    """
    GET /api/metrics/ledger
    Returns balance sheet snapshot with Money values as strings and ISO timestamp.
    """
    try:
        ds = dashboard_service
        ledger = getattr(ds, "ledger_service", None) if ds else None
        if not ledger:
            return _ledger_defaults()

        pos = ledger.get_financial_position()
        ts = pos.get("timestamp")
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else _now_iso()

        return {
            "cash": _money_str(pos.get("cash")),
            "inventory_value": _money_str(pos.get("inventory_value")),
            "accounts_receivable": _money_str(pos.get("accounts_receivable")),
            "accounts_payable": _money_str(pos.get("accounts_payable")),
            "accrued_liabilities": _money_str(pos.get("accrued_liabilities")),
            "total_assets": _money_str(pos.get("total_assets")),
            "total_liabilities": _money_str(pos.get("total_liabilities")),
            "total_equity": _money_str(pos.get("total_equity")),
            "accounting_identity_valid": bool(
                pos.get("accounting_identity_valid", True)
            ),
            "identity_difference": _money_str(pos.get("identity_difference")),
            "timestamp": ts_iso,
        }
    except Exception:
        return _ledger_defaults()


# -------- BSR --------


def _bsr_defaults() -> Dict[str, Any]:
    return {
        "products": [],
        "timestamp": _now_iso(),
    }


@router.get("/bsr")
async def get_bsr() -> Dict[str, Any]:
    """
    GET /api/metrics/bsr
    Returns product index metrics and optional market EMA metrics.
    Indices are numbers or null; EMA values serialized as strings.
    """
    try:
        ds = dashboard_service
        bsr = getattr(ds, "bsr_service", None) if ds else None
        now_iso = _now_iso()
        if not bsr:
            return {
                "products": [],
                "timestamp": now_iso,
            }

        # Build products list with numeric/null indices
        products: List[Dict[str, Any]] = []
        for asin in getattr(bsr, "product_metrics", {}).keys():
            try:
                idx = bsr.get_product_indices(asin)
            except Exception:
                idx = {}

            def to_num(x: Any) -> Optional[float]:
                if x is None:
                    return None
                try:
                    return float(x)
                except Exception:
                    return None

            products.append(
                {
                    "asin": asin,
                    "velocity_index": to_num(idx.get("velocity_index")),
                    "conversion_index": to_num(idx.get("conversion_index")),
                    "composite_index": to_num(idx.get("composite_index")),
                }
            )

        market = {}  # type: ignore[var-annotated]
        try:
            market = bsr.get_market_metrics() or {}
        except Exception:
            market = {}

        resp: Dict[str, Any] = {
            "products": products,
            "timestamp": now_iso,
        }
        if market.get("market_ema_velocity") is not None:
            resp["market_ema_velocity"] = str(market.get("market_ema_velocity"))
        if market.get("market_ema_conversion") is not None:
            resp["market_ema_conversion"] = str(market.get("market_ema_conversion"))
        if market.get("competitor_count") is not None:
            try:
                resp["competitor_count"] = int(market.get("competitor_count"))  # type: ignore[arg-type]
            except Exception:
                pass

        return resp
    except Exception:
        return _bsr_defaults()


# -------- Fees --------


@router.get("/fees")
async def get_fees() -> Dict[str, Dict[str, Any]]:
    """
    GET /api/metrics/fees
    Returns fee summary keyed by fee type with totals, counts, and averages.
    """
    try:
        ds = dashboard_service
        fee_agg = getattr(ds, "fee_aggregator", None) if ds else None
        if not fee_agg:
            return {}
        return fee_agg.get_summary_by_type()
    except Exception:
        # Stable default: empty mapping
        return {}
