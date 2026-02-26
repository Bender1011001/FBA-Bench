from __future__ import annotations

"""
Centralized, versioned model parameters for agents and skills.

- Strongly typed with Pydantic v2
- Single source of truth for defaults ("no magic numbers")
- Optional YAML overlay at configs/model_params.yaml (environment override via MODEL_PARAMS_YAML)
- Safe fallbacks if YAML or optional dependencies are missing

Usage:
    from config.model_config import get_model_params
    params = get_model_params()
    adv = params.advanced_agent
    margin = adv.min_margin
"""

import logging  # noqa: E402
import os  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402

from pydantic import BaseModel, Field, ValidationError  # noqa: E402

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)


class AdvancedAgentParams(BaseModel):
    # Pricing controls
    min_margin: float = Field(0.12, ge=0.0, description="Minimum margin over cost")
    undercut: float = Field(
        0.01, ge=0.0, description="Percent to undercut competitor price"
    )
    max_change_pct: float = Field(
        0.15, gt=0.0, description="Max per-tick change fraction"
    )
    price_sensitivity: float = Field(
        0.10, ge=0.0, le=1.0, description="Heuristic demand sensitivity"
    )
    reaction_speed: float = Field(
        1.0, gt=0.0, description="Adjustment amplifier/damper"
    )

    # Inventory behavior
    inventory_low_threshold: int = Field(10, ge=0)
    inventory_target: int = Field(100, ge=1)
    # Inventory ratio thresholds and nudges used inside decision logic
    inv_low_ratio: float = Field(0.5, gt=0.0)
    inv_high_ratio: float = Field(1.2, gt=0.0)
    inv_low_nudge: float = Field(
        0.2, description="Increase price when too low inventory"
    )
    inv_high_nudge: float = Field(
        -0.15, description="Lower price when too high inventory"
    )

    # Confidence computation shaping
    confidence_log_divisor: float = Field(3.0, gt=0.0)
    confidence_demand_cap: float = Field(0.3, ge=0.0, le=0.99)

    # Smoothing/memory windows
    demand_avg_window: int = Field(
        7, ge=1, description="Moving window for demand average"
    )
    price_avg_window: int = Field(
        7, ge=1, description="Moving window for price average"
    )

    # Confidence calculation parameters for DIYRunner
    confidence_product_data_boost: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="Confidence boost for each valid product data point.",
    )
    confidence_market_data_boost_per_item: float = Field(
        0.05, ge=0.0, le=1.0, description="Confidence boost per market data item."
    )
    confidence_max_cap: float = Field(
        0.95, ge=0.0, le=1.0, description="Maximum confidence cap."
    )

    # Reasoning parameters for DIYRunner (sales rank, inventory)
    reasoning_high_demand_rank_threshold: int = Field(
        10000, ge=1, description="Sales rank threshold for 'high demand' in reasoning."
    )
    reasoning_low_demand_rank_threshold: int = Field(
        500000, ge=1, description="Sales rank threshold for 'low demand' in reasoning."
    )
    reasoning_low_inventory_threshold: int = Field(
        10, ge=0, description="Inventory threshold for 'low inventory' in reasoning."
    )
    reasoning_high_inventory_threshold: int = Field(
        100, ge=0, description="Inventory threshold for 'high inventory' in reasoning."
    )
    reasoning_high_market_demand_factor: float = Field(
        1.2,
        gt=1.0,
        description="Market demand factor for 'high market demand' in reasoning.",
    )
    reasoning_low_market_demand_factor: float = Field(
        0.8,
        lt=1.0,
        description="Market demand factor for 'low market demand' in reasoning.",
    )
    reasoning_competitor_price_deviation_pct: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="Percentage deviation from average competitor price to trigger custom reasoning.",
    )
    reasoning_default_current_price_multiplier: float = Field(
        1.5,
        gt=0.0,
        description="Multiplier for cost to derive a default current price when unavailable for reasoning.",
    )

    class Config:
        extra = "ignore"


class PricingStrategyParams(BaseModel):
    # Competitive Pricing defaults
    margin_target: float = Field(
        0.30, ge=0.0, description="Target profit margin for competitive strategy"
    )
    competitor_sensitivity: float = Field(0.5, ge=0.0, le=1.0)

    # Dynamic Pricing defaults
    base_margin: float = Field(0.25, ge=0.0)
    elasticity_factor: float = Field(0.30, ge=0.0, le=2.0)

    # Rank and inventory shaping (for DIY runner strategies)
    top_rank_threshold: int = Field(10_000, ge=1)
    mid_rank_threshold: int = Field(50_000, ge=1)
    poor_rank_threshold: int = Field(500_000, ge=1)
    rank_high_mult: float = Field(1.2, gt=0.0)
    rank_mid_mult: float = Field(1.1, gt=0.0)
    rank_poor_mult: float = Field(0.9, gt=0.0)

    low_inventory_threshold: int = Field(10, ge=0)
    high_inventory_threshold: int = Field(100, ge=0)
    low_inventory_mult: float = Field(1.1, gt=0.0)
    high_inventory_mult: float = Field(0.95, gt=0.0)

    # History smoothing
    dampening_change_ratio: float = Field(0.10, ge=0.0, le=1.0)
    dampening_multiplier: float = Field(0.9, gt=0.0, le=1.0)
    price_history_window: int = Field(10, ge=1)

    # Safety
    minimum_margin_over_cost: float = Field(0.10, ge=0.0, le=1.0)

    # Elasticity estimation
    elasticity_history_min_points: int = Field(6, ge=3)
    elasticity_ridge_alpha: float = Field(1.0, ge=0.0)
    elasticity_clip_min: float = Field(-5.0)
    elasticity_clip_max: float = Field(-0.1)

    class Config:
        extra = "ignore"


class FinancialAnalystParams(BaseModel):
    total_budget_cents: int = Field(1_000_000, ge=0)
    warning_threshold: float = Field(0.80, ge=0.0, le=1.0)
    critical_threshold: float = Field(0.95, ge=0.0, le=1.0)
    min_cash_reserve_cents: int = Field(100_000, ge=0)
    starting_cash_cents: int = Field(500_000, ge=0)

    # Budget allocation defaults
    alloc_inventory: float = Field(0.40, ge=0.0, le=1.0)
    alloc_marketing: float = Field(0.25, ge=0.0, le=1.0)
    alloc_operations: float = Field(0.20, ge=0.0, le=1.0)
    alloc_customer_service: float = Field(0.10, ge=0.0, le=1.0)
    alloc_fees: float = Field(0.05, ge=0.0, le=1.0)
    budget_period_days: int = Field(30, ge=1)

    # Monitoring cadence (ticks)
    monitor_every_ticks: int = Field(3, ge=1)
    health_every_ticks: int = Field(5, ge=1)
    cost_opt_every_ticks: int = Field(10, ge=1)
    forecast_every_ticks: int = Field(15, ge=1)

    # Forecasting configuration
    forecast_confidence_default: float = Field(0.7, ge=0.0, le=0.99)
    # Holt-Winters seasonal period in days (when daily aggregation is available)
    hw_seasonal_period: int = Field(7, ge=1)
    use_holt_winters: bool = Field(True)
    # Fallback moving-average window (days)
    forecast_ma_window_days: int = Field(14, ge=1)

    # Burn rate and health score parameters
    default_burn_rate_cents: int = Field(
        100,
        ge=0,
        description="Default daily cash burn rate in cents if history is insufficient.",
    )
    burn_rate_history_window: int = Field(
        7,
        ge=1,
        description="Number of days to consider for calculating historical burn rate.",
    )
    margin_score_weight: float = Field(
        0.4,
        ge=0.0,
        le=1.0,
        description="Weight for profit margin in financial health score.",
    )
    runway_score_weight: float = Field(
        0.4,
        ge=0.0,
        le=1.0,
        description="Weight for cash runway in financial health score.",
    )
    burn_score_weight: float = Field(
        0.2,
        ge=0.0,
        le=1.0,
        description="Weight for burn rate efficiency in financial health score.",
    )
    target_cash_runway_days: int = Field(
        90,
        ge=1,
        description="Target number of days for cash runway to achieve full score.",
    )

    # Reallocation & optimization parameters
    max_reallocation_cents: int = Field(
        10000,
        ge=0,
        description="Maximum amount in cents to reallocate in a single budget reallocation action.",
    )
    default_cost_reduction_target: float = Field(
        0.2,
        ge=0.0,
        le=1.0,
        description="Default percentage target for cost reduction actions.",
    )
    max_investment_cents: int = Field(
        50000,
        ge=0,
        description="Maximum amount in cents to recommend for a single growth investment.",
    )
    default_expected_roi: float = Field(
        1.5, ge=0.0, description="Default expected ROI for investment recommendations."
    )
    default_investment_risk_level: str = Field(
        "moderate", description="Default risk level for investment recommendations."
    )
    low_profit_margin_threshold: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="Threshold below which profit margin is considered low.",
    )
    high_fee_percentage_threshold: float = Field(
        0.2,
        ge=0.0,
        le=1.0,
        description="Threshold above which fee percentage is considered high.",
    )

    class Config:
        extra = "ignore"


class PlannerParams(BaseModel):
    # Strategy type thresholds (hierarchical_planner)
    recovery_profit_margin_lt: float = Field(0.10, ge=0.0, le=1.0)
    recovery_revenue_growth_lt: float = Field(0.05, ge=0.0, le=1.0)
    defensive_competitive_pressure_gt: float = Field(0.70, ge=0.0, le=1.0)
    growth_revenue_growth_gt: float = Field(0.15, ge=0.0, le=1.0)
    growth_profit_margin_gt: float = Field(0.15, ge=0.0, le=1.0)
    exploratory_volatility_gt: float = Field(0.60, ge=0.0, le=1.0)

    # Inventory action thresholds
    low_inventory_level: int = Field(50, ge=0)

    # Alignment scoring thresholds
    meaningful_alignment_threshold: float = Field(0.3, ge=0.0, le=1.0)
    aligned_threshold: float = Field(0.6, ge=0.0, le=1.0)
    synergy_bonus: float = Field(0.2, ge=0.0, le=1.0)

    # Scheduling conflict window (seconds)
    scheduling_conflict_seconds: int = Field(3600, ge=1)

    # Overdue objective threshold when overdue (progress > min_progress)
    overdue_min_progress: float = Field(0.2, ge=0.0, le=1.0)
    strategy_refresh_days: int = Field(
        90,
        ge=1,
        description="Days after which strategic plan is considered old and may be refreshed.",
    )
    tactical_action_cleanup_days: int = Field(
        7,
        ge=1,
        description="Days after which completed or failed tactical actions are purged from memory.",
    )

    class Config:
        extra = "ignore"


class ModelParams(BaseModel):
    """
    Root of all configurable numeric parameters.
    """

    version: str = Field("1.0")
    advanced_agent: AdvancedAgentParams = Field(default_factory=AdvancedAgentParams)  # type: ignore[arg-type]
    pricing: PricingStrategyParams = Field(default_factory=PricingStrategyParams)  # type: ignore[arg-type]
    financial_analyst: FinancialAnalystParams = Field(
        default_factory=FinancialAnalystParams  # type: ignore[arg-type]
    )
    planner: PlannerParams = Field(default_factory=PlannerParams)  # type: ignore[arg-type]

    class Config:
        extra = "ignore"


_cached_params: Optional[ModelParams] = None


def _load_yaml(path: str) -> Dict[str, Any]:
    if yaml is None:
        logger.debug("PyYAML not installed; skipping YAML overlay load")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                logger.warning("Model params YAML is not a mapping; ignoring")
                return {}
            return data
    except FileNotFoundError:
        logger.info(f"No model params YAML found at {path}; using built-in defaults")
        return {}
    except Exception as e:
        logger.error(f"Failed to load model params YAML from {path}: {e}")
        return {}


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)  # type: ignore
        else:
            result[k] = v
    return result


def get_model_params(
    force_reload: bool = False, override: Optional[Dict[str, Any]] = None
) -> ModelParams:
    """
    Obtain global ModelParams with optional YAML overlay and programmatic override.

    Precedence:
      Built-in defaults < YAML overlay (configs/model_params.yaml or MODEL_PARAMS_YAML) < override dict
    """
    global _cached_params
    if _cached_params is not None and not force_reload and override is None:
        return _cached_params

    defaults = ModelParams().model_dump()  # type: ignore[call-arg]

    yaml_path = os.getenv("MODEL_PARAMS_YAML") or os.path.join(
        "configs", "model_params.yaml"
    )
    overlay = _load_yaml(yaml_path)

    merged = _deep_merge(defaults, overlay)

    if override:
        merged = _deep_merge(merged, override)

    try:
        params = ModelParams.model_validate(merged)
    except ValidationError as e:
        logger.error(f"Invalid model parameters; using defaults. Error: {e}")
        params = ModelParams()  # type: ignore[call-arg]

    _cached_params = params
    return params


# --- Enums and Planning/Data Entities required by unit tests ---

from dataclasses import dataclass  # noqa: E402
from datetime import datetime  # noqa: E402
from enum import Enum  # noqa: E402


class ExpenseCategory(str, Enum):
    INVENTORY = "inventory"
    MARKETING = "marketing"
    OPERATIONS = "operations"
    CUSTOMER_SERVICE = "customer_service"
    FEES = "fees"
    OTHER = "other"


class PlanPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class StrategicObjective:
    objective_id: str
    title: str
    description: str
    target_metrics: Dict[str, Any]
    timeframe_days: int
    priority: PlanPriority
    status: PlanStatus
    created_at: datetime
    target_completion: datetime


@dataclass
class TacticalAction:
    action_id: str
    title: str
    description: str
    action_type: str
    parameters: Dict[str, Any]
    strategic_objective_id: str
    priority: PlanPriority
    status: PlanStatus
    created_at: datetime
    scheduled_execution: datetime
    estimated_duration_hours: float
    expected_impact: Dict[str, Any]


__all__ = [
    # Parameters root
    "ModelParams",
    "get_model_params",
    "settings",
    # Enums and entities for tests
    "ExpenseCategory",
    "PlanPriority",
    "PlanStatus",
    "StrategicObjective",
    "TacticalAction",
]

settings = get_model_params()
