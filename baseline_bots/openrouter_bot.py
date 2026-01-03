from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from constraints.agent_gateway import AgentGateway
from llm_interface.config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient
from llm_interface.prompt_adapter import PromptAdapter
from llm_interface.response_parser import LLMResponseParser


@dataclass
class SimulationState:
    products: List[Any]
    current_tick: int
    simulation_time: datetime
    recent_events: List[Any]


class OpenRouterBot:
    """
    LLM bot using OpenRouter as the provider. Accepts dependencies and delegates to implementations:
    - llm_client.generate_response(prompt=..., temperature=..., max_tokens=..., top_p=...)
    - prompt_adapter to build prompt text
    - agent_gateway to preprocess (inject budget) and postprocess
    - response_parser to convert model output into domain actions (e.g., SetPriceCommand)
    Supports free models like moonshotai/kimi-k2:free, deepseek/deepseek-r1-0528:free.
    """

    def __init__(
        self,
        agent_id: str,
        prompt_adapter: PromptAdapter,
        response_parser: LLMResponseParser,
        agent_gateway: AgentGateway,
        model_name: str = "moonshotai/kimi-k2:free",
        model_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.prompt_adapter = prompt_adapter
        self.response_parser = response_parser
        self.agent_gateway = agent_gateway
        # Normalize model params early (used to build client config)
        self.model_params = dict(model_params or {})

        # Configure OpenRouter client via LLMConfig (env-driven API key)
        cfg = LLMConfig(
            provider="openrouter",
            model=model_name,
            api_key_env="OPENROUTER_API_KEY",
            base_url=os.getenv("OPENROUTER_BASE_URL") or None,
            temperature=float(self.model_params.get("temperature", 0.7)),
            max_tokens=int(self.model_params.get("max_tokens_per_action", 4096)),
            top_p=float(self.model_params.get("top_p", 1.0)),
            custom_params={},
        )
        self.llm_client = OpenRouterClient(cfg)

    async def decide(self, state: SimulationState) -> List[Any]:
        actions: List[Any] = []
        # 1) Build raw prompt from state
        try:
            if hasattr(self.prompt_adapter, "build_prompt"):
                raw_prompt = self.prompt_adapter.build_prompt(state)  # type: ignore[attr-defined]
            else:
                raw_prompt = f"State at tick {getattr(state, 'current_tick', '?')}"
        except (AttributeError, TypeError):
            raw_prompt = "State unavailable"

        # 2) Preprocess via AgentGateway (inject budgets, guardrails)
        try:
            pre = await self.agent_gateway.preprocess_request(self.agent_id, raw_prompt)
            processed_prompt = (
                pre.get("modified_prompt", raw_prompt) if isinstance(pre, dict) else pre
            )
        except SystemExit:
            # Hard stop enforced by gateway in tests
            return []
        except (AttributeError, TypeError, ValueError):
            # Fail safe: if gateway hard-fails, return no actions per tests
            return []

        # 3) Call LLM with configured params
        temperature = self.model_params.get("temperature", 0.7)
        max_tokens = self.model_params.get("max_tokens_per_action", 4096)
        top_p = self.model_params.get("top_p", 1.0)

        try:
            llm_response = await self.llm_client.generate_response(
                prompt=processed_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError):
            # LLM failure -> no actions; parser may penalize in other tests
            try:
                if hasattr(self.response_parser, "trust_metrics"):
                    self.response_parser.trust_metrics.apply_penalty(  # type: ignore[attr-defined]
                        self.agent_id, 1.0, "LLM call failed"
                    )
            except (AttributeError, TypeError):
                pass
            return []

        # 4) Parse and validate into domain actions
        try:
            content = ""
            try:
                # Common OpenAI-like payload: choices[0].message.content
                content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
            except (AttributeError, TypeError, IndexError):
                content = ""

            actions = []
            if hasattr(self.response_parser, "parse_and_validate"):
                # Support parsers with (content, agent_id) and legacy (content) signatures
                try:
                    parse_result = self.response_parser.parse_and_validate(content, self.agent_id)  # type: ignore[arg-type]
                except TypeError:
                    parse_result = self.response_parser.parse_and_validate(content)  # type: ignore[misc]

                # Await if coroutine
                try:
                    import inspect  # local import to avoid global dependency

                    if inspect.isawaitable(parse_result):
                        parse_result = await parse_result  # type: ignore[assignment]
                except (AttributeError, TypeError):
                    pass

                # Normalize results: tuple(parsed_json, error) | list(actions) | iterable | None
                if isinstance(parse_result, tuple) and len(parse_result) >= 1:
                    parsed_json = parse_result[0]
                    if isinstance(parsed_json, dict):
                        maybe = parsed_json.get("actions")
                        if isinstance(maybe, list):
                            actions = maybe
                        elif maybe is not None:
                            try:
                                actions = list(maybe)  # type: ignore[arg-type]
                            except (TypeError, ValueError):
                                actions = []
                    elif isinstance(parsed_json, list):
                        actions = parsed_json
                    elif parsed_json is not None:
                        try:
                            actions = list(parsed_json)  # type: ignore[arg-type]
                        except (TypeError, ValueError):
                            actions = []
                elif isinstance(parse_result, list):
                    actions = parse_result
                elif parse_result is not None:
                    try:
                        actions = list(parse_result)  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        actions = []
            else:
                actions = []
        except (AttributeError, TypeError, ValueError):
            # Ensure trust penalty on parsing/validation failures as tests expect
            try:
                if hasattr(self.response_parser, "trust_metrics"):
                    self.response_parser.trust_metrics.apply_penalty(  # type: ignore[attr-defined]
                        self.agent_id, 1.0, "LLM parse/validation error"
                    )
            except (AttributeError, TypeError):
                pass
            actions = []

        # Fallback: if parser succeeded but returned no actions, try extracting directly from content JSON
        if not actions:
            try:
                import json as _json

                _direct = _json.loads(content)
                if isinstance(_direct, dict):
                    _acts = _direct.get("actions")
                    if isinstance(_acts, list):
                        actions = _acts
            except (ImportError, ValueError, TypeError):
                # Ignore fallback errors; keep actions as-is
                pass

        # Convert parsed dict actions into typed SetPriceCommand events where applicable
        try:
            from datetime import datetime as _dt
            from uuid import uuid4 as _uuid4

            from money import Money  # type: ignore

            from events import SetPriceCommand  # type: ignore

            converted: List[Any] = []
            for a in list(actions or []):
                # If it's already a SetPriceCommand-like instance, keep it
                if hasattr(a, "asin") and hasattr(a, "new_price"):
                    converted.append(a)
                    continue
                if isinstance(a, dict):
                    atype = (a.get("type") or a.get("action") or "").lower()
                    # Support both nested parameters and flattened schema produced by parser
                    params = a.get("parameters") or a.get("params") or a
                    if atype in ("set_price", "setpricecommand"):
                        asin = params.get("asin") or params.get("product_asin") or ""
                        price = params.get("price") or params.get("new_price")
                        try:
                            price_money = (
                                price
                                if isinstance(price, Money)
                                else Money.from_dollars(float(price))
                            )
                            converted.append(
                                SetPriceCommand(
                                    event_id=str(_uuid4()),
                                    timestamp=getattr(state, "simulation_time", _dt.utcnow()),
                                    agent_id=self.agent_id,
                                    asin=str(asin),
                                    new_price=price_money,
                                    reason="Test price adjustment",
                                )
                            )
                            continue
                        except (TypeError, ValueError, AttributeError):
                            # If price is malformed or missing, retain original dict for visibility
                            pass
                # Fallback: keep original shape
                converted.append(a)
            actions = converted
        except (ImportError, AttributeError, TypeError, ValueError):
            # Best-effort conversion; do not fail decision flow
            pass

        # 5) Postprocess via AgentGateway (record usage, route events, etc.)
        try:
            await self.agent_gateway.postprocess_response(
                self.agent_id,
                "llm_decision",
                processed_prompt if isinstance(processed_prompt, str) else str(processed_prompt),
                content,
            )
        except (AttributeError, TypeError, ValueError):
            # Non-fatal for tests
            pass

        return actions
