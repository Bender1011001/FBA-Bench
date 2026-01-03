from __future__ import annotations

"""
CrewAI Agent Runner for FBA-Bench.

Production-ready runner with:
- Soft dependency on crewai (optional import)
- Pydantic v2 config schemas and task input validation
- Unified async run(task_input: dict) - normalized result shape
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

from pydantic import BaseModel, Field, ValidationError, field_validator

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


class CrewAIRunnerConfig(BaseModel):
    """Pydantic v2 config for CrewAI runner."""

    model: Optional[str] = Field(
        default=None, description="Model name for the LLM provider"
    )
    temperature: Optional[float] = Field(default=0.3, ge=0.0, le=2.0)
    max_steps: Optional[int] = Field(default=5, ge=1)
    tools: Optional[List[Union[ToolSpec, Callable[..., Any], Dict[str, Any]]]] = None
    memory: Optional[bool] = Field(
        default=False, description="Enable memory if supported"
    )
    system_prompt: Optional[str] = Field(
        default="You are an FBA pricing expert. Provide JSON-only outputs.",
    )
    agent_name: Optional[str] = Field(default="CrewAI Pricing Agent")
    allow_delegation: Optional[bool] = Field(default=False)
    verbose: Optional[bool] = Field(
        default=False, description="Enable verbose logging for CrewAI operations"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                    "max_steps": 4,
                    "memory": False,
                    "system_prompt": "Pricing specialist; output strictly JSON.",
                    "agent_name": "pricing_agent_1",
                }
            ]
        }
    }


class CrewAITaskInput(BaseModel):
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
        # Lazy import to avoid hard dependency
        from fba_bench_api.core.redis_client import get_redis  # type: ignore

        client = await get_redis()
        payload = json.dumps(event)
        await client.publish(topic, payload)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:  # pragma: no cover
        logger.debug("Progress publish skipped (redis unavailable or misconfigured): %s", exc)


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


def _format_task_prompt(cfg: CrewAIRunnerConfig, ti: CrewAITaskInput) -> str:
    """Create a deterministic prompt for CrewAI Task."""
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

    # Require JSON-only output
    parts.append(
        "Respond ONLY with a JSON object: "
        '{"decisions":[{"asin":"B0...","new_price":19.99,"reasoning":"..."}],'
        '"meta":{"tick":%d}}' % (ti.tick or 0)
    )
    return "\n".join(parts)


# ------------------------------ Runner ----------------------------------------


class CrewAIRunner(AgentRunner):
    """CrewAI-backed agent runner with unified async run()."""

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        # Validate and store config safely (do not import crewai here)
        self._cfg = CrewAIRunnerConfig.model_validate(config or {})
        self._crewai_agent = None
        self._crew = None
        self._tools_spec: List[ToolSpec] = _normalize_tools(self._cfg.tools)
        super().__init__(agent_id, config)

    def _do_initialize(self) -> None:
        """Instantiate CrewAI agent and crew (soft import)."""
        try:
            from crewai import (
                Agent as CrewAgent,  # type: ignore
                Crew,
                Task,
            )
        except (ImportError, AttributeError, TypeError) as e:
            raise AgentRunnerInitializationError(
                "CrewAI is not installed or incompatible version. Install extras: pip install 'crewai>=0.28'",
                agent_id=self.agent_id,
                framework="CrewAI",
            ) from e

        # Minimal agent; tools added per-run to allow dynamic overrides
        _verbose = bool(self._cfg.verbose)
        self._crewai_agent = CrewAgent(
            role=self._cfg.agent_name or "CrewAI Agent",
            goal="Make optimal FBA pricing decisions with JSON-only outputs.",
            backstory="You are a pricing specialist for FBA.",
            verbose=_verbose,
            allow_delegation=bool(self._cfg.allow_delegation),
        )

        # Create a placeholder task; will be replaced in run()
        placeholder = Task(
            description="Initialization placeholder task",
            agent=self._crewai_agent,
            expected_output="JSON with pricing decisions",
        )
        self._crew = Crew(
            agents=[self._crewai_agent], tasks=[placeholder], verbose=_verbose
        )

    def _wrap_tools_for_crewai(self, tools_spec: List[ToolSpec]) -> List[Any]:
        """Best-effort wrapping of tools to CrewAI Tool interface.

        CrewAI currently integrates with python callables via crewai_tools or built-in adapters.
        To avoid a hard dependency on crewai_tools, we dynamically create simple adapters.
        """
        wrapped: List[Any] = []
        if not tools_spec:
            return wrapped

        try:
            # Some versions expose a simple Tool class; else directly pass callables to Task with context
            from crewai import Tool as CrewTool  # type: ignore

            for ts in tools_spec:
                if not ts.callable:
                    continue

                func = ts.callable

                async def _run(value: str, _f=func) -> str:
                    try:
                        payload = json.loads(value) if isinstance(value, str) else value
                    except (json.JSONDecodeError, TypeError, ValueError):
                        payload = {"input": value}
                    res = _f(payload)
                    if asyncio.iscoroutine(res):
                        res = await res
                    return json.dumps(res) if not isinstance(res, str) else res

                # Crew Tool expects a sync callable; provide sync shim
                def _sync_runner(value: str, _af=_run):
                    return asyncio.run(_af(value))

                wrapped.append(
                    CrewTool(
                        name=ts.name or getattr(func, "__name__", "tool"),
                        description=ts.description or "Runner-provided tool",
                        func=_sync_runner,
                    )
                )
            return wrapped
        except (ImportError, AttributeError, TypeError, ValueError):
            # Fallback: return empty list if wrapping is not supported
            logger.debug("CrewAI Tool adapter not available; continuing without tools")
            return []

    async def run(self, task_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single CrewAI run and return normalized result.

        Returns:
          {
            "status": "success"|"failed",
            "output": str,
            "steps": [ {"role","content","tool_call"?:{...}} ],
            "tool_calls": [ {name,args,result}? ],
            "metrics": { "duration_ms":..., "token_usage":{...}? }
          }
        """
        started = time.monotonic()
        steps: List[Dict[str, Any]] = []
        tool_calls: List[Dict[str, Any]] = []
        topic = f"runner:crewai:{self.agent_id}"

        try:
            inp = CrewAITaskInput.model_validate(task_input or {})
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

        # Ensure initialized; AgentRunner constructor usually did it, but guard
        if self.status != AgentRunnerStatus.READY:
            self._do_initialize()
            self.status = AgentRunnerStatus.READY

        # Merge and normalize tools (config + per-run)
        run_tools = _normalize_tools(inp.tools) if inp.tools else []
        tools_spec = run_tools or self._tools_spec
        wrapped_tools = self._wrap_tools_for_crewai(tools_spec)

        # Build prompt and Task
        prompt = _format_task_prompt(self._cfg, inp)
        steps.append({"role": "system", "content": self._cfg.system_prompt or ""})
        if inp.prompt:
            steps.append({"role": "user", "content": inp.prompt})

        try:
            from crewai import Task  # type: ignore

            # Some versions of Crew accept tools at Crew or Task level; attach if supported.
            # We set Task with description; Crew already exists.
            task_kwargs: Dict[str, Any] = {
                "description": prompt,
                "agent": self._crewai_agent,
                "expected_output": "JSON with pricing decisions",
            }
            if wrapped_tools:
                task_kwargs["tools"] = wrapped_tools

            task = Task(**task_kwargs)
            # Replace tasks, run
            self._crew.tasks = [task]  # type: ignore[attr-defined]

            await _maybe_publish_progress(
                topic, {"phase": "inference_start", "at": _now_iso()}
            )
            result = await asyncio.to_thread(self._crew.kickoff)  # type: ignore[attr-defined]
            await _maybe_publish_progress(
                topic, {"phase": "inference_end", "at": _now_iso()}
            )

            output_text = result if isinstance(result, str) else str(result)

            # Basic post-processing: attempt to detect tool usage if the framework surfaces it
            # CrewAI's public API for tool traces is limited; record provided tools as available.
            for ts in tools_spec:
                tool_calls.append(
                    {"name": ts.name or "tool", "args": None, "result": None}
                )

            steps.append({"role": "assistant", "content": output_text})

            duration_ms = int((time.monotonic() - started) * 1000)
            metrics = {"duration_ms": duration_ms}

            await _maybe_publish_progress(
                topic,
                {"phase": "complete", "at": _now_iso(), "duration_ms": duration_ms},
            )

            return {
                "status": "success",
                "output": output_text,
                "steps": steps,
                "tool_calls": tool_calls,
                "metrics": metrics,
            }
        except (AttributeError, TypeError, ValueError, RuntimeError, AgentRunnerDecisionError) as e:
            logger.exception("CrewAI run failed: %s", e)
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
        # Map Simulation context to task_input prompt; keep same output text
        task_input = {
            "prompt": "Make pricing decisions for the given state.",
            "products": context.get("products"),
            "market_conditions": context.get("market_conditions"),
            "recent_events": context.get("recent_events"),
            "tick": context.get("tick", 0),
        }
        # Run in a nested loop-safe way
        try:
            result = asyncio.run(self.run(task_input))
        except RuntimeError:
            # Already in event loop; offload
            result = asyncio.get_event_loop().run_until_complete(self.run(task_input))  # type: ignore
        if result.get("status") != "success":
            raise AgentRunnerDecisionError(
                f"CrewAI decision failed: {result.get('output','')}",
                agent_id=self.agent_id,
                framework="CrewAI",
            )
        # Adapt as a plain dict for ToolCall wrapper upstream
        return result

    def _do_cleanup(self) -> None:
        self._crewai_agent = None
        self._crew = None
        logger.info("CrewAI runner %s cleaned up", self.agent_id)


__all__ = ["CrewAIRunner", "CrewAIRunnerConfig", "CrewAITaskInput", "ToolSpec"]
