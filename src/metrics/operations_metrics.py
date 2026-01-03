# metrics/operations_metrics.py
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class AbstractSalesService(Protocol):
    """Protocol for a sales service."""

    def get_current_inventory_value(self) -> float: ...


@dataclass
class OperationsMetricsConfig:
    """Configuration for OperationsMetrics."""

    default_on_zero_division: float = 0.0


class OperationsMetrics:
    def __init__(
        self,
        sales_service: Optional[AbstractSalesService] = None,
        initial_inventory_value: float = 0.0,
        config: Optional[OperationsMetricsConfig] = None,
    ):
        if sales_service is not None and not isinstance(
            sales_service, AbstractSalesService
        ):
            raise TypeError(
                "sales_service must implement AbstractSalesService protocol."
            )
        self.sales_service = sales_service
        self.config = config if config else OperationsMetricsConfig()
        self.total_revenue = 0.0
        self.inventory_history: List[Dict] = []  # {'tick': int, 'value': float}
        self.stockout_days = 0
        self.total_operational_days = 0
        self.initial_inventory_value = initial_inventory_value

        # Unit-test compatibility: lightweight metric registry
        self._metrics: Dict[str, Any] = {}

    def update(self, current_tick: int, events: List[Dict]):
        # Assuming tick starts at 0, day count is tick + 1
        self.total_operational_days = current_tick + 1

        # Update revenue from SaleOccurred events
        for event in events:
            if event.get("type") == "SaleOccurred":
                # Prefer explicit total_revenue/amount fields, fallback to unit_price * units if present
                amount = event.get("amount")
                if isinstance(amount, (int, float)):
                    self.total_revenue += float(amount)
                else:
                    units = event.get("units_sold") or event.get("units", 0)
                    unit_price = event.get("unit_price") or event.get("price") or 0.0
                    try:
                        self.total_revenue += float(units) * float(unit_price)
                    except (ValueError, TypeError):
                        # ignore if not computable
                        pass

        # Resolve inventory value via service if available, else via events fallback, else last known value
        current_inventory_value = self._resolve_inventory_value(events)
        self.inventory_history.append(
            {"tick": current_tick, "value": current_inventory_value}
        )

        # Check for stockouts (simplified: if inventory value drops to zero)
        if current_inventory_value == 0:
            self.stockout_days += 1

    def _resolve_inventory_value(self, events: List[Dict]) -> float:
        """
        Determine current inventory value using the following precedence:
        1) sales_service.get_current_inventory_value() if available
        2) Any event that carries 'inventory_value' or ('inventory_quantity' and 'unit_cost'/'cost_basis')
        3) Last known inventory value (previous history) or initial_inventory_value
        """
        # 1) Service method if present
        try:
            getter: Optional[Callable[[], float]] = getattr(
                self.sales_service, "get_current_inventory_value", None
            )
            if callable(getter):
                val = getter()
                if isinstance(val, (int, float)):
                    return float(val)
        except (AttributeError, RuntimeError):
            pass

        # 2) Fallback via events data
        latest_val: Optional[float] = None
        for e in reversed(events):  # prefer most recent event first
            if isinstance(e, dict):
                if "inventory_value" in e and isinstance(
                    e["inventory_value"], (int, float)
                ):
                    latest_val = float(e["inventory_value"])
                    break
                qty = e.get("inventory_quantity")
                unit_cost = e.get("unit_cost") or e.get("cost_basis")
                if isinstance(qty, (int, float)) and isinstance(
                    unit_cost, (int, float)
                ):
                    latest_val = float(qty) * float(unit_cost)
                    break

        if latest_val is not None:
            return latest_val

        # 3) Prior value or initial
        if self.inventory_history:
            return float(self.inventory_history[-1]["value"])
        return float(self.initial_inventory_value)

    def calculate_inventory_turnover(self) -> float:
        if not self.inventory_history:
            return 0.0

        # Calculate average inventory value based on history
        # Note: We rely on history populated during updates.
        inventory_values = [d["value"] for d in self.inventory_history]
        
        # Avoid zero division
        if not inventory_values:
            return 0.0
            
        average_inventory_value = sum(inventory_values) / len(inventory_values)

        if average_inventory_value > 0:
            return self.total_revenue / average_inventory_value
        return 0.0

    def calculate_stockout_percentage(self) -> float:
        if self.total_operational_days == 0:
            return 0.0
        return (self.stockout_days / self.total_operational_days) * 100

    def get_metrics_breakdown(self) -> Dict[str, float]:
        inventory_turnover = self.calculate_inventory_turnover()
        stockout_percentage = self.calculate_stockout_percentage()

        # Simple overall score heuristic: higher turnover is good, lower stockout is good.
        # This is a placeholder logic for overall_score to avoid missing key errors downstream.
        overall_score = 0.0
        if inventory_turnover > 0:
             overall_score += min(50.0, inventory_turnover * 5) # Cap contribution
        overall_score += max(0.0, 50.0 - stockout_percentage) # Cap contribution

        return {
            "overall_score": overall_score,
            "inventory_turnover": inventory_turnover,
            "stockout_percentage": stockout_percentage,
        }

    # ---- Unit-test compatible helpers expected by tests ----
    def calculate_throughput(self, data: Dict[str, float]) -> float:
        units = float(data.get("units_produced", 0.0))
        period = float(data.get("time_period", 0.0))
        return units / period if period > 0 else 0.0

    def calculate_cycle_time(self, data: Dict[str, float]) -> float:
        total_time = float(data.get("total_production_time", 0.0))
        units = float(data.get("units_produced", 0.0))
        return total_time / units if units > 0 else 0.0

    def calculate_utilization_rate(self, data: Dict[str, float]) -> float:
        actual = float(data.get("actual_output", 0.0))
        capacity = float(data.get("maximum_capacity", 0.0))
        return actual / capacity if capacity > 0 else 0.0

    def calculate_defect_rate(self, data: Dict[str, float]) -> float:
        defective = float(data.get("defective_units", 0.0))
        total = float(data.get("total_units", 0.0))
        return defective / total if total > 0 else 0.0

    def calculate_overall_equipment_effectiveness(
        self, data: Dict[str, float]
    ) -> float:
        availability = float(data.get("availability", 0.0))
        performance = float(data.get("performance", 0.0))
        quality = float(data.get("quality", 0.0))
        return availability * performance * quality

    def generate_operations_report(self, data: Dict[str, float]) -> Dict[str, float]:
        throughput = self.calculate_throughput(data)
        cycle_time = self.calculate_cycle_time(data)
        utilization = self.calculate_utilization_rate(data)
        defect_rate = self.calculate_defect_rate(data)
        oee = self.calculate_overall_equipment_effectiveness(data)
        return {
            "throughput": throughput,
            "cycle_time": cycle_time,
            "utilization_rate": utilization,
            "defect_rate": defect_rate,
            "overall_equipment_effectiveness": oee,
        }
