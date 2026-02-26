"""
Reflection Module

Handles daily memory consolidation and sorting, determining which memories
get promoted from short-term to long-term storage using various algorithms.
It also includes an advanced structured reflection system for cognitive analysis.
"""

import json
import logging
import random
import statistics  # For calculating averages in quality metrics
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from fba_events import BaseEvent  # Corrected import path
from fba_events.bus import EventBus  # Corrected import path
from llm_interface.contract import BaseLLMClient  # Added import for BaseLLMClient

from .dual_memory_manager import DualMemoryManager, MemoryEvent
from .memory_config import ConsolidationAlgorithm, MemoryConfig

logger = logging.getLogger(__name__)


class ReflectionTrigger(Enum):
    """Types of reflection triggers for structured reflection loops."""

    PERIODIC = "periodic"
    EVENT_DRIVEN = "event_driven"
    PERFORMANCE_THRESHOLD = "performance_threshold"


@dataclass
class ReflectionInsight:
    """A structured insight generated from reflection analysis."""

    category: str  # e.g., "strategy", "performance", "behavior", "environment"
    title: str
    description: str
    evidence: List[str]  # Supporting evidence from analysis
    confidence: float  # 0.0 to 1.0
    actionability: float  # How actionable this insight is
    priority: str = "medium"  # "low", "medium", "high", "critical"
    suggested_actions: List[str] = field(default_factory=list)
    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyAdjustment:
    """A policy adjustment recommendation from reflection."""

    adjustment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_area: str = field(
        default=""
    )  # e.g., "pricing", "inventory", "marketing", "risk"
    current_parameters: Dict[str, Any] = field(default_factory=dict)
    recommended_parameters: Dict[str, Any] = field(default_factory=dict)
    rationale: str = field(default="")
    expected_impact: Dict[str, float] = field(default_factory=dict)
    confidence: float = field(default=0.0)
    implementation_urgency: str = (
        "next_cycle"  # "immediate", "within_day", "within_week", "next_cycle"
    )
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StructuredReflectionResult:
    """Comprehensive result from structured reflection process."""

    # Use defaults for all fields that appear after a defaulted field to satisfy dataclass ordering rules
    reflection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    trigger_type: ReflectionTrigger = ReflectionTrigger.PERIODIC
    reflection_timestamp: datetime = field(default_factory=datetime.now)
    analysis_period_start: datetime = field(default_factory=datetime.now)
    analysis_period_end: datetime = field(default_factory=datetime.now)

    # Analysis results
    decisions_analyzed: int = 0
    events_processed: int = 0
    performance_metrics: Dict[str, float] = field(
        default_factory=dict
    )  # Ensure default

    # Generated insights
    insights: List[ReflectionInsight] = field(default_factory=list)
    critical_insights_count: int = 0

    # Policy recommendations
    policy_adjustments: List[PolicyAdjustment] = field(default_factory=list)
    high_priority_adjustments: int = 0

    # Reflection quality metrics
    analysis_depth_score: float = 0.0
    insight_novelty_score: float = 0.0
    actionability_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["insights"] = [insight.to_dict() for insight in self.insights]
        data["policy_adjustments"] = [adj.to_dict() for adj in self.policy_adjustments]
        return data


@dataclass
class ConsolidationResult:
    """Results from a memory consolidation process."""

    memories_considered: int
    memories_promoted: int
    memories_discarded: int
    algorithm_used: str
    consolidation_time: datetime = field(default_factory=datetime.now)
    quality_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConsolidationAlgorithmBase(ABC):
    """Abstract base class for memory consolidation algorithms."""

    @abstractmethod
    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        """
        Score memories for consolidation priority.

        Args:
            memories: List of candidate memories for consolidation
            config: Memory configuration

        Returns:
            Dict mapping memory event_id to consolidation score (0.0 to 1.0)
        """

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """Get the name of this consolidation algorithm."""


class ImportanceScoreAlgorithm(ConsolidationAlgorithmBase):
    """Consolidation based on memory importance scores."""

    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        """Score memories based on their importance scores and configurable weights."""
        scores = {}
        current_time = datetime.now()

        for memory in memories:
            base_score = memory.importance_score

            # Boost score based on access frequency (configurable weight)
            access_boost_factor = config.consolidation_weights.get(  # type: ignore[attr-defined]
                "access_frequency_boost", 0.05
            )
            access_boost = min(
                config.consolidation_weights.get("max_access_boost", 0.3),  # type: ignore[attr-defined]
                memory.access_count * access_boost_factor,
            )

            # Boost score for recent access (configurable weight and decay)
            recency_boost = 0.0
            if memory.last_accessed:
                hours_since_access = (
                    current_time - memory.last_accessed
                ).total_seconds() / 3600
                recency_decay_hours = config.consolidation_weights.get(  # type: ignore[attr-defined]
                    "recency_decay_hours", 24
                )
                if hours_since_access < recency_decay_hours:
                    recency_boost_factor = config.consolidation_weights.get(  # type: ignore[attr-defined]
                        "recency_boost_factor", 0.2
                    )
                    recency_boost = recency_boost_factor * (
                        1 - hours_since_access / recency_decay_hours
                    )

            # Domain-specific adjustments (configurable weights from config)
            domain_multiplier = config.consolidation_weights.get(  # type: ignore[attr-defined]
                "domain_multipliers", {}
            ).get(memory.domain, 1.0)

            final_score = min(
                1.0, (base_score + access_boost + recency_boost) * domain_multiplier
            )
            scores[memory.event_id] = final_score

        return scores

    def get_algorithm_name(self) -> str:
        return "importance_score"


class RecencyFrequencyAlgorithm(ConsolidationAlgorithmBase):
    """Consolidation based on recency and frequency of access."""

    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        """Score memories using recency-frequency analysis and configurable parameters."""
        scores = {}  # type: ignore[var-annotated]
        current_time = datetime.now()

        if not memories:
            return scores

        max_access_count = max((m.access_count for m in memories), default=1)

        for memory in memories:
            # Frequency component (configurable weight)
            frequency_weight = config.consolidation_weights.get("frequency_weight", 0.5)  # type: ignore[attr-defined]
            frequency_score = min(
                frequency_weight,
                memory.access_count / max_access_count * frequency_weight,
            )

            # Recency component (configurable weight and decay)
            recency_weight = config.consolidation_weights.get("recency_weight", 0.5)  # type: ignore[attr-defined]
            recency_decay_days = config.consolidation_weights.get(  # type: ignore[attr-defined]
                "recency_decay_days", 7
            )
            recency_score = 0.0
            if memory.last_accessed:
                hours_since_access = (
                    current_time - memory.last_accessed
                ).total_seconds() / 3600
                if hours_since_access < recency_decay_days * 24:
                    recency_score = max(
                        0.0,
                        recency_weight
                        * (1 - hours_since_access / (recency_decay_days * 24)),
                    )

            scores[memory.event_id] = frequency_score + recency_score

        return scores

    def get_algorithm_name(self) -> str:
        return "recency_frequency"


class StrategicValueAlgorithm(ConsolidationAlgorithmBase):
    """Consolidation based on strategic business value and configurable weights."""

    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        """Score memories based on strategic business importance and configurable parameters."""
        scores = {}
        current_time = datetime.now()

        # Strategic event type weights (configurable from config)
        strategic_event_weights = config.consolidation_weights.get(  # type: ignore[attr-defined]
            "strategic_event_type_weights",
            {
                "SaleOccurred": 0.7,
                "CompetitorPriceUpdated": 0.8,
                "ProductPriceUpdated": 0.6,
                "BudgetWarning": 0.9,
                "BudgetExceeded": 1.0,
                "DemandOscillationEvent": 0.8,
                "FeeHikeEvent": 0.7,
                "ReviewBombEvent": 0.9,
                "ListingHijackEvent": 1.0,
            },
        )

        # Domain strategic importance (configurable from config)
        domain_strategic_weights = config.consolidation_weights.get(  # type: ignore[attr-defined]
            "domain_strategic_weights",
            {
                "strategy": 1.0,
                "pricing": 0.9,
                "competitors": 0.8,
                "sales": 0.7,
                "operations": 0.6,
            },
        )

        for memory in memories:
            base_weight = strategic_event_weights.get(memory.event_type, 0.3)

            # Adjust for memory age (configurable penalty)
            age_days = (current_time - memory.timestamp).days
            age_penalty_per_day = config.consolidation_weights.get(  # type: ignore[attr-defined]
                "age_penalty_per_day", 0.1
            )
            age_penalty = max(0.0, 1.0 - age_days * age_penalty_per_day)

            # Adjust for domain strategic importance
            domain_weight = domain_strategic_weights.get(memory.domain, 0.5)

            scores[memory.event_id] = base_weight * age_penalty * domain_weight

        return scores

    def get_algorithm_name(self) -> str:
        return "strategic_value"


class RandomSelectionAlgorithm(ConsolidationAlgorithmBase):
    """Random consolidation for baseline experiments."""

    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        """Assign random scores for baseline comparison."""
        scores = {}
        rng = random.Random(
            config.randomization_seed  # type: ignore[attr-defined]
        )  # Use config seed for reproducibility
        for memory in memories:
            scores[memory.event_id] = rng.random()

        return scores

    def get_algorithm_name(self) -> str:
        return "random_selection"


class LLMReflectionAlgorithm(ConsolidationAlgorithmBase):
    """LLM-based reflection for intelligent memory consolidation."""

    def __init__(
        self, llm_client: BaseLLMClient
    ):  # Made llm_client a required dependency
        if llm_client is None:
            raise ValueError(
                "LLM client must be provided for LLMReflectionAlgorithm."
            )  # Explicit error instead of silent fallback
        self.llm_client = llm_client
        # Define a flexible prompt template with placeholders
        self.prompt_template = """
You are an advanced cognitive reflection module for an FBA agent. Your task is to review a list of recent memories (events) and assess their strategic importance for long-term retention.

For each memory, provide a strategic importance score between 0.0 (not important) and 1.0 (critically important).

Consider the following criteria for importance:
- **Impact on long-term business goals:** Does this memory influence strategic decisions, market positioning, or sustained profitability?
- **Novelty/Surprise:** Was this an unexpected event or observation that changes the agent's understanding of the environment?
- **Actionability:** Does this memory directly inform potential future actions or prevent past mistakes?
- **Recurrence:** Is this a pattern or trend that the agent should learn from?
- **Severity/Magnitude:** For negative events, how significant was the impact?

Your output should be a JSON array of objects, each with the `event_id` of the memory and its `strategic_score`.

---

MEMORIES FOR REFLECTION:
{memories_json}

---

Provide your response as a JSON array ONLY:
[
    {{
        "event_id": "...",
        "strategic_score": 0.X
    }},
    ...
]
"""

    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        """Score memories using LLM-based reflection."""

        memory_summaries = []
        for memory in memories:
            memory_summaries.append(
                {
                    "event_id": memory.event_id,
                    "timestamp": memory.timestamp.isoformat(),
                    "content": memory.content,
                    "domain": memory.domain,
                    "event_type": memory.event_type,
                }
            )

        memories_json = json.dumps(memory_summaries, indent=2)
        full_prompt = self.prompt_template.format(
            memories_json=memories_json
        )  # Use templating

        try:
            llm_response = await self.llm_client.generate_response(
                prompt=full_prompt,
                # Corrected: use the LLM client's model name for generation
                model=self.llm_client.config.model,  # Assuming llm_client has a config attribute
                temperature=config.llm_reflection_config.llm_temperature,  # Configurable  # type: ignore[attr-defined]
                max_tokens=config.llm_reflection_config.llm_max_tokens,  # Configurable  # type: ignore[attr-defined]
            )

            response_content = (
                llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            )

            if not response_content:
                raise ValueError("LLM reflection response content is empty.")

            scores_list = json.loads(response_content)

            scores = {item["event_id"]: item["strategic_score"] for item in scores_list}

            # Validate scores
            for event_id, score in scores.items():
                if not (0.0 <= score <= 1.0):
                    logger.warning(
                        f"LLM returned out-of-range score {score} for {event_id}. Clamping to 0-1."
                    )
                    scores[event_id] = max(0.0, min(1.0, score))

            if not any(scores.values()):
                logger.warning(
                    "LLM reflection resulted in all zero scores. Falling back to ImportanceScoreAlgorithm."
                )
                fallback = ImportanceScoreAlgorithm()
                return await fallback.score_memories(memories, config)

            return scores

        except json.JSONDecodeError as e:
            logger.error(
                f"LLM reflection response was not valid JSON. Error: {e}. Response: {response_content[:500]}..."
            )
            logger.warning(
                "Falling back to ImportanceScoreAlgorithm due to invalid LLM response."
            )
            fallback = ImportanceScoreAlgorithm()
            return await fallback.score_memories(memories, config)
        except Exception as e:
            logger.error(f"Error during LLM reflection: {e}", exc_info=True)
            logger.warning(
                "Falling back to ImportanceScoreAlgorithm due to LLM reflection error."
            )
            fallback = ImportanceScoreAlgorithm()
            return await fallback.score_memories(memories, config)

    def get_algorithm_name(self) -> str:
        return "llm_reflection"


class ReflectionModule:
    """
    Daily reflection and memory consolidation system.

    Analyzes short-term memories and determines which should be promoted
    to long-term storage using configurable consolidation algorithms.
    It orchestrates the consolidation process and tracks its effectiveness.
    """

    def __init__(
        self,
        memory_manager: DualMemoryManager,
        config: MemoryConfig,
        llm_client: Optional[BaseLLMClient] = None,
    ):  # Added LLM client as optional dependency
        self.memory_manager = memory_manager
        self.config = config
        self.agent_id = memory_manager.agent_id
        self.llm_client = llm_client

        # Initialize consolidation algorithms, passing LLM client if available and needed
        self.algorithms: Dict[ConsolidationAlgorithm, ConsolidationAlgorithmBase] = {
            ConsolidationAlgorithm.IMPORTANCE_SCORE: ImportanceScoreAlgorithm(),
            ConsolidationAlgorithm.RECENCY_FREQUENCY: RecencyFrequencyAlgorithm(),
            ConsolidationAlgorithm.STRATEGIC_VALUE: StrategicValueAlgorithm(),
            ConsolidationAlgorithm.RANDOM_SELECTION: RandomSelectionAlgorithm(),
            ConsolidationAlgorithm.LLM_REFLECTION: (
                LLMReflectionAlgorithm(llm_client)
                if llm_client
                else _FallbackLLMReflectionAlgorithm(
                    "LLM client not provided for LLMReflectionAlgorithm. Falling back to importance scoring."
                )
            ),
        }

        # Reflection statistics
        self.reflection_history: List[ConsolidationResult] = []
        self.total_reflections = 0

        logger.info(f"ReflectionModule initialized for agent {self.agent_id}")

    async def perform_reflection(
        self, current_time: Optional[datetime] = None
    ) -> ConsolidationResult:
        """
        Perform a comprehensive reflection and memory consolidation cycle.

        Args:
            current_time: Current simulation time (defaults to now).

        Returns:
            ConsolidationResult with details about the consolidation process.
        """
        current_time = current_time or datetime.now()

        logger.info(
            f"Starting memory consolidation for agent {self.agent_id} at {current_time}"
        )

        candidate_memories = await self.memory_manager.get_memories_for_promotion()

        if not candidate_memories:
            logger.info(
                "No memories available for consolidation. Skipping consolidation."
            )
            return ConsolidationResult(
                memories_considered=0,
                memories_promoted=0,
                memories_discarded=0,
                consolidation_time=current_time,
                algorithm_used=self.config.consolidation_algorithm.value,
                quality_metrics={},
            )

        algorithm = self.algorithms.get(self.config.consolidation_algorithm)
        if not algorithm:
            logger.error(
                f"Configured consolidation algorithm {self.config.consolidation_algorithm.value} not found."
            )
            # Fallback to a default algorithm if the configured one is missing (e.g., ImportanceScoreAlgorithm)
            algorithm = ImportanceScoreAlgorithm()

        logger.debug(f"Using consolidation algorithm: {algorithm.get_algorithm_name()}")
        memory_scores = await algorithm.score_memories(candidate_memories, self.config)

        # Select memories for promotion based on scores and configured thresholds
        memories_to_promote = await self._select_memories_for_promotion(
            candidate_memories, memory_scores
        )

        promote_success = await self.memory_manager.promote_memories(
            memories_to_promote
        )
        if not promote_success:
            logger.warning(
                "Memory promotion encountered issues, not all memories might be promoted."
            )

        # Determine which memories to discard from short-term based on configured policy
        memories_to_discard = [
            m
            for m in candidate_memories
            if m.event_id not in [p.event_id for p in memories_to_promote]
            and self._should_discard_memory(m, current_time)
        ]

        if memories_to_discard:
            memory_ids_to_discard = [m.event_id for m in memories_to_discard]
            await self.memory_manager.short_term_store.remove(memory_ids_to_discard)
            logger.debug(
                f"Removed {len(memory_ids_to_discard)} old memories from short-term store"
            )

        quality_metrics = await self._calculate_quality_metrics(
            candidate_memories, memories_to_promote, memory_scores
        )

        result = ConsolidationResult(
            memories_considered=len(candidate_memories),
            memories_promoted=len(memories_to_promote),
            memories_discarded=len(memories_to_discard),
            consolidation_time=current_time,
            algorithm_used=algorithm.get_algorithm_name(),
            quality_metrics=quality_metrics,
        )

        self.reflection_history.append(result)
        self.total_reflections += 1
        self.memory_manager.last_reflection_time = (
            current_time  # Update manager's reflection time
        )

        logger.info(
            f"Consolidation completed: {result.memories_promoted} promoted, {result.memories_discarded} discarded. Algorithm: {result.algorithm_used}"
        )

        return result

    async def _select_memories_for_promotion(
        self, candidate_memories: List[MemoryEvent], memory_scores: Dict[str, float]
    ) -> List[MemoryEvent]:
        """Select memories for promotion based on scores, capacity, and configurable thresholds."""

        scored_memories = [
            (memory, memory_scores.get(memory.event_id, 0.0))
            for memory in candidate_memories
        ]
        scored_memories.sort(
            key=lambda x: x[1], reverse=True
        )  # Sort by score, highest first

        total_candidates = len(candidate_memories)

        # Determine max promotions based on consolidation percentage
        consolidation_percentage = (
            self.config.consolidation_config.consolidation_percentage  # type: ignore[attr-defined]
        )
        max_promotions_by_percentage = int(total_candidates * consolidation_percentage)

        # Check long-term memory capacity
        current_long_term_size = await self.memory_manager.long_term_store.size()
        available_capacity = max(
            0, self.config.long_term_capacity - current_long_term_size
        )

        # Final limit on promotions: Minimum of percentage-based and available capacity
        max_promotions = min(max_promotions_by_percentage, available_capacity)

        promotion_threshold = (
            self.config.consolidation_config.promotion_score_threshold  # type: ignore[attr-defined]
        )  # Configurable threshold

        memories_to_promote = []  # type: ignore[var-annotated]
        for memory, score in scored_memories:
            if len(memories_to_promote) >= max_promotions:
                break  # Capacity reached
            if score >= promotion_threshold:  # Only promote if score meets threshold
                memories_to_promote.append(memory)

        return memories_to_promote

    def _should_discard_memory(
        self, memory: MemoryEvent, current_time: datetime
    ) -> bool:
        """Determine if a memory should be discarded from short-term storage based on config."""

        # Check if memory has exceeded short-term retention period
        age = current_time - memory.timestamp
        max_age = timedelta(days=self.config.short_term_retention_days)
        if age > max_age:
            return True

        # Check if memory has low importance and hasn't been accessed (configurable thresholds)
        low_importance_threshold = (
            self.config.consolidation_config.discard_low_importance_threshold  # type: ignore[attr-defined]
        )
        if (
            memory.importance_score < low_importance_threshold
            and memory.access_count == 0
        ):
            return True

        # Add other potential discard criteria based on configuration
        return False

    async def _calculate_quality_metrics(
        self,
        candidate_memories: List[MemoryEvent],
        promoted_memories: List[MemoryEvent],
        memory_scores: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate quality metrics for the consolidation process."""
        if not candidate_memories:
            return {
                "promotion_rate": 0.0,
                "avg_promoted_score": 0.0,
                "avg_candidate_score": 0.0,
                "score_selectivity": 0.0,
                "domain_diversity": 0.0,
                "event_type_diversity": 0.0,
            }

        promotion_rate = len(promoted_memories) / len(candidate_memories)

        promoted_scores = [
            memory_scores.get(memory.event_id, 0.0) for memory in promoted_memories
        ]
        avg_promoted_score = (
            statistics.mean(promoted_scores) if promoted_scores else 0.0
        )

        all_scores = [
            memory_scores.get(memory.event_id, 0.0) for memory in candidate_memories
        ]
        avg_candidate_score = statistics.mean(all_scores) if all_scores else 0.0

        score_selectivity = avg_promoted_score - avg_candidate_score

        promoted_domains = set(memory.domain for memory in promoted_memories)
        domain_diversity = len(promoted_domains) / max(
            1, len(self.config.memory_domains)
        )  # Avoid ZeroDivisionError

        promoted_event_types = set(memory.event_type for memory in promoted_memories)
        event_type_diversity = len(
            promoted_event_types
        )  # Can normalize against total possible event types if known

        return {
            "promotion_rate": promotion_rate,
            "avg_promoted_score": avg_promoted_score,
            "avg_candidate_score": avg_candidate_score,
            "score_selectivity": score_selectivity,
            "domain_diversity": domain_diversity,
            "event_type_diversity": event_type_diversity,
        }

    def get_reflection_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about reflection history."""
        if not self.reflection_history:
            return {
                "total_reflections": 0,
                "avg_promotion_rate": 0.0,
                "avg_quality_score": 0.0,
                "total_memories_considered": 0,
                "total_memories_promoted": 0,
                "reflection_history": [],
            }

        total_considered = sum(r.memories_considered for r in self.reflection_history)
        total_promoted = sum(r.memories_promoted for r in self.reflection_history)
        avg_promotion_rate = total_promoted / max(1, total_considered)

        quality_scores_list = []
        for result in self.reflection_history:
            if result.quality_metrics:
                quality_scores_list.append(
                    result.quality_metrics.get("score_selectivity", 0.0)
                    * self.config.reflection_quality_weights.get(  # type: ignore[attr-defined]
                        "score_selectivity", 0.4
                    )
                    + result.quality_metrics.get("domain_diversity", 0.0)
                    * self.config.reflection_quality_weights.get(  # type: ignore[attr-defined]
                        "domain_diversity", 0.3
                    )
                    + result.quality_metrics.get("avg_promoted_score", 0.0)
                    * self.config.reflection_quality_weights.get(  # type: ignore[attr-defined]
                        "avg_promoted_score", 0.3
                    )
                )

        avg_quality_score = (
            statistics.mean(quality_scores_list) if quality_scores_list else 0.0
        )

        return {
            "total_reflections": self.total_reflections,
            "avg_promotion_rate": avg_promotion_rate,
            "avg_quality_score": avg_quality_score,
            "total_memories_considered": total_considered,
            "total_memories_promoted": total_promoted,
            "reflection_history": [
                result.to_dict()
                for result in self.reflection_history[
                    -self.config.reflection_history_size :  # type: ignore[attr-defined]
                ]
            ],  # Configurable history size
        }

    async def set_consolidation_algorithm(self, algorithm: ConsolidationAlgorithm):
        """Change the consolidation algorithm for future reflections."""
        if algorithm == ConsolidationAlgorithm.LLM_REFLECTION and not self.llm_client:
            raise ValueError(
                "Cannot set LLM_REFLECTION algorithm: LLM client not provided to ReflectionModule."
            )

        if algorithm in self.algorithms:
            self.config.consolidation_algorithm = algorithm
            logger.info(f"Consolidation algorithm changed to {algorithm.value}")
        else:
            raise ValueError(f"Unknown consolidation algorithm: {algorithm}")

    def clear_reflection_history(self):
        """Clear reflection history for fresh experiments."""
        self.reflection_history.clear()
        self.total_reflections = 0
        logger.info("Reflection history cleared")


# Fallback for LLMReflectionAlgorithm if no LLM client is provided
class _FallbackLLMReflectionAlgorithm(ConsolidationAlgorithmBase):
    def __init__(self, reason: str = "LLM client not available."):
        self.reason = reason
        logger.warning(f"Using FallbackLLMReflectionAlgorithm: {self.reason}")

    async def score_memories(
        self, memories: List[MemoryEvent], config: MemoryConfig
    ) -> Dict[str, float]:
        logger.warning(
            "FallbackLLMReflectionAlgorithm engaged. Scoring memories using ImportanceScoreAlgorithm."
        )
        importance_algo = ImportanceScoreAlgorithm()
        return await importance_algo.score_memories(memories, config)

    def get_algorithm_name(self) -> str:
        return "llm_reflection_fallback"


class ReflectionComponent:  # Refactored from StructuredReflectionLoop
    """
    Manages structured reflection processing within the agent.
    Delegates insight generation and policy adjustments to specialized handlers.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager: DualMemoryManager,
        config: MemoryConfig,
        event_bus: EventBus,
    ):
        self.agent_id = agent_id
        self.memory_manager = memory_manager
        self.config = config
        self.event_bus = event_bus
        self.reflection_history: List[StructuredReflectionResult] = []

    async def perform_structured_reflection(
        self,
        trigger_type: ReflectionTrigger,
        current_time: datetime,
        sim_events: List[Dict[str, Any]],
        agent_decisions: List[Dict[str, Any]],
        current_performance: Dict[str, float],
    ) -> StructuredReflectionResult:
        """
        Performs a comprehensive structured reflection cycle.
        """
        analysis_period_start = current_time - timedelta(
            hours=self.config.structured_reflection_config.analysis_period_hours  # type: ignore[attr-defined]
        )
        if (
            self.last_reflection_time  # type: ignore[has-type]
        ):  # Check if last reflection time is set for longer running agents
            analysis_period_start = self.last_reflection_time  # type: ignore[has-type]

        # Step 1: Gather and Analyze Data
        # Assume sim_events and agent_decisions are already filtered for the analysis period by caller
        decision_analysis = await self._analyze_recent_decisions(
            agent_decisions, current_performance
        )

        # Step 2: Generate Insights
        insights = await self._generate_insights(
            decision_analysis, sim_events, current_time
        )

        # Step 3: Generate Policy Adjustments
        policy_adjustments = await self._generate_policy_adjustments(
            insights, current_performance, current_time
        )

        # Step 4: Calculate Reflection Quality Metrics
        analysis_depth_score = self._calculate_analysis_depth_score(decision_analysis)
        insight_novelty_score = self._calculate_insight_novelty_score(insights)
        actionability_score = self._calculate_actionability_score(
            insights, policy_adjustments
        )

        reflection_result = StructuredReflectionResult(
            agent_id=self.agent_id,
            trigger_type=trigger_type,
            reflection_timestamp=current_time,
            analysis_period_start=analysis_period_start,
            analysis_period_end=current_time,
            decisions_analyzed=len(agent_decisions),
            events_processed=len(sim_events),
            performance_metrics=current_performance,
            insights=insights,
            critical_insights_count=len(
                [i for i in insights if i.priority == "critical"]
            ),
            policy_adjustments=policy_adjustments,
            high_priority_adjustments=len(
                [
                    a
                    for a in policy_adjustments
                    if a.implementation_urgency == "immediate"
                ]
            ),
            analysis_depth_score=analysis_depth_score,
            insight_novelty_score=insight_novelty_score,
            actionability_score=actionability_score,
        )
        self.reflection_history.append(reflection_result)
        self.last_reflection_time = current_time  # Update current reflection time
        return reflection_result

    async def _analyze_recent_decisions(
        self,
        agent_decisions: List[Dict[str, Any]],
        current_performance: Dict[str, float],
    ) -> Dict[str, Any]:
        """Analyzes recent agent decisions and their outcomes."""
        analysis: Dict[str, Any] = {
            "analysis_timestamp": datetime.now().isoformat(),
            "decisions_analyzed": len(agent_decisions),
            "performance_patterns": await self._identify_performance_patterns(
                agent_decisions, current_performance
            ),
            "decision_effectiveness": await self._analyze_decision_effectiveness(
                agent_decisions
            ),
            "failure_analysis": await self._analyze_decision_failures(agent_decisions),
            "success_factors": await self._analyze_decision_successes(agent_decisions),
            "recommendations": [],
        }
        analysis["recommendations"] = self._generate_decision_recommendations(analysis)
        return analysis

    async def _identify_performance_patterns(
        self, decisions: List[Dict[str, Any]], performance_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Identifies patterns and trends in agent performance."""
        patterns: Dict[str, Any] = {
            "trend": "stable",
            "cyclical_patterns": [],
            "performance_drivers": [],
            "risk_factors": [],
        }

        overall_score = performance_metrics.get("overall_score", 0.0)
        if (
            overall_score
            > self.config.structured_reflection_config.performance_threshold_improving  # type: ignore[attr-defined]
        ):
            patterns["trend"] = "improving"
        elif (
            overall_score
            < self.config.structured_reflection_config.performance_threshold_declining  # type: ignore[attr-defined]
        ):
            patterns["trend"] = "declining"

        # Add more sophisticated pattern detection logic here (e.g., ML-based anomaly detection)
        return patterns

    async def _analyze_decision_effectiveness(
        self, decisions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyzes the effectiveness of different types of decisions."""
        effectiveness_by_type: Dict[str, Dict[str, Any]] = {}
        decision_outcomes: Dict[str, List[bool]] = {}  # Track True/False for success

        for decision in decisions:
            d_type = decision.get("type", "unknown_decision")
            outcome = decision.get("success", False)  # Assuming 'success' key
            if d_type not in decision_outcomes:
                decision_outcomes[d_type] = []
            decision_outcomes[d_type].append(outcome)

        for d_type, outcomes_list in decision_outcomes.items():
            success_rate = (
                sum(outcomes_list) / len(outcomes_list) if outcomes_list else 0.0
            )
            effectiveness_by_type[d_type] = {
                "total_decisions": len(outcomes_list),
                "success_rate": success_rate,
                "average_impact_score": (
                    statistics.mean(
                        [
                            d.get("impact_score", 0.0)
                            for d in decisions
                            if d.get("type") == d_type
                            and d.get("impact_score") is not None
                        ]
                    )
                    if any(d.get("type") == d_type for d in decisions)
                    else 0.0
                ),
            }
        return effectiveness_by_type

    async def _analyze_decision_failures(
        self, decisions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyzes patterns and root causes of failed decisions."""
        failures = [d for d in decisions if not d.get("success", True)]
        # More sophisticated analysis would extract failure reasons, correlate with context etc.
        return {
            "total_failures": len(failures),
            "failure_rate": len(failures) / max(1, len(decisions)),
        }

    async def _analyze_decision_successes(
        self, decisions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyzes factors contributing to successful decisions."""
        successes = [d for d in decisions if d.get("success", False)]
        # More sophisticated analysis would extract common success factors
        return {
            "total_successes": len(successes),
            "success_rate": len(successes) / max(1, len(decisions)),
        }

    def _generate_decision_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generates recommendations based on the decision analysis."""
        recs = []
        failure_rate = analysis.get("failure_analysis", {}).get("failure_rate", 0.0)
        if (
            failure_rate
            > self.config.structured_reflection_config.failure_rate_threshold  # type: ignore[attr-defined]
        ):
            recs.append(
                "HIGH PRIORITY: Agent is experiencing frequent failures. Implement more robust decision-making processes."
            )

        # Add more complex conditional recommendations based on patterns, effectiveness etc.
        return recs

    async def _generate_insights(
        self,
        analysis_results: Dict[str, Any],
        sim_events: List[Dict[str, Any]],
        current_time: datetime,
    ) -> List[ReflectionInsight]:
        """Generates actionable insights from all analysis results."""
        insights: List[ReflectionInsight] = []

        # Example: Insight from performance decline
        if analysis_results.get("performance_patterns", {}).get("trend") == "declining":
            insights.append(
                ReflectionInsight(
                    category="performance",
                    title="Sustained Performance Decline",
                    description="Agent's overall performance metrics have shown a sustained declining trend over the analysis period.",
                    evidence=[
                        f"Performance metrics: {analysis_results['performance_patterns']}"
                    ],
                    confidence=0.9,
                    actionability=0.8,
                    priority="critical",  # High priority for performance issues
                    suggested_actions=[
                        "Initiate comprehensive strategy review.",
                        "Adjust market response parameters.",
                        "Investigate external factors from recent events.",
                    ],
                    created_at=current_time,
                )
            )

        # Example: Insight from high failure rate in a specific decision type
        for d_type, effectiveness in analysis_results.get(
            "decision_effectiveness", {}
        ).items():
            if (
                effectiveness.get("success_rate", 1.0)
                < self.config.structured_reflection_config.decision_failure_rate_threshold  # type: ignore[attr-defined]
            ):
                insights.append(
                    ReflectionInsight(
                        category="behavior",
                        title=f"Suboptimal {d_type.replace('_', ' ').title()} Decisions",
                        description=f"Agent consistently struggles with '{d_type}' decisions, indicated by a low success rate of {effectiveness.get('success_rate', 0.0):.2f}.",
                        evidence=[
                            f"Decision type: {d_type}, Success rate: {effectiveness.get('success_rate', 0.0):.2f}"
                        ],
                        confidence=0.85,
                        actionability=0.75,
                        priority="high",
                        suggested_actions=[
                            f"Re-evaluate '{d_type}' decision logic.",
                            "Gather more contextual data before '{d_type}' actions.",
                        ],
                        created_at=current_time,
                    )
                )

        # Add insights related to memory context from sim_events (placeholder concept)
        for event in sim_events:
            if "BudgetExceeded" in event.get(
                "event_type", ""
            ):  # Example: critical event triggering insight
                insights.append(
                    ReflectionInsight(
                        category="environment",
                        title="Budget Constraint Violation Detected",
                        description="A critical event, BudgetExceeded, occurred during the analysis period.",
                        evidence=[f"Event: {event}"],
                        confidence=0.95,
                        actionability=0.9,
                        priority="critical",
                        suggested_actions=[
                            "Review agent budgeting strategy.",
                            "Optimize resource allocation.",
                        ],
                        created_at=current_time,
                    )
                )

        # Rank all generated insights
        return await self._rank_insights_by_priority(insights)

    async def _generate_policy_adjustments(
        self,
        insights: List[ReflectionInsight],
        current_performance: Dict[str, float],
        current_time: datetime,
    ) -> List[PolicyAdjustment]:
        """Generates concrete policy adjustments based on high-priority insights."""
        adjustments: List[PolicyAdjustment] = []

        for insight in insights:
            if insight.priority in ["high", "critical"] and insight.suggested_actions:
                # Example: Adjust pricing policy if performance is declining due to price issues
                if (
                    "performance" in insight.category.lower()
                    and insight.title == "Sustained Performance Decline"
                    and current_performance.get("profit_margin", 0.0)
                    < self.config.structured_reflection_config.min_acceptable_profit_margin  # type: ignore[attr-defined]
                ):
                    adjustments.append(
                        PolicyAdjustment(
                            policy_area="pricing",
                            current_parameters={"strategy": "dynamic_pricing"},
                            recommended_parameters={
                                "strategy": "cost_plus_pricing_stable"
                            },
                            rationale=f"Performance decline linked to aggressive dynamic pricing under unstable market conditions. Insight: {insight.title}",
                            expected_impact={"profit_margin": 0.02, "stability": 0.1},
                            confidence=insight.confidence,
                            implementation_urgency="immediate",
                            created_at=current_time,
                        )
                    )

                # Example: Adjust risk management policy for high failure rates
                if (
                    "risk" in insight.category.lower()
                    and insight.title == "High Decision Failure Rate"
                ):
                    adjustments.append(
                        PolicyAdjustment(
                            policy_area="risk_management",
                            current_parameters={"risk_assessment_level": "basic"},
                            recommended_parameters={
                                "risk_assessment_level": "enhanced",
                                "pre_action_validation_enabled": True,
                            },
                            rationale=f"Systematic decision failures detected. Enhanced risk assessment and pre-action validation needed. Insight: {insight.title}",
                            expected_impact={
                                "failure_rate": -0.15,
                                "decision_quality": 0.1,
                            },
                            confidence=insight.confidence,
                            implementation_urgency="immediate",
                            created_at=current_time,
                        )
                    )

        return await self._validate_policy_adjustments(adjustments)

    async def _rank_insights_by_priority(
        self, insights: List[ReflectionInsight]
    ) -> List[ReflectionInsight]:
        """Ranks insights based on priority, confidence, and actionability."""
        priority_weights = (
            self.config.structured_reflection_config.insight_priority_weights  # type: ignore[attr-defined]
        )

        def insight_score(insight):
            p_weight = priority_weights.get(insight.priority, 1)
            return p_weight * insight.confidence * insight.actionability

        return sorted(insights, key=insight_score, reverse=True)

    def _calculate_analysis_depth_score(self, analysis: Dict[str, Any]) -> float:
        """Calculates a score for how deep and comprehensive the analysis was."""
        score = 0.0
        if analysis.get("decisions_analyzed", 0) > 0:
            score += 0.2
        if analysis.get("performance_patterns"):
            score += 0.2
        if analysis.get("decision_effectiveness"):
            score += 0.2
        if analysis.get("failure_analysis", {}).get("total_failures", 0) > 0:
            score += 0.2
        if analysis.get("success_factors", {}).get("total_successes", 0) > 0:
            score += 0.2
        return min(1.0, score)

    def _calculate_insight_novelty_score(
        self, insights: List[ReflectionInsight]
    ) -> float:
        """Calculates a score for how novel the generated insights are."""
        if not insights:
            return 0.0

        unique_titles = set(insight.title for insight in insights)
        # Placeholder: a more advanced implementation would compare against a historical log of insights
        return min(
            1.0, len(unique_titles) / (len(insights) + 1e-6) + (len(insights) > 0) * 0.2
        )  # Bonus for any insights

    def _calculate_actionability_score(
        self, insights: List[ReflectionInsight], adjustments: List[PolicyAdjustment]
    ) -> float:
        """Calculates a score for how actionable the reflection results are."""
        if not insights and not adjustments:
            return 0.0

        avg_insight_actionability = (
            statistics.mean([i.actionability for i in insights]) if insights else 0.0
        )
        adjustment_clarity_score = (
            statistics.mean([a.confidence for a in adjustments]) if adjustments else 0.0
        )

        num_high_priority_adjustments = len(
            [a for a in adjustments if a.implementation_urgency == "immediate"]
        )

        # Composite score
        score = (
            avg_insight_actionability * 0.5
            + adjustment_clarity_score * 0.3
            + (num_high_priority_adjustments / max(1, len(insights))) * 0.2
        )

        return min(1.0, score)

    async def _validate_policy_adjustments(
        self, adjustments: List[PolicyAdjustment]
    ) -> List[PolicyAdjustment]:
        """Validates and filters policy adjustments based on confidence and other criteria."""
        validated = []
        min_confidence = (
            self.config.structured_reflection_config.policy_adjustment_min_confidence  # type: ignore[attr-defined]
        )

        for adjustment in adjustments:
            if adjustment.confidence >= min_confidence:
                validated.append(adjustment)
            else:
                logger.warning(
                    f"Policy adjustment {adjustment.adjustment_id} for '{adjustment.policy_area}' excluded due to low confidence: {adjustment.confidence:.2f}"
                )
        return validated

    async def _publish_reflection_completed_event(
        self, reflection_result: StructuredReflectionResult
    ):
        """Publishes an event when structured reflection is completed."""
        event_data = reflection_result.to_dict()  # Use to_dict for full serialization

        try:
            await self.event_bus.publish(
                BaseEvent(
                    event_id=reflection_result.reflection_id,
                    timestamp=reflection_result.reflection_timestamp,
                    event_type="AgentStructuredReflectionCompleted",  # Specific event type
                    data=event_data,
                )
            )
        except Exception as e:
            logger.error(
                f"Failed to publish structured reflection completed event: {e}",
                exc_info=True,
            )


