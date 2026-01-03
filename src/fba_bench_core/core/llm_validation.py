from __future__ import annotations

"""
Validation utilities for LLM outputs defined in fba_bench.core.llm_outputs.

Features:
- Pydantic v2-based strict and non-strict validation for defined contracts
- JSON parsing and safe, optional loose type coercions in non-strict mode
- JSON Schema export via Pydantic's model_json_schema()
- Optional jsonschema-based validation path for strict external schema checks
- Centralized logging of validation outcomes using the project's logging utilities
- Convenience mapping from contract names to concrete models

Public API:
- get_schema(model)
- validate_output(model, payload, strict=True)
- validate_with_jsonschema(schema, payload)
- validate_by_name(contract, payload, strict=True)
- CONTRACT_REGISTRY
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from fba_bench.core.llm_outputs import AgentResponse, FbaDecision, TaskPlan, ToolCall
from fba_bench.core.logging import (
    setup_logging,
)  # Ensure consistent formatting/handlers
from pydantic import BaseModel, ConfigDict, ValidationError

# Initialize logging (idempotent)
setup_logging()
logger = logging.getLogger(__name__)


# ---- Contract Registry -------------------------------------------------------

CONTRACT_REGISTRY: Dict[str, Type[BaseModel]] = {
    "fba_decision": FbaDecision,
    "task_plan": TaskPlan,
    "tool_call": ToolCall,
    "agent_response": AgentResponse,
}


# ---- Helpers ----------------------------------------------------------------


def _truncate_payload_for_log(
    payload: Union[str, bytes, Dict[str, Any]], limit: int = 600
) -> str:
    try:
        if isinstance(payload, (str, bytes)):
            s = (
                payload.decode("utf-8", errors="replace")
                if isinstance(payload, bytes)
                else payload
            )
            return (s[:limit] + "...") if len(s) > limit else s
        # dict-like
        s = json.dumps(payload, ensure_ascii=False)
        return (s[:limit] + "...") if len(s) > limit else s
    except (TypeError, ValueError, AttributeError):
        return "<unserializable payload>"


def _parse_payload(payload: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, bytes):
        try:
            return json.loads(payload.decode("utf-8", errors="replace"))
        except Exception as e:
            raise ValueError(f"Failed to parse bytes payload to JSON: {e}") from e
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception as e:
            raise ValueError(f"Failed to parse string payload to JSON: {e}") from e
    raise TypeError(f"Unsupported payload type: {type(payload).__name__}")


def coerce_loose_types(obj: Any) -> Any:
    """
    Best-effort, safe coercions for non-strict mode:
    - "123" -> 123 when used as numeric
    - "123.45" -> 123.45
    - "true"/"false" -> True/False (case-insensitive) if unambiguous
    - Trim whitespace around strings
    This is applied generically; Pydantic will still perform type validation.
    """
    if isinstance(obj, dict):
        return {k: coerce_loose_types(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [coerce_loose_types(v) for v in obj]
    if isinstance(obj, str):
        s = obj.strip()
        # boolean
        low = s.lower()
        if low in ("true", "false"):
            return low == "true"
        # int
        try:
            if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
                return int(s)
        except (TypeError, ValueError):
            pass
        # float
        try:
            # Reject if it contains non-numeric except one dot / leading sign
            f = float(s)
            return f
        except (TypeError, ValueError):
            return s
    return obj


def _sanitize_reserved_keys(obj: Any) -> Any:
    """
    Recursively rename reserved Pydantic v2 keys that would crash validation, e.g., 'model_config'.
    We map 'model_config' -> '__model_cfg__' at any nesting depth.
    This is a pre-parse sanitation step and preserves strict-mode semantics:
    such fields will be considered 'extra' unless explicitly modeled.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            nk = "__model_cfg__" if k == "model_config" else k
            sanitized[nk] = _sanitize_reserved_keys(v)
        return sanitized
    if isinstance(obj, list):
        return [_sanitize_reserved_keys(v) for v in obj]
    return obj


def _build_model_variant(base: Type[BaseModel], *, strict: bool) -> Type[BaseModel]:
    """
    Build a model subclass with adjusted model_config:
    - strict=True: no coercions, forbid extra
    - strict=False: allow coercions, ignore extra (strip unknowns)
    Implemented via dynamic subclass creation to avoid Pydantic creating
    an annotation for 'model_config' which can trigger reserved-name errors.
    """
    cfg = ConfigDict(strict=strict, extra="forbid" if strict else "ignore")
    name = f"{base.__name__}{'Strict' if strict else 'Lax'}"
    # Create subclass via `type(...)` and set model_config directly to avoid
    # putting 'model_config' into __annotations__.
    subclass = type(
        name,
        (base,),
        {
            "model_config": cfg,
            "__module__": getattr(base, "__module__", __name__),
        },
    )
    return cast(Type[BaseModel], subclass)


def _normalize_pydantic_errors(e: ValidationError) -> List[Dict[str, Any]]:
    errs: List[Dict[str, Any]] = []
    for err in e.errors():
        loc = "/".join(str(p) for p in err.get("loc", []))
        errs.append(
            {
                "loc": loc,
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
                "input": err.get("input", None),
                "ctx": err.get("ctx", None),
            }
        )
    return errs


def _find_extra_fields(input_obj: Any, dumped_obj: Any, path: str = "") -> List[str]:
    """
    Recursively detect keys present in the raw input that are not present in the
    Pydantic model dump. Returns list of paths to extra fields.

    This is used in strict mode to flag unknown/extra fields that nested models
    might otherwise accept due to dynamic subclassing limitations.
    """
    extras: List[str] = []

    if isinstance(input_obj, dict):
        if not isinstance(dumped_obj, dict):
            # If the model dumped a non-dict for this path, everything under input is extra
            for k in input_obj.keys():
                extras.append(f"{path}/{k}" if path else k)
            return extras
        for k, v in input_obj.items():
            if k not in dumped_obj:
                extras.append(f"{path}/{k}" if path else k)
            else:
                extras.extend(
                    _find_extra_fields(
                        v, dumped_obj.get(k), f"{path}/{k}" if path else k
                    )
                )
    elif isinstance(input_obj, list):
        # Compare list items pairwise where possible
        if not isinstance(dumped_obj, list):
            # Model dumped non-list - treat all items as extras under current path indices
            for i, _ in enumerate(input_obj):
                extras.append(f"{path}[{i}]")
            return extras
        for i, item in enumerate(input_obj):
            if i < len(dumped_obj):
                extras.extend(_find_extra_fields(item, dumped_obj[i], f"{path}[{i}]"))
            else:
                extras.append(f"{path}[{i}]")
    # primitives produce no extras by themselves
    return extras


# ---- Public API --------------------------------------------------------------


def get_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Return the JSON Schema for the provided Pydantic model.
    """
    try:
        schema = model.model_json_schema()
        return schema
    except Exception as e:
        logger.exception("Failed generating schema for model=%s: %s", model.__name__, e)
        raise


def validate_output(
    model: Type[BaseModel],
    payload: Union[str, bytes, Dict[str, Any]],
    strict: bool = True,
) -> Tuple[bool, Optional[BaseModel], List[Dict[str, Any]]]:
    """
    Validate the given payload (JSON string/bytes/dict) against the provided model.
    Behavior depends on 'strict':
    - strict=True: extra fields forbidden; type coercions disabled; exact type matching required
    - strict=False: extra fields ignored/stripped; safe coercions attempted

    Returns: (ok, instance_or_none, errors)
    """
    truncated = _truncate_payload_for_log(payload)
    try:
        data = _parse_payload(payload)
    except Exception as e:
        error = {"loc": "root", "msg": str(e), "type": "json_parse_error"}
        logger.error(
            "LLM output parse failure for model=%s | errors=1 | payload=%s",
            model.__name__,
            truncated,
        )
        return False, None, [error]

    # Sanitize reserved keys like 'model_config' to avoid Pydantic v2 conflicts
    data = _sanitize_reserved_keys(data)

    if not strict:
        data = coerce_loose_types(data)

    variant = _build_model_variant(model, strict=strict)
    try:
        # First perform Pydantic model validation (this will enforce types)
        instance = variant.model_validate(data)
        logger.debug(
            "LLM output validated successfully for model=%s | strict=%s",
            model.__name__,
            strict,
        )

        # In strict mode, perform two additional checks:
        # 1) Compare original input to model_dump to detect unknown extra fields
        # 2) Validate against JSON Schema to catch nested additionalProperties cases
        if strict:
            # 1) Detect extra fields via recursive comparison
            dumped = instance.model_dump()
            extras = _find_extra_fields(data, dumped)
            if extras:
                errors = []
                for extra_path in extras:
                    errors.append(
                        {
                            "loc": extra_path,
                            "msg": f"extra field '{extra_path.split('/')[-1]}' not permitted in strict mode",
                            "type": "extra_forbidden",
                        }
                    )
                logger.warning(
                    "LLM output failed strict validation for model=%s | found %d extra fields | payload=%s",
                    model.__name__,
                    len(extras),
                    truncated,
                )
                return False, None, errors

            # 2) JSON Schema validation (if jsonschema available)
            schema = get_schema(variant)
            js_errors = validate_with_jsonschema(schema, data)
            # validate_with_jsonschema returns [] if valid, or a list of dicts describing errors
            if js_errors:
                errors = []
                for js_err in js_errors:
                    # Handle the case where jsonschema isn't installed (import sentinel)
                    if (
                        js_err.get("validator") == "import"
                        or js_err.get("validator") == "internal"
                    ):
                        # Log and treat as schema validation not available; don't fail strictly on import absence
                        logger.debug(
                            "jsonschema not available for strict validation; skipping schema enforcement for model=%s",
                            model.__name__,
                        )
                        errors = []
                        break
                    # Map typical jsonschema error shape to our normalized format
                    path = js_err.get("path", "root")
                    message = js_err.get(
                        "message", js_err.get("message", "Schema validation error")
                    )
                    validator = js_err.get("validator", "")
                    if validator == "additionalProperties":
                        errors.append(
                            {
                                "loc": path,
                                "msg": f"extra field '{str(path).split('/')[-1]}' not permitted in strict mode",
                                "type": "extra_forbidden",
                            }
                        )
                    else:
                        errors.append(
                            {
                                "loc": path,
                                "msg": message,
                                "type": "schema_error",
                            }
                        )
                if errors:
                    logger.warning(
                        "LLM output failed JSON schema validation in strict mode for model=%s | error_count=%d | payload=%s",
                        model.__name__,
                        len(errors),
                        truncated,
                    )
                    return False, None, errors

        # If we reached here, validation succeeded under the requested mode
        return True, instance, []
    except ValidationError as e:
        errors = _normalize_pydantic_errors(e)
        logger.warning(
            "LLM output validation failed for model=%s | strict=%s | error_count=%d | payload=%s",
            model.__name__,
            strict,
            len(errors),
            truncated,
        )
        return False, None, errors
    except (TypeError, AttributeError, RuntimeError, KeyError) as e:
        # Unexpected error
        err = {"loc": "root", "msg": str(e), "type": "internal_error"}
        logger.exception(
            "LLM output validation crashed for model=%s | strict=%s | payload=%s",
            model.__name__,
            strict,
            truncated,
        )
        return False, None, [err]


def validate_with_jsonschema(
    schema: Dict[str, Any], payload: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Validate payload using jsonschema. Returns a list of normalized errors:
    [{"path": "...", "message": "...", "validator": "..."}]. Empty list if valid.
    Guarded by try/except import to keep dependency optional.
    """
    try:
        from jsonschema import (
            ValidationError as JSValidationError,  # type: ignore
            validate as js_validate,  # type: ignore
        )
    except ImportError:
        # jsonschema isn't available; return a sentinel error letting caller decide
        return [
            {
                "path": "root",
                "message": "jsonschema library not available; install 'jsonschema' to enable strict validation",
                "validator": "import",
            }
        ]

    try:
        js_validate(instance=payload, schema=schema)
        return []
    except JSValidationError as e:  # pragma: no cover - depends on input
        path = "/".join(str(p) for p in list(e.path))
        return [
            {
                "path": path if path else "root",
                "message": e.message,
                "validator": getattr(e, "validator", "unknown"),
            }
        ]
    except Exception as e:  # pragma: no cover - unexpected
        return [{"path": "root", "message": str(e), "validator": "internal"}]


def validate_by_name(
    contract: str, payload: Union[str, bytes, Dict[str, Any]], strict: bool = True
) -> Tuple[bool, Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Convenience wrapper to validate by contract registry key.
    On success returns (True, model_dump(), []).
    On failure returns (False, None, errors).
    """
    model = CONTRACT_REGISTRY.get(contract)
    if model is None:
        err = {
            "loc": "contract",
            "msg": f"Unknown contract '{contract}'",
            "type": "unknown_contract",
        }
        logger.error("Unknown LLM contract requested: %s", contract)
        return False, None, [err]

    ok, instance, errors = validate_output(model, payload, strict=strict)
    if not ok or instance is None:
        return False, None, errors
    # Return sanitized dict
    return True, instance.model_dump(), []
