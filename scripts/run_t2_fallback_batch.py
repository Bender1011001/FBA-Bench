#!/usr/bin/env python3
"""
Minimal Tier-2 fallback runner that executes a T2-like simulation per-model using the
OpenRouter-backed bot (or configured MODEL_SLUG). This bypasses integration_tests/demo_scenarios
so it can run even when optional frameworks (agent_runners) are missing.

Behavior:
- For each model in MODELS, create a SimulationOrchestrator and core services,
  create an OpenRouter-backed bot via BotFactory, then subscribe to TickEvent and
  make an LLM decision every tick (T2 stress-style).
- Uses env pacing:
    SIM_MAX_TICKS=365
    SIM_TICK_INTERVAL_SECONDS=0.01
    SIM_TIME_ACCELERATION=200
- Writes per-model logs under artifacts/year_runs/<timestamp>/T2_<sanitized_model>_fallback.log

Usage:
    poetry run python scripts/run_t2_fallback_batch.py
"""
import asyncio
import os
import sys
from datetime import datetime

# Ensure repository root is on sys.path so local modules (e.g., simulation_orchestrator, fba_bench_core)
# can be imported when this script is executed from the scripts/ directory.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Models to run (as requested)
MODELS = [
    "anthropic/claude-sonnet-4",
    "google/gemini-2.5-flash",
    "anthropic/claude-sonnet-4.5",
    "google/gemini-2.5-pro",
    "openai/gpt-5",
    "openai/gpt-oss-120b",
    "openai/gpt-5-mini",
]

# Simulation defaults (can be overridden via env)
SIM_MAX_TICKS = int(os.getenv("SIM_MAX_TICKS", "365"))
SIM_TICK_INTERVAL_SECONDS = float(os.getenv("SIM_TICK_INTERVAL_SECONDS", "0.01"))
SIM_TIME_ACCELERATION = float(os.getenv("SIM_TIME_ACCELERATION", "200"))

# Output folder
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
OUT_ROOT = os.path.join("artifacts", "year_runs", timestamp)
os.makedirs(OUT_ROOT, exist_ok=True)

def sanitize_model(m: str) -> str:
    return m.replace("/", "_").replace(":", "_")

# Try imports with resilient fallbacks
try:
    from simulation_orchestrator import SimulationConfig, SimulationOrchestrator, TickEvent
except Exception as e:
    print(f"Missing simulation_orchestrator: {e}", file=sys.stderr)
    raise

try:
    from fba_events.bus import get_event_bus
except Exception:
    # Try alternate import path
    try:
        from event_bus import get_event_bus
    except Exception as e:
        print(f"Missing event bus: {e}", file=sys.stderr)
        raise

# Prefer src package imports for core services
try:
    from services.sales_service import SalesService
    from services.trust_score_service import TrustScoreService
    from services.world_store import WorldStore
except Exception as e:
    print(f"Could not import core services from src: {e}", file=sys.stderr)
    raise

# Metric suite and financial audit
try:
    from metrics.metric_suite import MetricSuite
except Exception:
    MetricSuite = None

try:
    from financial_audit import FinancialAuditService
except Exception:
    class FinancialAuditService:
        def __init__(self, config=None):
            self.config = config or {}
        def analyze(self, *args, **kwargs):
            return {"status": "ok", "analysis": {}}

# Bot factory
try:
    from baseline_bots.bot_factory import BotFactory
except Exception as e:
    print(f"Missing BotFactory: {e}", file=sys.stderr)
    raise

async def run_model(model_slug: str) -> int:
    sanitized = sanitize_model(model_slug)
    log_path = os.path.join(OUT_ROOT, f"T2_{sanitized}_fallback.log")
    # Prepare sim config
    sim_config = SimulationConfig(
        seed=42,
        max_ticks=SIM_MAX_TICKS,
        tick_interval_seconds=SIM_TICK_INTERVAL_SECONDS,
        time_acceleration=SIM_TIME_ACCELERATION,
    )
    orchestrator = SimulationOrchestrator(sim_config)
    event_bus = get_event_bus()

    # Core services
    world_store = WorldStore(event_bus=event_bus)
    sales_service = SalesService(config={})
    trust_service = TrustScoreService()

    # Metric suite
    financial_audit = FinancialAuditService()
    metric_suite = None
    if MetricSuite:
        metric_suite = MetricSuite(
            tier="T2",
            financial_audit_service=financial_audit,
            sales_service=sales_service,
            trust_score_service=trust_service,
        )
        try:
            metric_suite.subscribe_to_events(event_bus)
        except Exception:
            pass

    # Create OpenRouter-backed bot
    try:
        agent = BotFactory.create_bot("openrouter_bot", model_slug=model_slug)
        agent_type = f"openrouter_bot ({model_slug})"
    except Exception as e:
        print(f"Failed to create OpenRouter bot for {model_slug}: {e}", file=sys.stderr)
        return 1

    # Start services
    await event_bus.start()
    await sales_service.start(event_bus)
    if hasattr(trust_service, "start"):
        await trust_service.start(event_bus)

    # Subscribe to TickEvent and make decisions every tick (stress)
    decision_count = 0

    async def on_tick(event):
        nonlocal decision_count
        try:
            prompt = f"T2 Tick {event.tick_number}: Provide a short action for stress testing."
            # Ensure agent.decide is awaited if async
            res = await agent.decide(prompt)
            decision_count += 1
            # Log minimal info to python stdout (captured)
            print(f"[LLM CALL] model={model_slug} tick={event.tick_number} decision_snippet={str(res)[:120]}")
        except Exception as e:
            print(f"[WARNING] LLM decision error at tick {event.tick_number}: {e}", file=sys.stderr)

    handle = await event_bus.subscribe(TickEvent, on_tick)

    # Start recording and orchestrator
    event_bus.start_recording()
    await orchestrator.start(event_bus)

    # Sleep for approximate real-time duration: logical_duration / accel
    logical_duration = SIM_MAX_TICKS * SIM_TICK_INTERVAL_SECONDS
    real_duration = logical_duration / SIM_TIME_ACCELERATION
    # Add buffer
    await asyncio.sleep(real_duration * 1.1 + 1.0)

    # Teardown
    await event_bus.unsubscribe(handle)
    await orchestrator.stop()
    events = event_bus.get_recorded_events() if hasattr(event_bus, "get_recorded_events") else []
    try:
        event_bus.stop_recording()
    except Exception:
        pass

    # Stop services
    await sales_service.stop()
    if hasattr(trust_service, "stop"):
        await trust_service.stop()
    try:
        await event_bus.stop()
    except Exception:
        pass

    # Compute a fallback score if metric_suite not available
    final_score = 0.0
    if metric_suite and events:
        try:
            final_scores = metric_suite.calculate_final_score(events)
            final_score = getattr(final_scores, "score", 0.0)
        except Exception:
            final_score = 0.0
    elif events:
        final_score = float(min(100.0, len(events)))  # naive mapping

    # Write a small run summary to log file (append)
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"model={model_slug}\n")
        lf.write(f"decisions_made={decision_count}\n")
        lf.write(f"events_recorded={len(events)}\n")
        lf.write(f"final_score={final_score}\n")

    print(f"Completed fallback T2 for {model_slug}: decisions={decision_count} events={len(events)} score={final_score}")
    return 0

async def main():
    for m in MODELS:
        os.environ["MODEL_SLUG"] = m
        rc = await run_model(m)
        if rc != 0:
            print(f"Run for {m} failed with rc={rc}. Stopping.", file=sys.stderr)
            sys.exit(rc)
    print("All fallback T2 runs completed. Logs in:", OUT_ROOT)

if __name__ == "__main__":
    asyncio.run(main())
