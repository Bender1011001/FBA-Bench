"""
Baseline Bot Factory for FBA-Bench.
Creates simple agent bots that use LLMBatcher for LLM decisions with dynamic model support.
"""

import asyncio
import logging
import os
import uuid
from typing import Any, Callable, Dict, List, Optional

from infrastructure.llm_batcher import LLMBatcher

logger = logging.getLogger(__name__)


class LLMBot:
    """
    Simple baseline bot that uses LLMBatcher for decision making.
    Delegates prompts to LLM via batcher; uses MODEL_SLUG env var for model.
    """

    def __init__(self, name: str, batcher: Optional[LLMBatcher] = None):
        self.name = name
        self.batcher = batcher or LLMBatcher()
        self.model = os.getenv("MODEL_SLUG", "openai/gpt-4o-mini")  # Default fallback
        if not self.batcher._running:
            asyncio.create_task(self.batcher.start())

    async def decide(self, prompt: str, callback: Callable[[str, Any, Optional[Exception]], Any] = None) -> str:
        """
        Make a decision by sending prompt to LLM via batcher.

        Args:
            prompt: The decision prompt
            callback: Optional callback for async response handling

        Returns:
            The LLM response content
        """
        request_id = f"bot_{self.name}_{uuid.uuid4().hex[:8]}"
        if callback is None:
            callback = lambda req_id, response, error: response if response else str(error)

        # Add request to batcher
        self.batcher.add_request(request_id, prompt, self.model, callback)

        # For sync-like behavior, wait a bit for processing (in real use, use events/callbacks)
        await asyncio.sleep(0.5)  # Allow batching/processing time

        # Simulate retrieving response (in full impl, use event bus or queue)
        # For now, assume callback has been called; return placeholder
        return f"Decision from {self.model}: Processed '{prompt[:20]}...'"

    async def run_action(self, action_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific action type with context."""
        prompt = f"Context: {context}. Perform {action_type} action."
        response = await self.decide(prompt)
        return {"action": action_type, "response": response, "model": self.model}


class BotFactory:
    """Factory for creating baseline bots."""

    @staticmethod
    def create_bot(bot_name: str, model_slug: Optional[str] = None) -> Optional[Any]:
        """
        Create a bot by name, supporting OpenRouter for LLM calls when MODEL_SLUG is set.

        Supported bots:
        - gpt_4o_mini_bot: Uses OpenRouterBot with MODEL_SLUG or defaults to gpt-4o-mini
        - claude_sonnet_bot: Same, but logs as Claude
        - greedy_script_bot: Simple rule-based (no LLM)
        - grok_4_bot: Same as above
        - openrouter_bot: Explicit OpenRouter LLM bot

        Args:
            bot_name: The bot type to create
            model_slug: Override model (from --model flag)

        Returns:
            Bot instance (OpenRouterBot or LLMBot) or None if unknown
        """
        model = model_slug or os.getenv("MODEL_SLUG", "openai/gpt-4o-mini")
        if bot_name in ["gpt_4o_mini_bot", "claude_sonnet_bot", "grok_4_bot", "openrouter_bot"]:
            # Use OpenRouterBot for real LLM calls
            try:
                from baseline_bots.openrouter_bot import OpenRouterBot
                from constraints.agent_gateway import AgentGateway
                from llm_interface.prompt_adapter import PromptAdapter
                from llm_interface.response_parser import LLMResponseParser

                # Create dependencies (simple defaults for demo)
                prompt_adapter = PromptAdapter()
                response_parser = LLMResponseParser()
                agent_gateway = AgentGateway()

                agent_id = f"demo_bot_{bot_name}"
                return OpenRouterBot(
                    agent_id=agent_id,
                    prompt_adapter=prompt_adapter,
                    response_parser=response_parser,
                    agent_gateway=agent_gateway,
                    model_name=model,
                )
            except ImportError as e:
                logger.warning(f"OpenRouterBot dependencies missing: {e}. Falling back to stub LLMBot.")
                batcher = LLMBatcher()
                return LLMBot(bot_name, batcher)
        elif bot_name == "greedy_script_bot":
            # Simple non-LLM bot for fallback
            class GreedyScriptBot:
                async def decide(self, prompt: str) -> str:
                    return "Greedy action: Maximize immediate profit."

                async def run_action(self, action_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
                    return {"action": action_type, "response": "Scripted response", "model": "greedy_script"}

            return GreedyScriptBot()
        else:
            logger.warning(f"Unknown bot: {bot_name}")
            return None

    @staticmethod
    def get_available_bots() -> List[str]:
        """Get list of available bot names."""
        return [
            "gpt_4o_mini_bot",
            "claude_sonnet_bot",
            "grok_4_bot",
            "greedy_script_bot",
        ]
