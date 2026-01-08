"""
Comprehensive Error Handling and Logging System for FBA-Bench.

This module provides a centralized error handling and logging system
that ensures robust error management and detailed logging throughout
the FBA-Bench application.
"""

import json
import logging
import sys
import threading
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from benchmarking.registry.global_variables import global_variables

# Set up logger
logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categories for errors."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    INTEGRATION = "integration"
    EXECUTION = "execution"
    NETWORK = "network"
    DATABASE = "database"
    EXTERNAL_SERVICE = "external_service"
    AGENT = "agent"
    SCENARIO = "scenario"
    METRIC = "metric"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for an error."""

    component: str
    operation: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ErrorDetails:
    """Detailed information about an error."""

    error_id: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    stack_trace: Optional[str] = None
    cause: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result["severity"] = self.severity.value
        result["category"] = self.category.value
        result["context"] = self.context.to_dict()
        result["timestamp"] = self.timestamp.isoformat()
        return result


class ErrorHandler:
    """
    Centralized error handler for FBA-Bench.

    This class provides comprehensive error handling, logging, and recovery
    mechanisms for all components of the system.
    """

    def __init__(self):
        """Initialize the error handler."""
        self.error_history: List[ErrorDetails] = []
        self.error_callbacks: Dict[str, List[Callable]] = {}
        self.error_stats: Dict[str, Dict[str, int]] = {}
        self.lock = threading.Lock()
        self.max_history_size = 1000

        # Set up logging
        self._setup_logging()

        logger.info("ErrorHandler initialized")

    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        # Create logs directory if it doesn't exist
        logs_dir = Path(global_variables.paths.logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, global_variables.system.log_level.value))

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create formatter
        formatter = logging.Formatter(global_variables.system.log_format)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler
        if global_variables.system.log_file:
            file_handler = logging.FileHandler(global_variables.system.log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        else:
            # Default log file
            log_file = logs_dir / "fba_bench.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        # Error log file
        error_log_file = logs_dir / "fba_bench_errors.log"
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

        logger.info("Logging system configured")

    def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        suggestions: List[str] = None,
        reraise: bool = False,
    ) -> ErrorDetails:
        """
        Handle an error.

        Args:
            error: The exception that occurred
            context: Context information about the error
            severity: Error severity level
            category: Error category
            suggestions: Suggested recovery actions
            reraise: Whether to reraise the exception

        Returns:
            ErrorDetails object with information about the error
        """
        # Create error details
        error_details = ErrorDetails(
            error_id=self._generate_error_id(),
            error_type=type(error).__name__,
            error_message=str(error),
            severity=severity,
            category=category,
            context=context,
            stack_trace=traceback.format_exc(),
            cause=str(error.__cause__) if error.__cause__ else None,
            suggestions=suggestions or [],
        )

        # Add to history
        with self.lock:
            self.error_history.append(error_details)

            # Limit history size
            if len(self.error_history) > self.max_history_size:
                self.error_history = self.error_history[-self.max_history_size :]

            # Update statistics
            self._update_error_stats(error_details)

        # Log the error
        self._log_error(error_details)

        # Trigger callbacks
        self._trigger_error_callbacks(error_details)

        # Reraise if requested
        if reraise:
            raise error

        return error_details

    def _generate_error_id(self) -> str:
        """Generate a unique error ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(hash(threading.get_ident()) % 10000).zfill(4)
        return f"ERR_{timestamp}_{random_suffix}"

    def _update_error_stats(self, error_details: ErrorDetails) -> None:
        """Update error statistics."""
        category = error_details.category.value
        severity = error_details.severity.value

        if category not in self.error_stats:
            self.error_stats[category] = {}

        if severity not in self.error_stats[category]:
            self.error_stats[category][severity] = 0

        self.error_stats[category][severity] += 1

    def _log_error(self, error_details: ErrorDetails) -> None:
        """Log an error."""
        # Create log message
        log_message = (
            f"[{error_details.error_id}] "
            f"{error_details.severity.value.upper()} "
            f"in {error_details.context.component}.{error_details.context.operation}: "
            f"{error_details.error_message}"
        )

        # Log with appropriate level
        if error_details.severity == ErrorSeverity.DEBUG:
            logger.debug(log_message)
        elif error_details.severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif error_details.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif error_details.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif error_details.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)

        # Log detailed error information
        detailed_log = json.dumps(error_details.to_dict(), indent=2, default=str)
        logger.debug(f"Error details:\n{detailed_log}")

    def _trigger_error_callbacks(self, error_details: ErrorDetails) -> None:
        """Trigger error callbacks."""
        # Trigger general error callbacks
        for callback in self.error_callbacks.get("error", []):
            try:
                callback(error_details)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

        # Trigger category-specific callbacks
        category = error_details.category.value
        for callback in self.error_callbacks.get(f"error_{category}", []):
            try:
                callback(error_details)
            except Exception as e:
                logger.error(f"Error in category-specific error callback: {e}")

    def register_error_callback(self, callback_type: str, callback: Callable) -> None:
        """
        Register an error callback.

        Args:
            callback_type: Type of callback ("error" or "error_{category}")
            callback: Callback function
        """
        if callback_type not in self.error_callbacks:
            self.error_callbacks[callback_type] = []

        self.error_callbacks[callback_type].append(callback)
        logger.debug(f"Registered error callback: {callback_type}")

    def get_error_history(
        self,
        limit: Optional[int] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        component: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[ErrorDetails]:
        """
        Get error history with optional filtering.

        Args:
            limit: Maximum number of errors to return
            severity: Filter by severity
            category: Filter by category
            component: Filter by component
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of error details
        """
        with self.lock:
            errors = self.error_history.copy()

        # Apply filters
        if severity:
            errors = [e for e in errors if e.severity == severity]

        if category:
            errors = [e for e in errors if e.category == category]

        if component:
            errors = [e for e in errors if e.context.component == component]

        if start_time:
            errors = [e for e in errors if e.timestamp >= start_time]

        if end_time:
            errors = [e for e in errors if e.timestamp <= end_time]

        # Sort by timestamp (newest first)
        errors.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit
        if limit:
            errors = errors[:limit]

        return errors

    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics.

        Returns:
            Dictionary with error statistics
        """
        with self.lock:
            stats = self.error_stats.copy()

        # Calculate totals
        total_errors = sum(
            sum(severity_counts.values()) for severity_counts in stats.values()
        )

        return {
            "total_errors": total_errors,
            "by_category": stats,
            "by_severity": self._get_stats_by_severity(),
            "recent_errors": len(
                [
                    e
                    for e in self.error_history
                    if (datetime.now() - e.timestamp).total_seconds()
                    < 3600  # Last hour
                ]
            ),
        }

    def _get_stats_by_severity(self) -> Dict[str, int]:
        """Get error statistics grouped by severity."""
        stats = {}

        for severity in ErrorSeverity:
            stats[severity.value] = sum(
                severity_counts.get(severity.value, 0)
                for severity_counts in self.error_stats.values()
            )

        return stats

    def clear_error_history(self) -> None:
        """Clear error history."""
        with self.lock:
            self.error_history.clear()
            self.error_stats.clear()

        logger.info("Error history cleared")

    def export_error_history(self, file_path: str) -> None:
        """
        Export error history to a file.

        Args:
            file_path: Path to the output file
        """
        with self.lock:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_errors": len(self.error_history),
                "statistics": self.get_error_statistics(),
                "errors": [error.to_dict() for error in self.error_history],
            }

        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Error history exported to {file_path}")

    def get_error_suggestions(
        self, error_type: str, category: ErrorCategory
    ) -> List[str]:
        """
        Get suggestions for handling a specific type of error.

        Args:
            error_type: Type of error
            category: Error category

        Returns:
            List of suggestions
        """
        suggestions = []

        # Common suggestions based on category
        if category == ErrorCategory.VALIDATION:
            suggestions.extend(
                [
                    "Check input data format and values",
                    "Verify all required fields are provided",
                    "Ensure data types match expected types",
                ]
            )
        elif category == ErrorCategory.CONFIGURATION:
            suggestions.extend(
                [
                    "Verify configuration file format",
                    "Check for missing or invalid configuration values",
                    "Ensure configuration matches environment requirements",
                ]
            )
        elif category == ErrorCategory.INTEGRATION:
            suggestions.extend(
                [
                    "Check if all required services are running",
                    "Verify network connectivity",
                    "Check authentication credentials",
                ]
            )
        elif category == ErrorCategory.EXECUTION:
            suggestions.extend(
                [
                    "Check for sufficient system resources",
                    "Verify execution parameters",
                    "Review execution logs for more details",
                ]
            )
        elif category == ErrorCategory.NETWORK:
            suggestions.extend(
                [
                    "Check network connectivity",
                    "Verify service endpoints are accessible",
                    "Check firewall and proxy settings",
                ]
            )
        elif category == ErrorCategory.DATABASE:
            suggestions.extend(
                [
                    "Check database connection",
                    "Verify database permissions",
                    "Check for database locks or deadlocks",
                ]
            )
        elif category == ErrorCategory.EXTERNAL_SERVICE:
            suggestions.extend(
                [
                    "Check external service status",
                    "Verify API credentials",
                    "Check rate limits and quotas",
                ]
            )

        # Type-specific suggestions
        if "Timeout" in error_type:
            suggestions.extend(
                [
                    "Increase timeout values",
                    "Check for network latency",
                    "Consider implementing retry logic",
                ]
            )
        elif "Connection" in error_type:
            suggestions.extend(
                [
                    "Check network connectivity",
                    "Verify service availability",
                    "Check firewall settings",
                ]
            )
        elif "Authentication" in error_type or "Auth" in error_type:
            suggestions.extend(
                [
                    "Verify credentials",
                    "Check authentication token validity",
                    "Ensure proper permissions",
                ]
            )

        return suggestions


def handle_errors(
    component: str,
    operation: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    reraise: bool = False,
    suggestions: List[str] = None,
):
    """
    Decorator for handling errors in functions.

    Args:
        component: Component name
        operation: Operation name
        severity: Error severity
        category: Error category
        reraise: Whether to reraise exceptions
        suggestions: Suggested recovery actions
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create error context
            context = ErrorContext(
                component=component,
                operation=operation,
                parameters={"args": str(args), "kwargs": str(kwargs)},
            )

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Handle the error
                error_handler.handle_error(
                    error=e,
                    context=context,
                    severity=severity,
                    category=category,
                    suggestions=suggestions,
                    reraise=reraise,
                )

                # Return None if not reraising
                if not reraise:
                    return None

        return wrapper

    return decorator


def log_function_calls(
    component: str,
    operation: str,
    log_level: int = logging.DEBUG,
    log_args: bool = True,
    log_result: bool = True,
):
    """
    Decorator for logging function calls.

    Args:
        component: Component name
        operation: Operation name
        log_level: Logging level
        log_args: Whether to log function arguments
        log_result: Whether to log function result
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create log message
            message = f"[{component}] {operation}"

            if log_args:
                message += f" args={args} kwargs={kwargs}"

            # Log function call
            logger.log(log_level, f"CALL: {message}")

            try:
                # Call function
                result = func(*args, **kwargs)

                # Log result
                if log_result:
                    logger.log(log_level, f"RESULT: {message} -> {result}")

                return result
            except Exception as e:
                # Log exception
                logger.log(log_level, f"EXCEPTION: {message} -> {e}")
                raise

        return wrapper

    return decorator


# Global instance of the error handler
error_handler = ErrorHandler()
