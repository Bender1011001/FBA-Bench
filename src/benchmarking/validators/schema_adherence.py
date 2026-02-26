from __future__ import annotations

"""
Schema adherence validator.

Key: "schema_adherence"

Validates run.output against a contract provided in context.

Contract format (simple, minimal-deps):
- context["contract"] = {
    "required": {
        "field_name": "type_name" | ["type_name1","type_name2"] | {"path":"nested.path","type":"type_name"}
        ...
    }
  }

Supported type_name values: "str","int","float","bool","list","dict","number"
- "number" accepts int or float
- For nested fields in dicts, you can specify required entries either as:
  - "details.score": "number" (using dot in key)
  - {"path":"details.score","type":"number"}

Behavior:
- Missing fields -> error
- Type mismatch -> error
- Produces info-level summary counts

Deterministic and non-fatal.
"""

from typing import Any, Dict, List, Optional, Tuple, Union  # noqa: E402

from .registry import register_validator  # noqa: E402
from .types import Issue, ValidationOutput, normalize_output  # noqa: E402

_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "number": (int, float),
}


def _get_nested(d: Dict[str, Any], path: str) -> Tuple[bool, Any]:
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _requirements_from_contract(
    contract: Dict[str, Any],
) -> List[Tuple[str, Union[type, Tuple[type, ...]]]]:
    out: List[Tuple[str, Union[type, Tuple[type, ...]]]] = []
    if not isinstance(contract, dict):
        return out
    req = contract.get("required") or {}
    if not isinstance(req, dict):
        return out
    for key, spec in req.items():
        path: Optional[str] = None
        typespec: Optional[Union[type, Tuple[type, ...]]] = None
        if isinstance(spec, str):
            path = key
            typespec = _TYPE_MAP.get(spec)  # type: ignore[assignment]
        elif isinstance(spec, list):
            # list of type names
            resolved = tuple(_TYPE_MAP.get(s) for s in spec if s in _TYPE_MAP)
            if resolved:
                path = key
                typespec = resolved  # type: ignore
        elif isinstance(spec, dict):
            path = spec.get("path") or key
            tname = spec.get("type")
            typespec = _TYPE_MAP.get(tname) if isinstance(tname, str) else None  # type: ignore[assignment]
        else:
            continue
        if path and typespec:
            out.append((path, typespec))
    return out


def schema_adherence_validate(
    report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx = context or {}
    contract = ctx.get("contract") or {}
    out = ValidationOutput()

    runs = report.get("runs") or []
    total_checked = 0
    violations = 0

    requirements = _requirements_from_contract(contract)

    for idx, run in enumerate(runs):
        if not isinstance(run, dict) or run.get("status") != "success":
            continue
        output = run.get("output")
        if not isinstance(output, dict):
            out.add_issue(
                Issue(
                    id="missing_output",
                    severity="error",
                    message=f"Run[{idx}] has non-dict output; cannot validate schema",
                    path=["runs", str(idx), "output"],
                )
            )
            violations += 1
            continue

        for path, tp in requirements:
            total_checked += 1
            ok, val = _get_nested(output, path)
            if not ok:
                violations += 1
                out.add_issue(
                    Issue(
                        id="schema_missing_field",
                        severity="error",
                        message=f"Run[{idx}] missing required output field '{path}'",
                        path=["runs", str(idx), "output", *path.split(".")],
                    )
                )
                continue
            # type check
            if isinstance(tp, tuple):
                if not isinstance(val, tp):
                    violations += 1
                    out.add_issue(
                        Issue(
                            id="schema_type_mismatch",
                            severity="error",
                            message=f"Run[{idx}] output.{path} type mismatch: got {type(val).__name__}",
                            path=["runs", str(idx), "output", *path.split(".")],
                        )
                    )
            else:
                if not isinstance(val, tp):
                    violations += 1
                    out.add_issue(
                        Issue(
                            id="schema_type_mismatch",
                            severity="error",
                            message=f"Run[{idx}] output.{path} type mismatch: expected {tp.__name__}, got {type(val).__name__}",
                            path=["runs", str(idx), "output", *path.split(".")],
                        )
                    )

    out.summary.details.update(
        {
            "required_fields": [p for p, _ in requirements],
            "total_checked": total_checked,
            "violations": violations,
        }
    )
    return normalize_output(out)


register_validator("schema_adherence", schema_adherence_validate)
