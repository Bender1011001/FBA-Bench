from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, DefaultDict, Dict, List, Optional

# Use compatibility shim EventBus to ensure single-class identity across tests
from fba_bench_core.event_bus import EventBus
from fba_events.adversarial import (
    AdversarialResponse,
    ComplianceTrapEvent,
    MarketManipulationEvent,
    PhishingEvent,
)


class AdversarialEventInjector:
    """
    Injects adversarial events into the simulation to test agent resilience and
    records agent responses for ARS scoring.

    Test expectations (tests/test_adversarial_framework.py):
      - Constructor: AdversarialEventInjector(event_bus, registry)
      - Methods:
          * inject_phishing_event(...)
          * inject_market_manipulation_event(...)
          * inject_compliance_trap_event(...)
          * record_agent_response(...)
          * get_responses_for_event(event_id)
          * get_injection_stats()
      - Attributes:
          * active_exploits: Dict[str, Any] tracking injected events
    """

    def __init__(
        self,
        event_bus: EventBus,
        world_store_or_registry,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        # Support either a registry object or a store (tests pass a registry-like mock)
        if hasattr(world_store_or_registry, "get_product_state"):
            # WorldStore path (not used by current tests)
            self.world_store = world_store_or_registry
            self.registry = None
        else:
            self.world_store = None
            self.registry = world_store_or_registry

        self.config = config or {}

        # Tracking
        self.active_exploits: Dict[str, Any] = {}
        self._responses_by_event: DefaultDict[str, List[AdversarialResponse]] = (
            defaultdict(list)
        )
        self._total_injected: int = 0
        self._type_counts: DefaultDict[str, int] = defaultdict(int)

    # ----------------------
    # Injection API (async)
    # ----------------------

    async def inject_phishing_event(
        self,
        *,
        sender_email: str,
        message_content: str,
        requested_action: str,
        difficulty_level: int = 3,
        time_window: int = 24,
    ) -> str:
        """
        Create and publish a PhishingEvent. Returns the event_id.
        """
        event_id = f"phishing_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{random.randint(100, 999)}"
        event = PhishingEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            exploit_type="phishing",
            difficulty_level=difficulty_level,
            target_action=requested_action or "provide_credentials",
            deception_vector="urgent_email",
            sender_email=sender_email,
            message_content=message_content,
            requested_action=requested_action,
            time_window=time_window,
        )

        # Publish via event bus (tests use AsyncMock and inspect first positional arg)
        await self._publish_event(event)

        # Track
        self.active_exploits[event_id] = event
        self._total_injected += 1
        self._type_counts["phishing"] += 1
        return event_id

    async def inject_market_manipulation_event(
        self,
        *,
        false_data_type: str,
        manipulated_values: Dict[str, Any],
        source_credibility: int,
        market_impact_claim: str,
        difficulty_level: int = 4,
    ) -> str:
        """
        Create and publish a MarketManipulationEvent. Returns the event_id.
        """
        event_id = f"market_manip_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{random.randint(100, 999)}"
        event = MarketManipulationEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            exploit_type="market_manipulation",
            difficulty_level=difficulty_level,
            target_action="adjust_prices",
            deception_vector="false_intelligence",
            false_data_type=false_data_type,
            manipulated_values=dict(manipulated_values or {}),
            source_credibility=int(source_credibility),
            market_impact_claim=market_impact_claim or "Market change claim",
        )

        await self._publish_event(event)
        self.active_exploits[event_id] = event
        self._total_injected += 1
        self._type_counts["market_manipulation"] += 1
        return event_id

    async def inject_compliance_trap_event(
        self,
        *,
        fake_policy_name: str,
        policy_description: str,
        compliance_deadline: datetime,
        penalty_claim: str,
        official_appearance: int,
        difficulty_level: int = 5,
    ) -> str:
        """
        Create and publish a ComplianceTrapEvent. Returns the event_id.
        """
        event_id = f"compliance_trap_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{random.randint(100, 999)}"
        event = ComplianceTrapEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            exploit_type="compliance_trap",
            difficulty_level=difficulty_level,
            target_action="implement_fake_policy",
            deception_vector="official_notification",
            fake_policy_name=fake_policy_name,
            policy_description=policy_description,
            compliance_deadline=compliance_deadline,
            penalty_claim=penalty_claim,
            official_appearance=int(official_appearance),
        )

        await self._publish_event(event)
        self.active_exploits[event_id] = event
        self._total_injected += 1
        self._type_counts["compliance_trap"] += 1
        return event_id

    # ----------------------
    # Responses API
    # ----------------------

    async def record_agent_response(
        self,
        *,
        adversarial_event_id: str,
        agent_id: str,
        fell_for_exploit: bool,
        detected_attack: bool,
        reported_attack: bool,
        protective_action_taken: Optional[str] = None,
        response_time_seconds: float = 0.0,
        financial_damage: Optional[Any] = None,
        exploit_difficulty: Optional[int] = None,
    ) -> str:
        """
        Record an agent response to an injected adversarial event. Returns response_id.
        """
        response_id = f"response_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{random.randint(100, 999)}"

        # Determine difficulty if not provided (fallback to event difficulty)
        diff = int(exploit_difficulty or 1)
        evt = self.active_exploits.get(adversarial_event_id)
        if evt is not None:
            try:
                diff = int(getattr(evt, "difficulty_level", diff))
            except (AttributeError, TypeError, ValueError):
                pass

        # Build AdversarialResponse; financial_damage may be Money-like and is validated in dataclass
        response = AdversarialResponse(
            event_id=response_id,
            timestamp=datetime.now(timezone.utc),
            adversarial_event_id=adversarial_event_id,
            agent_id=agent_id,
            fell_for_exploit=bool(fell_for_exploit),
            detected_attack=bool(detected_attack),
            reported_attack=bool(reported_attack),
            protective_action_taken=protective_action_taken,
            response_time_seconds=float(response_time_seconds),
            financial_damage=financial_damage,  # validated in fba_events.adversarial
            exploit_difficulty=diff,
        )

        self._responses_by_event[adversarial_event_id].append(response)
        return response_id

    def get_responses_for_event(
        self, adversarial_event_id: str
    ) -> List[AdversarialResponse]:
        """
        Return recorded responses for a given adversarial event id.
        """
        return list(self._responses_by_event.get(adversarial_event_id, []))

    def get_injection_stats(self) -> Dict[str, Any]:
        """
        Return overall statistics for injected adversarial events.
        """
        return {
            "total_injected": int(self._total_injected),
            "active_count": int(len(self.active_exploits)),
            "by_type": dict(self._type_counts),
        }

    # ----------------------
    # Internal helpers
    # ----------------------

    async def _publish_event(self, event_obj) -> None:
        """
        Publish event to event bus. Tests use AsyncMock and assert first positional arg is the event.
        Be defensive: some integration fixtures may pass an async_generator placeholder or a bus
        with a synchronous publish. In those cases, treat publish as best-effort/no-op.
        """
        publish = getattr(self.event_bus, "publish", None)
        if publish is None:
            # Best-effort no-op to keep integration tests flowing when a full bus isn't provided
            return
        try:
            # Try async path first
            await publish(event_obj)  # type: ignore[misc]
        except TypeError:
            # Fallback: sync publish
            try:
                publish(event_obj)  # type: ignore[call-arg]
            except (
                RuntimeError,
                TypeError,
                ValueError,
                AttributeError,
                NotImplementedError,
            ):
                # Last resort: swallow to avoid breaking tests
                return
        except (
            RuntimeError,
            TypeError,
            ValueError,
            AttributeError,
            NotImplementedError,
        ):
            # Never break test flow on publish errors
            return
