#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import psutil
from fba_bench_core.money import Money
from redteam.adversarial_event_injector import AdversarialEventInjector
from redteam.exploit_registry import ExploitDefinition, ExploitRegistry
from redteam.resistance_scorer import AdversaryResistanceScorer

from fba_events.bus import InMemoryEventBus as EventBus


@dataclass
class TestEvent:
    seq: int
    created_ts: float
    payload: Dict[str, Any]


async def eventbus_stress_test(total_events: int = 5000, subscribers: int = 1) -> Dict[str, Any]:
    bus = EventBus()
    await bus.start()

    processed = 0
    latencies: List[float] = []
    done = asyncio.Event()

    async def handler(evt: TestEvent) -> None:
        nonlocal processed
        latencies.append(time.perf_counter() - evt.created_ts)
        processed += 1
        if processed >= total_events * subscribers:
            done.set()

    # Subscribe N handlers to the same event type
    subs = []
    for _ in range(subscribers):
        subs.append(await bus.subscribe(TestEvent, handler))

    # Publish events
    t0 = time.perf_counter()
    for i in range(total_events):
        await bus.publish(TestEvent(seq=i, created_ts=time.perf_counter(), payload={"k": i}))
    publish_done = time.perf_counter()

    try:
        await asyncio.wait_for(done.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        pass
    t1 = time.perf_counter()

    # Unsubscribe
    for h in subs:
        await bus.unsubscribe(h)

    await bus.stop()

    published_duration = publish_done - t0
    end_to_end = t1 - t0
    events_per_sec_publish_path = (
        total_events / published_duration if published_duration > 0 else 0.0
    )
    events_per_sec_e2e = (total_events * subscribers) / end_to_end if end_to_end > 0 else 0.0

    lat_ms = [x * 1000.0 for x in latencies]
    avg_lat_ms = (sum(lat_ms) / len(lat_ms)) if lat_ms else 0.0
    p95_ms = sorted(lat_ms)[int(0.95 * len(lat_ms))] if lat_ms else 0.0

    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / (1024 * 1024)

    return {
        "component": "EventBus",
        "total_events": total_events,
        "subscribers": subscribers,
        "publish_duration_s": published_duration,
        "end_to_end_duration_s": end_to_end,
        "publish_throughput_eps": events_per_sec_publish_path,
        "end_to_end_throughput_eps": events_per_sec_e2e,
        "avg_handler_latency_ms": avg_lat_ms,
        "p95_handler_latency_ms": p95_ms,
        "process_memory_mb": mem_mb,
        "processed": processed,
        "expected_processed": total_events * subscribers,
    }


async def money_stress_test(iterations: int = 200000) -> Dict[str, Any]:
    proc = psutil.Process()
    mem_before = proc.memory_info().rss / (1024 * 1024)

    total = Money.zero()
    t0 = time.perf_counter()
    for i in range(iterations):
        # Deterministic set of operations to avoid optimizer weirdness
        a = Money.from_dollars((i % 1000) / 100.0)
        b = Money.from_dollars(((i * 7) % 1000) / 100.0)
        c = a + b
        d = c - a
        # Multiply by small integers to remain exact
        e = d * 2
        # Divide by integer (exact in cents due to rounding)
        f = e // 2
        total = total + f
    t1 = time.perf_counter()

    mem_after = proc.memory_info().rss / (1024 * 1024)
    duration = t1 - t0
    ops = iterations * 6  # a,b,c,d,e,f created/computed per loop
    ops_per_sec = ops / duration if duration > 0 else 0.0

    return {
        "component": "Money",
        "iterations": iterations,
        "duration_s": duration,
        "ops_per_sec": ops_per_sec,
        "final_total_cents": total.cents,
        "memory_delta_mb": mem_after - mem_before,
        "process_memory_mb": mem_after,
    }


async def adversarial_stress_test(injections: int = 2000) -> Dict[str, Any]:
    bus = EventBus()
    await bus.start()

    registry = ExploitRegistry(validation_enabled=False)
    injector = AdversarialEventInjector(bus, registry)
    scorer = AdversaryResistanceScorer()

    # Register a basic phishing exploit to mirror README quickstart
    registry.register_exploit(
        ExploitDefinition(
            name="Perf Phishing",
            author="perf_suite",
            version="1.0.0",
            category="phishing",
            difficulty=3,
            description="Performance harness phishing scenario",
            exploit_type="phishing",
            context_requirements={
                "sender_email": "attacker@example.com",
                "message_content": "Urgent action required",
                "requested_action": "provide_test_info",
            },
        )
    )

    t0 = time.perf_counter()
    # Inject events concurrently in batches to avoid giant task lists
    batch = 200
    event_ids: List[str] = []
    for start in range(0, injections, batch):
        end = min(injections, start + batch)
        tasks = []
        for i in range(start, end):
            tasks.append(
                injector.inject_phishing_event(
                    sender_email="attacker@example.com",
                    message_content=f"Urgent action required {i}",
                    requested_action="provide_test_info",
                    difficulty_level=3,
                    time_window=24,
                )
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, str):
                event_ids.append(r)
    inject_done = time.perf_counter()

    # Generate synthetic responses for all events
    # Alternate between resisted and fell for exploit to simulate mixed outcomes
    resp_tasks = []
    for idx, eid in enumerate(event_ids):
        resp_tasks.append(
            injector.record_agent_response(
                adversarial_event_id=eid,
                agent_id="agent_perf",
                fell_for_exploit=(idx % 5 == 0),  # 20% failure rate
                detected_attack=(idx % 2 == 0),
                reported_attack=(idx % 4 == 0),
                response_time_seconds=float((idx % 90) + 1),
                financial_damage=Money(250) if (idx % 5 == 0) else Money(0),
                exploit_difficulty=3,
            )
        )
    await asyncio.gather(*resp_tasks, return_exceptions=True)
    responses_done = time.perf_counter()

    # Score
    all_responses = []
    for eid in event_ids:
        all_responses.extend(injector.get_responses_for_event(eid))
    score_start = time.perf_counter()
    ars_score, breakdown = scorer.calculate_ars(all_responses)
    score_done = time.perf_counter()

    await bus.stop()

    inject_duration = inject_done - t0
    response_duration = responses_done - inject_done
    scoring_duration = score_done - score_start

    return {
        "component": "AdversarialFramework",
        "injections": injections,
        "inject_duration_s": inject_duration,
        "inject_throughput_eps": injections / inject_duration if inject_duration > 0 else 0.0,
        "responses_recorded": len(all_responses),
        "response_record_duration_s": response_duration,
        "scoring_duration_s": scoring_duration,
        "ars_score": ars_score,
        "ars_breakdown": breakdown.__dict__,
    }


async def main_async(args: argparse.Namespace) -> int:
    results: Dict[str, Any] = {"benchmarks": []}

    if args.eventbus:
        eb = await eventbus_stress_test(
            total_events=args.eventbus_events, subscribers=args.eventbus_subs
        )
        results["benchmarks"].append(eb)

    if args.money:
        mn = await money_stress_test(iterations=args.money_iters)
        results["benchmarks"].append(mn)

    if args.adversarial:
        adv = await adversarial_stress_test(injections=args.adversarial_injections)
        results["benchmarks"].append(adv)

    # Print and persist
    print(json.dumps(results, indent=2, default=str))
    out_path = args.output or f"perf_results/system_stress_results_{int(time.time())}.json"
    # Late import to avoid pathlib dependency in tight loop paths
    from pathlib import Path  # local import

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[system_stress_suite] Results saved to: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="System Stress Suite: EventBus, Money, Adversarial")
    p.add_argument("--output", type=str, default=None, help="Output JSON path")
    p.add_argument("--eventbus", action="store_true", help="Run EventBus stress test")
    p.add_argument("--eventbus-events", type=int, default=5000, help="Total events to publish")
    p.add_argument("--eventbus-subs", type=int, default=1, help="Subscribers per event")
    p.add_argument("--money", action="store_true", help="Run Money stress test")
    p.add_argument("--money-iters", type=int, default=200000, help="Iterations for Money ops")
    p.add_argument(
        "--adversarial", action="store_true", help="Run Adversarial Framework stress test"
    )
    p.add_argument(
        "--adversarial-injections", type=int, default=2000, help="Number of adversarial events"
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
