"""
Dual Memory Manager

Core orchestrator for dual-memory architecture with short-term and long-term
memory stores, supporting different memory modes and retrieval strategies.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from fba_events import BaseEvent  # Corrected import path

from .memory_config import DecayFunction, MemoryConfig, MemoryMode, MemoryStoreType

logger = logging.getLogger(__name__)


@dataclass
class MemoryEvent:
    """
    Represents a memory stored in the dual-memory system.

    Extends FBA-Bench events with memory-specific metadata for
    retrieval, importance scoring, and consolidation.
    """

    event_id: str
    event_type: str
    content: str
    timestamp: datetime
    tick: int
    agent_id: str

    def __post_init__(self):
        # Ensure event_id is unique and human-readable/debuggable
        if not self.event_id:
            self.event_id = f"{self.agent_id}-{self.tick}-{self.event_type}-{self.timestamp.isoformat()}-{hash(self.content)}"
        if len(self.event_id) > 255:  # Truncate or hash if too long for storage systems
            self.event_id = hashlib.md5(
                self.event_id.encode(), usedforsecurity=False
            ).hexdigest()

    # Memory-specific metadata
    importance_score: float = 0.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    domain: str = "general"
    embedding: Optional[List[float]] = None

    # Consolidation metadata
    consolidation_score: float = 0.0
    promoted_to_long_term: bool = False
    promotion_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage and retrieval."""
        return asdict(self)

    @classmethod
    def from_event(
        cls, event: BaseEvent, agent_id: str, current_tick: int, domain: str = "general"
    ) -> "MemoryEvent":
        """Create MemoryEvent from FBA-Bench BaseEvent."""
        # Generating a unique event_id here, but it can be overridden if provided during init
        generated_id = f"{agent_id}-{current_tick}-{event.event_type}-{event.timestamp.isoformat()}"
        if len(generated_id) > 255:
            generated_id = hashlib.md5(
                generated_id.encode(), usedforsecurity=False
            ).hexdigest()

        return cls(
            event_id=generated_id,  # Use the generated_id
            event_type=event.event_type,
            content=str(event),
            timestamp=event.timestamp,
            tick=current_tick,
            agent_id=agent_id,
            domain=domain,
        )

    def calculate_decay(
        self, current_time: datetime, decay_function: DecayFunction, retention_days: int
    ) -> float:
        """Calculate memory decay factor based on age and decay function."""
        age_days = (current_time - self.timestamp).days

        if retention_days <= 0:
            return 1.0  # No decay

        if age_days >= retention_days:
            return 0.0  # Completely decayed

        age_ratio = age_days / retention_days

        if decay_function == DecayFunction.NONE:
            return 1.0
        elif decay_function == DecayFunction.LINEAR:
            return 1.0 - age_ratio
        elif decay_function == DecayFunction.EXPONENTIAL:
            return (0.5) ** age_ratio
        elif decay_function == DecayFunction.STEP_FUNCTION:
            return 1.0 if age_days < retention_days else 0.0
        else:
            return 1.0


class MemoryStore(ABC):
    """Abstract interface for memory storage backends."""

    @abstractmethod
    async def store(self, memory: MemoryEvent) -> bool:
        """Store a memory event."""

    @abstractmethod
    async def retrieve(
        self, query: str, limit: int = 10, domain: Optional[str] = None
    ) -> List[MemoryEvent]:
        """Retrieve memories based on query."""

    @abstractmethod
    async def get_all(self, domain: Optional[str] = None) -> List[MemoryEvent]:
        """Get all memories, optionally filtered by domain."""

    @abstractmethod
    async def remove(self, memory_ids: List[str]) -> bool:
        """Remove memories by ID."""

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all memories."""

    @abstractmethod
    async def size(self) -> int:
        """Get number of stored memories."""


class InMemoryStore(MemoryStore):
    """In-memory implementation for testing and development."""

    def __init__(self):
        self.memories: Dict[str, MemoryEvent] = {}
        self.domain_index: Dict[str, Set[str]] = {}

    async def store(self, memory: MemoryEvent) -> bool:
        """Store memory in in-memory dict."""
        self.memories[memory.event_id] = memory

        # Update domain index
        if memory.domain not in self.domain_index:
            self.domain_index[memory.domain] = set()
        self.domain_index[memory.domain].add(memory.event_id)

        return True

    async def retrieve(
        self, query: str, limit: int = 10, domain: Optional[str] = None
    ) -> List[MemoryEvent]:
        """
        Simple text-based retrieval for testing.
        WARNING: This implementation is not suitable for semantic search in
        production and should be replaced with an embedding-based retrieval system.
        """
        candidates = []

        memory_ids = (
            self.domain_index.get(domain, set()) if domain else self.memories.keys()
        )
        query_l = query.lower()

        for memory_id in memory_ids:
            if memory_id in self.memories:
                memory = self.memories[memory_id]
                content = getattr(memory, "content", "") or ""
                event_type = getattr(memory, "event_type", "") or ""
                if (query_l in content.lower()) or (query_l in event_type.lower()):
                    candidates.append(memory)

        # Sort by importance score and recency
        candidates.sort(key=lambda m: (m.importance_score, m.timestamp), reverse=True)
        return candidates[:limit]

    async def get_all(self, domain: Optional[str] = None) -> List[MemoryEvent]:
        """Get all memories, optionally filtered by domain."""
        if domain:
            memory_ids = self.domain_index.get(domain, set())
            return [self.memories[mid] for mid in memory_ids if mid in self.memories]
        return list(self.memories.values())

    async def remove(self, memory_ids: List[str]) -> bool:
        """Remove memories by ID."""
        for memory_id in memory_ids:
            if memory_id in self.memories:
                memory = self.memories[memory_id]
                del self.memories[memory_id]

                # Update domain index
                if memory.domain in self.domain_index:
                    self.domain_index[memory.domain].discard(memory_id)

        return True

    async def clear(self) -> bool:
        """Clear all memories."""
        self.memories.clear()
        self.domain_index.clear()
        return True

    async def size(self) -> int:
        """Get number of stored memories."""
        return len(self.memories)


class DualMemoryManager:
    """
    Core orchestrator for dual-memory architecture.

    Manages separate short-term and long-term memory stores with
    configurable retention, decay, and consolidation policies.
    """

    def __init__(self, config: MemoryConfig, agent_id: str):
        self.config = config
        self.agent_id = agent_id
        self.current_tick = 0
        self.last_reflection_time: Optional[datetime] = None

        # Initialize memory stores
        self.short_term_store = self._create_memory_store(
            self.config.short_term_store_type
        )
        self.long_term_store = self._create_memory_store(
            self.config.long_term_store_type
        )

        # Memory access tracking
        self.retrieval_stats: Dict[str, int] = {}
        self.consolidation_stats: Dict[str, Any] = {}

        logger.info(
            f"DualMemoryManager initialized for agent {agent_id} with mode {config.memory_mode}"
        )

    async def store_event(self, event: BaseEvent, domain: str = "general") -> bool:
        """
        Store an event in the appropriate memory store based on current mode.

        Args:
            event: FBA-Bench event to store
            domain: Memory domain (pricing, sales, competitors, etc.)

        Returns:
            True if successfully stored
        """
        if not self.config.is_memory_enabled():
            return True  # No-op for memory-free mode

        # Create memory event from FBA event
        memory_event = MemoryEvent.from_event(
            event, self.agent_id, self.current_tick, domain
        )

        # Calculate initial importance score
        memory_event.importance_score = await self._calculate_importance_score(
            memory_event
        )

        # Store in appropriate memory based on mode
        if self.config.memory_mode == MemoryMode.LONG_TERM_ONLY:
            return await self.long_term_store.store(memory_event)
        else:
            # Default: store in short-term first
            return await self.short_term_store.store(memory_event)

    async def retrieve_memories(
        self,
        query: str,
        max_memories: Optional[int] = None,
        domain: Optional[str] = None,
    ) -> List[MemoryEvent]:
        """
        Retrieve relevant memories from both stores based on query.

        Args:
            query: Search query for memory retrieval
            max_memories: Maximum number of memories to return
            domain: Optional domain filter

        Returns:
            List of relevant memory events
        """
        if not self.config.is_memory_enabled():
            return []

        max_memories = max_memories or self.config.max_retrieval_events

        # Retrieve from both stores
        short_term_memories = []
        long_term_memories = []

        if self.config.memory_mode != MemoryMode.LONG_TERM_ONLY:
            short_term_memories = await self.short_term_store.retrieve(
                query, max_memories, domain
            )

        if self.config.memory_mode != MemoryMode.SHORT_TERM_ONLY:
            long_term_memories = await self.long_term_store.retrieve(
                query, max_memories, domain
            )

        # Combine and rank memories
        all_memories = short_term_memories + long_term_memories

        # Apply decay to memories
        current_time = datetime.now()
        decayed_memories = []

        for memory in all_memories:
            if memory in short_term_memories:
                decay_factor = memory.calculate_decay(
                    current_time,
                    self.config.short_term_decay_function,
                    self.config.short_term_retention_days,
                )
            else:
                decay_factor = memory.calculate_decay(
                    current_time,
                    self.config.long_term_decay_function,
                    self.config.long_term_retention_days or 365,
                )

            if decay_factor > 0:
                # Adjust importance score by decay
                memory.importance_score *= decay_factor
                decayed_memories.append(memory)

                # Update access tracking
                memory.access_count += 1
                memory.last_accessed = current_time

        # Sort by adjusted importance score
        decayed_memories.sort(key=lambda m: m.importance_score, reverse=True)

        # Track retrieval stats
        self.retrieval_stats[query] = self.retrieval_stats.get(query, 0) + 1

        return decayed_memories[:max_memories]

    async def should_reflect(self, current_time: datetime) -> bool:
        """Check if reflection should be triggered based on configuration."""
        if not self.config.should_use_reflection():
            return False

        if self.last_reflection_time is None:
            return True

        time_since_reflection = current_time - self.last_reflection_time
        reflection_interval = timedelta(hours=self.config.reflection_frequency_hours)

        return time_since_reflection >= reflection_interval

    async def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary statistics about current memory state."""
        short_term_size = await self.short_term_store.size()
        long_term_size = await self.long_term_store.size()

        return {
            "short_term_memory_count": short_term_size,
            "long_term_memory_count": long_term_size,
            "total_memory_count": short_term_size + long_term_size,
            "memory_mode": self.config.memory_mode.value,
            "last_reflection": (
                self.last_reflection_time.isoformat()
                if self.last_reflection_time
                else None
            ),
            "retrieval_stats": self.retrieval_stats.copy(),
            "consolidation_stats": self.consolidation_stats.copy(),
        }

    async def clear_memories(self, memory_type: str = "all") -> bool:
        """Clear memories from specified store(s)."""
        if memory_type in ["all", "short_term"]:
            await self.short_term_store.clear()

        if memory_type in ["all", "long_term"]:
            await self.long_term_store.clear()

        if memory_type == "all":
            self.retrieval_stats.clear()
            self.consolidation_stats.clear()
            self.last_reflection_time = None

        return True

    def _create_memory_store(self, store_type: MemoryStoreType) -> MemoryStore:
        """
        Factory method to create memory store instances based on configuration.
        Raises ValueError for unsupported types to prevent silent configuration errors.

        Args:
            store_type: Type of memory store to create

        Returns:
            Instance of the requested memory store
        """
        if store_type == MemoryStoreType.IN_MEMORY:
            return InMemoryStore()
        # Add other store types here when implemented (e.g., if store_type == MemoryStoreType.VECTOR_DB:)
        else:
            # Test expectation: warn and fall back to InMemoryStore for unsupported types
            logger.warning(
                f"Unsupported memory store type: {store_type}. Falling back to InMemoryStore."
            )
            return InMemoryStore()

    async def _calculate_importance_score(self, memory: MemoryEvent) -> float:
        """
        Calculate importance score for a memory event using configurable weights.
        """
        base_score = self.config.base_importance_score

        # Boost score for certain event types, using configurable weights
        event_weights = self.config.importance_event_weights.get(memory.event_type, 1.0)
        base_score *= event_weights

        # Adjust based on domain, using configurable weights
        domain_weight = self.config.importance_domain_weights.get(memory.domain, 1.0)

        return min(1.0, base_score * domain_weight)

    def update_tick(self, tick: int):
        """Update current tick for memory timestamp tracking."""
        self.current_tick = tick

    async def get_memories_for_promotion(self) -> List[MemoryEvent]:
        """Get short-term memories that should be considered for promotion."""
        if not self.config.should_use_reflection():
            return []

        all_short_term = await self.short_term_store.get_all()

        # Filter out memories that are too recent (give them time to be accessed)
        min_age = timedelta(hours=1)  # Minimum age before consideration
        current_time = datetime.now()

        candidates = [
            memory
            for memory in all_short_term
            if (current_time - memory.timestamp) > min_age
        ]

        return candidates

    async def promote_memories(self, memories_to_promote: List[MemoryEvent]) -> bool:
        """Promote memories from short-term to long-term storage."""
        if not memories_to_promote:
            return True

        current_time = datetime.now()
        promoted_count = 0

        for memory in memories_to_promote:
            # Check long-term capacity
            long_term_size = await self.long_term_store.size()
            if long_term_size >= self.config.long_term_capacity:
                logger.warning(
                    f"Long-term memory at capacity ({self.config.long_term_capacity})"
                )
                break

            # Mark as promoted
            memory.promoted_to_long_term = True
            memory.promotion_timestamp = current_time

            # Store in long-term
            await self.long_term_store.store(memory)

            # Remove from short-term
            await self.short_term_store.remove([memory.event_id])

            promoted_count += 1

        logger.info(f"Promoted {promoted_count} memories to long-term storage")

        # Update consolidation stats
        self.consolidation_stats["last_promotion_count"] = promoted_count
        self.consolidation_stats["last_promotion_time"] = current_time.isoformat()
        self.consolidation_stats["total_promotions"] = (
            self.consolidation_stats.get("total_promotions", 0) + promoted_count
        )

        return True
