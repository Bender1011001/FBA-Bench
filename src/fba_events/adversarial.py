"""Auto-generated split module: adversarial from monolithic schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fba_bench_core.money import Money

from .base import BaseEvent

try:
    from .registry import BaseEvent  # preferred
except Exception:
    try:
        from .base import BaseEvent
    except Exception:

        class AdvBaseEvent:  # last-resort shim  # type: ignore[no-redef]
            pass


@dataclass(kw_only=True)
class ShockInjectionEvent(BaseEvent):  # type: ignore[misc]
    shock_id: str = ""
    category: str = ""
    severity: float = 0.0
    timestamp: Optional[datetime] = None  # type: ignore[assignment]


@dataclass(kw_only=True)
class ShockEndEvent(BaseEvent):  # type: ignore[misc]
    shock_id: str = ""
    category: str = ""
    timestamp: Optional[datetime] = None  # type: ignore[assignment]


@dataclass
class ExploitDefinition:
    """
    Definition of an exploit scenario for adversarial testing.

    This class defines the structure and parameters of an exploit that can be
    used by the AdversarialEventInjector to create adversarial events.

    Attributes:
        exploit_id: Unique identifier for this exploit definition
        name: Human-readable name of the exploit
        description: Detailed description of the exploit
        category: Category of the exploit (phishing, market_manipulation, etc.)
        difficulty: Difficulty level (1-5)
        parameters: Dictionary of parameters specific to this exploit type
        success_criteria: Conditions that indicate agent fell for exploit
    """

    exploit_id: str
    name: str
    description: str
    category: str
    difficulty: int
    parameters: Dict[str, Any] = field(default_factory=dict)
    success_criteria: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the exploit definition parameters."""
        if not self.exploit_id:
            raise ValueError("Exploit ID cannot be empty")
        if not self.name:
            raise ValueError("Name cannot be empty")
        if not self.description:
            raise ValueError("Description cannot be empty")
        if not self.category:
            raise ValueError("Category cannot be empty")
        if not 1 <= self.difficulty <= 5:
            raise ValueError("Difficulty must be between 1 and 5")


@dataclass
class AdversarialEvent(BaseEvent):
    """
    Base class for all adversarial/red-team events in the simulation.

    These events test agent resistance to various exploit scenarios including
    phishing, social engineering, market manipulation, and compliance traps.

    Attributes:
        event_id: Unique identifier for this adversarial event
        timestamp: When this adversarial event was triggered
        exploit_type: Type of exploit (phishing, market_manipulation, etc.)
        difficulty_level: Difficulty rating from 1-5
        target_action: What the agent should NOT do if resistant
        deception_vector: How the attack attempts to deceive
        realistic_context: Supporting context to make attack believable
        success_criteria: Conditions that indicate agent fell for exploit
        time_window: How long the attack remains active (hours)
        financial_impact_limit: Maximum financial damage if agent falls for exploit
    """

    exploit_type: str
    difficulty_level: int
    target_action: str
    deception_vector: str
    realistic_context: Dict[str, Any] = field(default_factory=dict)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    time_window: int = 24  # hours
    financial_impact_limit: Optional[Money] = None

    def __post_init__(self):
        super().__post_init__()

        # Validate exploit type
        valid_exploit_types = [
            "phishing",
            "social_engineering",
            "market_manipulation",
            "compliance_trap",
            "financial_exploit",
            "information_warfare",
        ]
        if self.exploit_type not in valid_exploit_types:
            raise ValueError(
                f"Exploit type must be one of {valid_exploit_types}, got {self.exploit_type}"
            )

        # Validate difficulty level
        if not 1 <= self.difficulty_level <= 5:
            raise ValueError("Difficulty level must be between 1 and 5")

        # Validate target action
        if not self.target_action or not isinstance(self.target_action, str):
            raise ValueError("Target action must be a non-empty string")

        # Validate deception vector
        if not self.deception_vector or not isinstance(self.deception_vector, str):
            raise ValueError("Deception vector must be a non-empty string")

        # Validate time window
        if self.time_window <= 0:
            raise ValueError("Time window must be positive")

        # Validate financial impact limit if provided
        if self.financial_impact_limit is not None and not isinstance(
            self.financial_impact_limit, Money
        ):
            raise TypeError("Financial impact limit must be Money type if provided")

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "exploit_type": self.exploit_type,
            "difficulty_level": self.difficulty_level,
            "target_action": self.target_action,
            "deception_vector": self.deception_vector,
            "time_window": self.time_window,
            "financial_impact_limit": (
                str(self.financial_impact_limit)
                if self.financial_impact_limit
                else None
            ),
        }


@dataclass
class PhishingEvent(AdversarialEvent):
    """
    Phishing/social engineering adversarial event.

    Tests agent susceptibility to fraudulent communications that attempt
    to trick them into revealing sensitive information or taking harmful actions.

    Attributes:
        sender_email: Fake email address of the phishing attempt
        message_content: The deceptive message content
        requested_action: What the phishing email is asking the agent to do
        spoofed_domain: Domain being impersonated (if any)
        urgency_indicators: Phrases/elements designed to create urgency
    """

    sender_email: str = ""
    message_content: str = ""
    requested_action: str = ""
    spoofed_domain: Optional[str] = None
    urgency_indicators: List[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        # Set exploit_type for phishing events
        object.__setattr__(self, "exploit_type", "phishing")

        # Validate required fields
        if not self.sender_email or "@" not in self.sender_email:
            raise ValueError("Sender email must be a valid email format")
        if not self.message_content:
            raise ValueError("Message content cannot be empty")
        if not self.requested_action:
            raise ValueError("Requested action cannot be empty")

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            **super().to_summary_dict(),  # Include base adversarial event details
            "sender_email": self.sender_email,
            "requested_action": self.requested_action,
            "spoofed_domain": self.spoofed_domain,
        }


@dataclass
class MarketManipulationEvent(AdversarialEvent):
    """
    Market manipulation adversarial event.

    Tests agent resistance to false market information designed to
    influence pricing, inventory, or strategic decisions.

    Attributes:
        false_data_type: Type of false data (pricing, sales, reviews, etc.)
        manipulated_values: The false values being presented
        source_credibility: How credible the source appears (1-5)
        market_impact_claim: Claimed impact on market conditions
    """

    false_data_type: str = ""
    manipulated_values: Dict[str, Any] = field(default_factory=dict)
    source_credibility: int = 3
    market_impact_claim: str = ""

    def __post_init__(self):
        super().__post_init__()
        # Set exploit_type for market manipulation events
        object.__setattr__(self, "exploit_type", "market_manipulation")

        # Validate fields
        valid_data_types = [
            "pricing",
            "sales_data",
            "reviews",
            "competitor_intel",
            "demand_forecast",
        ]
        if self.false_data_type not in valid_data_types:
            raise ValueError(f"False data type must be one of {valid_data_types}")

        if not 1 <= self.source_credibility <= 5:
            raise ValueError("Source credibility must be between 1 and 5")

        if not self.market_impact_claim:
            raise ValueError("Market impact claim cannot be empty")

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            **super().to_summary_dict(),  # Include base adversarial event details
            "false_data_type": self.false_data_type,
            "source_credibility": self.source_credibility,
        }


@dataclass
class ComplianceTrapEvent(AdversarialEvent):
    """
    Compliance trap adversarial event.

    Tests agent susceptibility to fake policy changes or compliance
    requirements that look legitimate but are actually harmful.

    Attributes:
        fake_policy_name: Name of the fake policy/requirement
        policy_description: Description of the fake policy
        compliance_deadline: Fake deadline for compliance
        penalty_claim: Claimed penalties for non-compliance
        official_appearance: How official the communication appears (1-5)
    """

    fake_policy_name: str = ""
    policy_description: str = ""
    compliance_deadline: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(days=30)
    )
    penalty_claim: str = ""
    official_appearance: int = 3

    def __post_init__(self):
        super().__post_init__()
        # Set exploit_type for compliance trap events
        object.__setattr__(self, "exploit_type", "compliance_trap")

        # Validate fields
        if not self.fake_policy_name:
            raise ValueError("Fake policy name cannot be empty")
        if not self.policy_description:
            raise ValueError("Policy description cannot be empty")
        if not isinstance(self.compliance_deadline, datetime):
            raise TypeError("Compliance deadline must be a datetime object")
        if not self.penalty_claim:
            raise ValueError("Penalty claim cannot be empty")
        if not 1 <= self.official_appearance <= 5:
            raise ValueError("Official appearance must be between 1 and 5")

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            **super().to_summary_dict(),  # Include base adversarial event details
            "fake_policy_name": self.fake_policy_name,
            "compliance_deadline": self.compliance_deadline.isoformat(),
            "penalty_claim": self.penalty_claim,
        }


@dataclass
class AdversarialResponse(BaseEvent):
    """
    Agent response to an adversarial event, used for ARS calculation.

    Tracks how an agent responded to an adversarial attack, including
    whether they fell for the exploit, detected it, or took protective action.

    Attributes:
        event_id: Unique identifier for this response event
        timestamp: When the response was recorded
        adversarial_event_id: ID of the adversarial event this responds to
        agent_id: ID of the agent that responded
        fell_for_exploit: Whether the agent fell for the adversarial attack
        detected_attack: Whether the agent detected the attack
        reported_attack: Whether the agent reported the attack
        protective_action_taken: What protective action was taken (if any)
        response_time_seconds: How long it took to respond
        financial_damage: Actual financial damage incurred (if any)
        exploit_difficulty: Difficulty level of the exploit (copied for analysis)
    """

    adversarial_event_id: str
    agent_id: str
    fell_for_exploit: bool
    detected_attack: bool
    reported_attack: bool
    protective_action_taken: Optional[str] = None
    response_time_seconds: float = 0.0
    financial_damage: Optional[Money] = None
    exploit_difficulty: int = 1

    def __post_init__(self):
        super().__post_init__()

        # Validate required fields
        if not self.adversarial_event_id:
            raise ValueError("Adversarial event ID cannot be empty")
        if not self.agent_id:
            raise ValueError("Agent ID cannot be empty")

        # Validate response time
        if self.response_time_seconds < 0:
            raise ValueError("Response time must be non-negative")

        # Validate exploit difficulty
        if not 1 <= self.exploit_difficulty <= 5:
            raise ValueError("Exploit difficulty must be between 1 and 5")

        # Validate financial damage if provided (accept Money-like)
        if self.financial_damage is not None and not isinstance(
            self.financial_damage, Money
        ):
            cents_attr = getattr(self.financial_damage, "cents", None)
            if isinstance(cents_attr, int):
                # Accept duck-typed Money-like with .cents
                pass
            elif isinstance(self.financial_damage, (int, float)):
                # Interpret numeric as cents and coerce to Money
                object.__setattr__(
                    self, "financial_damage", Money(int(round(self.financial_damage)))
                )
            else:
                raise TypeError("Financial damage must be Money type if provided")

        # Logic validation: can't both fall for exploit and detect it
        if self.fell_for_exploit and self.detected_attack:
            raise ValueError(
                "Agent cannot both fall for exploit and detect it simultaneously"
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "adversarial_event_id": self.adversarial_event_id,
            "agent_id": self.agent_id,
            "fell_for_exploit": self.fell_for_exploit,
            "detected_attack": self.detected_attack,
            "reported_attack": self.reported_attack,
            "protective_action_taken": self.protective_action_taken,
            "response_time_seconds": round(self.response_time_seconds, 2),
            "financial_damage": (
                str(self.financial_damage) if self.financial_damage else None
            ),
            "exploit_difficulty": self.exploit_difficulty,
        }
