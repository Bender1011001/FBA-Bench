import asyncio
import logging
from typing import Any, Dict, List, Optional

import psutil

class PerformanceMonitor:
    """
    Minimal performance monitor that returns a complete metrics dict and
    simple bottleneck detection plus optimization suggestions.
    """

    def __init__(self, resource_manager: object | None = None) -> None:
        self.resource_manager = resource_manager
        self._last: Dict[str, float] = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_percent": 0.0,
            "disk_read_mbs": 0.0,
            "disk_write_mbs": 0.0,
            "process_memory_mb": 0.0,
            "system_percent": 0.0,
            "total_llm_cost": 0.0,
        }
        self._monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring_interval: float = 0.5
        self._metrics_history: List[Dict[str, float]] = []
        self.logger = logging.getLogger(__name__)

    def monitor_system_resources(self) -> Dict[str, float]:
        # [Existing logic retained - Base sampling via psutil]
        try:
            cpu_p = float(psutil.cpu_percent())
            mem_p = float(psutil.virtual_memory().percent)
            disk_p = float(psutil.disk_usage("/").percent)
            self._last.update(
                {"cpu_percent": cpu_p, "memory_percent": mem_p, "disk_percent": disk_p}
            )
        except Exception:
            pass

        # [Existing logic retained - Resource Manager Integration]
        try:
            rm = self.resource_manager
            if rm:
                if hasattr(rm, "monitor_memory_usage"):
                    mem_metrics = rm.monitor_memory_usage()
                    if isinstance(mem_metrics, dict):
                        if "process_memory_mb" in mem_metrics:
                            self._last["process_memory_mb"] = float(mem_metrics.get("process_memory_mb", 0.0))
                        if "system_percent" in mem_metrics:
                            self._last["system_percent"] = float(mem_metrics.get("system_percent", 0.0))
                        # Mirror system_percent if psutil failed
                        if "system_percent" in mem_metrics and self._last.get("memory_percent", 0.0) == 0.0:
                            self._last["memory_percent"] = float(mem_metrics.get("system_percent", 0.0))
                
                if hasattr(rm, "get_resource_metrics"):
                    res_metrics = rm.get_resource_metrics()
                    if isinstance(res_metrics, dict):
                        if "total_llm_cost" in res_metrics:
                            self._last["total_llm_cost"] = float(res_metrics.get("total_llm_cost", 0.0))
                        if "total_tokens_used" in res_metrics:
                            self._last["total_tokens_used"] = float(res_metrics.get("total_tokens_used", 0.0))
        except Exception:
            pass

        # Record history
        try:
            self._metrics_history.append(dict(self._last))
            if len(self._metrics_history) > 1000:
                self._metrics_history.pop(0)
        except Exception:
            pass

        return dict(self._last)

    def detect_bottlenecks(self, metrics: Dict[str, float]) -> List[str]:
        # [Existing logic retained from original first definition]
        cpu_high = metrics.get("cpu_percent", 0.0) > 80.0
        mem_high = (metrics.get("memory_percent", 0.0) > 80.0 or metrics.get("system_percent", 0.0) > 80.0)
        disk_high = (metrics.get("disk_percent", 0.0) > 80.0)

        descriptions: List[str] = []
        if cpu_high:
            descriptions.append("High CPU usage")
        if mem_high:
            descriptions.append("High memory usage")
        if disk_high:
            descriptions.append("High disk usage")

        # Cost bottlenecks
        try:
            total_cost = float(metrics.get("total_llm_cost", 0.0))
            cost_limit = 0.0
            if self.resource_manager:
                cost_limit = float(getattr(self.resource_manager, "cost_limit", 0.0))
            
            if cost_limit > 0.0:
                ratio = total_cost / cost_limit
                if ratio >= 1.0:
                    descriptions.append("LLM Cost Limit Exceeded")
                elif ratio >= 0.9:
                    descriptions.append("Approaching LLM Cost Limit")
        except Exception:
            pass

        return descriptions

    def suggest_optimizations(self, bottlenecks: Any) -> list[str]:
        suggestions: list[str] = []
        # [Existing logic retained]
        if isinstance(bottlenecks, list):
            text = " ".join(bottlenecks).lower()
            if "cpu" in text:
                suggestions.append("Consider scaling horizontally")
            if "memory" in text:
                suggestions.append("Optimize memory usage")
            if "disk" in text:
                suggestions.append("Move to faster storage")
        return suggestions

    def monitor_memory_usage(self) -> float:
        """Return latest memory usage percent."""
        metrics = self.monitor_system_resources()
        return float(metrics.get("memory_percent", 0.0))

    async def start(self) -> None:
        """Start background monitoring."""
        if self._monitoring:
            return
        self._monitoring = True

        async def _loop():
            while self._monitoring:
                try:
                    self.monitor_system_resources()
                except Exception:
                    pass
                await asyncio.sleep(self._monitoring_interval)

        self._monitor_task = asyncio.create_task(_loop())
        self.logger.info("PerformanceMonitor started.")

    async def stop(self) -> None:
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    def get_last_metrics(self) -> Dict[str, float]:
        """Return the most recently sampled metrics dict."""
        return dict(self._last)

    def generate_performance_report(self) -> Dict[str, Any]:
        """
        Consolidated Report Generation:
        Combines historical averaging (from original 2nd def) with 
        bottleneck detection (from original 1st def).
        """
        last = self.get_last_metrics()
        history = list(self._metrics_history)
        n = len(history)

        def _avg(key: str) -> float:
            if n == 0:
                return 0.0
            try:
                return sum(float(m.get(key, 0.0)) for m in history) / float(n)
            except Exception:
                return 0.0

        # Calculate averages based on history
        avg_metrics = {
            "cpu_percent": _avg("cpu_percent"),
            "memory_percent": _avg("memory_percent"),
            "disk_percent": _avg("disk_percent"),
            "process_memory_mb": _avg("process_memory_mb"),
            "system_percent": _avg("system_percent"),
            "total_llm_cost": _avg("total_llm_cost"),
        }

        # Detect bottlenecks based on the LATEST snapshot
        bottlenecks = self.detect_bottlenecks(last)
        suggestions = self.suggest_optimizations(bottlenecks)

        report = {
            "samples": n,
            "num_data_points": n,
            "latest": last,
            "last": last,  # Back-compat alias
            "averages": avg_metrics,
            "avg_metrics": avg_metrics,  # Back-compat alias
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
            "resources": {}
        }

        # Include resource manager metrics if available
        if self.resource_manager and hasattr(self.resource_manager, "get_resource_metrics"):
            try:
                report["resources"] = self.resource_manager.get_resource_metrics()
            except Exception:
                pass

        # Summary string
        report["summary"] = (
            f"Avg CPU: {avg_metrics['cpu_percent']:.2f}%, "
            f"Avg Memory: {avg_metrics['memory_percent']:.2f}%, "
            f"Avg LLM Cost: ${avg_metrics['total_llm_cost']:.4f}"
        )

        return report
