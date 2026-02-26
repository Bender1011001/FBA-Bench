"""
Memory Mode Implementations

Concrete implementations of different memory modes for systematic experimentation,
including reflection-enabled, consolidation-disabled, and various hybrid approaches.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fba_events.bus import EventBus  # Corrected import path

from .dual_memory_manager import DualMemoryManager, MemoryEvent
from .memory_config import MemoryConfig, MemoryMode
from .memory_enforcer import MemoryEnforcer
from .reflection_module import ReflectionModule

logger = logging.getLogger(__name__)


class MemoryModeStrategy(ABC):
    """
    Abstract base class for memory mode strategies.

    Each strategy implements a different approach to memory management,
    enabling systematic comparison of memory architectures.
    """

    def __init__(self, config: MemoryConfig, agent_id: str, event_bus: EventBus):
        self.config = config
        self.agent_id = agent_id
        self.event_bus = event_bus

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the memory mode strategy."""

    @abstractmethod
    async def store_event(self, event, domain: str = "general") -> bool:
        """Store an event according to this mode's strategy."""

    @abstractmethod
    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve memories according to this mode's strategy."""

    @abstractmethod
    async def update_tick(self, tick: int):
        """Update for new simulation tick."""

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about this memory mode's performance."""

    @abstractmethod
    async def cleanup(self):
        """Clean up resources used by this memory mode."""

    def get_mode_name(self) -> str:
        """Get the name of this memory mode."""
        return self.__class__.__name__


class MemoryFreeMode(MemoryModeStrategy):
    """
    Memory-free mode for baseline experiments.

    No persistent memory - only provides current tick context.
    Useful for establishing baseline performance without memory assistance.
    """

    def __init__(self, config: MemoryConfig, agent_id: str, event_bus: EventBus):
        super().__init__(config, agent_id, event_bus)
        self.current_tick_events: List[MemoryEvent] = []
        self.stats = {"events_ignored": 0, "retrievals_attempted": 0}

    async def initialize(self) -> bool:
        """Initialize memory-free mode."""
        logger.info(f"MemoryFreeMode initialized for agent {self.agent_id}")
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event only for current tick (no persistence)."""
        # Create memory event but don't persist it
        memory_event = MemoryEvent.from_event(event, self.agent_id, 0, domain)

        # Only keep current tick events
        self.current_tick_events.append(memory_event)

        # Limit to recent events only
        if len(self.current_tick_events) > 10:
            self.current_tick_events = self.current_tick_events[-10:]

        self.stats["events_ignored"] += 1
        return True

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """
        Return an empty list as this mode is 'memory-free'.
        This explicitly contradicts its previous behavior of returning current_tick_events for a true baseline.
        """
        self.stats["retrievals_attempted"] += 1
        return []  # Empty list for memory-free mode

    async def update_tick(self, tick: int):
        """Clear previous tick events."""
        self.current_tick_events.clear()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory-free mode statistics."""
        return {
            "mode": "memory_free",
            "total_events_ignored": self.stats["events_ignored"],
            "total_retrievals": self.stats["retrievals_attempted"],
            "current_tick_events": len(self.current_tick_events),
        }

    async def cleanup(self):
        """Clean up memory-free mode."""
        self.current_tick_events.clear()
        self.stats.clear()


class ShortTermOnlyMode(MemoryModeStrategy):
    """
    Short-term memory only mode.

    Uses only short-term memory store with configurable retention period.
    No long-term storage or reflection/consolidation.
    """

    def __init__(self, config: MemoryConfig, agent_id: str, event_bus: EventBus):
        super().__init__(config, agent_id, event_bus)
        self.memory_manager = DualMemoryManager(config, agent_id)

    async def initialize(self) -> bool:
        """Initialize short-term only mode."""
        logger.info(f"ShortTermOnlyMode initialized for agent {self.agent_id}")
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event in short-term memory only."""
        return await self.memory_manager.store_event(event, domain)

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve from short-term memory only."""
        # Only retrieve from short-term store
        return await self.memory_manager.short_term_store.retrieve(query, max_memories)

    async def update_tick(self, tick: int):
        """Update tick and perform memory decay."""
        self.memory_manager.update_tick(tick)

        # Perform aggressive cleanup of old short-term memories
        await self._cleanup_old_memories()

    async def _cleanup_old_memories(self):
        """Remove old memories that exceed retention period."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(
            days=self.config.short_term_retention_days
        )

        all_memories = await self.memory_manager.short_term_store.get_all()
        memories_to_remove = [
            memory.event_id for memory in all_memories if memory.timestamp < cutoff_time
        ]

        if memories_to_remove:
            await self.memory_manager.short_term_store.remove(memories_to_remove)
            logger.debug(
                f"Removed {len(memories_to_remove)} old memories from short-term store"
            )

    async def get_statistics(self) -> Dict[str, Any]:
        """Get short-term only mode statistics."""
        short_term_size = await self.memory_manager.short_term_store.size()

        return {
            "mode": "short_term_only",
            "short_term_memory_count": short_term_size,
            "retention_days": self.config.short_term_retention_days,
            "capacity_utilization": short_term_size / self.config.short_term_capacity,
        }

    async def cleanup(self):
        """Clean up short-term only mode."""
        await self.memory_manager.clear_memories("short_term")


class LongTermOnlyMode(MemoryModeStrategy):
    """
    Long-term memory only mode.

    All events are immediately stored in long-term memory.
    No short-term storage or forgetting.
    """

    def __init__(self, config: MemoryConfig, agent_id: str, event_bus: EventBus):
        super().__init__(config, agent_id, event_bus)
        self.memory_manager = DualMemoryManager(config, agent_id)

    async def initialize(self) -> bool:
        """Initialize long-term only mode."""
        logger.info(f"LongTermOnlyMode initialized for agent {self.agent_id}")
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event directly in long-term memory."""
        memory_event = MemoryEvent.from_event(
            event, self.agent_id, self.memory_manager.current_tick, domain
        )
        memory_event.importance_score = (
            await self.memory_manager._calculate_importance_score(memory_event)
        )

        # Store directly in long-term memory
        return await self.memory_manager.long_term_store.store(memory_event)

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve from long-term memory only."""
        return await self.memory_manager.long_term_store.retrieve(query, max_memories)

    async def update_tick(self, tick: int):
        """Update tick - no special processing for long-term only."""
        self.memory_manager.update_tick(tick)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get long-term only mode statistics."""
        long_term_size = await self.memory_manager.long_term_store.size()

        return {
            "mode": "long_term_only",
            "long_term_memory_count": long_term_size,
            "capacity_utilization": long_term_size / self.config.long_term_capacity,
        }

    async def cleanup(self):
        """Clean up long-term only mode."""
        await self.memory_manager.clear_memories("long_term")


class ReflectionEnabledMode(MemoryModeStrategy):
    """
    Full dual-memory mode with reflection and consolidation.

    Uses both short-term and long-term memory with daily reflection
    to consolidate important memories from short-term to long-term storage.
    """

    def __init__(self, config: MemoryConfig, agent_id: str, event_bus: EventBus):
        super().__init__(config, agent_id, event_bus)
        self.memory_manager = DualMemoryManager(config, agent_id)
        self.reflection_module = ReflectionModule(self.memory_manager, config)
        self.memory_enforcer = MemoryEnforcer(config, agent_id, event_bus)

    async def initialize(self) -> bool:
        """Initialize reflection-enabled mode."""
        logger.info(f"ReflectionEnabledMode initialized for agent {self.agent_id}")
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event using full memory system."""
        return await self.memory_enforcer.store_event_in_memory(event, domain)

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve memories from both short-term and long-term stores."""
        return await self.memory_manager.retrieve_memories(query, max_memories)

    async def update_tick(self, tick: int):
        """Update tick and check for reflection triggers."""
        self.memory_enforcer.update_tick(tick)

        # Check if reflection should be triggered
        await self.memory_enforcer.check_reflection_trigger()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get reflection-enabled mode statistics."""
        memory_stats = await self.memory_enforcer.get_memory_statistics()
        return {"mode": "reflection_enabled", **memory_stats}

    async def cleanup(self):
        """Clean up reflection-enabled mode."""
        await self.memory_enforcer.clear_memory_history()


class ConsolidationDisabledMode(MemoryModeStrategy):
    """
    Dual-memory mode without intelligent consolidation.

    Uses both memory stores but with simple time-based promotion
    instead of reflection-based consolidation.
    """

    def __init__(
        self, config: MemoryConfig, agent_id: str, event_bus: EventBus, **kwargs
    ):
        super().__init__(config, agent_id, event_bus)
        # Disable reflection for this mode by creating a deep copy and modifying it
        from copy import (
            deepcopy,  # Import deepcopy locally to avoid circular dependencies if it's not a top-level import
        )

        config_copy = deepcopy(config)
        config_copy.reflection_enabled = False

        self.memory_manager = DualMemoryManager(config_copy, agent_id)
        self.promotion_interval_hours = kwargs.get(
            "promotion_interval_hours", 24
        )  # Make configurable
        self.last_promotion_time: Optional[datetime] = None

    async def initialize(self) -> bool:
        """Initialize consolidation-disabled mode."""
        logger.info(f"ConsolidationDisabledMode initialized for agent {self.agent_id}")
        self.last_promotion_time = datetime.now()
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event in short-term memory."""
        return await self.memory_manager.store_event(event, domain)

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve from both memory stores."""
        return await self.memory_manager.retrieve_memories(query, max_memories)

    async def update_tick(self, tick: int):
        """Update tick and perform time-based promotion."""
        self.memory_manager.update_tick(tick)

        current_time = datetime.now()
        if self.last_promotion_time is None:
            self.last_promotion_time = current_time

        # Check if it's time for time-based promotion
        time_since_promotion = current_time - self.last_promotion_time
        if time_since_promotion >= timedelta(hours=self.promotion_interval_hours):
            await self._perform_time_based_promotion()
            self.last_promotion_time = current_time

    async def _perform_time_based_promotion(self):
        """Perform simple time-based memory promotion."""
        # Get all short-term memories older than 1 day
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=1)

        all_short_term = await self.memory_manager.short_term_store.get_all()
        memories_to_promote = [
            memory for memory in all_short_term if memory.timestamp < cutoff_time
        ]

        # Promote oldest memories up to consolidation percentage
        max_promotions = int(
            len(memories_to_promote) * self.config.consolidation_percentage
        )

        # Sort by timestamp (oldest first) and promote
        memories_to_promote.sort(key=lambda m: m.timestamp)
        selected_memories = memories_to_promote[:max_promotions]

        if selected_memories:
            await self.memory_manager.promote_memories(selected_memories)
            logger.info(
                f"Time-based promotion: {len(selected_memories)} memories promoted"
            )

    async def get_statistics(self) -> Dict[str, Any]:
        """Get consolidation-disabled mode statistics."""
        memory_summary = await self.memory_manager.get_memory_summary()

        return {
            "mode": "consolidation_disabled",
            "promotion_method": "time_based",
            "last_promotion": (
                self.last_promotion_time.isoformat()
                if self.last_promotion_time
                else None
            ),
            **memory_summary,
        }

    async def cleanup(self):
        """Clean up consolidation-disabled mode."""
        await self.memory_manager.clear_memories("all")


class HybridReflectionMode(MemoryModeStrategy):
    """
    Hybrid mode with configurable reflection frequency and criteria.

    Allows for experimentation with different reflection schedules
    and consolidation thresholds.
    """

    def __init__(self, config: MemoryConfig, agent_id: str, event_bus: EventBus):
        super().__init__(config, agent_id, event_bus)
        self.memory_manager = DualMemoryManager(config, agent_id)
        self.reflection_module = ReflectionModule(self.memory_manager, config)

        # Hybrid-specific settings
        self.adaptive_reflection = (
            True  # Adjust reflection frequency based on memory load
        )
        self.reflection_threshold = (
            0.8  # Trigger reflection when short-term is 80% full
        )

    async def initialize(self) -> bool:
        """Initialize hybrid reflection mode."""
        logger.info(f"HybridReflectionMode initialized for agent {self.agent_id}")
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event with adaptive reflection triggering."""
        result = await self.memory_manager.store_event(event, domain)

        # Check if adaptive reflection should be triggered
        if self.adaptive_reflection:
            await self._check_adaptive_reflection_trigger()

        return result

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve memories with hybrid strategy."""
        return await self.memory_manager.retrieve_memories(query, max_memories)

    async def update_tick(self, tick: int):
        """Update tick with hybrid reflection logic."""
        self.memory_manager.update_tick(tick)

        # Regular time-based reflection check
        current_time = datetime.now()
        if await self.memory_manager.should_reflect(current_time):
            await self.reflection_module.perform_reflection(current_time)

    async def _check_adaptive_reflection_trigger(self):
        """Check if reflection should be triggered based on memory load."""
        short_term_size = await self.memory_manager.short_term_store.size()
        short_term_utilization = short_term_size / self.config.short_term_capacity

        if short_term_utilization >= self.reflection_threshold:
            logger.info(
                f"Adaptive reflection triggered at {short_term_utilization:.2%} utilization"
            )
            await self.reflection_module.perform_reflection()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get hybrid reflection mode statistics."""
        memory_summary = await self.memory_manager.get_memory_summary()
        reflection_stats = self.reflection_module.get_reflection_statistics()

        short_term_size = await self.memory_manager.short_term_store.size()
        short_term_utilization = short_term_size / self.config.short_term_capacity

        return {
            "mode": "hybrid_reflection",
            "adaptive_reflection": self.adaptive_reflection,
            "reflection_threshold": self.reflection_threshold,
            "current_utilization": short_term_utilization,
            "memory_summary": memory_summary,
            "reflection_statistics": reflection_stats,
        }

    async def cleanup(self):
        """Clean up hybrid reflection mode."""
        await self.memory_manager.clear_memories("all")
        self.reflection_module.clear_reflection_history()


class SelectiveMemoryMode(MemoryModeStrategy):
    """
    Selective memory mode that only stores specific types of events.

    Useful for testing domain-specific memory effects
    (e.g., only pricing events, only sales events).
    """

    def __init__(
        self,
        config: MemoryConfig,
        agent_id: str,
        event_bus: EventBus,
        allowed_domains: List[str] = None,
        allowed_event_types: List[str] = None,
    ):
        super().__init__(config, agent_id, event_bus)
        self.memory_manager = DualMemoryManager(config, agent_id)

        # Selective filtering criteria
        self.allowed_domains = allowed_domains or ["all"]
        self.allowed_event_types = allowed_event_types or []

        # Statistics
        self.events_filtered = 0
        self.events_stored = 0

    async def initialize(self) -> bool:
        """Initialize selective memory mode."""
        logger.info(f"SelectiveMemoryMode initialized for agent {self.agent_id}")
        logger.info(f"Allowed domains: {self.allowed_domains}")
        logger.info(f"Allowed event types: {self.allowed_event_types}")
        return True

    async def store_event(self, event, domain: str = "general") -> bool:
        """Store event only if it meets selection criteria."""

        # Check domain filter
        if "all" not in self.allowed_domains and domain not in self.allowed_domains:
            self.events_filtered += 1
            return True  # Silently ignore

        # Check event type filter
        if (
            self.allowed_event_types
            and event.event_type not in self.allowed_event_types
        ):
            self.events_filtered += 1
            return True  # Silently ignore

        # Store the event
        result = await self.memory_manager.store_event(event, domain)
        if result:
            self.events_stored += 1

        return result

    async def retrieve_memories(
        self, query: str, max_memories: int = 10
    ) -> List[MemoryEvent]:
        """Retrieve memories with selective filtering."""
        memories = await self.memory_manager.retrieve_memories(query, max_memories)

        # Additional filtering during retrieval if needed
        filtered_memories = []
        for memory in memories:
            if (
                "all" in self.allowed_domains or memory.domain in self.allowed_domains
            ) and (
                not self.allowed_event_types
                or memory.event_type in self.allowed_event_types
            ):
                filtered_memories.append(memory)

        return filtered_memories[:max_memories]

    async def update_tick(self, tick: int):
        """Update tick for selective memory mode."""
        self.memory_manager.update_tick(tick)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get selective memory mode statistics."""
        memory_summary = await self.memory_manager.get_memory_summary()

        total_events = self.events_stored + self.events_filtered
        selection_rate = self.events_stored / total_events if total_events > 0 else 0.0

        return {
            "mode": "selective_memory",
            "allowed_domains": self.allowed_domains,
            "allowed_event_types": self.allowed_event_types,
            "events_stored": self.events_stored,
            "events_filtered": self.events_filtered,
            "selection_rate": selection_rate,
            "memory_summary": memory_summary,
        }

    async def cleanup(self):
        """Clean up selective memory mode."""
        await self.memory_manager.clear_memories("all")
        self.events_filtered = 0
        self.events_stored = 0


class MemoryModeFactory:
    """
    Factory for creating memory mode instances based on configuration.

    Simplifies the creation and management of different memory modes
    for experimental purposes.
    """

    @staticmethod
    def create_memory_mode(
        config: MemoryConfig, agent_id: str, event_bus: EventBus, **kwargs
    ) -> MemoryModeStrategy:
        """
        Create a memory mode instance based on configuration.

        Args:
            config: Memory configuration
            agent_id: Agent identifier
            event_bus: Event bus for communication
            **kwargs: Additional arguments for specific modes

        Returns:
            Configured memory mode instance
        """

        mode_mapping = {
            MemoryMode.MEMORY_FREE: MemoryFreeMode,
            MemoryMode.SHORT_TERM_ONLY: ShortTermOnlyMode,
            MemoryMode.LONG_TERM_ONLY: LongTermOnlyMode,
            MemoryMode.REFLECTION_ENABLED: ReflectionEnabledMode,
            MemoryMode.CONSOLIDATION_DISABLED: ConsolidationDisabledMode,
            MemoryMode.HYBRID_REFLECTION: HybridReflectionMode,
            getattr(MemoryMode, 'SELECTIVE_MEMORY', None): SelectiveMemoryMode,  # Added SelectiveMemoryMode to mapping  # type: ignore[attr-defined]
        }

        mode_class = mode_mapping.get(config.memory_mode)

        if mode_class is None:
            raise ValueError(f"Unknown memory mode: {config.memory_mode}")

        # All modes should be able to accept **kwargs in their __init__ if needed,
        # so we can simplify this logic.
        return mode_class(
            config, agent_id, event_bus, **kwargs
        )  # Pass kwargs to all modes

    @staticmethod
    def get_available_modes() -> List[MemoryMode]:
        """Get list of available memory modes."""
        return list(MemoryMode)

    @staticmethod
    def get_mode_description(mode: MemoryMode) -> str:
        """Get description of a memory mode."""
        descriptions = {
            MemoryMode.MEMORY_FREE: "No persistent memory - current tick context only",
            MemoryMode.SHORT_TERM_ONLY: "Short-term memory with configurable retention period",
            MemoryMode.LONG_TERM_ONLY: "Long-term memory without forgetting",
            MemoryMode.REFLECTION_ENABLED: "Full dual-memory with daily reflection and consolidation",
            MemoryMode.CONSOLIDATION_DISABLED: "Dual-memory with time-based promotion instead of reflection",
            MemoryMode.HYBRID_REFLECTION: "Adaptive reflection based on memory load and time",
            getattr(MemoryMode, 'SELECTIVE_MEMORY', None): "Stores only specific types of events or from allowed domains.",  # type: ignore[attr-defined]
        }

        return descriptions.get(mode, "No description available")
