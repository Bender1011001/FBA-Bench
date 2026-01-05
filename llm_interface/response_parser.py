"""LLM Response Parser for converting model outputs to domain actions."""
import json
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class LLMResponseParser:
    """Parses LLM responses into structured actions for the simulation."""

    def __init__(self):
        """Initialize parser (can add trust metrics later if needed)."""
        pass

    def parse_and_validate(
        self, content: str, agent_id: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Parse and validate LLM response content.

        Args:
            content: Raw LLM response text (should be JSON)
            agent_id: Optional agent ID for tracking

        Returns:
            Tuple of (parsed_json_dict, error_message)
            parsed_json_dict contains {"actions": [...]}, error_message is None on success
        """
        try:
            # Try to parse as JSON
            parsed = json.loads(content)

            # Validate structure
            if isinstance(parsed, dict):
                # Expected format: {"actions": [...]}
                if "actions" in parsed:
                    actions = parsed["actions"]
                    if isinstance(actions, list):
                        return (parsed, None)
                    else:
                        logger.warning(f"Actions is not a list: {type(actions)}")
                        return ({"actions": []}, "Invalid actions format")
                else:
                    # Try to extract actions from other formats
                    logger.warning("No 'actions' key in response, returning empty actions")
                    return ({"actions": []}, None)
            else:
                logger.warning(f"Response is not a dict: {type(parsed)}")
                return ({"actions": []}, "Response not a dictionary")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return ({"actions": []}, f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return ({"actions": []}, f"Parse error: {e}")
