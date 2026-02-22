"""
Memory Integration Validator

Provides comprehensive validation and consistency checking for agent memory systems.
Ensures memory integrity, detects contradictions, and validates action-memory alignment.
"""

import json
import logging
import re  # Added for advanced content parsing
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from fba_bench_core.money import Money  # Assuming Money class is used for financial values

from fba_events import BaseEvent  # Corrected import path
from fba_events.bus import EventBus  # Corrected import path

from .dual_memory_manager import DualMemoryManager, MemoryEvent
from .memory_config import MemoryConfig

logger = logging.getLogger(__name__)


class InconsistencyType(Enum):
    """Types of memory inconsistencies that can be detected."""

    CONTRADICTION = "contradiction"
    TEMPORAL_CONFLICT = "temporal_conflict"
    LOGICAL_INCONSISTENCY = "logical_inconsistency"
    STALE_INFORMATION = "stale_information"
    MISSING_CONTEXT = "missing_context"
    CONFIDENCE_MISMATCH = "confidence_mismatch"
    INVALID_IMPACT = "invalid_impact"  # New type for action-outcome mismatch


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryInconsistency:
    """Represents a detected memory inconsistency."""

    inconsistency_type: InconsistencyType
    severity: ValidationSeverity
    description: str
    conflicting_memories: List[str]  # Memory event IDs
    evidence: List[str]
    confidence: float  # Confidence in the inconsistency detection
    suggested_resolution: str
    inconsistency_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # Using asdict for consistency


@dataclass
class ValidationResult:
    """Result of memory validation process."""

    agent_id: str
    memories_checked: int
    inconsistencies_found: List[MemoryInconsistency]
    validation_passed: bool
    confidence_score: float
    recommendations: List[str]
    validation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    validation_timestamp: datetime = field(default_factory=datetime.now)
    action_validated: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        # Manually convert nested objects to dicts for full JSON serialization
        data = asdict(self)
        data["inconsistencies_found"] = [
            inc.to_dict() for inc in self.inconsistencies_found
        ]
        return data


class MemoryConsistencyChecker:
    """
    Validates memory retrieval consistency and detects contradictions.

    Provides comprehensive checking of memory consistency, identifies conflicting
    information, and flags potential issues in agent memory systems.
    """

    def __init__(self, agent_id: str, config: MemoryConfig):
        """
        Initialize the Memory Consistency Checker.

        Args:
            agent_id: Unique identifier for the agent
            config: Memory configuration. Must contain parameters for validation thresholds.
        """
        self.agent_id = agent_id
        self.config = config

        # Consistency checking parameters (now configurable via MemoryConfig)
        self.contradiction_threshold = config.validation_config.contradiction_threshold
        self.temporal_window_hours = config.validation_config.temporal_window_hours
        self.confidence_threshold = config.validation_config.confidence_threshold
        self.dramatic_price_change_percent = (
            config.validation_config.dramatic_price_change_percent
        )
        self.high_inventory_threshold = (
            config.validation_config.high_inventory_threshold
        )
        self.tight_budget_threshold = config.validation_config.tight_budget_threshold

        # Tracking and statistics
        self.validation_history: List[ValidationResult] = []
        self.detected_inconsistencies: List[MemoryInconsistency] = []
        self.total_validations = 0
        self.total_inconsistencies_found = 0

        logger.info(f"MemoryConsistencyChecker initialized for agent {agent_id}")

    async def validate_memory_retrieval(
        self, retrieved_facts: List[MemoryEvent], proposed_action: Dict[str, Any]
    ) -> ValidationResult:
        """
        Check consistency between retrieved facts and proposed action.

        Args:
            retrieved_facts: List of retrieved memory events
            proposed_action: Action that the agent wants to take

        Returns:
            ValidationResult with consistency analysis
        """
        logger.info(
            f"Validating memory retrieval for agent {self.agent_id} - "
            f"{len(retrieved_facts)} facts, action: {proposed_action.get('type', 'unknown')}"
        )

        validation_id = str(uuid.uuid4())
        current_time = datetime.now()

        inconsistencies = []

        # Check for contradictions within retrieved facts
        fact_contradictions = await self.detect_contradictions(retrieved_facts)
        inconsistencies.extend(fact_contradictions)

        # Check action-memory consistency
        action_inconsistencies = await self.flag_inconsistencies(
            proposed_action, retrieved_facts
        )
        inconsistencies.extend(action_inconsistencies)

        # Check temporal consistency
        temporal_inconsistencies = await self._check_temporal_consistency(
            retrieved_facts
        )
        inconsistencies.extend(temporal_inconsistencies)

        # Check confidence consistency
        confidence_inconsistencies = await self._check_confidence_consistency(
            retrieved_facts
        )
        inconsistencies.extend(confidence_inconsistencies)

        # Determine overall validation result
        critical_inconsistencies = [
            inc
            for inc in inconsistencies
            if inc.severity in [ValidationSeverity.HIGH, ValidationSeverity.CRITICAL]
        ]
        validation_passed = len(critical_inconsistencies) == 0

        # Calculate confidence score
        confidence_score = await self._calculate_validation_confidence(
            retrieved_facts, inconsistencies, proposed_action
        )

        # Generate recommendations
        recommendations = await self._generate_validation_recommendations(
            inconsistencies, proposed_action
        )

        # Create validation result
        validation_result = ValidationResult(
            validation_id=validation_id,
            agent_id=self.agent_id,
            validation_timestamp=current_time,
            action_validated=proposed_action,
            memories_checked=len(retrieved_facts),
            inconsistencies_found=inconsistencies,
            validation_passed=validation_passed,
            confidence_score=confidence_score,
            recommendations=recommendations,
        )

        # Update statistics
        self.validation_history.append(validation_result)
        self.detected_inconsistencies.extend(inconsistencies)
        self.total_validations += 1
        self.total_inconsistencies_found += len(inconsistencies)

        logger.info(
            f"Memory validation completed - passed: {validation_passed}, "
            f"inconsistencies: {len(inconsistencies)}, confidence: {confidence_score:.2f}"
        )

        return validation_result

    async def detect_contradictions(
        self, fact_set: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """
        Identify conflicting information within a set of facts.

        Args:
            fact_set: List of memory events to check for contradictions

        Returns:
            List of detected inconsistencies
        """
        logger.debug(f"Detecting contradictions in {len(fact_set)} facts")

        inconsistencies = []
        current_time = datetime.now()

        # Group facts by domain for targeted contradiction checking
        facts_by_domain = {}
        for fact in fact_set:
            domain = fact.domain
            if domain not in facts_by_domain:
                facts_by_domain[domain] = []
            facts_by_domain[domain].append(fact)

        # Check for contradictions within each domain
        for domain, domain_facts in facts_by_domain.items():
            domain_contradictions = await self._detect_domain_contradictions(
                domain, domain_facts
            )
            inconsistencies.extend(domain_contradictions)

        # Check for cross-domain contradictions
        cross_domain_contradictions = await self._detect_cross_domain_contradictions(
            facts_by_domain
        )
        inconsistencies.extend(cross_domain_contradictions)

        # Check for temporal contradictions (more specific than general temporal consistency)
        temporal_contradictions = await self._detect_temporal_contradictions_specific(
            fact_set
        )
        inconsistencies.extend(temporal_contradictions)

        logger.debug(f"Found {len(inconsistencies)} contradictions")
        return inconsistencies

    async def flag_inconsistencies(
        self, agent_action: Dict[str, Any], known_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """
        Alert on discrepancies between agent action and known facts.

        Args:
            agent_action: Proposed action by the agent
            known_facts: Known facts from memory

        Returns:
            List of detected inconsistencies
        """
        logger.debug(
            f"Flagging inconsistencies for action: {agent_action.get('type', 'unknown')}"
        )

        inconsistencies = []
        current_time = datetime.now()

        action_type = agent_action.get("type", "unknown")
        action_parameters = agent_action.get("parameters", {})

        # Check pricing action consistency
        if action_type == "set_price":
            price_inconsistencies = await self._check_pricing_action_consistency(
                action_parameters, known_facts
            )
            inconsistencies.extend(price_inconsistencies)

        # Check inventory action consistency
        elif action_type == "place_order":
            inventory_inconsistencies = await self._check_inventory_action_consistency(
                action_parameters, known_facts
            )
            inconsistencies.extend(inventory_inconsistencies)

        # Check marketing action consistency
        elif action_type == "run_marketing_campaign":
            marketing_inconsistencies = await self._check_marketing_action_consistency(
                action_parameters, known_facts
            )
            inconsistencies.extend(marketing_inconsistencies)

        # Check general action-memory alignment and expected impact
        general_inconsistencies = await self._check_general_action_consistency(
            agent_action, known_facts
        )
        inconsistencies.extend(general_inconsistencies)

        logger.debug(f"Found {len(inconsistencies)} action inconsistencies")
        return inconsistencies

    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive validation statistics."""
        current_time = datetime.now()

        stats = {
            "agent_id": self.agent_id,
            "total_validations": self.total_validations,
            "total_inconsistencies": self.total_inconsistencies_found,
            "validation_history_size": len(self.validation_history),
            "configuration": {
                "contradiction_threshold": self.contradiction_threshold,
                "temporal_window_hours": self.temporal_window_hours,
                "confidence_threshold": self.confidence_threshold,
                "dramatic_price_change_percent": self.dramatic_price_change_percent,
                "high_inventory_threshold": self.high_inventory_threshold,
                "tight_budget_threshold": self.tight_budget_threshold,
            },
        }

        if self.validation_history:
            # Calculate success rates
            passed_validations = len(
                [v for v in self.validation_history if v.validation_passed]
            )
            stats["validation_success_rate"] = passed_validations / max(
                1, len(self.validation_history)
            )

            # Calculate average confidence
            avg_confidence = sum(
                v.confidence_score for v in self.validation_history
            ) / max(1, len(self.validation_history))
            stats["average_confidence_score"] = avg_confidence

            # Recent validation summary
            recent_validation = self.validation_history[-1]
            stats["latest_validation"] = (
                recent_validation.to_dict()
            )  # Using to_dict for full serialization

        if self.detected_inconsistencies:
            # Inconsistency type distribution
            type_counts: Dict[str, int] = {}
            severity_counts: Dict[str, int] = {}

            for inconsistency in self.detected_inconsistencies:
                inc_type = inconsistency.inconsistency_type.value
                severity = inconsistency.severity.value

                type_counts[inc_type] = type_counts.get(inc_type, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            stats["inconsistency_types"] = type_counts
            stats["inconsistency_severities"] = severity_counts

        return stats

    # Private helper methods

    async def _detect_domain_contradictions(
        self, domain: str, domain_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Detect contradictions within a specific domain."""
        inconsistencies = []

        if domain == "pricing":
            inconsistencies.extend(
                await self._check_pricing_contradictions(domain_facts)
            )
        elif domain == "inventory":
            inconsistencies.extend(
                await self._check_inventory_contradictions(domain_facts)
            )
        # Add more domain-specific contradiction checks as needed

        return inconsistencies

    async def _check_pricing_contradictions(
        self, pricing_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """More robust check for pricing contradictions."""
        inconsistencies = []
        current_time = datetime.now()

        prices_by_asin: Dict[str, List[Tuple[Money, datetime, str]]] = (
            {}
        )  # (price, timestamp, event_id)
        for fact in pricing_facts:
            # Attempt to extract price. This is still heuristic, ideally events would have structured data
            price_match = re.search(
                r"price(?: change)?(?: from)?.*?([$€£]?\d+\.?\d*)",
                fact.content,
                re.IGNORECASE,
            )
            asin_match = re.search(r"ASIN (\w+)", fact.content)

            if price_match and asin_match:
                try:
                    price_str = price_match.group(1).lstrip("$€£")
                    price_money = Money.from_dollars(
                        price_str, currency="USD"
                    )  # Assuming currency
                    asin = asin_match.group(1)

                    if asin not in prices_by_asin:
                        prices_by_asin[asin] = []
                    prices_by_asin[asin].append(
                        (price_money, fact.timestamp, fact.event_id)
                    )
                except Exception as e:
                    logger.debug(
                        f"Could not parse price from memory event {fact.event_id}: {e}"
                    )

        for asin, prices in prices_by_asin.items():
            prices.sort(key=lambda x: x[1])  # Sort by timestamp
            for i, (price1, ts1, id1) in enumerate(prices[:-1]):
                for price2, ts2, id2 in prices[i + 1 :]:
                    # If prices for the same ASIN significantly diverge at similar times
                    time_diff_hours = (ts2 - ts1).total_seconds() / 3600
                    if (
                        time_diff_hours < self.temporal_window_hours
                        and await self._are_pricing_facts_contradictory_robust(
                            price1, price2, asin
                        )
                    ):
                        inconsistencies.append(
                            MemoryInconsistency(
                                inconsistency_type=InconsistencyType.CONTRADICTION,
                                severity=ValidationSeverity.CRITICAL,
                                description=f"Conflicting pricing information for ASIN {asin} detected within "
                                f"{time_diff_hours:.1f} hours. Prices: {price1} vs {price2}.",
                                conflicting_memories=[id1, id2],
                                evidence=[
                                    f"Fact ID {id1}: {price1} at {ts1}",
                                    f"Fact ID {id2}: {price2} at {ts2}",
                                ],
                                confidence=0.9,
                                suggested_resolution="Verify the actual price of the product and reconcile memory.",
                                detected_at=current_time,
                            )
                        )
        return inconsistencies

    async def _check_inventory_contradictions(
        self, inventory_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """More robust check for inventory contradictions."""
        inconsistencies = []
        current_time = datetime.now()

        inventory_levels_by_asin: Dict[str, List[Tuple[int, datetime, str]]] = (
            {}
        )  # (level, timestamp, event_id)
        for fact in inventory_facts:
            level_match = re.search(
                r"inventory(?: level)?.*?(\d+)", fact.content, re.IGNORECASE
            )
            asin_match = re.search(r"ASIN (\w+)", fact.content)

            if level_match and asin_match:
                try:
                    level = int(level_match.group(1))
                    asin = asin_match.group(1)

                    if asin not in inventory_levels_by_asin:
                        inventory_levels_by_asin[asin] = []
                    inventory_levels_by_asin[asin].append(
                        (level, fact.timestamp, fact.event_id)
                    )
                except Exception as e:
                    logger.debug(
                        f"Could not parse inventory level from memory event {fact.event_id}: {e}"
                    )

        for asin, levels in inventory_levels_by_asin.items():
            levels.sort(key=lambda x: x[1])  # Sort by timestamp
            for i, (level1, ts1, id1) in enumerate(levels[:-1]):
                for level2, ts2, id2 in levels[i + 1 :]:
                    time_diff_hours = (ts2 - ts1).total_seconds() / 3600
                    # If inventory levels for the same ASIN drastically change without clear events
                    if (
                        time_diff_hours < self.temporal_window_hours
                        and abs(level1 - level2) > self.high_inventory_threshold * 10
                    ):  # Example of a "drastic" change
                        inconsistencies.append(
                            MemoryInconsistency(
                                inconsistency_type=InconsistencyType.CONTRADICTION,
                                severity=ValidationSeverity.CRITICAL,
                                description=f"Conflicting inventory information for ASIN {asin} detected within "
                                f"{time_diff_hours:.1f} hours. Levels: {level1} vs {level2}.",
                                conflicting_memories=[id1, id2],
                                evidence=[
                                    f"Fact ID {id1}: {level1} at {ts1}",
                                    f"Fact ID {id2}: {level2} at {ts2}",
                                ],
                                confidence=0.9,
                                suggested_resolution="Verify the actual inventory level and reconcile memory.",
                                detected_at=current_time,
                            )
                        )
        return inconsistencies

    async def _detect_cross_domain_contradictions(
        self, facts_by_domain: Dict[str, List[MemoryEvent]]
    ) -> List[MemoryInconsistency]:
        """Detect contradictions across different domains."""
        inconsistencies = []

        # Example: Check for contradictions between pricing and sales domains
        if "pricing" in facts_by_domain and "sales" in facts_by_domain:
            pricing_facts = facts_by_domain["pricing"]
            sales_facts = facts_by_domain["sales"]

            for price_fact in pricing_facts:
                for sales_fact in sales_facts:
                    if await self._are_pricing_sales_contradictory_robust(
                        price_fact, sales_fact
                    ):
                        inconsistencies.append(
                            MemoryInconsistency(
                                inconsistency_id=str(uuid.uuid4()),
                                inconsistency_type=InconsistencyType.LOGICAL_INCONSISTENCY,
                                severity=ValidationSeverity.HIGH,
                                description="Pricing strategy appears to contradict recent sales performance data.",
                                conflicting_memories=[
                                    price_fact.event_id,
                                    sales_fact.event_id,
                                ],
                                evidence=[
                                    f"Pricing: {price_fact.content[:100]}",
                                    f"Sales: {sales_fact.content[:100]}",
                                ],
                                confidence=0.8,
                                suggested_resolution="Review pricing strategy effectiveness in light of actual sales. Agent may be misinterpreting market response.",
                                detected_at=datetime.now(),
                            )
                        )
        return inconsistencies

    async def _detect_temporal_contradictions_specific(
        self, fact_set: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """More specific temporal contradiction detection, e.g., price changes."""
        inconsistencies = []

        # Example: if a product price is reported as changed multiple times in a very short period
        pricing_events: Dict[str, List[Tuple[Money, datetime, str]]] = {}
        for fact in fact_set:
            if "productpriceupdated" in fact.event_type.lower():
                price_match = re.search(r"new_price: (\d+\.?\d*)", fact.content)
                asin_match = re.search(r"ASIN (\w+)", fact.content)
                if price_match and asin_match:
                    try:
                        new_price = Money.from_dollars(float(price_match.group(1)))
                        asin = asin_match.group(1)
                        if asin not in pricing_events:
                            pricing_events[asin] = []
                        pricing_events[asin].append(
                            (new_price, fact.timestamp, fact.event_id)
                        )
                    except Exception as e:
                        logger.debug(
                            f"Could not parse price from ProductPriceUpdated event {fact.event_id}: {e}"
                        )

        for asin, events in pricing_events.items():
            events.sort(key=lambda x: x[1])  # Sort by timestamp
            for i, (price1, ts1, id1) in enumerate(events[:-1]):
                for price2, ts2, id2 in events[i + 1 :]:
                    time_diff_minutes = (ts2 - ts1).total_seconds() / 60
                    # If two reported price changes for same ASIN happen too quickly, it might be an error
                    if time_diff_minutes < 5 and price1 != price2:  # e.g., 5 minutes
                        inconsistencies.append(
                            MemoryInconsistency(
                                inconsistency_type=InconsistencyType.TEMPORAL_CONFLICT,
                                severity=ValidationSeverity.MEDIUM,
                                description=f"Rapid, conflicting price updates for ASIN {asin} detected within {time_diff_minutes:.1f} minutes. "
                                f"Prices: {price1} at {ts1} vs {price2} at {ts2}.",
                                conflicting_memories=[id1, id2],
                                evidence=[f"Event ID {id1}", f"Event ID {id2}"],
                                confidence=0.7,
                                suggested_resolution="Verify the correct price update sequence and root cause of rapid changes.",
                                detected_at=datetime.now(),
                            )
                        )
        return inconsistencies

    async def _check_temporal_consistency(
        self, retrieved_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Check for general temporal consistency issues, especially stale information."""
        inconsistencies = []
        current_time = datetime.now()

        # Check for stale information, more aggressively flagging critical time-sensitive data
        for fact in retrieved_facts:
            age_hours = (current_time - fact.timestamp).total_seconds() / 3600

            if age_hours > self.temporal_window_hours:
                # Check for particularly time-sensitive information (e.g., current prices, inventory)
                severity = ValidationSeverity.LOW
                resolution = "Consider refreshing this information or noting its age."

                if (
                    "price" in fact.content.lower()
                    or "inventory" in fact.content.lower()
                ):
                    severity = ValidationSeverity.MEDIUM
                    resolution = "This is time-sensitive data. Agent should refresh or confirm current status."

                if (
                    age_hours > self.temporal_window_hours * 2
                ):  # Double the general window for higher severity
                    severity = ValidationSeverity.HIGH
                    resolution = "Critical time-sensitive data is very stale. Refresh immediately."

                inconsistencies.append(
                    MemoryInconsistency(
                        inconsistency_type=InconsistencyType.STALE_INFORMATION,
                        severity=severity,
                        description=f"Potentially stale information detected (age: {age_hours:.1f} hours).",
                        conflicting_memories=[fact.event_id],
                        evidence=[
                            f"Fact age: {age_hours:.1f} hours. Content: {fact.content[:100]}"
                        ],
                        confidence=0.6,
                        suggested_resolution=resolution,
                        detected_at=current_time,
                    )
                )
        return inconsistencies

    async def _check_confidence_consistency(
        self, retrieved_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Check for confidence-related inconsistencies."""
        inconsistencies = []
        current_time = datetime.now()

        # Flag if critical decisions are being made primarily with low confidence facts
        low_confidence_facts = [
            f for f in retrieved_facts if f.importance_score < self.confidence_threshold
        ]

        if (
            low_confidence_facts
            and len(low_confidence_facts)
            > len(retrieved_facts) * self.confidence_threshold
        ):  # If a majority are low confidence (using threshold as percentage)
            inconsistencies.append(
                MemoryInconsistency(
                    inconsistency_type=InconsistencyType.CONFIDENCE_MISMATCH,
                    severity=ValidationSeverity.MEDIUM,
                    description=f"A significant portion ({len(low_confidence_facts)}/{len(retrieved_facts)}) of retrieved facts have low confidence.",
                    conflicting_memories=[f.event_id for f in low_confidence_facts],
                    evidence=[f"Low confidence facts: {len(low_confidence_facts)}"],
                    confidence=0.7,
                    suggested_resolution="Seek higher-confidence information or reduce reliance on uncertain facts.",
                    detected_at=current_time,
                )
            )

        return inconsistencies

    async def _check_pricing_action_consistency(
        self, action_parameters: Dict[str, Any], known_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Check consistency of pricing actions with known facts."""
        inconsistencies = []
        current_time = datetime.now()

        proposed_price_raw = action_parameters.get("price")
        asin = action_parameters.get("asin")

        if not proposed_price_raw or not asin:
            return inconsistencies

        try:
            proposed_price = Money.from_dollars(
                proposed_price_raw, currency="USD"
            )  # Assuming USD
        except (ValueError, TypeError):
            inconsistencies.append(
                MemoryInconsistency(
                    inconsistency_type=InconsistencyType.LOGICAL_INCONSISTENCY,
                    severity=ValidationSeverity.CRITICAL,
                    description=f"Proposed price '{proposed_price_raw}' is not a valid monetary value for ASIN {asin}.",
                    conflicting_memories=[],
                    evidence=[f"Invalid price input: {proposed_price_raw}"],
                    confidence=1.0,
                    suggested_resolution="Ensure the proposed price is a valid number.",
                    detected_at=current_time,
                )
            )
            return inconsistencies  # Exit early if price itself is invalid

        # Filter relevant pricing facts for this ASIN
        pricing_facts = [
            f for f in known_facts if "price" in f.content.lower() and asin in f.content
        ]

        for fact in pricing_facts:
            # Attempt to extract current price from fact content
            current_price_match = re.search(
                r"current price: (\$?\d+\.?\d*)", fact.content, re.IGNORECASE
            )

            if current_price_match:
                try:
                    current_price_money = Money.from_dollars(
                        current_price_match.group(1), currency="USD"
                    )

                    if await self._is_dramatic_price_change_robust(
                        proposed_price, current_price_money
                    ):
                        inconsistencies.append(
                            MemoryInconsistency(
                                inconsistency_type=InconsistencyType.LOGICAL_INCONSISTENCY,
                                severity=ValidationSeverity.HIGH,
                                description=f"Proposed price change for ASIN {asin} from {current_price_money} to {proposed_price} is dramatic "
                                f"({(proposed_price.to_decimal() / current_price_money.to_decimal() - 1)*100:.2f}% change) without clear justification in memory.",
                                conflicting_memories=[fact.event_id],
                                evidence=[
                                    f"Proposed: {proposed_price}",
                                    f"Current in memory: {current_price_money}",
                                    f"Fact: {fact.content[:100]}",
                                ],
                                confidence=0.85,
                                suggested_resolution="Review the rationale for a dramatic price change. Ensure market conditions support this decision.",
                                detected_at=current_time,
                            )
                        )
                except Exception as e:
                    logger.debug(
                        f"Could not parse current price from memory event {fact.event_id}: {e}"
                    )

        return inconsistencies

    async def _check_inventory_action_consistency(
        self, action_parameters: Dict[str, Any], known_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Check consistency of inventory actions with known facts."""
        inconsistencies = []
        current_time = datetime.now()

        order_quantity = action_parameters.get("quantity")
        asin = action_parameters.get("asin")  # Assuming ASIN for inventory actions

        if not isinstance(order_quantity, int) or order_quantity <= 0 or not asin:
            # Invalid or incomplete action parameters
            return inconsistencies

        # Filter relevant inventory facts for this ASIN
        inventory_facts = [
            f
            for f in known_facts
            if "inventory" in f.content.lower() and asin in f.content
        ]

        for fact in inventory_facts:
            # Attempt to extract inventory level from fact content
            level_match = re.search(
                r"inventory(?: level)?.*?(\d+)", fact.content, re.IGNORECASE
            )

            if level_match:
                try:
                    current_inventory_level = int(level_match.group(1))

                    # Scenario: Ordering more when inventory is already very high
                    if (
                        current_inventory_level > self.high_inventory_threshold
                        and order_quantity > current_inventory_level / 2
                    ):
                        inconsistencies.append(
                            MemoryInconsistency(
                                inconsistency_type=InconsistencyType.LOGICAL_INCONSISTENCY,
                                severity=ValidationSeverity.MEDIUM,
                                description=f"Large order quantity ({order_quantity}) proposed for ASIN {asin} despite existing high inventory (level: {current_inventory_level}).",
                                conflicting_memories=[fact.event_id],
                                evidence=[
                                    f"Order: {order_quantity}",
                                    f"Current inventory: {current_inventory_level}",
                                    f"Fact: {fact.content[:100]}",
                                ],
                                confidence=0.7,
                                suggested_resolution="Review inventory levels and demand forecast before placing large orders.",
                                detected_at=current_time,
                            )
                        )
                except Exception as e:
                    logger.debug(
                        f"Could not parse inventory level from memory event {fact.event_id}: {e}"
                    )

        return inconsistencies

    async def _check_marketing_action_consistency(
        self, action_parameters: Dict[str, Any], known_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Check consistency of marketing actions with known facts."""
        inconsistencies = []
        current_time = datetime.now()

        campaign_budget_raw = action_parameters.get("budget")
        campaign_type = action_parameters.get("campaign_type")

        if not campaign_budget_raw or not campaign_type:
            return inconsistencies

        try:
            campaign_budget = Money.from_dollars(
                campaign_budget_raw, currency="USD"
            )  # Assuming USD
        except (ValueError, TypeError):
            inconsistencies.append(
                MemoryInconsistency(
                    inconsistency_type=InconsistencyType.LOGICAL_INCONSISTENCY,
                    severity=ValidationSeverity.CRITICAL,
                    description=f"Proposed campaign budget '{campaign_budget_raw}' is not a valid monetary value for '{campaign_type}' campaign.",
                    conflicting_memories=[],
                    evidence=[f"Invalid budget input: {campaign_budget_raw}"],
                    confidence=1.0,
                    suggested_resolution="Ensure the proposed budget is a valid number.",
                    detected_at=current_time,
                )
            )
            return inconsistencies

        # Filter relevant financial/budget facts
        financial_facts = [
            f
            for f in known_facts
            if "budget" in f.content.lower() or "financial" in f.content.lower()
        ]

        for fact in financial_facts:
            # Scenario: High marketing spend when budget is tight
            budget_status_match = re.search(
                r"(?:budget is|financial situation is) (tight|strained|limited)",
                fact.content,
                re.IGNORECASE,
            )

            if (
                budget_status_match
                and campaign_budget.to_decimal() > self.tight_budget_threshold
            ):
                inconsistencies.append(
                    MemoryInconsistency(
                        inconsistency_type=InconsistencyType.LOGICAL_INCONSISTENCY,
                        severity=ValidationSeverity.HIGH,
                        description=f"High marketing budget ({campaign_budget}) proposed for '{campaign_type}' campaign despite recent memory indicating tight financial constraints.",
                        conflicting_memories=[fact.event_id],
                        evidence=[
                            f"Campaign budget: {campaign_budget}",
                            f"Financial context: {fact.content[:100]}",
                        ],
                        confidence=0.8,
                        suggested_resolution="Adjust marketing budget to align with current financial constraints.",
                        detected_at=current_time,
                    )
                )

        return inconsistencies

    async def _check_general_action_consistency(
        self, agent_action: Dict[str, Any], known_facts: List[MemoryEvent]
    ) -> List[MemoryInconsistency]:
        """Check general consistency between action, its expected impact, and memory context."""
        inconsistencies = []
        current_time = datetime.now()

        action_type = agent_action.get("type", "unknown")
        expected_impact = agent_action.get(
            "expected_impact", {}
        )  # Agent's stated expected impact of its action

        # Check if action aligns with recent context
        # Define a 'recent' window based on temporal_window_hours
        recent_cutoff_time = current_time - timedelta(hours=self.temporal_window_hours)
        contextual_facts = [f for f in known_facts if f.timestamp > recent_cutoff_time]

        if contextual_facts:
            for fact in contextual_facts:
                if await self._does_context_contraindicate_action_robust(
                    fact, agent_action
                ):
                    inconsistencies.append(
                        MemoryInconsistency(
                            inconsistency_type=InconsistencyType.MISSING_CONTEXT,
                            severity=ValidationSeverity.HIGH,
                            description=f"Action '{action_type}' contradicts strong recent contextual information in memory.",
                            conflicting_memories=[fact.event_id],
                            evidence=[
                                f"Action: {json.dumps(agent_action)[:100]}",
                                f"Contraindicating fact: {fact.content[:100]}",
                            ],
                            confidence=0.9,
                            suggested_resolution="Carefully review the recent context before taking this action. Adjust action or reasoning.",
                            detected_at=current_time,
                        )
                    )

        # Check if expected impact aligns with known facts
        if expected_impact:
            for fact in known_facts:
                if await self._does_expected_impact_contradict_fact(
                    expected_impact, fact
                ):
                    inconsistencies.append(
                        MemoryInconsistency(
                            inconsistency_type=InconsistencyType.INVALID_IMPACT,
                            severity=ValidationSeverity.MEDIUM,
                            description=f"Agent's expected impact for '{action_type}' contradicts known facts in memory.",
                            conflicting_memories=[fact.event_id],
                            evidence=[
                                f"Expected impact: {json.dumps(expected_impact)[:100]}",
                                f"Conflicting fact: {fact.content[:100]}",
                            ],
                            confidence=0.7,
                            suggested_resolution="Re-evaluate expected impact based on current knowledge.",
                            detected_at=current_time,
                        )
                    )
        return inconsistencies

    async def _calculate_validation_confidence(
        self,
        retrieved_facts: List[MemoryEvent],
        inconsistencies: List[MemoryInconsistency],
        proposed_action: Dict[str, Any],
    ) -> float:
        """Calculate confidence score for the validation."""
        base_confidence = 1.0  # Start with high confidence

        # Reduce confidence based on inconsistencies found
        for inconsistency in inconsistencies:
            severity_penalty = {
                ValidationSeverity.LOW: 0.05,
                ValidationSeverity.MEDIUM: 0.15,
                ValidationSeverity.HIGH: 0.3,
                ValidationSeverity.CRITICAL: 0.5,
            }
            base_confidence -= severity_penalty.get(inconsistency.severity, 0.1)

        # Boost confidence based on number and quality of retrieved facts
        if retrieved_facts:
            avg_fact_importance = sum(
                f.importance_score for f in retrieved_facts
            ) / len(retrieved_facts)

            # More facts and higher average importance should increase confidence in validation
            base_confidence += (avg_fact_importance * 0.1) * min(
                len(retrieved_facts) / 10, 1.0
            )  # Cap boost

        # Ensure confidence is within [0, 1] range
        return max(0.0, min(1.0, base_confidence))

    async def _generate_validation_recommendations(
        self,
        inconsistencies: List[MemoryInconsistency],
        proposed_action: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        if not inconsistencies:
            recommendations.append(
                "Validation passed successfully. Proceed with confidence."
            )
            return recommendations

        # Group recommendations by inconsistency type
        contradiction_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.CONTRADICTION
            ]
        )
        temporal_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.TEMPORAL_CONFLICT
            ]
        )
        logical_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.LOGICAL_INCONSISTENCY
            ]
        )
        stale_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.STALE_INFORMATION
            ]
        )
        missing_context_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.MISSING_CONTEXT
            ]
        )
        confidence_mismatch_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.CONFIDENCE_MISMATCH
            ]
        )
        invalid_impact_count = len(
            [
                i
                for i in inconsistencies
                if i.inconsistency_type == InconsistencyType.INVALID_IMPACT
            ]
        )

        if contradiction_count > 0:
            recommendations.append(
                f"HIGH PRIORITY: Resolve {contradiction_count} memory contradictions before executing action."
            )

        if temporal_count > 0:
            recommendations.append(
                f"MEDIUM PRIORITY: Address {temporal_count} temporal conflicts. Refresh time-sensitive information."
            )

        if logical_count > 0:
            recommendations.append(
                f"MEDIUM PRIORITY: Review {logical_count} logical inconsistencies. Re-evaluate action logic or context."
            )

        if stale_count > 0:
            recommendations.append(
                f"LOW PRIORITY: {stale_count} pieces of information are stale. Consider requesting fresh data."
            )

        if missing_context_count > 0:
            recommendations.append(
                f"MEDIUM PRIORITY: {missing_context_count} instances of missing context for this action. Seek additional information."
            )

        if confidence_mismatch_count > 0:
            recommendations.append(
                f"LOW PRIORITY: {confidence_mismatch_count} low-confidence facts were retrieved. Prioritize higher quality data if possible."
            )

        if invalid_impact_count > 0:
            recommendations.append(
                f"HIGH PRIORITY: {invalid_impact_count} instances where action's expected impact contradicts memory. Re-evaluate action effectiveness."
            )

        # Critical severity recommendations will force a halt if blocking mode is on
        critical_inconsistencies_exist = any(
            i.severity == ValidationSeverity.CRITICAL for i in inconsistencies
        )
        if critical_inconsistencies_exist:
            recommendations.append(
                "CRITICAL: One or more severe inconsistencies require immediate attention. Action may be blocked."
            )

        return recommendations

    # Robust helper methods for domain-specific checks

    async def _are_pricing_facts_contradictory_robust(
        self, price1: Money, price2: Money, asin: str
    ) -> bool:
        """Check if two parsed pricing facts for the same ASIN significantly contradict."""
        if price1.currency != price2.currency:
            logger.warning(
                f"Currency mismatch in pricing facts for ASIN {asin}: {price1.currency} vs {price2.currency}"
            )
            return False  # Not a contradiction if currencies are different, but a data quality issue

        # Define a tunable threshold for "contradictory" price difference, e.g., 20%
        # This is now configured by `dramatic_price_change_percent`
        price_diff_percentage = (
            abs((price1.to_decimal() - price2.to_decimal()) / price1.to_decimal())
            if price1.to_decimal() != 0
            else Decimal("inf")
        )

        return price_diff_percentage > self.dramatic_price_change_percent

    async def _are_inventory_facts_contradictory_robust(
        self, level1: int, level2: int, asin: str
    ) -> bool:
        """Check if two parsed inventory facts for the same ASIN significantly contradict."""
        # Simple percentage difference check for inventory levels
        level_diff_percentage = (
            abs((level1 - level2) / level1) if level1 != 0 else float("inf")
        )

        # A 50% difference might be considered contradictory unless explained by an event
        return level_diff_percentage > 0.5

    async def _are_pricing_sales_contradictory_robust(
        self, price_fact: MemoryEvent, sales_fact: MemoryEvent
    ) -> bool:
        """Check if pricing and sales facts contradict each other in a more robust way."""
        # This would ideally use structured events to parse actual price and sales velocity figures
        # For now, it's still heuristic but improved.
        price_content = price_fact.content.lower()
        sales_content = sales_fact.content.lower()

        # Heuristic 1: Price increase, but significant sales decrease
        # This would ideally be a rule checking time-aligned "ProductPriceUpdated" and "SaleOccurred" events.
        if (
            "price increased" in price_content
            and "sales decreased significantly" in sales_content
        ):
            return True

        # Heuristic 2: Price decrease, but significant sales decrease (unexpected)
        if (
            "price decreased" in price_content
            and "sales decreased significantly" in sales_content
        ):
            return True  # Could indicate a product quality issue, or misinterpretation of demand.

        return False

    async def _does_context_contraindicate_action_robust(
        self, fact: MemoryEvent, action: Dict[str, Any]
    ) -> bool:
        """Check if a memory fact strongly contraindicates a proposed action."""
        action_type = action.get("type", "")
        fact_content = fact.content.lower()

        # More robust heuristics
        if action_type == "run_marketing_campaign":
            budget_tightness_match = re.search(
                r"(?:budget (?:is|remains)|financial situation (?:is|remains)) (critically low|very tight|severely limited)",
                fact_content,
            )
            if budget_tightness_match:
                return True  # Strongly contraindicates launching new campaigns

        if action_type == "place_order":
            inventory_status_match = re.search(
                r"(?:inventory (?:is|remains)|stock (?:is|remains)) (excessive|overstocked|very high)",
                fact_content,
            )
            if inventory_status_match:
                return True  # Strongly contraindicates placing new orders

        if action_type == "set_price" and "market crash" in fact_content:
            # If market is crashing, a price increase might be contra-indicated
            # Robustly parse the current price from the fact for comparison
            current_price_match = re.search(
                r"price(?: change)?(?: from)?.*?([$€£]?\d+\.?\d*)",
                fact.content,
                re.IGNORECASE,
            )
            if current_price_match:
                try:
                    current_price_money = Money.from_dollars(
                        current_price_match.group(1), currency="USD"
                    )
                    proposed_price_raw = action.get("parameters", {}).get("price")
                    if proposed_price_raw:
                        proposed_price_money = Money.from_dollars(
                            proposed_price_raw, currency="USD"
                        )
                        if (
                            proposed_price_money > current_price_money
                            and fact.timestamp
                            > datetime.now()
                            - timedelta(hours=self.temporal_window_hours)
                        ):
                            return True
                except Exception as e:
                    logger.debug(
                        f"Could not parse prices for comparison in _does_context_contraindicate_action_robust: {e}"
                    )

        return False

    async def _does_expected_impact_contradict_fact(
        self, expected_impact: Dict[str, Any], fact: MemoryEvent
    ) -> bool:
        """
        Check if the agent's expected impact for an action contradicts a known fact.
        This requires understanding both the expected_impact structure and robust fact parsing.
        """
        # Example: Agent expects "sales_increase" but memory says "market is shrinking"
        expected_sales_increase = expected_impact.get("sales_increase", False)
        if expected_sales_increase:
            if (
                "market shrinking" in fact.content.lower()
                or "decreasing demand" in fact.content.lower()
            ):
                return True

        # Example: Agent expects "cost_reduction" but memory says "supplier costs rising"
        expected_cost_reduction = expected_impact.get("cost_reduction", False)
        if expected_cost_reduction:
            if (
                "supplier costs rising" in fact.content.lower()
                or "raw material prices up" in fact.content.lower()
            ):
                return True

        return False



class MemoryIntegrationGateway:
    """
    Gateway that intercepts agent actions for validation.

    Provides pre-action validation and post-action learning to ensure
    memory-action consistency and continuous improvement.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager: DualMemoryManager,
        consistency_checker: MemoryConsistencyChecker,
        config: MemoryConfig,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Initialize the Memory Integration Gateway.

        Args:
            agent_id: Unique identifier for the agent
            memory_manager: Memory management system
            consistency_checker: Memory consistency checker
            config: Memory configuration
            event_bus: Event bus for publishing validation events
        """
        self.agent_id = agent_id
        self.memory_manager = memory_manager
        self.consistency_checker = consistency_checker
        self.config = config
        self.event_bus = event_bus or get_event_bus()  # Ensure event_bus is initialized

        # Gateway statistics
        self.validations_performed = 0
        self.validations_passed = 0
        self.validations_failed = 0
        self.actions_blocked = 0
        self.learning_events = 0

        # Gateway configuration
        self.validation_enabled = True
        self.blocking_mode = False  # If True, blocks actions on validation failure
        self.learning_enabled = True

        logger.info(f"MemoryIntegrationGateway initialized for agent {agent_id}")

    async def pre_action_validation(
        self, action: Dict[str, Any], agent_memory: Optional[DualMemoryManager] = None
    ) -> Tuple[bool, ValidationResult]:
        """
        Validate action before execution against agent memory.

        Args:
            action: Proposed action to validate
            agent_memory: Optional specific memory manager (uses default if None)

        Returns:
            Tuple of (should_proceed, validation_result)
        """
        logger.info(
            f"Pre-action validation for agent {self.agent_id} - action: {action.get('type', 'unknown')}"
        )

        if not self.validation_enabled:
            # Create a simple passed validation result
            dummy_result = ValidationResult(
                agent_id=self.agent_id,
                action_validated=action,
                memories_checked=0,
                inconsistencies_found=[],
                validation_passed=True,
                confidence_score=1.0,
                recommendations=["validation_disabled"],
            )
            return True, dummy_result

        memory_mgr = agent_memory or self.memory_manager

        # Retrieve relevant memories for validation
        relevant_memories = await self._retrieve_relevant_memories(action, memory_mgr)

        # Perform validation
        validation_result = await self.consistency_checker.validate_memory_retrieval(
            relevant_memories, action
        )

        # Update statistics
        self.validations_performed += 1
        if validation_result.validation_passed:
            self.validations_passed += 1
        else:
            self.validations_failed += 1

        # Determine if action should proceed
        should_proceed = validation_result.validation_passed

        if not should_proceed and self.blocking_mode:
            self.actions_blocked += 1
            logger.warning(
                f"Action blocked due to validation failure: {action.get('type', 'unknown')}. Inconsistencies: {validation_result.inconsistencies_found}"
            )
        elif not should_proceed:
            logger.warning(
                f"Action validation failed but proceeding (non-blocking mode): {action.get('type', 'unknown')}. Inconsistencies: {validation_result.inconsistencies_found}"
            )
            should_proceed = True  # Allow action in non-blocking mode

        # Publish validation event
        await self._publish_validation_event(validation_result, should_proceed)

        logger.info(
            f"Pre-action validation completed - proceed: {should_proceed}, "
            f"confidence: {validation_result.confidence_score:.2f}"
        )

        return should_proceed, validation_result

    async def post_action_learning(
        self, action: Dict[str, Any], outcome: Dict[str, Any]
    ) -> bool:
        """
        Update memory system based on action results.

        Args:
            action: Action that was executed
            outcome: Results and outcomes from the action

        Returns:
            True if learning was successful
        """
        logger.info(
            f"Post-action learning for agent {self.agent_id} - action: {action.get('type', 'unknown')}"
        )

        if not self.learning_enabled:
            return True

        try:
            # Create learning event from action and outcome
            learning_event = self._create_learning_event_robust(action, outcome)

            # Store learning event in memory
            domain = self._determine_action_domain(action)
            success = await self.memory_manager.store_event(learning_event, domain)

            if success:
                self.learning_events += 1

                # Update consistency checker with new information
                await self._update_consistency_patterns(action, outcome)

                # Publish learning event
                await self._publish_learning_event(action, outcome)

                logger.info("Post-action learning completed successfully")
                return True
            else:
                logger.error("Failed to store learning event in memory")
                return False

        except Exception as e:
            logger.error(f"Error during post-action learning: {e}", exc_info=True)
            return False

    def get_gateway_status(self) -> Dict[str, Any]:
        """Get comprehensive gateway status and statistics."""
        total_validations = self.validations_performed
        success_rate = self.validations_passed / max(1, total_validations)

        status = {
            "agent_id": self.agent_id,
            "validation_enabled": self.validation_enabled,
            "blocking_mode": self.blocking_mode,
            "learning_enabled": self.learning_enabled,
            "statistics": {
                "validations_performed": self.validations_performed,
                "validations_passed": self.validations_passed,
                "validations_failed": self.validations_failed,
                "validation_success_rate": success_rate,
                "actions_blocked": self.actions_blocked,
                "learning_events": self.learning_events,
            },
            "consistency_checker_stats": self.consistency_checker.get_validation_statistics(),
        }

        return status

    def configure_gateway(
        self,
        validation_enabled: Optional[bool] = None,
        blocking_mode: Optional[bool] = None,
        learning_enabled: Optional[bool] = None,
    ):
        """Configure gateway behavior."""
        if validation_enabled is not None:
            self.validation_enabled = validation_enabled
            logger.info(f"Validation {'enabled' if validation_enabled else 'disabled'}")

        if blocking_mode is not None:
            self.blocking_mode = blocking_mode
            logger.info(f"Blocking mode {'enabled' if blocking_mode else 'disabled'}")

        if learning_enabled is not None:
            self.learning_enabled = learning_enabled
            logger.info(f"Learning {'enabled' if learning_enabled else 'disabled'}")

    # Private helper methods

    async def _retrieve_relevant_memories(
        self, action: Dict[str, Any], memory_mgr: DualMemoryManager
    ) -> List[MemoryEvent]:
        """Retrieve memories relevant to the proposed action (more specific query generation)."""
        action_type = action.get("type", "unknown")

        # Generate a more specific query based on known action types and parameters
        query_parts = [action_type]
        if action_type == "set_price" and "asin" in action.get("parameters", {}):
            query_parts.append(f"price of ASIN {action['parameters']['asin']}")
        elif action_type == "place_order" and "asin" in action.get("parameters", {}):
            query_parts.append(f"inventory for ASIN {action['parameters']['asin']}")
        elif action_type == "run_marketing_campaign" and "campaign_type" in action.get(
            "parameters", {}
        ):
            query_parts.append(
                f"marketing campaign for {action['parameters']['campaign_type']}"
            )

        query = " ".join(query_parts) if query_parts else "general market conditions"

        # Retrieve relevant memories
        relevant_memories = await memory_mgr.retrieve_memories(
            query, max_memories=self.config.max_retrieval_events
        )

        return relevant_memories

    def _create_learning_event_robust(
        self, action: Dict[str, Any], outcome: Dict[str, Any]
    ) -> BaseEvent:
        """
        Create a robust, type-safe learning event from action and outcome.
        Ensures dynamically added attributes are handled properly.
        """
        action_type = action.get("type", "unknown")
        success = outcome.get("success", False)
        impact = outcome.get("impact", {})

        # Construct content for the learning event
        learning_content = f"Agent performed action: {action_type}. Success: {success}. Impact: {json.dumps(impact)}"

        # Create a new BaseEvent (or a more specific LearningEvent type if defined)
        # Pass all relevant data as event_data
        event_data = {
            "action_type": action_type,
            "success": success,
            "impact": impact,
            "content": learning_content,  # Store the generated content here
            "agent_id": self.agent_id,  # Also include agent_id for context
        }

        # Create a BaseEvent instance and append data.
        # This approach ensures BaseEvent structure while adding rich metadata.
        learning_event = BaseEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type="AgentLearningEvent",  # A distinct event type for learning
            data=event_data,
        )

        return learning_event

    def _determine_action_domain(self, action: Dict[str, Any]) -> str:
        """Determine memory domain for an action."""
        action_type = action.get("type", "unknown")

        domain_mapping = {
            "set_price": "pricing",
            "place_order": "inventory",
            "run_marketing_campaign": "marketing",
            "respond_to_customer": "customer_service",
            "research_market": "market_intelligence",  # Example new domain
            "strategize": "strategy",  # Example new domain
        }

        return domain_mapping.get(action_type, "general")

    async def _update_consistency_patterns(
        self, action: Dict[str, Any], outcome: Dict[str, Any]
    ):
        """Update consistency checker with new patterns learned based on outcomes."""
        action_type = action.get("type", "unknown")
        success = outcome.get("success", False)

        # Dynamic adjustment of validation thresholds based on action outcome
        if success:
            # If an action succeeded, we might subtly relax the threshold for future similar actions
            # Or reinforce that certain patterns are valid.
            self.consistency_checker.contradiction_threshold = min(
                0.95, self.consistency_checker.contradiction_threshold * 1.01
            )
        else:
            # If an action failed, we should tighten the validation to prevent similar errors
            self.consistency_checker.contradiction_threshold = max(
                0.5, self.consistency_checker.contradiction_threshold * 0.95
            )

        logger.debug(
            f"[_update_consistency_patterns] Adjusted contradiction_threshold to {self.consistency_checker.contradiction_threshold:.2f}"
        )

    async def _publish_validation_event(
        self, validation_result: ValidationResult, should_proceed: bool
    ):
        """Publish validation event."""
        # Use asdict for better serialization of complex dataclass objects
        event_data = {
            "agent_id": self.agent_id,
            "event_type": "MemoryValidationCompleted",
            "timestamp": validation_result.validation_timestamp.isoformat(),
            "validation_result": validation_result.to_dict(),  # Full validation result object
            "should_proceed": should_proceed,
        }

        try:
            await self.event_bus.publish(
                BaseEvent(
                    event_id=validation_result.validation_id,  # Use validation_id as event_id
                    timestamp=validation_result.validation_timestamp,
                    event_type="MemoryValidationCompleted",
                    data=event_data,
                )
            )
        except Exception as e:
            logger.error(f"Failed to publish validation event: {e}", exc_info=True)

    async def _publish_learning_event(
        self, action: Dict[str, Any], outcome: Dict[str, Any]
    ):
        """Publish learning event."""
        learning_event_data = {
            "agent_id": self.agent_id,
            "action_type": action.get("type", "unknown"),
            "learning_success": outcome.get("success", False),
            "impact_metrics": outcome.get("impact", {}),
            "action_details": action,  # Include full action for detailed learning
        }

        try:
            await self.event_bus.publish(
                BaseEvent(
                    event_id=str(uuid.uuid4()),  # New UUID for the learning event
                    timestamp=datetime.now(),
                    event_type="AgentPostActionLearning",  # A specific event for this
                    data=learning_event_data,
                )
            )
        except Exception as e:
            logger.error(f"Failed to publish learning event: {e}", exc_info=True)
