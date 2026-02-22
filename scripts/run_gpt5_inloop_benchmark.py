#!/usr/bin/env python3
"""
GPT-5 In-Loop Agent Benchmark (Daily decisions + End-of-day reflection + Long-term memory)

This runner executes a Tier scenario day-by-day and invokes GPT-5:
- One decision call per simulated day (set_price-style action format in JSON)
- One reflection call at end-of-day to summarize insights and propose memory entries
- Strict budget enforcement with a hard cap (default: $10 per full run)
- Token and cost metering using BudgetEnforcer; cost is conservatively estimated if API does not return usage
- Long-term memory persistence via EpisodicLearningManager

Why a wrapper instead of patching ScenarioEngine:
- Keeps simulator core stable while enabling high-fidelity LLM-in-loop benchmarking
- Isolates budget logic and API error handling
- Easy to evolve into an engine plugin later

Usage:
  python scripts/run_gpt5_inloop_benchmark.py \
    --scenario scenarios/tier_1_moderate.yaml \
    --agent-id gpt5_inloop_agent \
    --seed 1337 \
    --days 7 \
    --budget-usd 10

Environment:
  - Reads .env in repo root if present (simple parser) then falls back to process env
  - Supports OpenRouter by default via OPENROUTER_API_KEY
  - To use OpenAI directly, set OPENAI_API_KEY and pass --provider openai (requires base url changes below if needed)

Artifacts:
  results/gpt5_inloop/<timestamp>/
    - day_#.decision.json            (raw API response + parsed action JSON + token/cost usage)
    - day_#.reflection.json          (raw API response + parsed reflection JSON + token/cost usage)
    - summary.json                   (cost totals, token totals, run status)
    - metrics.csv                    (per-day cost, tokens, latency, and derived fields)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

# Money helpers (used by prompt adapter expectations)
from fba_bench_core.money import Money
from services.cost_tracking_service import CostTrackingService

# Budget enforcement
from constraints.budget_enforcer import BudgetEnforcer
from learning.episodic_learning import EpisodicLearningManager
from llm_interface.config import LLMConfig
from llm_interface.contract import LLMClientError
from llm_interface.generic_openai_client import GenericOpenAIClient
from llm_interface.openrouter_client import OpenRouterClient
from llm_interface.prompt_adapter import PromptAdapter
from llm_interface.response_parser import LLMResponseParser

# Load repo-local modules
from scenarios.scenario_engine import ScenarioEngine

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logger = logging.getLogger("gpt5_inloop")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)


# -----------------------------------------------------------------------------
# Simple .env loader (non-dependency)
# -----------------------------------------------------------------------------
def load_dotenv_if_present(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" in s:
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and (k not in os.environ):
                    os.environ[k] = v
    except Exception as e:
        logger.warning(f"Failed to parse .env file {env_path}: {e}")


# -----------------------------------------------------------------------------
# Minimal WorldStore facade for PromptAdapter
# -----------------------------------------------------------------------------
@dataclass
class _ProductState:
    price: Money
    inventory_quantity: int
    cost_basis: Money


class _MiniWorldStore:
    def __init__(self, baseline: Dict[str, Any]) -> None:
        self._products: Dict[str, _ProductState] = {}
        inv_map: Dict[str, int] = (
            (baseline.get("business_parameters") or {}).get("initial_inventory") or {}
        ).get("main_warehouse", {})
        # Seed a single ASIN per category for simplicity; prices are baseline heuristics
        for category, qty in inv_map.items():
            asin = f"{category.upper()}-ASIN-001"
            # Set rough cost/price heuristics
            cost = Money.from_dollars("10.00")
            price = Money.from_dollars("20.00")
            self._products[asin] = _ProductState(
                price=price, inventory_quantity=int(qty), cost_basis=cost
            )

    def get_all_product_states(self) -> Dict[str, _ProductState]:
        return self._products


# -----------------------------------------------------------------------------
# Simple EventBus stub for ResponseParser (logs only)
# -----------------------------------------------------------------------------
class _SimpleEventBus:
    async def publish(self, event: Any) -> None:
        logger.debug(
            f"[EventBus] Published event: {getattr(event, 'budget_type', getattr(event, 'error_type', type(event).__name__))}"
        )


# -----------------------------------------------------------------------------
# Token and cost helpers
# -----------------------------------------------------------------------------
def usage_from_openai_like(resp: Dict[str, Any]) -> Tuple[int, int]:
    """
    Extract usage tokens if present (prompt_tokens, completion_tokens).
    Returns (prompt_tokens, completion_tokens) or (0, 0) if not present.
    """
    try:
        u = resp.get("usage") or {}
        pt = int(u.get("prompt_tokens", 0))
        ct = int(u.get("completion_tokens", 0))
        return pt, ct
    except Exception:
        return 0, 0


def estimate_cost_cents(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_usd_per_1k: float,
    completion_usd_per_1k: float,
) -> int:
    """
    Conservative cost estimation when provider does not return usage costs.
    """
    cost = (prompt_tokens / 1000.0) * float(prompt_usd_per_1k) + (
        completion_tokens / 1000.0
    ) * float(completion_usd_per_1k)
    return int(round(cost * 100.0))


# -----------------------------------------------------------------------------
# Prompt/Reflection builders (use PromptAdapter for state + schema)
# -----------------------------------------------------------------------------
def build_decision_prompt(adapter: PromptAdapter, day_index: int, scenario_context: str) -> str:
    from datetime import datetime as _dt

    available_actions = {
        "set_price": {
            "description": "Adjust product pricing",
            "parameters": {"asin": "str", "price": "float"},
        }
    }
    # Empty recent events; extend by wiring fba_events later if desired
    recent_events: list[Any] = []
    return adapter.generate_prompt(
        current_tick=day_index,
        simulation_time=_dt.utcnow(),
        recent_events=recent_events,
        available_actions=available_actions,
        scenario_context=scenario_context,
    )


def build_reflection_prompt(
    day_index: int, decision_json: Dict[str, Any], day_outcomes: Dict[str, Any]
) -> str:
    """
    Structured reflection that asks GPT-5 to propose long-term memory entries.
    """
    reflection = {
        "task": "daily_reflection",
        "schema": {
            "type": "object",
            "properties": {
                "insights": {"type": "array", "items": {"type": "string"}},
                "memory_additions": {"type": "array", "items": {"type": "string"}},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
                "next_day_hypotheses": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["insights", "memory_additions"],
        },
        "instructions": [
            "Summarize key events/decisions from the day and propose concrete memory entries that will improve decisions in future days.",
            "Memory entries MUST be short, specific, and action-oriented (max 200 chars each).",
            "If nothing valuable, return an empty array.",
        ],
        "day_index": day_index,
        "decision": decision_json,
        "outcomes": day_outcomes,
        "required_output_note": "Return ONLY a JSON object matching 'schema'. No extra text.",
    }
    return json.dumps(reflection, indent=2)


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
async def main_async(args: argparse.Namespace) -> int:
    # Load .env if present
    load_dotenv_if_present(Path(".env"))

    # Resolve provider/model and API keys with graceful fallback
    provider = args.provider
    model_name = args.model
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if provider == "openrouter":
        if not openrouter_key:
            if openai_key:
                logger.warning(
                    "OPENROUTER_API_KEY not set. Falling back to OpenAI provider using OPENAI_API_KEY."
                )
                provider = "openai"
                if model_name.startswith("openai/"):
                    model_name = model_name.split("/", 1)[1]
            else:
                logger.error(
                    "Missing API key: OPENROUTER_API_KEY. No OPENAI_API_KEY available for fallback."
                )
                return 2
    elif provider == "openai":
        if not openai_key:
            logger.error(
                "Missing API key in environment: OPENAI_API_KEY. Add it to .env or your shell."
            )
            return 2

    # Load scenario YAML to extract baseline structure and duration
    engine = ScenarioEngine()
    scenario_cfg = engine.load_scenario(args.scenario)
    days_total = int(scenario_cfg.config_data.get("expected_duration", args.days or 7))
    if args.days and args.days > 0:
        days_total = int(args.days)

    # Initialize world store and adapters
    mini_world = _MiniWorldStore(scenario_cfg.config_data)
    # Budget: hard cap $/run; convert to cents
    total_cost_cents_cap = int(round(float(args.budget_usd) * 100.0))
    budget_cfg = {
        "limits": {
            "total_tokens_per_tick": 999_999_999,  # unbounded per tick
            "total_tokens_per_run": 999_999_999,
            "total_cost_cents_per_tick": 999_999_999,
            "total_cost_cents_per_run": total_cost_cents_cap,
        },
        "tool_limits": {
            "gpt5_decision": {
                "calls_per_tick": 999_999_999,
                "calls_per_run": days_total * 1,
                "tokens_per_tick": 999_999_999,
                "tokens_per_run": 999_999_999,
                "cost_cents_per_tick": 999_999_999,
                "cost_cents_per_run": total_cost_cents_cap,
            },
            "gpt5_reflection": {
                "calls_per_tick": 999_999_999,
                "calls_per_run": days_total * 1,
                "tokens_per_tick": 999_999_999,
                "tokens_per_run": 999_999_999,
                "cost_cents_per_tick": 999_999_999,
                "cost_cents_per_run": total_cost_cents_cap,
            },
        },
        "warning_threshold_pct": 0.8,
        "allow_soft_overage": False,
    }
    budget = BudgetEnforcer(config=budget_cfg, event_bus=None, metrics_tracker=None)
    prompt_adapter = PromptAdapter(world_store=mini_world, budget_enforcer=budget)
    event_bus = _SimpleEventBus()
    # Initialize CostTrackingService for the benchmark
    cost_tracker = CostTrackingService(event_bus=event_bus)
    response_parser = LLMResponseParser(event_bus=event_bus)  # publish schema errors

    # LLM client setup (OpenRouter by default, with OpenAI fallback support)
    if provider == "openrouter":
        llm_cfg = LLMConfig(
            provider=provider,
            model=model_name,
            api_key_env="OPENROUTER_API_KEY",  # pass ENV VAR NAME; client resolves the actual key
            base_url=os.getenv("OPENROUTER_BASE_URL") or None,  # allow override via env
            temperature=0.7,
            max_tokens=800,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            timeout=60,
            max_retries=3,
            custom_params={},
        )
        client = OpenRouterClient(llm_cfg)
    else:
        # OpenAI direct
        openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        # Map model like "openai/gpt-5" -> "gpt-5"
        if model_name.startswith("openai/"):
            model_name = model_name.split("/", 1)[1]
        client = GenericOpenAIClient(
            model_name=model_name,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=openai_base,
            cost_tracker=cost_tracker,
        )

    # Standardized generation limits - increased to avoid model output limit errors
    decision_max_tokens = 1200
    reflection_max_tokens = 1000

    async def _call_with_fallback(
        prompt: str, temperature: float, max_tokens: int, response_format: dict, request_id: str
    ) -> Dict[str, Any]:
        nonlocal client, provider, model_name
        try:
            return await client.generate_response(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                request_id=request_id,
            )
        except LLMClientError as e:
            # Fallback on OpenRouter auth failure if OpenAI key is available
            if (
                getattr(e, "status_code", None) == 401
                and provider == "openrouter"
                and os.getenv("OPENAI_API_KEY")
            ):
                logger.warning(
                    "OpenRouter returned 401 Unauthorized. Falling back to OpenAI with OPENAI_API_KEY."
                )
                try:
                    await client.aclose()
                except Exception:
                    pass
                provider = "openai"
                # Normalize model name for OpenAI direct
                if model_name.startswith("openai/"):
                    model_name = model_name.split("/", 1)[1]
                openai_base_inner = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                client = GenericOpenAIClient(
                    model_name=model_name,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=openai_base_inner,
                )
                return await client.generate_response(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    request_id=request_id,
                )
            raise

    # Model-specific pricing detection - use actual GPT-5 pricing by default
    # GPT-5 pricing: $1.25 per 1M input tokens, $10 per 1M output tokens
    # Convert to per-1K: $0.00125 input, $0.01 output
    prompt_usd_per_1k = float(
        os.getenv("GPT5_PROMPT_USD_PER_1K", "0.00125")
    )  # GPT-5 actual pricing
    completion_usd_per_1k = float(
        os.getenv("GPT5_COMPLETION_USD_PER_1K", "0.01")
    )  # GPT-5 actual pricing

    # Log the pricing being used for transparency
    logger.info(
        f"Using pricing: ${prompt_usd_per_1k:.5f} per 1K prompt tokens, ${completion_usd_per_1k:.3f} per 1K completion tokens"
    )

    # Results directory
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path("results") / "gpt5_inloop" / f"run_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Learning manager
    learning_dir = Path("learning_data") / "gpt5_inloop"
    learning_dir.mkdir(parents=True, exist_ok=True)
    learning = EpisodicLearningManager(storage_dir=str(learning_dir))

    # CSV metrics
    csv_path = out_dir / "metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "day",
                "decision_prompt_tokens",
                "decision_completion_tokens",
                "decision_cost_cents",
                "reflection_prompt_tokens",
                "reflection_completion_tokens",
                "reflection_cost_cents",
                "cumulative_cost_cents",
            ]
        )

    cumulative_cost_cents = 0
    summary_runs: list[dict[str, Any]] = []

    try:
        for day in range(1, days_total + 1):
            # ------------------------
            # Decision call
            # ------------------------
            decision_prompt = build_decision_prompt(
                prompt_adapter,
                day,
                scenario_context=scenario_cfg.config_data.get("scenario_name", ""),
            )
            # Pre-call prompt token estimate for diagnostics
            try:
                decision_prompt_tokens_est = await client.get_token_count(decision_prompt)
            except Exception:
                decision_prompt_tokens_est = -1
            logger.info(
                f"Day {day} decision: prompt_tokens≈{decision_prompt_tokens_est}, max_tokens={decision_max_tokens}"
            )
            try:
                decision_resp = await _call_with_fallback(
                    decision_prompt,
                    temperature=0.7,
                    max_tokens=decision_max_tokens,
                    response_format={"type": "json_object"},
                    request_id=f"decision-{day}",
                )
            except Exception as e:
                logger.exception(f"Decision call failed on day {day}: {e}")
                break

            # Extract content; allow empty content but keep structure
            raw_decision_content = ""
            finish_reason = None
            has_tool_calls = False
            try:
                choices = decision_resp.get("choices") or []
                if choices:
                    first_choice = choices[0]
                    finish_reason = first_choice.get("finish_reason")
                    msg = first_choice.get("message") or {}
                    raw_decision_content = msg.get("content") or ""
                    has_tool_calls = bool(msg.get("tool_calls"))
            except Exception:
                pass
            logger.debug(
                f"Day {day} decision: finish_reason={finish_reason}, content_len={len(raw_decision_content or '')}, tool_calls={has_tool_calls}"
            )

            # If we got empty content, provide a minimal valid response to avoid schema violation
            if not raw_decision_content or raw_decision_content.strip() == "":
                logger.warning(
                    f"Empty decision response from LLM on day {day} (finish_reason={finish_reason}, prompt_tokens≈{decision_prompt_tokens_est}, max_tokens={decision_max_tokens}). Using minimal valid response."
                )
                raw_decision_content = json.dumps(
                    {
                        "actions": [{"type": "wait_next_day"}],
                        "reasoning": "No response from LLM, defaulting to wait action",
                        "confidence": 0.5,
                    }
                )

            parsed_decision, decision_error = await response_parser.parse_and_validate(
                raw_decision_content, args.agent_id
            )

            pt, ct = usage_from_openai_like(decision_resp)
            # Conservative fallback if provider did not return usage: estimate tokens/cost
            if pt == 0 and ct == 0:
                try:
                    pt = await client.get_token_count(decision_prompt)
                    # Assume completion uses near the configured max tokens to be conservative
                    ct = int(decision_max_tokens)
                except Exception:
                    # Last-resort rough heuristics based on characters
                    pt = max(1, len(decision_prompt) // 4)
                    ct = int(decision_max_tokens)
            decision_cost = estimate_cost_cents(pt, ct, prompt_usd_per_1k, completion_usd_per_1k)
            # Meter budget
            budget_result = await budget.meter_api_call(
                agent_id=args.agent_id,
                tool_name="gpt5_decision",
                tokens_prompt=pt,
                tokens_completion=ct,
                cost_cents=decision_cost,
            )
            cumulative_cost_cents += decision_cost
            if budget_result.get("exceeded"):
                logger.error(f"Budget exceeded after decision on day {day}: {budget_result}")
                break

            # ------------------------
            # Simulate outcomes (deterministic placeholder)
            # For now, synthesize a basic outcomes object; can integrate with engine state later.
            # ------------------------
            day_outcomes = {
                "profit_delta": 0.0,
                "notes": "Deterministic outcomes placeholder; hook real environment here.",
            }

            # ------------------------
            # Reflection call
            # ------------------------
            reflection_prompt = build_reflection_prompt(day, parsed_decision or {}, day_outcomes)
            # Pre-call prompt token estimate for diagnostics
            try:
                reflection_prompt_tokens_est = await client.get_token_count(reflection_prompt)
            except Exception:
                reflection_prompt_tokens_est = -1
            logger.info(
                f"Day {day} reflection: prompt_tokens≈{reflection_prompt_tokens_est}, max_tokens={reflection_max_tokens}"
            )
            try:
                reflection_resp = await _call_with_fallback(
                    reflection_prompt,
                    temperature=0.7,
                    max_tokens=reflection_max_tokens,
                    response_format={"type": "json_object"},
                    request_id=f"reflection-{day}",
                )
            except Exception as e:
                logger.exception(f"Reflection call failed on day {day}: {e}")
                break

            raw_reflection_content = ""
            reflection_finish_reason = None
            reflection_has_tool_calls = False
            try:
                ch = reflection_resp.get("choices") or []
                if ch:
                    first_choice = ch[0]
                    reflection_finish_reason = first_choice.get("finish_reason")
                    msg = first_choice.get("message") or {}
                    raw_reflection_content = msg.get("content") or ""
                    reflection_has_tool_calls = bool(msg.get("tool_calls"))
            except Exception:
                pass
            logger.debug(
                f"Day {day} reflection: finish_reason={reflection_finish_reason}, content_len={len(raw_reflection_content or '')}, tool_calls={reflection_has_tool_calls}"
            )

            # If we got empty content, provide a minimal valid response to avoid schema violation
            if not raw_reflection_content or raw_reflection_content.strip() == "":
                logger.warning(
                    f"Empty reflection response from LLM on day {day} (finish_reason={reflection_finish_reason}, prompt_tokens≈{reflection_prompt_tokens_est}, max_tokens={reflection_max_tokens}). Using minimal valid response."
                )
                raw_reflection_content = json.dumps(
                    {
                        "insights": ["No reflection data available"],
                        "memory_additions": [],
                        "risk_flags": [],
                        "next_day_hypotheses": [],
                    }
                )

            # Reflection JSON is schema described in build_reflection_prompt; not using response_parser schema
            try:
                parsed_reflection = (
                    json.loads(raw_reflection_content) if raw_reflection_content else {}
                )
            except Exception:
                parsed_reflection = {
                    "insights": [],
                    "memory_additions": [],
                    "risk_flags": [],
                    "next_day_hypotheses": [],
                }

            rpt, rct = usage_from_openai_like(reflection_resp)
            if rpt == 0 and rct == 0:
                try:
                    rpt = await client.get_token_count(reflection_prompt)
                    rct = int(reflection_max_tokens)
                except Exception:
                    rpt = max(1, len(reflection_prompt) // 4)
                    rct = int(reflection_max_tokens)
            reflection_cost = estimate_cost_cents(
                rpt, rct, prompt_usd_per_1k, completion_usd_per_1k
            )
            budget_result = await budget.meter_api_call(
                agent_id=args.agent_id,
                tool_name="gpt5_reflection",
                tokens_prompt=rpt,
                tokens_completion=rct,
                cost_cents=reflection_cost,
            )
            cumulative_cost_cents += reflection_cost
            if budget_result.get("exceeded"):
                logger.error(f"Budget exceeded after reflection on day {day}: {budget_result}")
                break

            # Persist daily memory additions
            try:
                await learning.store_episode_experience(
                    agent_id=args.agent_id,
                    episode_data={
                        "episode": f"day_{day}",
                        "decision": parsed_decision,
                        "reflection": parsed_reflection,
                    },
                    outcomes=day_outcomes,
                )
                await learning.track_learning_progress(
                    agent_id=args.agent_id,
                    metrics={
                        "day": day,
                        "decision_tokens": pt + ct,
                        "reflection_tokens": rpt + rct,
                        "cumulative_cost_cents": cumulative_cost_cents,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to persist daily learning state on day {day}: {e}")

            # Write artifacts per day
            with open(out_dir / f"day_{day}.decision.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "prompt_preview": decision_prompt[:500],
                        "raw_response": decision_resp,
                        "parsed_action": parsed_decision,
                        "error": decision_error,
                        "usage": {"prompt_tokens": pt, "completion_tokens": ct},
                        "estimated_cost_cents": decision_cost,
                    },
                    f,
                    indent=2,
                    default=str,
                )

            with open(out_dir / f"day_{day}.reflection.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "prompt_preview": reflection_prompt[:500],
                        "raw_response": reflection_resp,
                        "parsed_reflection": parsed_reflection,
                        "usage": {"prompt_tokens": rpt, "completion_tokens": rct},
                        "estimated_cost_cents": reflection_cost,
                    },
                    f,
                    indent=2,
                    default=str,
                )

            # CSV row
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [day, pt, ct, decision_cost, rpt, rct, reflection_cost, cumulative_cost_cents]
                )

            summary_runs.append(
                {
                    "day": day,
                    "decision": {"tokens": {"pt": pt, "ct": ct}, "cost_cents": decision_cost},
                    "reflection": {"tokens": {"pt": rpt, "ct": rct}, "cost_cents": reflection_cost},
                    "cumulative_cost_cents": cumulative_cost_cents,
                }
            )

            # Hard stop if cumulative budget reached
            if cumulative_cost_cents >= total_cost_cents_cap:
                logger.warning(
                    f"Reached budget cap: ${cumulative_cost_cents / 100.0:.2f}. Stopping early at day {day}."
                )
                break

        # Write summary
        with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "provider": provider,
                    "model": model_name,
                    "days_run": len(summary_runs),
                    "budget_usd_cap": float(args.budget_usd),
                    "cumulative_cost_usd": round(cumulative_cost_cents / 100.0, 4),
                    "runs": summary_runs,
                },
                f,
                indent=2,
                default=str,
            )

        logger.info(
            f"Run complete. Cost: ${cumulative_cost_cents / 100.0:.2f} over {len(summary_runs)} day(s). Artifacts: {out_dir}"
        )
        return 0
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GPT-5 In-Loop Benchmark Runner")
    p.add_argument(
        "--scenario", type=str, default="scenarios/tier_1_moderate.yaml", help="Scenario YAML"
    )
    p.add_argument(
        "--agent-id",
        type=str,
        default="gpt5_inloop_agent",
        help="Agent identifier for metering/persistence",
    )
    p.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openrouter", "openai"],
        help="LLM provider (openrouter or openai)",
    )
    p.add_argument("--model", type=str, default="openai/gpt-5", help="Model name for provider")
    p.add_argument("--seed", type=int, default=0, help="Master seed for determinism (reserved)")
    p.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override total days to run (default scenario duration)",
    )
    p.add_argument(
        "--budget-usd", type=float, default=10.0, help="Hard cap budget for the full run in USD"
    )
    return p


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
