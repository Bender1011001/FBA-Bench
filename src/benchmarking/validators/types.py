from __future__ import annotations

"""
Typed interfaces and schemas for validator inputs/outputs.

This module defines:
- Pydantic v2 models for normalized validator outputs
- Callable protocol for function-style validators
- Helper utilities for safe type parsing and normalization
"""

from typing import Any, Dict, List, Optional, Protocol, Union  # noqa: E402

from pydantic import BaseModel, Field, field_validator  # noqa: E402


class Issue(BaseModel):
    id: str = Field(
        ..., description="Stable identifier for the issue type, e.g., 'missing_field'"
    )
    severity: str = Field(..., description="info|warning|error")
    message: str = Field(..., description="Human-readable description of the issue")
    path: Optional[List[str]] = Field(
        default=None, description="Path within the report payload (JSON pointer-ish)"
    )

    @field_validator("severity")
    @classmethod
    def _severity_valid(cls, v: str) -> str:
        allowed = {"info", "warning", "error"}
        if v not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v


class ValidationSummary(BaseModel):
    count: int = Field(default=0, description="Total issues count")
    by_severity: Dict[str, int] = Field(
        default_factory=dict, description="Counts by severity"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Validator-specific summary fields"
    )


class ValidationOutput(BaseModel):
    issues: List[Issue] = Field(default_factory=list)
    summary: ValidationSummary = Field(default_factory=ValidationSummary)

    def add_issue(self, issue: Issue) -> None:
        self.issues.append(issue)
        self.summary.count += 1
        sev = issue.severity
        self.summary.by_severity[sev] = self.summary.by_severity.get(sev, 0) + 1


class ValidatorCallable(Protocol):
    def __call__(
        self, report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]: ...


def normalize_output(obj: Union[ValidationOutput, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert a ValidationOutput or a plain dict into normalized dict with keys:
      {"issues": list[dict], "summary": dict}
    """
    if isinstance(obj, ValidationOutput):
        return {
            "issues": [i.model_dump() for i in obj.issues],
            "summary": obj.summary.model_dump(),
        }
    if isinstance(obj, dict):
        # Ensure keys exist with safe defaults
        issues = obj.get("issues", [])
        summary = obj.get("summary", {})
        return {
            "issues": list(issues),
            "summary": dict(summary),
        }
    raise TypeError("Validator outputs must be ValidationOutput or dict")
