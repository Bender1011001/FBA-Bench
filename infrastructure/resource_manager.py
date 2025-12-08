import logging
from typing import Dict

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Minimal resource manager:
    - Tracks token allocations per component and enforces a global token budget
    - Tracks LLM dollar costs per component and enforces a global cost limit

    Non-invasive test shims added:
    - set_global_token_cap(cap) : convenience for tests
    - monitor_memory_usage() : lightweight probe returning token/cost snapshot
    - get_resource_metrics() : summary dict for PerformanceMonitor integration
    """

    def __init__(self, token_budget: int = 1_000_000, cost_limit: float = 1_000_000.0) -> None:
        self.token_budget = token_budget
        self.cost_limit = cost_limit
        # tests inspect these private dicts
        self._token_budgets: Dict[str, int] = {}
        self._token_usage: Dict[str, int] = {}
        self._llm_costs: Dict[str, float] = {}
        # some tests assert a global cap attribute exists and equals default
        self._global_token_cap: int = token_budget

    @property
    def total_tokens_used(self) -> int:
        return sum(self._token_usage.values())

    @property
    def total_cost(self) -> float:
        return float(self.get_total_api_cost())

    def allocate_tokens(self, name: str, purpose: str, n: int) -> bool:
        """
        Allocate tokens for a named component and purpose.

        Tests call allocate_tokens(name, purpose, n) and expect a boolean result.
        Enforce budgets and return:
        - True when allocation succeeds
        - False when allocation would exceed per-name or global budgets
        """
        if n < 0:
            raise ValueError("n must be >= 0")
        used = self.total_tokens_used
        # Enforce per-name budget if set
        per_budget = self._token_budgets.get(name, None)
        if per_budget is not None and self._token_usage.get(name, 0) + n > per_budget:
            return False
        # Enforce global budget
        if used + n > self.token_budget:
            return False

        self._token_usage[name] = self._token_usage.get(name, 0) + int(n)
        # Keep a mirror "budget per name" if tests later depend on it
        self._token_budgets.setdefault(name, 0)
        return True

    def record_llm_cost(self, name: str, dollars: float, tokens: int = 0) -> None:
        """
        Record LLM cost and optional token usage for a given tool/model.

        Tests expect this to store a mapping for each name with total_cost and total_tokens.
        """
        if dollars < 0:
            raise ValueError("dollars must be >= 0")
        if tokens < 0:
            raise ValueError("tokens must be >= 0")

        prev = self._llm_costs.get(name, {"total_cost": 0.0, "total_tokens": 0})
        # If stored as float from older behavior, normalize to dict
        if isinstance(prev, (int, float)):
            prev = {"total_cost": float(prev), "total_tokens": 0}

        new_total_cost = float(prev.get("total_cost", 0.0)) + float(dollars)
        new_total_tokens = int(prev.get("total_tokens", 0)) + int(tokens)

        self._llm_costs[name] = {"total_cost": new_total_cost, "total_tokens": new_total_tokens}

        if tokens:
            # update token usage mirror for this name
            self._token_usage[name] = self._token_usage.get(name, 0) + int(tokens)

        # Validate cost limits, but do not raise on automatic tracking paths.
        # Tests expect a warning behavior here rather than an exception.
        try:
            self.enforce_cost_limits()
        except ValueError:
            try:
                logger.warning(
                    "Total API cost %.4f exceeded limit %.4f during record_llm_cost(%s).",
                    self.get_total_api_cost(),
                    float(self.cost_limit),
                    name,
                )
            except Exception:
                pass

    def get_total_api_cost(self) -> float:
        """Return aggregated API cost across all tracked models/tools."""
        total = 0.0
        for v in self._llm_costs.values():
            if isinstance(v, dict):
                total += float(v.get("total_cost", 0.0))
            elif isinstance(v, (int, float)):
                total += float(v)
        return float(total)

    def get_current_token_usage(self, name: str) -> int:
        """Return current token usage for a specific name. Special names: 'total', '*', 'all'."""
        if name is None:
            return int(self.total_tokens_used)
        key = str(name).lower()
        if key in ("total", "*", "all"):
            return int(self.total_tokens_used)
        return int(self._token_usage.get(name, 0))

    # keep enforce_cost_limits signature compatible
    def enforce_cost_limits(self, limit: float | None = None) -> None:
        """
        Enforce cost limits.

        If limit is provided, persist it as the active cost_limit so downstream metrics
        and bottleneck detection reflect the updated threshold.

        Raises:
            ValueError: if the total tracked API cost exceeds the enforced limit.
        """
        if limit is not None:
            self.cost_limit = float(limit)

        total = float(self.get_total_api_cost())
        if total > float(self.cost_limit):
            raise ValueError(
                f"Total API cost {total:.6f} exceeds limit {float(self.cost_limit):.6f}"
            )
        return None

    def get_usage_snapshot(self) -> Dict[str, Dict[str, float]]:
        """
        Return a snapshot of current usage and costs keyed by model/tool name.
        """
        snapshot: Dict[str, Dict[str, float]] = {}
        try:
            for name, v in self._llm_costs.items():
                total_cost = (
                    float(v.get("total_cost", 0.0)) if isinstance(v, dict) else float(v or 0.0)
                )
                snapshot[name] = {
                    "total_cost": total_cost,
                    "total_tokens": float(self._token_usage.get(name, 0)),
                }
        except Exception:
            pass
        return snapshot

    # --- Added test shims -------------------------------------------------

    def set_global_token_cap(self, cap: int) -> None:
        """Compatibility helper for tests to set a global cap."""
        try:
            self._global_token_cap = int(cap)
            self.token_budget = int(cap)
        except Exception:
            pass

    def monitor_memory_usage(self) -> Dict[str, float]:
        """
        Lightweight probe returning a dict for PerformanceMonitor:
        - system_percent: proxy via ratio of total tokens used to global cap
        - process_memory_mb: simple function of tracked dict sizes (best-effort)
        """
        try:
            system_pct = 0.0
            if self._global_token_cap > 0:
                system_pct = min(
                    100.0, 100.0 * float(self.total_tokens_used) / float(self._global_token_cap)
                )
        except Exception:
            system_pct = 0.0
        try:
            approx_mb = (
                len(self._token_usage) * 0.001
                + len(self._token_budgets) * 0.001
                + len(self._llm_costs) * 0.002
            )
        except Exception:
            approx_mb = 0.0
        return {"system_percent": float(system_pct), "process_memory_mb": float(approx_mb)}

    def get_resource_metrics(self) -> Dict[str, float]:
        """
        Summary metrics used by PerformanceMonitor:
        - total_llm_cost
        - total_tokens_used
        - cost_limit
        """
        metrics = {
            "total_llm_cost": float(self.get_total_api_cost()),
            "total_tokens_used": float(self.total_tokens_used),
            "cost_limit": float(self.cost_limit),
        }
        return metrics
        return {
            "tokens": dict(self._token_usage),
            "costs": dict(self._llm_costs),
            "totals": {
                "tokens": float(self.total_tokens_used),
                "cost": float(self.total_cost),
                "token_budget": float(self.token_budget),
                "cost_limit": float(self.cost_limit),
            },
        }

    # Compatibility helpers expected by some tests
    def set_global_token_cap(self, cap: int) -> None:
        """Set the global token cap used by tests and components."""
        if cap < 0:
            raise ValueError("cap must be >= 0")
        self._global_token_cap = int(cap)
        self.token_budget = int(cap)

    # Test-expected API: set_token_budget(name, n) to set per-tool token budgets explicitly
    def set_token_budget(self, name: str, n: int) -> None:
        if n < 0:
            raise ValueError("n must be >= 0")
        self._token_budgets[name] = int(n)
        # Ensure the usage key exists
        self._token_usage.setdefault(name, 0)

    # Convenience to set multiple budgets
    def set_token_budgets(self, budgets: Dict[str, int]) -> None:
        for k, v in budgets.items():
            self.set_token_budget(k, v)

    def monitor_memory_usage(self) -> Dict[str, float]:
        """
        Lightweight monitoring shim to satisfy tests that expect resource snapshots.
        Returns a dict with token/cost totals and process memory metrics.
        Issue 79: Moved psutil import to module level.
        """
        process_memory_mb = 0.0
        system_percent = 0.0
        
        if psutil:
            try:
                process_memory_mb = float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
                system_percent = float(psutil.virtual_memory().percent)
            except Exception:
                pass

        return {
            "total_tokens_used": float(self.total_tokens_used),
            "total_cost": float(self.total_cost),
            "total_llm_cost": float(self.get_total_api_cost()),
            "token_budget": float(self.token_budget),
            "cost_limit": float(self.cost_limit),
            "process_memory_mb": float(process_memory_mb),
            "system_percent": float(system_percent),
        }

    def get_resource_metrics(self) -> Dict[str, float]:
        """
        Return a standardized metrics dict used by monitoring/reporting components.
        Keys intentionally match tests' expectations.
        """
        return {
            "total_llm_cost": float(self.get_total_api_cost()),
            "total_tokens_used": float(self.total_tokens_used),
            "token_budget": float(self.token_budget),
            "cost_limit": float(self.cost_limit),
        }
