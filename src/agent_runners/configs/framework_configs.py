"""
Framework-specific configuration templates and examples.

Provides pre-built configurations for different agent frameworks
with sensible defaults and common use cases.

This module now uses the unified Pydantic config models exclusively.
"""

from typing import Any, Dict

from benchmarking.config.pydantic_config import (
    CrewConfig,
    FrameworkType,
    LLMConfig,
    MemoryConfig,
    UnifiedAgentRunnerConfig,
)


class FrameworkConfig:
    """Simple configuration to specify a framework type."""

    def __init__(self, framework_type: str):
        self.framework_type = framework_type


class DIYConfig:
    """Pre-built configurations for DIY agent runner."""

    @staticmethod
    def advanced_agent(
        agent_id: str, target_asin: str = "B0DEFAULT"
    ) -> UnifiedAgentRunnerConfig:
        """Configuration for event-driven advanced-style DIY agent using parameters."""
        params = {
            "agent_type": "advanced",
            "target_asin": target_asin,
            "strategy": "profit_maximizer",
            "price_sensitivity": 0.1,
            "reaction_speed": 1,
        }
        from benchmarking.config.pydantic_config import AgentConfig

        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Event-driven DIY agent with advanced strategies",
            agent_id=agent_id,
            framework=FrameworkType.DIY,
            # Populate agent_config for tests that expect it
            agent_config=AgentConfig(
                agent_id=agent_id, framework=FrameworkType.DIY, **params
            ),
            llm_config=None,
            memory_config=None,
            crew_config=None,
            verbose=False,
            max_iterations=5,
            timeout_seconds=30,
            custom_tools=[],
            custom_config={},
            parameters=params,
        )

    @staticmethod
    def baseline_greedy(agent_id: str) -> UnifiedAgentRunnerConfig:
        """Configuration for greedy baseline DIY bot."""
        params = {
            "agent_type": "baseline",
            "strategy": "greedy",
        }
        from benchmarking.config.pydantic_config import AgentConfig

        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Greedy baseline DIY pricing bot",
            agent_id=agent_id,
            framework=FrameworkType.DIY,
            agent_config=AgentConfig(
                agent_id=agent_id, framework=FrameworkType.DIY, **params
            ),
            llm_config=None,
            memory_config=None,
            crew_config=None,
            verbose=False,
            custom_tools=[],
            custom_config={
                "bot_type": "greedy",
                "reorder_threshold": 10,
                "reorder_quantity": 50,
            },
            parameters=params,
        )

    @staticmethod
    def llm_claude(
        agent_id: str, api_key: str, target_asin: str = "B0DEFAULT"
    ) -> UnifiedAgentRunnerConfig:
        """Configuration for Claude-based LLM DIY agent."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="DIY agent powered by Claude",
            agent_id=agent_id,
            framework=FrameworkType.DIY,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="anthropic",
                model="claude-3-sonnet",
                api_key=api_key,
                temperature=0.1,
            ),
            memory_config=None,
            crew_config=None,
            verbose=False,
            custom_tools=[],
            custom_config={
                "llm_type": "claude",
                "model_name": "anthropic/claude-3-sonnet:beta",
            },
            parameters={
                "agent_type": "llm",
                "target_asin": target_asin,
            },
        )

    @staticmethod
    def llm_gpt(
        agent_id: str, api_key: str, target_asin: str = "B0DEFAULT"
    ) -> UnifiedAgentRunnerConfig:
        """Configuration for GPT-based LLM DIY agent."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="DIY agent powered by GPT",
            agent_id=agent_id,
            framework=FrameworkType.DIY,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4o-mini",
                api_key=api_key,
                temperature=0.1,
            ),
            memory_config=None,
            crew_config=None,
            verbose=False,
            custom_tools=[],
            custom_config={
                "llm_type": "gpt",
                "model_name": "gpt-4o-mini",
            },
            parameters={
                "agent_type": "llm",
                "target_asin": target_asin,
            },
        )


class CrewAIConfig:
    """Pre-built configurations for CrewAI agent runner."""

    @staticmethod
    def standard_crew(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """Standard 4-agent crew configuration."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Standard CrewAI team with specialized agents",
            agent_id=agent_id,
            framework=FrameworkType.CREWAI,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4",
                temperature=0.1,
                api_key=api_key,
            ),
            memory_config=None,
            crew_config=CrewConfig(
                name=f"{agent_id}_crew",
                process="sequential",
                crew_size=4,
                roles=[
                    "pricing_specialist",
                    "inventory_manager",
                    "market_analyst",
                    "strategy_coordinator",
                ],
                collaboration_mode="sequential",
                allow_delegation=True,
            ),
            verbose=False,
        )

    @staticmethod
    def hierarchical_crew(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """Hierarchical crew with manager coordination."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Hierarchical CrewAI with manager coordination",
            agent_id=agent_id,
            framework=FrameworkType.CREWAI,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4",
                temperature=0.1,
                api_key=api_key,
            ),
            memory_config=None,
            crew_config=CrewConfig(
                name=f"{agent_id}_crew",
                process="hierarchical",
                crew_size=4,
                roles=[
                    "pricing_specialist",
                    "inventory_manager",
                    "market_analyst",
                    "strategy_coordinator",
                ],
                collaboration_mode="hierarchical",
                allow_delegation=True,
            ),
            verbose=True,
        )

    @staticmethod
    def focused_pricing_crew(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """Specialized crew focused on pricing optimization."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Focused pricing optimization CrewAI",
            agent_id=agent_id,
            framework=FrameworkType.CREWAI,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4",
                temperature=0.05,
                api_key=api_key,
            ),
            memory_config=None,
            crew_config=CrewConfig(
                name=f"{agent_id}_crew",
                process="sequential",
                crew_size=3,
                roles=["pricing_specialist", "market_analyst", "strategy_coordinator"],
                collaboration_mode="sequential",
                allow_delegation=False,
            ),
            verbose=False,
        )

    @staticmethod
    def claude_crew(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """CrewAI configuration using Claude models."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="CrewAI powered by Claude",
            agent_id=agent_id,
            framework=FrameworkType.CREWAI,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="anthropic",
                model="claude-3-sonnet",
                temperature=0.1,
                api_key=api_key,
            ),
            memory_config=None,
            crew_config=CrewConfig(
                name=f"{agent_id}_crew",
                process="sequential",
                crew_size=4,
                roles=[
                    "pricing_specialist",
                    "inventory_manager",
                    "market_analyst",
                    "strategy_coordinator",
                ],
                collaboration_mode="sequential",
                allow_delegation=True,
            ),
            verbose=False,
        )


class LangChainConfig:
    """Pre-built configurations for LangChain agent runner."""

    @staticmethod
    def reasoning_agent(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """LangChain agent with reasoning chains and memory."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="LangChain reasoning agent with buffer memory",
            agent_id=agent_id,
            framework=FrameworkType.LANGCHAIN,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4",
                temperature=0.1,
                api_key=api_key,
            ),
            memory_config=MemoryConfig(
                name=f"{agent_id}_memory",
                type="buffer",
                window_size=10,
            ),
            crew_config=None,
            max_iterations=5,
            verbose=False,
        )

    @staticmethod
    def memory_agent(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """LangChain agent with advanced memory system."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="LangChain agent with summary memory",
            agent_id=agent_id,
            framework=FrameworkType.LANGCHAIN,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4",
                temperature=0.2,
                api_key=api_key,
            ),
            memory_config=MemoryConfig(
                name=f"{agent_id}_memory",
                type="summary",
                window_size=20,
            ),
            crew_config=None,
            max_iterations=7,
            verbose=False,
        )

    @staticmethod
    def fast_agent(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """Fast LangChain agent with minimal memory for quick decisions."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Fast LangChain agent",
            agent_id=agent_id,
            framework=FrameworkType.LANGCHAIN,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-3.5-turbo",
                temperature=0.1,
                api_key=api_key,
            ),
            memory_config=MemoryConfig(
                name=f"{agent_id}_memory",
                type="buffer",
                window_size=5,
            ),
            crew_config=None,
            max_iterations=3,
            timeout_seconds=15,
            verbose=False,
        )

    @staticmethod
    def analytical_agent(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """Analytical LangChain agent for deep market analysis."""
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_runner",
            description="Analytical LangChain agent",
            agent_id=agent_id,
            framework=FrameworkType.LANGCHAIN,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4",
                temperature=0.05,
                api_key=api_key,
            ),
            memory_config=MemoryConfig(
                name=f"{agent_id}_memory",
                type="summary",
                window_size=15,
            ),
            crew_config=None,
            max_iterations=10,
            timeout_seconds=60,
            verbose=True,
        )


def get_framework_examples() -> Dict[str, Dict[str, Any]]:
    """Get example configurations for all frameworks."""
    return {
        "diy": {
            "advanced_agent": "Event-driven agent with pricing strategy (DIY)",
            "baseline_greedy": "Simple greedy pricing bot (DIY)",
            "llm_claude": "Claude-powered decision making (DIY)",
            "llm_gpt": "GPT-powered decision making (DIY)",
        },
        "crewai": {
            "standard_crew": "4-agent collaborative crew",
            "hierarchical_crew": "Manager-coordinated crew",
            "focused_pricing_crew": "Specialized pricing optimization",
            "claude_crew": "CrewAI with Claude models",
        },
        "langchain": {
            "reasoning_agent": "Reasoning chains with memory",
            "memory_agent": "Advanced memory system",
            "fast_agent": "Quick decisions, minimal memory",
            "analytical_agent": "Deep analytical capabilities",
        },
    }


def create_example_config(
    framework: str,
    config_type: str,
    agent_id: str,
    api_key: str = None,
    **kwargs,
) -> UnifiedAgentRunnerConfig:
    """
    Create an example configuration.

    Args:
        framework: Framework name (diy, crewai, langchain)
        config_type: Configuration type (e.g., 'standard_crew', 'reasoning_agent')
        agent_id: Agent identifier
        api_key: API key for LLM providers
        **kwargs: Additional parameters

    Returns:
        Pre-configured UnifiedAgentRunnerConfig instance
    """
    framework = framework.lower()
    config_type = config_type.lower()

    if framework == "diy":
        if config_type == "advanced_agent":
            return DIYConfig.advanced_agent(
                agent_id, kwargs.get("target_asin", "B0DEFAULT")
            )
        elif config_type == "baseline_greedy":
            return DIYConfig.baseline_greedy(agent_id)
        elif config_type == "llm_claude":
            if not api_key:
                raise ValueError("api_key is required for llm_claude")
            return DIYConfig.llm_claude(
                agent_id, api_key, kwargs.get("target_asin", "B0DEFAULT")
            )
        elif config_type == "llm_gpt":
            if not api_key:
                raise ValueError("api_key is required for llm_gpt")
            return DIYConfig.llm_gpt(
                agent_id, api_key, kwargs.get("target_asin", "B0DEFAULT")
            )

    elif framework == "crewai":
        if config_type == "standard_crew":
            if not api_key:
                raise ValueError("api_key is required for CrewAI")
            return CrewAIConfig.standard_crew(agent_id, api_key)
        elif config_type == "hierarchical_crew":
            if not api_key:
                raise ValueError("api_key is required for CrewAI")
            return CrewAIConfig.hierarchical_crew(agent_id, api_key)
        elif config_type == "focused_pricing_crew":
            if not api_key:
                raise ValueError("api_key is required for CrewAI")
            return CrewAIConfig.focused_pricing_crew(agent_id, api_key)
        elif config_type == "claude_crew":
            if not api_key:
                raise ValueError("api_key is required for CrewAI")
            return CrewAIConfig.claude_crew(agent_id, api_key)

    elif framework == "langchain":
        if config_type == "reasoning_agent":
            if not api_key:
                raise ValueError("api_key is required for LangChain")
            return LangChainConfig.reasoning_agent(agent_id, api_key)
        elif config_type == "memory_agent":
            if not api_key:
                raise ValueError("api_key is required for LangChain")
            return LangChainConfig.memory_agent(agent_id, api_key)
        elif config_type == "fast_agent":
            if not api_key:
                raise ValueError("api_key is required for LangChain")
            return LangChainConfig.fast_agent(agent_id, api_key)
        elif config_type == "analytical_agent":
            if not api_key:
                raise ValueError("api_key is required for LangChain")
            return LangChainConfig.analytical_agent(agent_id, api_key)

    elif framework == "leaderboard":
        if config_type == "gpt4o_champion":
            if not api_key:
                raise ValueError("api_key is required for Leaderboard models")
            return LeaderboardConfig.gpt4o_champion(agent_id, api_key)
        elif config_type == "claude35_sonnet_champion":
            if not api_key:
                raise ValueError("api_key is required for Leaderboard models")
            return LeaderboardConfig.claude35_sonnet_champion(agent_id, api_key)

    raise ValueError(f"Unknown configuration: {framework}.{config_type}")


class LeaderboardConfig:
    """High-performance configurations for Leaderboard contenders."""

    @staticmethod
    def gpt4o_champion(agent_id: str, api_key: str) -> UnifiedAgentRunnerConfig:
        """
        Optimized GPT-4o configuration for leaderboard dominance.
        Features: Low temperature, Chain-of-Thought prompting, JSON mode.
        """
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_gpt4o_champ",
            description="GPT-4o Champion Recommendation",
            agent_id=agent_id,
            framework=FrameworkType.LANGCHAIN,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="openai",
                model="gpt-4o-2024-08-06",  # Correct 4o model
                temperature=0.0,  # Strict adherence
                api_key=api_key,
                max_tokens=4096,
                top_p=0.9,
            ),
            memory_config=MemoryConfig(
                name=f"{agent_id}_memory",
                type="summary",  # Use summary memory to simulate long-term tracking
                window_size=50,  # Large window
            ),
            custom_config={
                "system_prompt": (
                    "You are the FBA-Bench Champion Agent. Your goal is to MAXIMIZE PROFIT above all else. "
                    "You are an expert in supply chain logistics, competitive pricing, and inventory management. "
                    "Analyze every tick carefully. Do not run out of stock. Do not overstock. "
                    "Undercut competitors aggressively but maintaining margin. "
                    "Use your memory to track price trends."
                )
            },
            max_iterations=10,
            verbose=True,
        )

    @staticmethod
    def claude35_sonnet_champion(
        agent_id: str, api_key: str
    ) -> UnifiedAgentRunnerConfig:
        """
        Optimized Claude 3.5 Sonnet configuration for leaderboard dominance.
        Features: High reasoning capability, large context window util.
        """
        return UnifiedAgentRunnerConfig(
            name=f"{agent_id}_c35sonnet_champ",
            description="Claude 3.5 Sonnet Champion Recommendation",
            agent_id=agent_id,
            framework=FrameworkType.LANGCHAIN,
            agent_config=None,
            llm_config=LLMConfig(
                name=f"{agent_id}_llm",
                provider="anthropic",
                model="claude-3-5-sonnet-20240620",
                temperature=0.1,
                api_key=api_key,
                max_tokens=4096,
            ),
            memory_config=MemoryConfig(
                name=f"{agent_id}_memory",
                type="buffer",  # Claude has huge context, use buffer
                window_size=100,
            ),
            custom_config={
                "system_prompt": (
                    "You are a sophisticated algorithmic trading agent on the FBA Bench Leaderboard. "
                    "Your primary directive is to maximize net asset value (NAV). "
                    "1. INVENTORY: Never stockout. Order lead time is non-zero. "
                    "2. PRICING: Calculate elasticity. If demand is high, raise prices. "
                    "3. STRATEGY: Be aggressive. Crush the baseline bots."
                )
            },
            max_iterations=10,
            verbose=True,
        )
