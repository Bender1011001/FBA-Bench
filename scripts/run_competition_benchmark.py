#!/usr/bin/env python3
"""
Multi-Agent Competition Benchmark Runner
=========================================
Runs all registered agents simultaneously in a single shared simulation,
with live leaderboard standings injected into every agent's prompt each tick
via PromptTemplates.competition_mode_template.

Features
--------
* Real LLM calls only   — every decision comes from a live OpenRouter API call
* Full recording        — every tick's prompt, raw response, usage, and standings
                          are saved to recording.json so the run is never wasted
* Deterministic replay  — pass --replay <recording.json> to replay any prior run
                          using the cached real responses; zero additional API cost
* New-baseline mode     — pass --new-baseline to invalidate golden masters after
                          the PromptTemplates adversarial-warning change

Usage
-----
  # Live run
  python scripts/run_competition_benchmark.py \
      --scenario scenarios/tier_1_moderate.yaml \
      --days 14 --seed 42 --budget-usd 50

  # Replay a previous run for free
  python scripts/run_competition_benchmark.py \
      --replay results/competition/run_20260221-120000/recording.json

  # Establish a new baseline
  python scripts/run_competition_benchmark.py \
      --scenario scenarios/tier_1_moderate.yaml \
      --days 14 --seed 42 --new-baseline

Output
------
  results/competition/run_<timestamp>/
    recording.json      — full tick-by-tick record (prompt, raw response, usage, standings)
    leaderboard.json    — final ranked results
    summary.json        — run metadata, total cost, baseline status
    metrics.csv         — per-agent per-day profit/cost table
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import json
import logging
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient
from llm_interface.response_parser import LLMResponseParser
from llm_interface.prompt_templates import PromptTemplates

logger = logging.getLogger("competition_benchmark")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

def _setup_file_logging(log_path: Path) -> None:
    """Add a FileHandler so output is captured even when stdout is /dev/null."""
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"))
    logging.getLogger().addHandler(fh)

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------
COMPETITION_AGENTS: List[Dict[str, Any]] = [
    {
        "id": "agent-claude-sonnet",
        "name": "Claude Sonnet 4.6",
        "avatar": "⚡",
        "color": "#d97757",
        "model": "anthropic/claude-sonnet-4-6",
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": None,
    },
    {
        "id": "agent-claude-opus",
        "name": "Claude Opus 4.6",
        "avatar": "🔮",
        "color": "#9b59b6",
        "model": "anthropic/claude-opus-4-6",
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": None,
    },
    {
        "id": "agent-gpt4o-mini",
        "name": "GPT-4o Mini",
        "avatar": "🧠",
        "color": "#10a37f",
        "model": "openai/gpt-4o-mini",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": None,
    },
    {
        "id": "agent-gpt35",
        "name": "GPT-3.5 Turbo",
        "avatar": "💬",
        "color": "#74aa9c",
        "model": "openai/gpt-3.5-turbo",
        "temperature": 0.8,
        "top_p": 1.0,
        "max_tokens": None,
    },
    {
        "id": "agent-grok4",
        "name": "Grok 4.1 Fast",
        "avatar": "𝕏",
        "color": "#000000",
        "model": "x-ai/grok-4.1-fast",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": None,
    },
    {
        "id": "agent-gemini-31-pro",
        "name": "Gemini 3.1 Pro Preview",
        "avatar": "♊",
        "color": "#1a73e8",
        "model": "google/gemini-3.1-pro-preview",
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": None,
    },
    # --- Free / community models removed: caused rate-limit failures ---
    # openai/gpt-oss-120b:free       — rate-limited, degraded quality
    # qwen/qwen3-coder:free          — rate-limited, degraded quality
    # nousresearch/hermes-3-llama-3.1-405b:free — rate-limited
    # GLM-4.5 Air                    — malformed JSON responses
    # DeepSeek R1 free tier          — routinely exceeds 120s timeout
    {
        "id": "agent-minimax-m25",
        "name": "MiniMax M2.5",
        "avatar": "🔺",
        "color": "#ff6b35",
        "model": "minimax/minimax-m2.5",
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": None,
    },
    # Kimi K2.5 removed — schema validation errors (missing reasoning/confidence fields)
    {
        "id": "agent-greedy-script",
        "name": "Greedy Script (baseline)",
        "avatar": "🤖",
        "color": "#666666",
        "model": None,  # rule-based, no LLM
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 0,
    },
]

# ---------------------------------------------------------------------------
# Minimal event bus stub (only needed so LLMResponseParser can publish errors)
# ---------------------------------------------------------------------------
class _NullEventBus:
    async def publish(self, *args: Any, **kwargs: Any) -> None:
        pass

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    agent_id: str
    agent_name: str
    cumulative_profit_cents: int = 0
    cumulative_revenue_cents: int = 0
    units_sold: int = 0
    current_price: float = 20.0
    cost_basis: float = 10.0
    inventory: int = 500
    rank: int = 0
    trend: str = "─"

    @property
    def cumulative_profit_usd(self) -> float:
        return self.cumulative_profit_cents / 100.0

    def to_standings_entry(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "agent_name": self.agent_name,
            "cumulative_profit_usd": self.cumulative_profit_usd,
            "units_sold": self.units_sold,
            "trend": self.trend,
        }

# ---------------------------------------------------------------------------
# Market simulation (not LLM — this is the demand model)
# ---------------------------------------------------------------------------

def _greedy_price(state: AgentState) -> float:
    """Rule-based price for the non-LLM baseline agent."""
    target_margin = 0.40
    if state.inventory > 700:
        target_margin = 0.20
    elif state.inventory < 150:
        target_margin = 0.60
    return state.cost_basis / (1.0 - target_margin)


def _simulate_sales(price: float, cost: float, inventory: int, rng: random.Random) -> int:
    """Simple price-elastic demand model shared by all agents."""
    base_demand = 30
    elasticity = 2.0
    margin_ratio = (price - cost) / price if price > 0 else 0
    demand = max(0, base_demand - int(elasticity * margin_ratio * base_demand))
    return min(max(0, demand + rng.randint(-3, 3)), inventory)


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

def _rank_agents(states: Dict[str, AgentState]) -> None:
    previous = {aid: s.rank for aid, s in states.items()}
    ordered = sorted(states.values(), key=lambda s: s.cumulative_profit_cents, reverse=True)
    for i, s in enumerate(ordered, 1):
        prev = previous.get(s.agent_id, i)
        s.trend = "▲" if i < prev else ("▼" if i > prev else "─")
        s.rank = i


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    tick: int,
    days_total: int,
    sim_time: datetime.datetime,
    states: Dict[str, AgentState],
    agent_id: str,
    total_cost_cents: int,
    total_cost_cents_cap: int,
    available_actions: Dict[str, Any],
    required_output_format: str,
) -> str:
    state = states[agent_id]
    portfolio = "\\n".join([
        f"  ASIN:      COMP-{agent_id[-6:].upper()}",
        f"  Price:     ${state.current_price:.2f}",
        f"  Cost:      ${state.cost_basis:.2f}",
        f"  Inventory: {state.inventory} units",
        f"  Margin:    {((state.current_price - state.cost_basis) / state.current_price * 100):.1f}%",
    ])
    context: Dict[str, Any] = {
        "current_tick": tick,
        "days_total": days_total,
        "simulation_time": sim_time,
        "budget_status": (
            f"BUDGET: ${total_cost_cents / 100.0:.2f} spent of "
            f"${total_cost_cents_cap / 100.0:.2f} cap"
        ),
        "product_portfolio": portfolio,
        "recent_events": "Market is active. All competitors are pricing dynamically.",
        "available_actions": json.dumps(available_actions, indent=2),
        "required_output_format": required_output_format,
        "competition_standings": [
            s.to_standings_entry()
            for s in sorted(states.values(), key=lambda x: x.rank)
        ],
    }
    return PromptTemplates.get_template("competition_mode", context)


# ---------------------------------------------------------------------------
# Cost accounting from OpenRouter usage field
# ---------------------------------------------------------------------------

def _strip_md_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences from an LLM response."""
    import re
    s = text.strip()
    s = re.sub(r"^```[^\n]*\n", "", s)
    s = re.sub(r"\n```$", "", s)
    return s.strip()


def _cost_cents_from_usage(usage: Dict[str, Any]) -> int:
    """
    OpenRouter returns cost in the usage object as cost (USD float) on some models,
    or we fall back to a conservative token-based estimate at ~$0.002 / 1K tokens.
    """
    cost_usd = usage.get("cost")
    if cost_usd is not None:
        try:
            return int(round(float(cost_usd) * 100.0))
        except (TypeError, ValueError):
            pass
    # Fallback: rough estimate
    total_tokens = usage.get("total_tokens", 0)
    return max(1, int(round(total_tokens / 1000.0 * 0.2)))  # $0.002 / 1K tokens


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_competition(args: argparse.Namespace) -> int:
    _load_dotenv(REPO_ROOT / ".env")

    # Set up file logging immediately so nothing is lost if stdout is detached
    if getattr(args, "log_file", None):
        _setup_file_logging(Path(args.log_file))

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "competition" / f"run_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    is_replay = bool(args.replay)
    # agent_id -> tick -> raw response string (populated in replay mode)
    replay_cache: Dict[str, Dict[int, str]] = {}

    if is_replay:
        replay_path = Path(args.replay)
        if not replay_path.exists():
            logger.error(f"Replay file not found: {replay_path}")
            return 2
        logger.info(f"REPLAY MODE — {replay_path}")
        with open(replay_path, "r", encoding="utf-8") as f:
            recording = json.load(f)
        for tick_rec in recording.get("ticks", []):
            tick_num = int(tick_rec["tick"])
            for agent_id, decision in tick_rec.get("agent_decisions", {}).items():
                replay_cache.setdefault(agent_id, {})[tick_num] = decision.get("raw_response", "")
        days_total = int(recording.get("days_total", args.days or 14))
        seed = int(recording.get("seed", args.seed))
        scenario = recording.get("scenario", "replay")
    else:
        days_total = args.days or 14
        seed = args.seed
        scenario = args.scenario or "scenarios/tier_1_moderate.yaml"
        logger.info(f"LIVE MODE — {days_total} days, seed={seed}")

    total_cost_cents_cap = int(round(float(args.budget_usd) * 100.0))
    rng = random.Random(seed)
    parser = LLMResponseParser(event_bus=_NullEventBus())

    # Build one OpenRouterClient per LLM agent
    clients: Dict[str, OpenRouterClient] = {}
    if not is_replay:
        for cfg in COMPETITION_AGENTS:
            if cfg["model"] is None:
                continue
            cfg_kwargs: Dict[str, Any] = {
                "provider": "openrouter",
                "model": cfg["model"],
                "api_key_env": "OPENROUTER_API_KEY",
                "temperature": cfg["temperature"],
                "top_p": cfg["top_p"],
                "timeout": 90.0,
            }
            if cfg["max_tokens"] is not None:
                cfg_kwargs["max_tokens"] = cfg["max_tokens"]
            llm_cfg = LLMConfig(**cfg_kwargs)
            clients[cfg["id"]] = OpenRouterClient(llm_cfg)
            logger.info(f"  Initialized client for {cfg['name']} ({cfg['model']})")

    # Agent states
    states: Dict[str, AgentState] = {
        cfg["id"]: AgentState(agent_id=cfg["id"], agent_name=cfg["name"])
        for cfg in COMPETITION_AGENTS
    }
    _rank_agents(states)

    available_actions = {
        "set_price": {
            "description": "Set a new price for your product.",
            "parameters": {"asin": "string", "price": "float"},
        }
    }
    required_output_format = json.dumps(
        {
            "actions": [{"type": "set_price", "parameters": {"asin": "<ASIN>", "price": 0.00}}],
            "reasoning": "<your strategic reasoning here>",
            "confidence": 0.0,
        },
        indent=2,
    )

    total_cost_cents = 0
    ticks_record: List[Dict[str, Any]] = []

    csv_path = out_dir / "metrics.csv"
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        "day", "agent_id", "agent_name", "rank",
        "price", "units_sold", "day_profit_usd", "cumulative_profit_usd",
        "prompt_tokens", "completion_tokens", "cost_cents", "from_cache",
    ])

    sim_base_date = datetime.datetime(2026, 1, 1, 9, 0, 0)

    # Agents whose clients need rebuilding (after timeout cancellation)
    _rebuild_clients: set = set()

    def _save_recording_incremental() -> None:
        """Write recording.json after every day so a crash never loses completed data."""
        recording_path = out_dir / "recording.json"
        with open(recording_path, "w", encoding="utf-8") as f_rec:
            json.dump({
                "run_id": f"competition_{ts}",
                "started_at": datetime.datetime.utcnow().isoformat() + "Z",
                "scenario": scenario,
                "days_total": days_total,
                "seed": seed,
                "mode": "replay" if is_replay else "live",
                "is_new_baseline": bool(args.new_baseline),
                "agents": [
                    {"id": c["id"], "name": c["name"], "model": c.get("model"), "avatar": c["avatar"]}
                    for c in COMPETITION_AGENTS
                ],
                "ticks": ticks_record,
                "total_cost_cents": total_cost_cents,
                "partial": True,  # overwritten to False when run completes normally
            }, f_rec, indent=2, default=str)

    try:
        for day in range(1, days_total + 1):
            sim_time = sim_base_date + datetime.timedelta(days=day - 1)
            tick = day

            logger.info(f"\\n{'='*62}")
            logger.info(f"  DAY {day:>3} / {days_total}   —   {len(states)} agents")
            logger.info(f"{'='*62}")

            tick_record: Dict[str, Any] = {
                "tick": tick,
                "simulation_time": sim_time.isoformat(),
                "standings_before": [
                    s.to_standings_entry()
                    for s in sorted(states.values(), key=lambda x: x.rank)
                ],
                "agent_decisions": {},
            }

            for cfg in COMPETITION_AGENTS:
                agent_id = cfg["id"]
                state = states[agent_id]
                new_price = state.current_price
                raw_response = ""
                prompt_tokens = 0
                completion_tokens = 0
                llm_cost_cents = 0
                from_cache = False
                parse_error: Optional[str] = None

                if cfg["model"] is None:
                    # Rule-based greedy baseline — no LLM
                    new_price = _greedy_price(state)
                    raw_response = json.dumps({
                        "actions": [{"type": "set_price", "parameters": {
                            "asin": f"COMP-{agent_id[-6:].upper()}",
                            "price": round(new_price, 2),
                        }}],
                        "reasoning": "Greedy rule: target margin based on inventory level.",
                        "confidence": 1.0,
                    })

                elif is_replay and agent_id in replay_cache and tick in replay_cache[agent_id]:
                    # Replay: re-parse the cached real response — no API call
                    raw_response = replay_cache[agent_id][tick]
                    from_cache = True
                    parsed, err = await parser.parse_and_validate(_strip_md_fences(raw_response), agent_id)
                    if err:
                        parse_error = str(err)
                        logger.warning(f"  [{cfg['name']}] replay parse error: {err}")
                    elif parsed and parsed.get("actions"):
                        price_val = parsed["actions"][0].get("parameters", {}).get("price")
                        if isinstance(price_val, (int, float)):
                            new_price = float(price_val)

                else:
                    # Live LLM call via OpenRouter
                    prompt = _build_prompt(
                        tick=tick,
                        days_total=days_total,
                        sim_time=sim_time,
                        states=states,
                        agent_id=agent_id,
                        total_cost_cents=total_cost_cents,
                        total_cost_cents_cap=total_cost_cents_cap,
                        available_actions=available_actions,
                        required_output_format=required_output_format,
                    )
                    client = clients[agent_id]
                    try:
                        # Build call kwargs — omit max_tokens when None (no limit)
                        call_kwargs: Dict[str, Any] = {
                            "prompt": prompt,
                            "temperature": cfg["temperature"],
                            "top_p": cfg["top_p"],
                            "response_format": {"type": "json_object"},
                            "request_id": f"comp-day{day}-{agent_id}",
                        }
                        if cfg["max_tokens"] is not None:
                            call_kwargs["max_tokens"] = cfg["max_tokens"]

                        # Hard wall-clock limit per agent per tick
                        resp = await asyncio.wait_for(
                            client.generate_response(**call_kwargs),
                            timeout=120.0,
                        )
                        raw_response = resp["choices"][0]["message"]["content"] or ""
                        usage = resp.get("usage") or {}
                        prompt_tokens = int(usage.get("prompt_tokens", 0))
                        completion_tokens = int(usage.get("completion_tokens", 0))
                        llm_cost_cents = _cost_cents_from_usage(usage)
                        total_cost_cents += llm_cost_cents

                        # Strip markdown fences before parsing (Claude Opus, etc.)
                        clean_response = _strip_md_fences(raw_response)
                        parsed, err = await parser.parse_and_validate(clean_response, agent_id)
                        if err:
                            parse_error = str(err)
                            logger.warning(f"  [{cfg['name']}] parse error: {err}")
                        elif parsed and parsed.get("actions"):
                            price_val = parsed["actions"][0].get("parameters", {}).get("price")
                            if isinstance(price_val, (int, float)):
                                new_price = float(price_val)

                    except asyncio.TimeoutError:
                        parse_error = "TimeoutError: agent exceeded 120s wall-clock limit"
                        logger.warning(f"  [{cfg['name']}] ⏰ {parse_error} — holding previous price")
                        # Flag for client rebuild — asyncio cancellation can corrupt
                        # the httpx connection pool; rebuild before next day.
                        _rebuild_clients.add(agent_id)
                    except Exception as e:
                        err_str = str(e)
                        if "429" in err_str or "rate" in err_str.lower():
                            parse_error = f"RateLimit(429): {err_str[:120]}"
                            logger.warning(f"  [{cfg['name']}] 🚦 {parse_error} — holding previous price")
                        else:
                            parse_error = err_str
                            logger.error(f"  [{cfg['name']}] LLM call failed: {err_str}")
                        # Hold previous price on all failures

                # Apply price floor, simulate market, update state
                state.current_price = max(state.cost_basis * 1.01, new_price)
                units = _simulate_sales(state.current_price, state.cost_basis, state.inventory, rng)
                day_profit_cents = int(round((state.current_price - state.cost_basis) * units * 100))
                state.cumulative_profit_cents += day_profit_cents
                state.cumulative_revenue_cents += int(round(state.current_price * units * 100))
                state.units_sold += units
                state.inventory = max(0, state.inventory - units)
                if state.inventory < 100:
                    state.inventory += 300  # restock

                tick_record["agent_decisions"][agent_id] = {
                    "raw_response": raw_response,
                    "parse_error": parse_error,
                    "from_cache": from_cache,
                    "new_price": state.current_price,
                    "units_sold": units,
                    "day_profit_cents": day_profit_cents,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "llm_cost_cents": llm_cost_cents,
                }

                logger.info(
                    f"  {cfg['avatar']}  {cfg['name']:<28}  "
                    f"price=${state.current_price:.2f}  "
                    f"sold={units:>3}  "
                    f"+${day_profit_cents/100:.2f}  "
                    f"[{'cache' if from_cache else 'live' if cfg['model'] else 'rule'}]"
                    + (f"  ⚠ {parse_error}" if parse_error else "")
                )

                if total_cost_cents >= total_cost_cents_cap:
                    logger.warning(f"Budget cap ${total_cost_cents_cap/100:.2f} reached. Stopping.")
                    break

            _rank_agents(states)
            ticks_record.append(tick_record)

            # Rebuild any clients whose connections were cancelled by asyncio.wait_for
            if not is_replay and _rebuild_clients:
                for aid in list(_rebuild_clients):
                    cfg_map = {c["id"]: c for c in COMPETITION_AGENTS}
                    cfg_r = cfg_map.get(aid)
                    if cfg_r and cfg_r["model"]:
                        try:
                            await clients[aid].aclose()
                        except Exception:
                            pass
                        cfg_kwargs_r: Dict[str, Any] = {
                            "provider": "openrouter",
                            "model": cfg_r["model"],
                            "api_key_env": "OPENROUTER_API_KEY",
                            "temperature": cfg_r["temperature"],
                            "top_p": cfg_r["top_p"],
                            "timeout": 90.0,
                        }
                        if cfg_r["max_tokens"] is not None:
                            cfg_kwargs_r["max_tokens"] = cfg_r["max_tokens"]
                        llm_cfg_r = LLMConfig(**cfg_kwargs_r)
                        clients[aid] = OpenRouterClient(llm_cfg_r)
                        logger.info(f"  ♻  Rebuilt client for {cfg_r['name']} after timeout")
                _rebuild_clients.clear()

            # Flush incremental recording — data is never lost if we crash mid-run
            _save_recording_incremental()
            csv_file.flush()

            logger.info(f"\\n  🏆  Standings after Day {day}")
            for s in sorted(states.values(), key=lambda x: x.rank):
                bar = "█" * min(28, max(1, int(s.cumulative_profit_usd / 8)))
                logger.info(f"  #{s.rank}  {s.agent_name:<28}  ${s.cumulative_profit_usd:>9,.2f}  {s.trend}  {bar}")

            for cfg in COMPETITION_AGENTS:
                agent_id = cfg["id"]
                s = states[agent_id]
                d = tick_record["agent_decisions"].get(agent_id, {})
                csv_writer.writerow([
                    day, agent_id, cfg["name"], s.rank,
                    s.current_price, d.get("units_sold", 0),
                    d.get("day_profit_cents", 0) / 100.0,
                    s.cumulative_profit_usd,
                    d.get("prompt_tokens", 0),
                    d.get("completion_tokens", 0),
                    d.get("llm_cost_cents", 0),
                    d.get("from_cache", False),
                ])

            if total_cost_cents >= total_cost_cents_cap:
                break

    finally:
        csv_file.close()
        for c in clients.values():
            try:
                await c.aclose()
            except Exception:
                pass

    final_leaderboard = [
        {
            "rank": s.rank,
            "agent_id": s.agent_id,
            "agent_name": s.agent_name,
            "cumulative_profit_usd": s.cumulative_profit_usd,
            "units_sold": s.units_sold,
        }
        for s in sorted(states.values(), key=lambda x: x.rank)
    ]
    completed_at = datetime.datetime.utcnow().isoformat() + "Z"

    # Final recording.json — mark partial=False now that run completed normally
    recording_path = out_dir / "recording.json"
    with open(recording_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": f"competition_{ts}",
            "started_at": datetime.datetime.utcnow().isoformat() + "Z",
            "completed_at": completed_at,
            "scenario": scenario,
            "days_total": days_total,
            "seed": seed,
            "mode": "replay" if is_replay else "live",
            "is_new_baseline": bool(args.new_baseline),
            "agents": [
                {"id": c["id"], "name": c["name"], "model": c.get("model"), "avatar": c["avatar"]}
                for c in COMPETITION_AGENTS
            ],
            "ticks": ticks_record,
            "total_cost_cents": total_cost_cents,
            "partial": False,
        }, f, indent=2, default=str)

    logger.info(f"\\n📼  Recording saved → {recording_path}")

    # leaderboard.json
    leaderboard_path = out_dir / "leaderboard.json"
    with open(leaderboard_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at_utc": completed_at,
            "is_new_baseline": bool(args.new_baseline),
            "prompt_template_version": "competition_mode_v1_with_adversarial_warning",
            "leaderboard": final_leaderboard,
        }, f, indent=2)

    # summary.json
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "mode": "replay" if is_replay else "live",
            "is_new_baseline": bool(args.new_baseline),
            "scenario": scenario,
            "days_run": len(ticks_record),
            "seed": seed,
            "total_cost_usd": round(total_cost_cents / 100.0, 4),
            "budget_cap_usd": args.budget_usd,
            "winner": final_leaderboard[0] if final_leaderboard else None,
            "artifacts": {
                "recording": str(recording_path),
                "leaderboard": str(leaderboard_path),
                "metrics_csv": str(csv_path),
            },
        }, f, indent=2)

    if args.new_baseline:
        marker = REPO_ROOT / "golden_masters" / "BASELINE_INVALIDATED"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "invalidated_at": completed_at,
            "reason": (
                "PromptTemplates updated with CRITICAL WARNING adversarial market context. "
                "All prior golden master scores are outdated."
            ),
            "new_baseline_leaderboard": str(leaderboard_path),
        }, indent=2), encoding="utf-8")
        logger.info(f"🔄  Golden masters invalidated → {marker}")

    logger.info(f"\\n{'='*62}")
    logger.info("  🏆  FINAL LEADERBOARD")
    logger.info(f"{'='*62}")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for e in final_leaderboard:
        logger.info(
            f"  {medals.get(e['rank'], '  ')}  #{e['rank']}  {e['agent_name']:<28}  "
            f"${e['cumulative_profit_usd']:>10,.2f}  ({e['units_sold']} units)"
        )
    logger.info(f"\\n  Total cost: ${total_cost_cents / 100.0:.2f}")
    logger.info(f"  Output:     {out_dir}")
    logger.info(f"  Replay:     python scripts/run_competition_benchmark.py --replay {recording_path}")
    return 0


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run all agents head-to-head with live standings in every prompt."
    )
    p.add_argument("--scenario", type=str, default="scenarios/tier_1_moderate.yaml")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--budget-usd", type=float, default=200.0,
                   help="Hard cost cap in USD (default $200). Use $500+ for full-year runs.")
    p.add_argument("--replay", type=str, default=None, metavar="RECORDING_JSON",
                   help="Replay a prior run for free using cached responses")
    p.add_argument("--new-baseline", action="store_true",
                   help="Invalidate golden masters and tag this run as the new baseline")
    p.add_argument("--log-file", type=str, default=None,
                   help="Write all log output to this file (used when launched detached)")
    return p


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(run_competition(args))
    except KeyboardInterrupt:
        logger.warning("Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
