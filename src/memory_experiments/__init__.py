"""
Memory Experiments Framework for FBA-Bench

This module provides a comprehensive framework for studying memory vs. reasoning
in agent performance, inspired by VendingBench's findings that "memory wasn't the bottleneck".

The framework includes:
- Dual-memory architecture (short-term + long-term)
- Daily reflection and memory consolidation
- A/B testing framework for memory modes
- Statistical validation and analysis
- Integration with existing FBA-Bench constraint and metrics systems

Key Components:
- DualMemoryManager: Core orchestrator for dual-memory system
- ReflectionModule: Daily memory consolidation and sorting
- MemoryEnforcer: Integration with constraint system
- ExperimentRunner: A/B testing framework
- MemoryMetrics: Memory-specific evaluation metrics
"""

from .dual_memory_manager import DualMemoryManager
from .experiment_runner import ExperimentRunner
from .memory_config import MemoryConfig
from .memory_enforcer import MemoryEnforcer
from .memory_metrics import MemoryMetrics
from .memory_modes import (
    ConsolidationDisabledMode,
    HybridReflectionMode,
    LongTermOnlyMode,
    MemoryFreeMode,
    MemoryMode,
    ReflectionEnabledMode,
    ShortTermOnlyMode,
)
from .reflective_memory_v1 import ReflectiveMemoryV1
from .reflection_module import ReflectionModule

__version__ = "1.0.0"
__author__ = "FBA-Bench Memory Research Team"

__all__ = [
    "MemoryConfig",
    "DualMemoryManager",
    "ReflectionModule",
    "MemoryEnforcer",
    "ExperimentRunner",
    "MemoryMetrics",
    "MemoryMode",
    "ReflectionEnabledMode",
    "ConsolidationDisabledMode",
    "ShortTermOnlyMode",
    "LongTermOnlyMode",
    "HybridReflectionMode",
    "MemoryFreeMode",
    "ReflectiveMemoryV1",
]
