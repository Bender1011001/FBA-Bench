"""
Lightweight learning utilities used by unit tests.

These modules provide simple, self-contained implementations of:
- Episodic learning (store/retrieve episodes + basic statistics)
- Reinforcement learning (tabular Q-learning)
- Curriculum learning (levels + student progress)
- Meta learning (recommend strategies from past experience)

They are intentionally dependency-light and do not integrate directly with the
benchmarking engine unless wired in by higher-level components.
"""

from .curriculum_learning import CurriculumLearning
from .episodic_learning import EpisodicLearning
from .meta_learning import MetaLearning
from .reinforcement_learning import ReinforcementLearning

__all__ = [
    "CurriculumLearning",
    "EpisodicLearning",
    "MetaLearning",
    "ReinforcementLearning",
]
