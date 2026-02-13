from __future__ import annotations

"""
LangChain Agent Runner for FBA-Bench.

Production-ready runner with:
- Soft dependency on langchain + langchain-openai (optional imports)
- Pydantic v2 config schemas and per-run input validation
- Unified async run(task_input: dict) returning normalized result
- Tool adapter for callable/dict tool descriptors
- Robust logging and optional Redis pub/sub progress events
- Compatibility with AgentRunner base (make_decision bridges to run)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .base_runner import (
    AgentRunner,
    AgentRunnerDecisionError,
    AgentRunnerInitializationError,
    AgentRunnerStatus,
)

logger = logging.getLogger(__name__)


# ----------------------------- Config Schemas ---------------------------------


class ToolSpec(BaseModel):
    """Unified tool spec accepted by runner.

    Supports two forms:
    - callable-only: pass via config.tools=[callable] or task_input["tools"]
    - dict descriptor: {"name","description","callable","schema"(optional)}

    callable can be sync or async function taking a single dict-like parameter.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None
    callable: Optional[Callable[..., Any]] = None

    @field_validator("callable")
    @classmethod
    def _ensure_callable(cls, v):
        if v is not None and not callable(v):
            raise ValueError("callable must be a function")
        return v


class LangChainRunnerConfig(BaseModel):
    """Pydantic v2 config for LangChain runner."""

    model: Optional[str] = Field(default="gpt-4o-mini", description="Chat model name")
    temperature: Optional[float] = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2048, ge=1)
    tools: Optional[List[Union[ToolSpec, Callable[..., Any], Dict[str, Any]]]] = None
    memory: Optional[bool] = Field(default=False)
    system_prompt: Optional[str] = Field(
        default="You are an FBA pricing expert. Provide JSON-only outputs."
    )
    agent_name: Optional[str] = Field(default="LangChain Pricing Agent")
    llm_model_kwargs: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional model kwargs for the LLM"
    )
    verbose: Optional[bool] = Field(
        default=False, description="Enable verbose logging for LangChain operations"
    )
    # OpenRouter / custom endpoint support
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for OpenAI-compatible API (e.g., OpenRouter)",
    )
    api_key: Optional[str] = Field(
        default=None, description="API key (falls back to OPENAI_API_KEY env var)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                    "max_tokens": 1024,
                    "memory": False,
                    "system_prompt": "Pricing specialist; output strictly JSON.",
                    "agent_name": "lc_pricing_agent_1",
                },
                {
                    "model": "openai/gpt-4o",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key": "sk-or-...",
                    "temperature": 0.0,
                },
            ]
        }
    )


class LangChainTaskInput(BaseModel):
    """Per-run input schema."""

    prompt: Optional[str] = Field(
        default=None, description="User high-level task prompt"
    )
    products: Optional[List[Dict[str, Any]]] = None
    market_conditions: Optional[Dict[str, Any]] = None
    recent_events: Optional[List[Dict[str, Any]]] = None
    tick: Optional[int] = 0
    tools: Optional[List[Union[ToolSpec, Callable[..., Any], Dict[str, Any]]]] = None
    extra: Optional[Dict[str, Any]] = None


# -------------------------- Internal Utilities --------------------------------


async def _maybe_publish_progress(topic: str, event: Dict[str, Any]) -> None:
    """Publish progress to Redis if REDIS_URL set and redis client available."""
    if not os.getenv("REDIS_URL"):
        return
    try:
        from fba_bench_api.core.redis_client import get_redis  # type: ignore

        client = await get_redis()
        payload = json.dumps(event)
        await client.publish(topic, payload)
    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:  # pragma: no cover
        logger.debug(
            "Progress publish skipped (redis unavailable or misconfigured): %s", exc
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_tools(
    tools: Optional[List[Union[ToolSpec, Callable[..., Any], Dict[str, Any]]]],
) -> List[ToolSpec]:
    """Normalize tool inputs into ToolSpec list."""
    if not tools:
        return []
    norm: List[ToolSpec] = []
    for t in tools:
        if isinstance(t, ToolSpec):
            norm.append(t)
        elif callable(t):
            norm.append(
                ToolSpec(
                    name=getattr(t, "__name__", "tool"),
                    description=t.__doc__,
                    callable=t,
                )
            )
        elif isinstance(t, dict):
            norm.append(ToolSpec.model_validate(t))
        else:
            raise ValueError(f"Unsupported tool descriptor type: {type(t)}")
    return norm


def _format_context_prompt(cfg: LangChainRunnerConfig, ti: LangChainTaskInput) -> str:
    """Create a deterministic context prompt."""
    parts: List[str] = []
    if cfg.system_prompt:
        parts.append(cfg.system_prompt)
    if ti.prompt:
        parts.append(ti.prompt)

    # Include structured context succinctly
    if ti.products:
        parts.append("PRODUCTS:")
        for p in ti.products:
            parts.append(
                f"- ASIN={p.get('asin','?')} price={p.get('current_price','?')} cost={p.get('cost','?')} "
                f"rank={p.get('sales_rank','?')} inv={p.get('inventory','?')}"
            )
    if ti.market_conditions:
        parts.append("MARKET:")
        for k, v in ti.market_conditions.items():
            parts.append(f"- {k}={v}")
    if ti.recent_events:
        parts.append("RECENT_EVENTS:")
        for e in ti.recent_events[-5:]:
            parts.append(f"- {e}")

    # Require JSON-only output with example schema
    parts.append(
        "Respond ONLY with a JSON object: "
        '{"decisions":[{"asin":"B0...","new_price":19.99,"reasoning":"..."}],'
        '"meta":{"tick":%d}}' % (ti.tick or 0)
    )
    return "\n".join(parts)


# ------------------------------ Runner ----------------------------------------


class LangChainRunner(AgentRunner):
    """LangChain-backed agent runner with unified async run()."""

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        # Validate config before optional imports
        self._cfg = LangChainRunnerConfig.model_validate(config or {})
        self._llm = None
        self._agent = None
        self._tools_spec: List[ToolSpec] = _normalize_tools(self._cfg.tools)
        super().__init__(agent_id, config)

    def _do_initialize(self) -> None:
        """Instantiate ChatOpenAI and optionally a tools-enabled agent (soft import)."""
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except (ImportError, AttributeError, TypeError) as e:
            raise AgentRunnerInitializationError(
                "LangChain + langchain-openai are not installed. Install extras: "
                "pip install 'langchain>=0.3' 'langchain-openai>=0.2'",
                agent_id=self.agent_id,
                framework="LangChain",
            ) from e

        # Response format JSON when supported (OpenAI-compatible)
        model_kwargs: Dict[str, Any] = self._cfg.llm_model_kwargs or {
            "response_format": {"type": "json_object"},
        }
        if not isinstance(model_kwargs, dict):
            logger.warning(
                "llm_model_kwargs in config is not a dict; ignoring custom kwargs."
            )
            model_kwargs = {"response_format": {"type": "json_object"}}

        # Build ChatOpenAI with optional base_url/api_key for OpenRouter support
        llm_kwargs: Dict[str, Any] = {
            "model": self._cfg.model or "gpt-4o-mini",
            "temperature": self._cfg.temperature or 0.3,
            "max_tokens": self._cfg.max_tokens or 2048,
            "model_kwargs": model_kwargs,
        }
        if self._cfg.base_url:
            llm_kwargs["base_url"] = self._cfg.base_url
        if self._cfg.api_key:
            llm_kwargs["api_key"] = self._cfg.api_key

        self._llm = ChatOpenAI(**llm_kwargs)

        # Build a tools-enabled agent if tools are available; otherwise keep None
        try:
            if self._tools_spec:
                self._agent = self._build_agent_with_tools(self._tools_spec)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            # Tools are optional; log and continue without tools
            logger.debug("Failed to initialize LangChain agent with tools: %s", e)
            self._agent = None

    def _wrap_tools_for_langchain(self, tools_spec: List[ToolSpec]) -> List[Any]:
        """Wrap ToolSpec into LangChain Tools."""
        wrapped: List[Any] = []
        if not tools_spec:
            return wrapped
        try:
            from langchain.tools import Tool  # type: ignore

            for ts in tools_spec:
                if not ts.callable:
                    continue

                func = ts.callable

                async def _run(value: str, _f=func):
                    # Accept JSON string or raw
                    try:
                        payload = json.loads(value) if isinstance(value, str) else value
                    except (json.JSONDecodeError, TypeError, ValueError):
                        payload = {"input": value}
                    res = _f(payload)
                    if asyncio.iscoroutine(res):
                        res = await res
                    return res

                def _sync_runner(value: str, _af=_run):
                    return asyncio.run(_af(value))

                wrapped.append(
                    Tool(
                        name=ts.name or getattr(func, "__name__", "tool"),
                        func=_sync_runner,
                        description=ts.description or "Runner-provided tool",
                    )
                )
            return wrapped
        except (ImportError, AttributeError, TypeError, ValueError):
            logger.debug(
                "LangChain Tool adapter not available; continuing without tools"
            )
            return []

    def _build_agent_with_tools(self, tools_spec: List[ToolSpec]) -> Any:
        """Build an agent using LangChain initialize_agent if available."""
        try:
            from langchain.agents import AgentType, initialize_agent  # type: ignore
        except (ImportError, AttributeError, TypeError) as e:
            # Tools not supported if agents not present
            logger.debug("LangChain agents unavailable: %s", e)
            return None

        tools = self._wrap_tools_for_langchain(tools_spec)
        if not tools:
            return None

        # Use a structured chat agent to encourage tool use and structured outputs
        agent = initialize_agent(
            tools=tools,
            llm=self._llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=bool(self._cfg.verbose),
        )
        return agent

    async def run(self, task_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single LangChain run and return normalized result."""
        started = time.monotonic()
        steps: List[Dict[str, Any]] = []
        tool_calls: List[Dict[str, Any]] = []
        topic = f"runner:langchain:{self.agent_id}"

        try:
            inp = LangChainTaskInput.model_validate(task_input or {})
        except ValidationError as ve:
            return {
                "status": "failed",
                "output": f"Invalid task_input: {ve}",
                "steps": [],
                "tool_calls": [],
                "metrics": {"duration_ms": int((time.monotonic() - started) * 1000)},
            }

        await _maybe_publish_progress(
            topic, {"phase": "start", "at": _now_iso(), "tick": inp.tick}
        )

        # Ensure initialized
        if self.status != AgentRunnerStatus.READY:
            self._do_initialize()
            self.status = AgentRunnerStatus.READY

        # Merge tools per-run if provided; rebuild agent if needed
        run_tools = _normalize_tools(inp.tools) if inp.tools else []
        tools_spec = run_tools or self._tools_spec
        if run_tools:
            # Per-run override: rebuild an agent instance
            self._agent = None
            try:
                self._agent = self._build_agent_with_tools(tools_spec)
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.debug("Failed to rebuild agent with per-run tools: %s", e)
                self._agent = None

        prompt = _format_context_prompt(self._cfg, inp)
        steps.append({"role": "system", "content": self._cfg.system_prompt or ""})
        if inp.prompt:
            steps.append({"role": "user", "content": inp.prompt})

        try:
            await _maybe_publish_progress(
                topic, {"phase": "inference_start", "at": _now_iso()}
            )

            if self._agent is not None:
                # Use agent with tools
                result_text = await asyncio.to_thread(self._agent.run, prompt)  # type: ignore
                # We don't have direct tool trace without deeper callbacks; record available tools
                for ts in tools_spec:
                    tool_calls.append(
                        {"name": ts.name or "tool", "args": None, "result": None}
                    )
            else:
                # Raw LLM call using messages to preserve system prompt
                try:
                    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
                except (ImportError, AttributeError, TypeError):
                    SystemMessage = None  # type: ignore
                    HumanMessage = None  # type: ignore

                if SystemMessage and HumanMessage:
                    msgs = []
                    if self._cfg.system_prompt:
                        msgs.append(SystemMessage(content=self._cfg.system_prompt))
                    msgs.append(HumanMessage(content=prompt))
                    resp = await asyncio.to_thread(self._llm.invoke, msgs)  # type: ignore
                else:
                    # Fallback: pass a plain string to .invoke
                    resp = await asyncio.to_thread(self._llm.invoke, prompt)  # type: ignore

                # resp could be a Message or dict-like
                result_text = getattr(resp, "content", None) or str(resp)

            await _maybe_publish_progress(
                topic, {"phase": "inference_end", "at": _now_iso()}
            )

            steps.append({"role": "assistant", "content": result_text})

            duration_ms = int((time.monotonic() - started) * 1000)
            metrics = {"duration_ms": duration_ms}

            await _maybe_publish_progress(
                topic,
                {"phase": "complete", "at": _now_iso(), "duration_ms": duration_ms},
            )

            return {
                "status": "success",
                "output": result_text,
                "steps": steps,
                "tool_calls": tool_calls,
                "metrics": metrics,
            }
        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            AgentRunnerDecisionError,
        ) as e:
            logger.exception("LangChain run failed: %s", e)
            await _maybe_publish_progress(
                topic, {"phase": "error", "at": _now_iso(), "error": str(e)}
            )
            return {
                "status": "failed",
                "output": f"Error: {e}",
                "steps": steps,
                "tool_calls": tool_calls,
                "metrics": {"duration_ms": int((time.monotonic() - started) * 1000)},
            }

    # ---------------- AgentRunner compatibility (decide/make_decision) ----------

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sync bridge to async run(); used by AgentRunner.make_decision_async."""
        task_input = {
            "prompt": "Make pricing decisions for the given state.",
            "products": context.get("products"),
            "market_conditions": context.get("market_conditions"),
            "recent_events": context.get("recent_events"),
            "tick": context.get("tick", 0),
        }
        try:
            result = asyncio.run(self.run(task_input))
        except RuntimeError:
            # Already in event loop; offload
            result = asyncio.get_event_loop().run_until_complete(self.run(task_input))  # type: ignore
        if result.get("status") != "success":
            raise AgentRunnerDecisionError(
                f"LangChain decision failed: {result.get('output','')}",
                agent_id=self.agent_id,
                framework="LangChain",
            )
        return result

    def _do_cleanup(self) -> None:
        self._agent = None
        self._llm = None
        logger.info("LangChain runner %s cleaned up", self.agent_id)


__all__ = ["LangChainRunner", "LangChainRunnerConfig", "LangChainTaskInput", "ToolSpec"]
