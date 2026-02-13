"""Agent Gateway for preprocessing/postprocessing LLM requests."""

import logging
from typing import Any, Dict, Optional

from .budget_enforcer import BudgetEnforcer
from .token_counter import TokenCounter

logger = logging.getLogger(__name__)


class AgentGateway:
    """
    Gateway for agent requests - handles preprocessing (budget injection)
    and postprocessing (usage tracking, event routing).
    """

    def __init__(
        self,
        budget_enforcer: Optional[BudgetEnforcer] = None,
        token_counter: Optional[TokenCounter] = None,
    ):
        """Initialize gateway with optional services."""
        self.budget_enforcer = budget_enforcer
        self.token_counter = token_counter or TokenCounter()

    async def preprocess_request(
        self,
        agent_id: str,
        prompt: str,
        action_type: str = "decide_action",
        model_name: str = "gpt-3.5-turbo",
    ) -> Dict[str, Any]:
        """
        Preprocess agent request before sending to LLM.
        Checks budget before allowing the request to proceed.

        Args:
            agent_id: The agent making the request
            prompt: The raw prompt
            action_type: Type of action being performed
            model_name: The target model name

        Returns:
            Dict with "modified_prompt" (str) and "can_proceed" (bool)
        """
        can_proceed = True
        if self.budget_enforcer:
            # Estimate tokens for the prompt
            tokens = self.token_counter.count_tokens(prompt, model=model_name).count
            # Check if agent can afford this call (roughly)
            can_proceed = self.budget_enforcer.can_afford(
                agent_id=agent_id,
                tool_name=action_type,
                estimated_tokens=tokens,
            )

        # In a real implementation, we could also inject budget status into the prompt here
        modified_prompt = prompt
        if self.budget_enforcer and getattr(
            self.budget_enforcer.config, "inject_budget_status", False
        ):
            status = self.budget_enforcer.format_budget_status_for_prompt()
            modified_prompt = f"{status}\n\n{prompt}"

        return {
            "modified_prompt": modified_prompt,
            "can_proceed": can_proceed,
        }

    async def postprocess_response(
        self,
        agent_id: str,
        action_type: str,
        raw_prompt: str,
        llm_response: str,
        model_name: str = "gpt-3.5-turbo",
    ) -> None:
        """
        Postprocess agent response after LLM call.
        Records actual usage in the budget enforcer.

        Args:
            agent_id: The agent that made the request
            action_type: Type of request (e.g., "decide_action")
            raw_prompt: The request that was sent
            llm_response: The response received
            model_name: The model used

        Returns:
            None
        """
        if self.budget_enforcer:
            # Count tokens for both prompt and response
            prompt_tokens = self.token_counter.count_tokens(
                raw_prompt, model=model_name
            ).count
            completion_tokens = self.token_counter.count_tokens(
                llm_response, model=model_name
            ).count

            # Use legacy cost if model-specific cost logic isn't here yet
            cost_rate = getattr(self.budget_enforcer, "_legacy", {}).get(
                "token_cost_per_1k", 0.01
            )
            cost_cents = int(
                self.token_counter.calculate_cost(
                    prompt_tokens + completion_tokens, cost_rate
                )
                * 100
            )

            await self.budget_enforcer.meter_api_call(
                agent_id=agent_id,
                tool_name=action_type,
                tokens_prompt=prompt_tokens,
                tokens_completion=completion_tokens,
                cost_cents=cost_cents,
            )

        logger.debug(
            f"AgentGateway postprocess: agent={agent_id}, "
            f"type={action_type}, response_len={len(llm_response)}"
        )

    async def process_tool_call(
        self,
        agent_id: str,
        tool_call: Any,
        world_store: Any,
        event_bus: Any,
    ) -> bool:
        """
        Process a tool call proposed by an agent.
        Placeholder for safety validation and command translation.

        Returns:
            bool: True if the tool call is allowed and processed.
        """
        # In a real system, we'd validate the tool_call against safety rules here.
        # e.g., if tool_call.name == "set_price" and tool_call.parameters["price"] < 0: return False

        logger.info(f"AgentGateway processing tool call for {agent_id}: {tool_call}")
        return True
