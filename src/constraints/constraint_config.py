import logging  # Added for logging warnings on invalid token cost input
from dataclasses import dataclass
from typing import (  # Added Optional for token_cost_per_1k_input and Any for config_dict typing
    Any,
    Dict,
    Optional,
)

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ConstraintConfig:
    max_tokens_per_action: int
    max_total_tokens: int
    token_cost_per_1k: float
    violation_penalty_weight: float
    grace_period_percentage: float
    hard_fail_on_violation: bool
    inject_budget_status: bool
    track_token_efficiency: bool
    token_cost_per_1k_input: Optional[float] = None
    """Cost per 1k input tokens, used for detailed cost tracking."""

    # compat: provide minimal dict-like access for legacy callers (e.g., BudgetEnforcer)
    def get(self, key, default=None):
        return getattr(self, key, default)

    # compat: allow attribute access via mapping-style indexing; provide "limits" mapping and mapping semantics
    def __getitem__(self, key):
        # Special-case mapping access to "limits" used by BudgetEnforcer._check_overall_limit()
        if key == "limits":
            return self.limits
        # compat: default 80% for legacy configs missing this key
        if key == "warning_threshold_pct":
            return getattr(self, "warning_threshold_pct", 80)  # compat: default 80%
        # Mapping semantics: raise KeyError when key is absent
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    @property
    def limits(self) -> Dict[str, int]:
        """
        compat: Provide a robust, backward-compatible limits mapping with canonical keys
        and the keys currently read by BudgetEnforcer._check_overall_limit().

        Included keys (when resolvable and coercible to int):
          - Canonical (legacy-friendly):
            * "overall_tokens_tick"
            * "overall_tokens_total"
          - Keys read by BudgetEnforcer:
            * "total_tokens_per_tick"
            * "total_tokens_per_run"
            * "total_cost_cents_per_tick"   (compat: default to very high if unavailable)
            * "total_cost_cents_per_run"    (compat: default to very high if unavailable)

        Candidate resolution (first hit wins):
          - per-tick tokens: ["overall_tokens_tick", "max_tokens_per_tick", "per_tick_limit", "tokens_per_tick_limit"]
          - total tokens:    ["overall_tokens_total", "max_tokens_total", "total_simulation_limit", "tokens_total_limit"]
        """

        def _as_int(val):
            try:
                return int(val)
            except (TypeError, ValueError):
                return None

        limits: Dict[str, int] = {}

        # Resolve per-tick overall tokens
        per_tick_val = None
        for name in (
            "overall_tokens_tick",
            "max_tokens_per_tick",
            "per_tick_limit",
            "tokens_per_tick_limit",
        ):
            v = getattr(self, name, None)
            if v is not None:
                iv = _as_int(v)
                if iv is not None:
                    per_tick_val = iv
                    break

        # Resolve total overall tokens (per run)
        total_val = None
        for name in (
            "overall_tokens_total",
            "max_tokens_total",
            "total_simulation_limit",
            "tokens_total_limit",
        ):
            v = getattr(self, name, None)
            if v is not None:
                iv = _as_int(v)
                if iv is not None:
                    total_val = iv
                    break

        # Populate canonical keys when available
        if per_tick_val is not None:
            limits["overall_tokens_tick"] = per_tick_val  # canonical
        if total_val is not None:
            limits["overall_tokens_total"] = total_val  # canonical

        # compat: Always expose BudgetEnforcer aliases even if canonical values are absent.
        #          Use resolved per-tick/total candidates; otherwise, provide a large safe ceiling
        #          to avoid KeyError in legacy callers.
        limits["total_tokens_per_tick"] = (
            per_tick_val if per_tick_val is not None else 999_999_999
        )  # compat: alias/fallback
        limits["total_tokens_per_run"] = (
            total_val if total_val is not None else 999_999_999
        )  # compat: alias/fallback

        # compat: BudgetEnforcer also reads cost limits; legacy ConstraintConfig
        # does not define cost ceilings, so default to effectively unbounded values
        # when not explicitly provided to avoid KeyError and preserve legacy behavior.
        cost_tick = _as_int(getattr(self, "total_cost_cents_per_tick", None))
        cost_run = _as_int(getattr(self, "total_cost_cents_per_run", None))
        if cost_tick is None:
            cost_tick = 999_999_999
        if cost_run is None:
            cost_run = 999_999_999
        limits["total_cost_cents_per_tick"] = cost_tick
        limits["total_cost_cents_per_run"] = cost_run

        return limits

    @classmethod
    def from_yaml(cls, filepath: str):
        """
        Loads ConstraintConfig from a YAML file with explicit structure validation.

        It validates top-level keys "budget_constraints" and "enforcement".
        Raises ValueError with a clear message if the root is not a mapping,
        or if the provided sections are the wrong type.
        Missing sections default to {} (backward-compat), but at least one
        of the two must be present.
        """
        with open(filepath) as f:
            config_dict: Dict[str, Any] = yaml.safe_load(f)

        if not isinstance(config_dict, dict):
            raise ValueError(
                f"ConstraintConfig YAML root must be a mapping (dict), got: {type(config_dict).__name__}"
            )

        budget_constraints: Dict[str, Any] = config_dict.get("budget_constraints", {})
        enforcement: Dict[str, Any] = config_dict.get("enforcement", {})

        if "budget_constraints" in config_dict and not isinstance(budget_constraints, dict):
            raise ValueError("`budget_constraints` must be a mapping (dict)")

        if "enforcement" in config_dict and not isinstance(enforcement, dict):
            raise ValueError("`enforcement` must be a mapping (dict)")

        if "budget_constraints" not in config_dict and "enforcement" not in config_dict:
            raise ValueError(
                "At least one of {`budget_constraints`,`enforcement`} must be provided at top level"
            )

        if "budget_constraints" not in config_dict:
            logger.debug("Defaulting `budget_constraints` to {} for backward-compatibility.")
        if "enforcement" not in config_dict:
            logger.debug("Defaulting `enforcement` to {} for backward-compatibility.")

        # Parse token_cost_per_1k_input, mirroring token_cost_per_1k loading
        token_cost_input = budget_constraints.get("token_cost_per_1k_input")
        if token_cost_input is not None:
            try:
                token_cost_input = float(token_cost_input)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid value for token_cost_per_1k_input: {token_cost_input}, "
                    "defaulting to None."
                )
                token_cost_input = None

        return cls(
            max_tokens_per_action=budget_constraints.get("max_tokens_per_action"),
            max_total_tokens=budget_constraints.get("max_total_tokens"),
            token_cost_per_1k=budget_constraints.get("token_cost_per_1k"),
            violation_penalty_weight=budget_constraints.get("violation_penalty_weight"),
            grace_period_percentage=budget_constraints.get("grace_period_percentage"),
            hard_fail_on_violation=enforcement.get("hard_fail_on_violation"),
            inject_budget_status=enforcement.get("inject_budget_status"),
            track_token_efficiency=enforcement.get("track_token_efficiency"),
            token_cost_per_1k_input=token_cost_input,
        )


# Default configurations for different tiers
def get_tier_config_path(tier: str) -> str:
    return f"constraints/tier_configs/{tier.lower()}_config.yaml"
