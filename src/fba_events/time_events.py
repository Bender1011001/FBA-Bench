"""
Event definitions related to time progression and simulation state in the FBA-Bench simulation.

This module defines `TickEvent`, the fundamental heartbeat of the simulation
that drives all time-dependent processes.

These events are central to the simulation's progress and the coordination
of all time-sensitive logic across various services and agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from .base import BaseEvent


@dataclass
class TickEvent(BaseEvent):
    """
    Represents the advancement of simulation time by one discrete step.
    Published by the `SimulationOrchestrator` at each time increment.

    This is the fundamental heartbeat of the FBA-Bench simulation. Its regular
    publication triggers all time-dependent processes and services to advance
    their internal states and perform actions relevant to the current simulation tick.

    Attributes:
        event_id (str): Unique identifier for this specific tick event. Inherited from `BaseEvent`.
        timestamp (datetime): The real-world UTC datetime when this tick event was processed/published.
                              Inherited from `BaseEvent`.
        tick_number (int): A sequential counter for the simulation ticks, starting from 0.
                           Represents the cumulative number of time steps taken.
        simulation_time (datetime): The logical simulation time corresponding to this tick.
                                    This time may be accelerated compared to real-world time,
                                    depending on the simulation's time granularity.
        metadata (Dict[str, Any]): Additional contextual information for this tick,
                                    e.g., seasonal factors, weekday/weekend indicators,
                                    or special simulation phases. Defaults to an empty dictionary.
    """

    tick_number: int
    simulation_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Validates tick-specific data upon initialization.
        Ensures `tick_number` is non-negative and `simulation_time` is a valid `datetime` object.
        """
        super().__post_init__()  # Call base class validation

        # Validate tick_number: Must be non-negative.
        if self.tick_number < 0:
            raise ValueError(
                f"Tick number must be >= 0, but got {self.tick_number} for TickEvent."
            )

        # Default simulation_time to event timestamp when not provided
        if self.simulation_time is None:
            self.simulation_time = self.timestamp
        # Validate simulation_time: Must be a datetime object.
        if not isinstance(self.simulation_time, datetime):
            raise TypeError(
                f"Simulation time must be a datetime object, but got {type(self.simulation_time)} for TickEvent."
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `TickEvent` into a concise summary dictionary.

        Datetime objects are converted to ISO 8601 format for easy serialization
        and readability in logs/reports. `metadata` is returned as a copy.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "tick_number": self.tick_number,
            "simulation_time": self.simulation_time.isoformat(),  # type: ignore[union-attr]
            "metadata": self.metadata.copy(),  # Return a copy to prevent external modification
        }
