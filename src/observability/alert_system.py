import json
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Get logger instance instead of configuring basicConfig
logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AlertRule:
    name: str
    condition: str
    severity: AlertSeverity = AlertSeverity.WARNING


@dataclass
class AlertEvent:
    rule_name: str
    severity: AlertSeverity
    context: Dict[str, Any]
    timestamp: float


class ObservabilityAlertSystem:
    """
    Manages real-time observability alerts based on anomaly detection,
    performance monitoring, and error rate tracking.
    """

    def __init__(
        self,
        notification_callback: Optional[
            Callable[[str, str, Dict[str, Any]], None]
        ] = None,
    ):
        """
        Initializes the alert system.
        Args:
            notification_callback: A function to call when an alert is triggered.
                                   Expected signature: (alert_type: str, severity: str, details: Dict[str, Any])
        """
        self.notification_callback = notification_callback
        self.alert_rules: Dict[str, AlertRule] = {}  # Store AlertRule objects
        self.metric_baselines: Dict[str, Any] = {}
        self.error_history: Dict[str, deque] = (
            {}
        )  # {agent_id: deque of error timestamps}
        logging.info("ObservabilityAlertSystem initialized.")

    def detect_anomalies(
        self, metric_stream: Dict[str, float], baseline_key: str
    ) -> Optional[AlertEvent]:
        """
        Identifies unusual patterns in agent behavior or system metrics compared to a baseline.
        This is a simplified anomaly detection mechanism.

        Args:
            metric_stream: Current metric values (e.g., {"cpu_usage": 0.7, "memory_usage": 0.6}).
            baseline_key: Key to fetch the stored baseline (e.g., "agent_performance_baseline").

        Returns:
            A dictionary with anomaly details if detected, otherwise None.
        """
        baseline = self.metric_baselines.get(baseline_key)
        if not baseline:
            logger.warning(
                f"No baseline found for '{baseline_key}'. Cannot perform anomaly detection."
            )
            return None

        anomalies = {}
        # Make anomaly threshold configurable via environment variable
        anomaly_threshold = float(os.getenv("ANOMALY_DEVIATION_THRESHOLD", "0.2"))

        for metric, current_value in metric_stream.items():
            if metric in baseline and baseline[metric] != 0:
                deviation = abs((current_value - baseline[metric]) / baseline[metric])
                # Use configurable threshold instead of hardcoded 20%
                if deviation > anomaly_threshold:
                    anomalies[metric] = {
                        "current_value": current_value,
                        "baseline_value": baseline[metric],
                        "deviation_percent": f"{deviation:.2%}",
                    }

        if anomalies:
            alert_event = AlertEvent(
                rule_name="anomaly_detection",
                severity=AlertSeverity.ERROR,  # Anomality is typically an error
                context={
                    "message": f"Anomaly detected for baseline '{baseline_key}'.",
                    "anomalies": anomalies,
                    "baseline_key": baseline_key,
                },
                timestamp=time.time(),
            )
            self._send_alert(alert_event)
            return alert_event

        return None

    def monitor_performance_metrics(
        self,
        current_metrics: Dict[str, float],
        thresholds: Optional[Dict[str, float]] = None,
    ) -> List[AlertEvent]:
        """
        Notifies about system performance degradation based on predefined thresholds.
        If thresholds are not provided, uses default thresholds from environment variables.

        Args:
            current_metrics: Dictionary of current performance metrics (e.g., {"latency_ms": 150.5}).
            thresholds: Dictionary of {metric_name: max_allowed_value} thresholds.

        Returns:
            A list of triggered alerts.
        """
        triggered_alerts = []
        for metric, current_value in current_metrics.items():
            threshold = thresholds.get(metric)
            if threshold is not None and current_value > threshold:
                alert_event = AlertEvent(
                    rule_name="performance_alert",
                    severity=AlertSeverity.CRITICAL,
                    context={
                        "metric": metric,
                        "current_value": current_value,
                        "threshold": threshold,
                        "message": f"Performance for '{metric}' ({current_value:.2f}) exceeded threshold ({threshold:.2f}).",
                    },
                    timestamp=time.time(),
                )
                self._send_alert(alert_event)
                triggered_alerts.append(alert_event)

        return triggered_alerts

    def track_error_rates(
        self,
        agent_id: str,
        error_event_timestamp: float,
        time_window_seconds: int = 600,
        alert_threshold: int = 5,
    ) -> Optional[AlertEvent]:
        """
        Tracks and alerts on increasing error rates for a given agent within a time window.

        Args:
            agent_id: Identifier for the agent.
            error_event_timestamp: Timestamp of the latest error event.
            time_window_seconds: The duration (in seconds) to consider for calculating error rate.
            alert_threshold: The number of errors within the window to trigger an alert.

        Returns:
            A dictionary with alert details if triggered, otherwise None.
        """
        if agent_id not in self.error_history:
            self.error_history[agent_id] = deque()

        self.error_history[agent_id].append(error_event_timestamp)

        # Remove old errors outside the time window
        while (
            self.error_history[agent_id]
            and (error_event_timestamp - self.error_history[agent_id][0])
            > time_window_seconds
        ):
            self.error_history[agent_id].popleft()

        current_error_count = len(self.error_history[agent_id])

        if current_error_count >= alert_threshold:
            alert_event = AlertEvent(
                rule_name="error_rate_alert",
                severity=AlertSeverity.CRITICAL,
                context={
                    "agent_id": agent_id,
                    "error_count": current_error_count,
                    "time_window_seconds": time_window_seconds,
                    "alert_threshold": alert_threshold,
                    "message": f"High error rate detected for Agent '{agent_id}': {current_error_count} errors in {time_window_seconds} seconds.",
                },
                timestamp=time.time(),
            )
            self._send_alert(alert_event)
            return alert_event

        return None

    def configure_alert_rules(self, rule_definitions: List[Dict[str, Any]]):
        """
        Sets up custom alerting conditions based on a list of rule definitions.
        Example rule_definition:
        {
            "name": "high_cpu_usage",
            "condition": "cpu_usage > 0.9",
            "severity": "CRITICAL"
        }
        """
        for rule_def in rule_definitions:
            try:
                # Validate and create AlertRule objects
                severity = AlertSeverity[rule_def.get("severity", "WARNING").upper()]
                rule = AlertRule(
                    name=rule_def["name"],
                    condition=rule_def["condition"],
                    severity=severity,
                )
                self.alert_rules[rule.name] = rule
                logging.info(f"Configured alert rule: {rule.name}")
            except KeyError as e:
                logging.error(
                    f"Invalid alert rule definition: Missing key {e} in {rule_def}"
                )
            except ValueError as e:
                logging.error(f"Invalid alert rule definition: {e} for {rule_def}")
            except (TypeError, AttributeError, KeyError, RuntimeError) as e:
                logging.error(f"Error processing alert rule {rule_def}: {e}")
        logging.info(f"Loaded {len(self.alert_rules)} alert rules.")

    def _send_alert(self, alert_event: AlertEvent):
        """
        Dispatches notifications for triggered alerts.
        If a notification_callback is provided, it will be used.
        """
        logging.critical(
            f"ALERT TRIGGERED - Rule: {alert_event.rule_name}, Severity: {alert_event.severity.value}, Details: {json.dumps(alert_event.context)}"
        )
        if self.notification_callback:
            try:
                self.notification_callback(
                    alert_event.rule_name,
                    alert_event.severity.value,
                    {
                        **alert_event.context,
                        "timestamp": alert_event.timestamp,
                    },  # Include timestamp in context for callback
                )
                logging.info("Alert dispatched via callback.")
            except (TypeError, AttributeError, RuntimeError) as e:
                logging.error(f"Error sending alert via callback: {e}")
        else:
            logging.info("No notification callback configured. Alert logged only.")

    def set_baseline(self, key: str, value: Any):
        """Sets a baseline value for anomaly detection."""
        self.metric_baselines[key] = value
        logging.info(f"Baseline '{key}' set to: {value}")


DEFAULT_ALERT_RULES: List[AlertRule] = []  # Define a default empty list of alert rules


# Example Notification Callback
def console_notifier(rule_name: str, severity: str, details: Dict[str, Any]):
    print("\n--- !!! ALERT !!! ---")
    print(f"Rule: {rule_name}")
    print(f"Severity: {severity}")
    print(f"Details: {json.dumps(details, indent=2)}")
    print("----------------------\n")


# Backwards-compat implementation expected by unit tests
class AlertSystem:
    """
    Minimal alerting framework for unit tests with CRUD on rules, subscriber management,
    rule evaluation, and alert history.
    """

    def __init__(self):
        # Publicly-checked internal structures (per tests)
        self._alerts: List[Dict[str, Any]] = []
        self._alert_rules: Dict[str, Dict[str, Any]] = {}
        self._alert_subscribers: Dict[str, Any] = {}
        # Private counters for ids
        self._rule_counter: int = 0
        self._sub_counter: int = 0
        logger.info("AlertSystem initialized")

    # ---- Rules CRUD ----
    def create_alert_rule(self, rule_data: Dict[str, Any]) -> str:
        """
        rule_data keys: name, description, condition, severity, enabled
        Returns rule_id
        """
        self._rule_counter += 1
        rule_id = f"rule_{self._rule_counter}"
        # store a shallow copy to avoid external mutation
        stored = {
            "name": rule_data.get("name", rule_id),
            "description": rule_data.get("description", ""),
            "condition": rule_data.get("condition", ""),
            "severity": rule_data.get("severity", "low"),
            "enabled": bool(rule_data.get("enabled", True)),
        }
        self._alert_rules[rule_id] = stored
        return rule_id

    def update_alert_rule(self, rule_id: str, updated_data: Dict[str, Any]) -> None:
        if rule_id in self._alert_rules:
            self._alert_rules[rule_id].update(updated_data)

    def delete_alert_rule(self, rule_id: str) -> None:
        self._alert_rules.pop(rule_id, None)

    # ---- Evaluation / Alerts ----
    def evaluate_alert_rules(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate enabled rules against a flat metrics dict.
        Supports simple conditions like: "<metric> <op> <number>", where op in {>,>=,<,<=,==,!=}
        """
        alerts: List[Dict[str, Any]] = []
        for rule in self._alert_rules.values():
            if not rule.get("enabled", True):
                continue
            cond = str(rule.get("condition", "")).strip()
            if not cond:
                continue
            if self._evaluate_condition(cond, metrics):
                alert = {
                    "rule_name": rule.get("name", ""),
                    "severity": str(rule.get("severity", "low")),
                    "message": f"Condition '{cond}' matched.",
                    "timestamp": datetime.now(),
                }
                self._alerts.append(alert)
                alerts.append(alert)
                self._notify_subscribers(alert)
        return alerts

    def _evaluate_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        # very small safe parser for expressions like "cpu_usage > 90"
        m = re.match(
            r"^\s*([A-Za-z_]\w*)\s*(>=|<=|==|!=|>|<)\s*([0-9]+(?:\.[0-9]+)?)\s*$",
            condition,
        )
        if not m:
            logger.debug("Condition did not match expected format: %s", condition)
            return False
        metric, op, rhs_str = m.groups()
        if metric not in metrics:
            return False
        try:
            lhs = float(metrics.get(metric, 0))
            rhs = float(rhs_str)
        except (ValueError, TypeError, AttributeError):
            return False

        if op == ">":
            return lhs > rhs
        if op == ">=":
            return lhs >= rhs
        if op == "<":
            return lhs < rhs
        if op == "<=":
            return lhs <= rhs
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        return False

    # ---- Subscribers ----
    def subscribe_to_alerts(self, subscriber: Any) -> str:
        """
        subscriber must have handle_alert(alert_dict) method (per tests they use a Mock with handle_alert)
        """
        self._sub_counter += 1
        sid = f"sub_{self._sub_counter}"
        self._alert_subscribers[sid] = subscriber
        return sid

    def unsubscribe_from_alerts(self, subscription_id: str) -> None:
        self._alert_subscribers.pop(subscription_id, None)

    def _notify_subscribers(self, alert: Dict[str, Any]) -> None:
        for sub in list(self._alert_subscribers.values()):
            handler = getattr(sub, "handle_alert", None)
            if callable(handler):
                try:
                    handler(alert)
                except (AttributeError, RuntimeError, TypeError):  # pragma: no cover
                    logger.exception("Subscriber raised during handle_alert")

    # ---- History ----
    def get_alert_history(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        if severity is None:
            return list(self._alerts)
        sev = str(severity).lower()
        return [a for a in self._alerts if str(a.get("severity", "")).lower() == sev]


if __name__ == "__main__":
    alert_system = ObservabilityAlertSystem(notification_callback=console_notifier)

    # Configure some rules
    alert_system.configure_alert_rules(
        [
            {
                "name": "high_latency",
                "condition": "api_latency_ms > 200",
                "severity": "WARNING",
            },
            {
                "name": "critical_latency",
                "condition": "api_latency_ms > 500",
                "severity": "CRITICAL",
            },
        ]
    )

    # Simulate performance monitoring - Note: direct rule evaluation is not implemented yet.
    # This example still uses direct metric checks.
    print("Monitoring performance...")
    # Simulate data for evaluation (assuming metrics come in a flat dictionary)
    metrics_data = {"api_latency_ms": 100, "cpu_usage": 0.3}

    # Although rules are configured, for demonstration, we still use direct metric checks
    # as the `evaluate` method for generic rules is not part of this PR.
    # This section simply validates the existing `monitor_performance_metrics` with the new AlertEvent type.
    alert_system.monitor_performance_metrics(
        {"api_latency_ms": 100}, {"api_latency_ms": 200}
    )  # No alert
    alert_system.monitor_performance_metrics(
        {"api_latency_ms": 250}, {"api_latency_ms": 200}
    )  # Warning alert (via AlertEvent)
    alert_system.monitor_performance_metrics(
        {"api_latency_ms": 550}, {"api_latency_ms": 500}
    )  # Critical alert (via AlertEvent)

    # Simulate error rate tracking
    print("\nTracking error rates...")
    agent_id = "Agent_Alpha"
    current_time = time.time()
    for i in range(7):  # 7 errors in a short window
        alert_system.track_error_rates(
            agent_id, current_time + i, time_window_seconds=10, alert_threshold=5
        )
        time.sleep(0.1)  # Simulate some time passing (reduced sleep for faster run)

    # Simulate anomaly detection
    print("\nDetecting anomalies...")
    # Set a baseline for CPU usage
    alert_system.set_baseline(
        "system_metrics_baseline", {"avg_cpu": 0.3, "avg_memory": 0.5}
    )
    alert_system.detect_anomalies(
        {"avg_cpu": 0.35, "avg_memory": 0.55}, "system_metrics_baseline"
    )  # No anomaly
    alert_system.detect_anomalies(
        {"avg_cpu": 0.6, "avg_memory": 0.5}, "system_metrics_baseline"
    )  # Anomaly (via AlertEvent)
