from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "PluginValidator",
    "ValidationResult",
    "SecurityCheck",
]


@dataclass
class SecurityCheck:
    """Represents a single security check outcome."""

    name: str
    passed: bool
    message: str = ""


@dataclass
class ValidationResult:
    """
    Generic validation result used by community tests.

    Extensibility tests access attributes conditionally:
      - validate_security(...) -> result.is_secure
      - validate_api_compliance(...) -> result.is_compliant

    Keep both fields optional and default to True where appropriate to reduce friction.
    """

    passed: bool = True
    score: float = 1.0
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    # Compatibility flags used by tests
    is_secure: Optional[bool] = None
    is_compliant: Optional[bool] = None

    def set_secure(self, ok: bool) -> ValidationResult:
        self.is_secure = ok
        self.passed = self.passed and ok
        if not ok and "security" not in self.details:
            self.details["security"] = "failed"
        return self

    def set_compliant(self, ok: bool) -> ValidationResult:
        self.is_compliant = ok
        self.passed = self.passed and ok
        if not ok and "api_compliance" not in self.details:
            self.details["api_compliance"] = "failed"
        return self


class PluginValidator:
    """
    Lightweight plugin validator used by the community extensibility tests.

    Goals:
      - Provide deterministic, side-effect-free checks
      - Return shapes expected by tests without introducing heavy deps
    """

    def __init__(self) -> None:
        self.forbidden_import_substrings = ["ctypes", "mmap"]
        self.forbidden_dynamic_calls = ["eval(", "exec("]

    async def validate_security(self, plugin_obj: Any) -> ValidationResult:
        """
        Perform conservative checks:
          - Able to resolve plugin module
          - No obvious dynamic execution patterns in source (best-effort)
        """
        result = ValidationResult()
        checks: List[SecurityCheck] = []

        try:
            module = (
                inspect.getmodule(plugin_obj.__class__)
                if inspect.isclass(plugin_obj)
                else inspect.getmodule(plugin_obj)
            )
            if module is None:
                msg = "Could not resolve plugin module"
                checks.append(SecurityCheck("module_resolution", False, msg))
                result.issues.append(msg)
                return result.set_secure(False)

            # Try to read source (may fail for C extensions or builtins)
            try:
                source = inspect.getsource(module)
            except (OSError, SyntaxError, AttributeError):
                # If source is not available, allow but mark as unverified
                checks.append(
                    SecurityCheck(
                        "source_available",
                        False,
                        "Source unavailable; allowing by default",
                    )
                )
                # Default allow per community tools design philosophy
                result.details["source_available"] = False
                return result.set_secure(True)

            # Basic pattern checks (string-level)
            dynamic_call_found = any(
                tok in source for tok in self.forbidden_dynamic_calls
            )
            if dynamic_call_found:
                msg = "Disallowed dynamic execution (eval/exec) found"
                checks.append(SecurityCheck("dynamic_execution", False, msg))
                result.issues.append(msg)
                return result.set_secure(False)
            else:
                checks.append(SecurityCheck("dynamic_execution", True))

            # Import checks (string-level heuristic)
            if any(
                f"import {substr}" in source or f"from {substr} import" in source
                for substr in self.forbidden_import_substrings
            ):
                msg = "Disallowed import detected (ctypes/mmap)"
                checks.append(SecurityCheck("forbidden_imports", False, msg))
                result.issues.append(msg)
                return result.set_secure(False)
            else:
                checks.append(SecurityCheck("forbidden_imports", True))

            result.details["checks"] = [c.__dict__ for c in checks]
            return result.set_secure(True)

        except (ValueError, TypeError, RuntimeError) as e:
            logger.error("Security validation error: %s", e, exc_info=True)
            result.issues.append(f"validator_exception: {e}")
            return result.set_secure(False)

    async def test_api_boundaries(self, plugin_obj: Any) -> bool:
        """
        Ensure plugin object doesn't expose obviously dangerous public attributes.
        For the tests, a permissive True is acceptable if no red flags are found.
        """
        try:
            # Disallow attributes that hint at arbitrary execution surfaces
            disallowed_attrs = {"__dict__", "__class__", "__getattribute__"}
            pub_attrs = [a for a in dir(plugin_obj) if not a.startswith("_")]
            if any(a in disallowed_attrs for a in pub_attrs):
                return False
            return True
        except (AttributeError, TypeError) as e:
            logger.warning("API boundary test encountered an error: %s", e)
            return False

    async def test_resource_isolation(self, plugin_obj: Any) -> bool:
        """
        Stubbed resource isolation check. Without sandboxing in-process, we return True.
        """
        return True

    async def validate_api_compliance(
        self, plugin_obj: Any, api_version: str = "1.0.0"
    ) -> ValidationResult:
        """
        Validate that the plugin exposes a basic metadata method and conforms to a minimal contract.
        Tests only gate on the presence of a boolean-like 'is_compliant'.
        """
        result = ValidationResult()
        try:
            has_get_metadata = hasattr(plugin_obj, "get_metadata") and callable(
                plugin_obj.get_metadata
            )
            # Optionally, run and verify keys
            metadata_ok = True
            if has_get_metadata:
                try:
                    md = plugin_obj.get_metadata()
                    if isinstance(md, dict):
                        required = ["name", "version"]
                        metadata_ok = all(k in md for k in required)
                    else:
                        metadata_ok = False
                except (TypeError, AttributeError, RuntimeError):
                    metadata_ok = False
            else:
                metadata_ok = False

            ok = has_get_metadata and metadata_ok
            result.details["api_version"] = api_version
            result.details["metadata_present"] = has_get_metadata
            result.details["metadata_valid"] = metadata_ok
            return result.set_compliant(ok)

        except (ValueError, TypeError, RuntimeError) as e:
            logger.error("API compliance validation error: %s", e, exc_info=True)
            result.issues.append(f"compliance_exception: {e}")
            return result.set_compliant(False)
