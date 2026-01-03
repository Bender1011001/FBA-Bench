import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from fba_events.bus import EventBus
from fba_events.llm import (
    LLMResponseErrorEvent,  # Assuming such an event exists or defining a new one
)
from llm_interface.schema_validator import LLM_RESPONSE_SCHEMA, validate_llm_response

logger = logging.getLogger(__name__)


class LLMResponseParser:
    """
    Parses and validates LLM responses, publishing events for schema violations and
    applying trust score penalties.
    """

    # Configurable penalty values
    JSON_PARSING_PENALTY: float = -0.1
    UNEXPECTED_PARSING_PENALTY: float = -0.15
    SCHEMA_VIOLATION_PENALTY: float = -0.05

    def __init__(self, event_bus: EventBus | Any):
        """
        Initialize the LLMResponseParser.
        
        Args:
            event_bus: An EventBus instance for publishing error events.
                       Can also accept a TrustMetrics-like object for backwards compatibility.
        """
        # Use duck typing to detect EventBus vs TrustMetrics
        if hasattr(event_bus, "publish") and callable(event_bus.publish):
            self.event_bus = event_bus
            self.trust_metrics = None
        else:
            # Backwards compatibility: trust_metrics-like object passed
            self.trust_metrics = event_bus

            # Provide a minimal event_bus with async publish for compatibility
            class _DummyBus:
                async def publish(self, *args, **kwargs):
                    return None

            self.event_bus = _DummyBus()

        self.LLM_RESPONSE_SCHEMA = LLM_RESPONSE_SCHEMA  # Expose for reference

    async def parse_and_validate(
        self, raw_llm_response: str, agent_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Parses the raw LLM string response into JSON and validates it against the schema.
        Publishes events for trust score penalties for invalid responses.

        Args:
            raw_llm_response: The raw string response received from the LLM.
            agent_id: The ID of the agent that generated this response, for logging/penalties.

        Returns:
            A tuple: (parsed_json, error_details).
            parsed_json will be the validated dictionary if successful, None otherwise.
            error_details will be a dictionary with error info if invalid, None otherwise.
        """
        parsed_json = None
        error_details = None

        try:
            # Attempt to parse the raw response as JSON
            parsed_json = json.loads(raw_llm_response)
        except json.JSONDecodeError as e:
            # Redact raw_llm_response content for security
            redacted_response = (
                raw_llm_response[:200] + "..."
                if len(raw_llm_response) > 200
                else raw_llm_response
            )
            error_message = f"Malformed JSON response: {e.msg}. Response snippet: {redacted_response}"
            error_details = {
                "error_type": "JSONParsingError",
                "message": error_message,
                "suggested_fix": "Ensure the entire response is a single, valid JSON object.",
                "trust_score_penalty": self.JSON_PARSING_PENALTY,
                "parsing_error": str(e),
            }
            logger.error(f"[{agent_id}] JSON Parsing Error: {error_details['message']}")
            await self._publish_llm_error(agent_id, error_details)
            return None, error_details
        except (TypeError, AttributeError, ValueError) as e:
            # Redact raw_llm_response content for security
            redacted_response = (
                raw_llm_response[:200] + "..."
                if len(raw_llm_response) > 200
                else raw_llm_response
            )
            error_message = f"An unexpected error occurred during JSON parsing: {e!s}. Response snippet: {redacted_response}"
            error_details = {
                "error_type": "UnexpectedParsingError",
                "message": error_message,
                "suggested_fix": "Review the LLM's raw output for unexpected characters or formatting.",
                "trust_score_penalty": self.UNEXPECTED_PARSING_PENALTY,
                "parsing_error": str(e),
            }
            logger.error(
                f"[{agent_id}] Unexpected Parsing Error: {error_details['message']}"
            )
            await self._publish_llm_error(agent_id, error_details)
            return None, error_details

        # If JSON parsing was successful, validate against the schema
        is_valid, validation_error_info = validate_llm_response(parsed_json)

        if not is_valid:
            # Check if this is a nested parameters issue and try to fix it
            if isinstance(parsed_json, dict) and "actions" in parsed_json:
                actions = parsed_json.get("actions", [])
                if isinstance(actions, list):
                    for action in actions:
                        if isinstance(action, dict) and "parameters" in action:
                            params = action.get("parameters", {})
                            if isinstance(params, dict):
                                # Merge parameters into the action object
                                action.update(params)
                                del action["parameters"]

                    # Re-validate after fix
                    is_valid, validation_error_info = validate_llm_response(parsed_json)

        # Special-case: treat "actions must be non-empty" as a soft condition (no penalty)
        if not is_valid:
            try:
                msg = str(validation_error_info.get("message", ""))
            except (AttributeError, TypeError):
                msg = ""
            path_str = ""
            try:
                path_str = str(validation_error_info.get("path", "") or "")
            except (AttributeError, TypeError):
                path_str = ""
            if "should be non-empty" in msg and (
                "actions" in msg or "actions" in path_str
            ):
                logger.info(
                    f"[{agent_id}] LLM response parsed; empty actions allowed without penalty."
                )
                return parsed_json, None

            error_message = f"LLM response failed schema validation: {validation_error_info.get('message', 'N/A')}"
            error_details = {
                "error_type": "SchemaViolation",
                "message": error_message,
                "path": validation_error_info.get("path", "N/A"),
                "invalid_value": validation_error_info.get("invalid_value", "N/A"),
                "suggested_fix": validation_error_info.get(
                    "suggested_fix", "Review schema documentation."
                ),
                "trust_score_penalty": self.SCHEMA_VIOLATION_PENALTY,
                "validation_details": validation_error_info,  # Full original validation error details
            }
            logger.warning(
                f"[{agent_id}] Schema Violation: {error_details['message']} at {error_details['path']}. Value: {error_details['invalid_value']}"
            )
            await self._publish_llm_error(agent_id, error_details)
            return None, error_details

        logger.info(f"[{agent_id}] LLM response successfully parsed and validated.")
        return parsed_json, None

    async def _publish_llm_error(self, agent_id: str, error_details: Dict[str, Any]):
        """
        Publishes an LLMResponseErrorEvent to the event bus and applies optional trust penalty.
        """
        # If a TrustMetrics-like object is attached, apply penalty (non-fatal best-effort)
        try:
            tm = getattr(self, "trust_metrics", None)
            if tm is not None:
                penalty = float(error_details.get("trust_score_penalty", 0.0) or 0.0)
                apply = getattr(tm, "apply_penalty", None)
                if callable(apply):
                    # Common expected signature: apply_penalty(agent_id, penalty_value)
                    apply(
                        agent_id, penalty
                    )  # intentionally sync; tests often patch to assert calls
        except (AttributeError, TypeError, ValueError):
            # Do not allow trust penalty path to interfere with event publishing
            logger.debug(
                "LLMResponseParser: trust_metrics penalty application skipped due to error"
            )

        event = LLMResponseErrorEvent(
            agent_id=agent_id,
            error_type=error_details["error_type"],
            message=error_details["message"],
            severity=(
                "Critical"
                if error_details["error_type"]
                in ["JSONParsingError", "UnexpectedParsingError"]
                else "Warning"
            ),
            details=error_details,
        )
        # Be defensive: event_bus in tests may be a stub without publish()
        try:
            publish = getattr(self.event_bus, "publish", None)
            if callable(publish):
                await publish(event)  # type: ignore[misc]
        except (AttributeError, TypeError, RuntimeError, asyncio.CancelledError):
            # Logging only; do not break caller flows when event bus is a mock
            logger.debug("LLMResponseParser: event_bus publish skipped due to error")
        logger.info(f"[{agent_id}] Published LLMResponseErrorEvent: {event.message}")
