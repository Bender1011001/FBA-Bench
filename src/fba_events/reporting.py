"""
Event definitions for financial reporting and significant loss events in the FBA-Bench simulation.

This module defines `ProfitReport`, which provides a structured summary of financial
performance over a reporting period, and `LossEvent`, which signals the occurrence
of a significant financial setback. These events are critical for financial
monitoring, performance evaluation, and risk management within the simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from fba_bench_core.money import Money  # External dependency for precise financial calculations

from .base import BaseEvent


@dataclass
class ProfitReport(BaseEvent):
    """
    Provides a structured summary of financial profit and loss for a specific reporting period.

    This event is typically published by a `FinancialAuditService` or `ReportingService`
    at regular intervals (e.g., end of simulation day, week, or month). It aggregates
    revenue, expenses, and net profit, along with breakdowns.

    Attributes:
        event_id (str): Unique identifier for this profit report event. Inherited from `BaseEvent`.
        timestamp (datetime): When the profit report was generated. Inherited from `BaseEvent`.
        reporting_period (str): A string describing the period covered by the report,
                                e.g., "Day 1", "Week 3", "Monthly June".
        total_revenue (Money): The total gross revenue for the reporting period. Must be a `Money` object.
        total_expenses (Money): The total expenses incurred during the reporting period. Must be a `Money` object.
        net_profit (Money): The net profit (or loss) for the period, calculated as `total_revenue - total_expenses`.
                            Must be a `Money` object. Minor rounding discrepancies are allowed.
        profit_margin (float): The profit margin percentage for the period
                                (net_profit / total_revenue) * 100.
        product_breakdown (Dict[str, Money]): An optional breakdown of profit contribution by product ASIN.
                                              Keys are ASINs, values are `Money` objects.
        expense_breakdown (Dict[str, Money]): An optional breakdown of expenses by category,
                                              e.g., {'advertising': Money(...), 'fulfillment': Money(...)}}.
        performance_vs_target (Dict[str, float]): A dictionary mapping performance metrics
                                                  to their achievement percentage against targets,
                                                  e.g., {'revenue_target_achieved': 95.5, 'profit_goal_met': 102.1}.
    """

    reporting_period: str
    total_revenue: Money
    total_expenses: Money
    net_profit: Money
    profit_margin: float
    product_breakdown: Dict[str, Money] = field(default_factory=dict)
    expense_breakdown: Dict[str, Money] = field(default_factory=dict)
    performance_vs_target: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """
        Validates the attributes of the `ProfitReport` event upon initialization.
        Ensures reporting period is provided, financial fields are `Money` objects,
        and net profit calculation is consistent.
        """
        super().__post_init__()  # Call base class validation

        # Validate reporting_period: Must be a non-empty string.
        if not self.reporting_period:
            raise ValueError("Reporting period cannot be empty for ProfitReport.")

        # Validate core financial fields are Money instances.
        money_fields = ["total_revenue", "total_expenses", "net_profit"]
        for field_name in money_fields:
            value = getattr(self, field_name)
            if not isinstance(value, Money):
                raise TypeError(
                    f"'{field_name}' must be a Money type, but got {type(value)} for ProfitReport."
                )

        # Validate profit calculation: Check if net_profit is consistent with revenue and expenses.
        # Allow for minor rounding discrepancies (up to 1 cent).
        calculated_profit = Money(self.total_revenue.cents - self.total_expenses.cents)
        if abs(self.net_profit.cents - calculated_profit.cents) > 1:
            raise ValueError(
                f"Net profit calculation error: expected {calculated_profit}, but got {self.net_profit} for ProfitReport."
            )

        # Validate profit_margin: Can be any float, but good practice might constrain it if needed.
        # For simplicity, no specific range validation here, but ensure it's a float.
        if not isinstance(self.profit_margin, float):
            raise TypeError("Profit margin must be a float for ProfitReport.")

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `ProfitReport` event into a concise summary dictionary.

        Financial `Money` objects are converted to string representation,
        percentages are rounded, and counts for breakdowns are provided
        instead of full dictionaries for brevity in logging.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "reporting_period": self.reporting_period,
            "total_revenue": str(self.total_revenue),
            "total_expenses": str(self.total_expenses),
            "net_profit": str(self.net_profit),
            "profit_margin": round(self.profit_margin, 4),  # Round for display
            "product_breakdown_count": len(self.product_breakdown),
            "expense_categories_count": len(self.expense_breakdown),
            "performance_metrics": self.performance_vs_target.copy(),  # Return a copy
        }


@dataclass
class LossEvent(BaseEvent):
    """
    Signals the occurrence of a significant financial loss or other negative event.

    This event is used to capture and report exceptional financial setbacks
    that are not part of regular operational expenses, allowing for their
    tracking, analysis, and remediation planning.

    Attributes:
        event_id (str): Unique identifier for this loss event. Inherited from `BaseEvent`.
        timestamp (datetime): When the loss occurred or was recorded. Inherited from `BaseEvent`.
        loss_type (str): The category of the loss, e.g., "operational_error", "fraud",
                         "writeoff", "market_downturn_impact", "supply_chain_disruption".
        amount (Money): The financial amount of the loss. Must be a positive `Money` object.
        cause (str): A detailed description of the root cause of the loss.
        affected_area (str): The business area or department primarily affected by the loss,
                             e.g., "inventory", "sales", "marketing", "operations".
        recovery_plan (str): An optional description of the plan devised to recover from the loss.
                             Defaults to an empty string.
        prevention_measures (List[str]): A list of measures implemented or planned to prevent
                                         recurrence of this type of loss. Defaults to empty list.
        severity (str): The severity of the loss's impact,
                        e.g., "low", "medium", "high", "critical". Defaults to "medium".
        insurance_claim (bool): `True` if an insurance claim is applicable or has been filed for this loss.
                                Defaults to `False`.
    """

    loss_type: str
    amount: Money
    cause: str
    affected_area: str
    recovery_plan: str = ""
    prevention_measures: List[str] = field(default_factory=list)
    severity: str = "medium"
    insurance_claim: bool = False

    def __post_init__(self):
        """
        Validates the attributes of the `LossEvent` upon initialization.
        Ensures loss type, amount (positive), cause, and affected area are provided,
        and severity is one of the allowed values.
        """
        super().__post_init__()  # Call base class validation

        # Validate loss_type: Must be a non-empty string.
        if not self.loss_type:
            raise ValueError("Loss type cannot be empty for LossEvent.")

        # Validate amount: Must be a Money instance and positive.
        if not isinstance(self.amount, Money):
            raise TypeError(
                f"Amount must be a Money type, but got {type(self.amount)} for LossEvent."
            )
        if self.amount.cents <= 0:
            raise ValueError(
                f"Loss amount must be positive, but got {self.amount} for LossEvent."
            )

        # Validate cause: Must be a non-empty string.
        if not self.cause:
            raise ValueError("Cause cannot be empty for LossEvent.")

        # Validate affected_area: Must be a non-empty string.
        if not self.affected_area:
            raise ValueError("Affected area cannot be empty for LossEvent.")

        # Validate severity: Must be one of the predefined categories.
        if self.severity not in ["low", "medium", "high", "critical"]:
            raise ValueError(
                f"Severity must be 'low', 'medium', 'high', or 'critical', but got '{self.severity}' for LossEvent."
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `LossEvent` into a concise summary dictionary.

        Indicates presence of recovery plan/prevention measures by boolean/count,
        and converts `Money` objects to string representation.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "loss_type": self.loss_type,
            "amount": str(self.amount),
            "cause": self.cause,
            "affected_area": self.affected_area,
            "recovery_plan_provided": bool(
                self.recovery_plan
            ),  # Indicate if a plan is present
            "prevention_measures_count": len(
                self.prevention_measures
            ),  # Count for summary
            "severity": self.severity,
            "insurance_claim": self.insurance_claim,
        }
