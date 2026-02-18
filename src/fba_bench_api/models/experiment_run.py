from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, JSONEncoded, TimestampMixin


class ExperimentRunORM(TimestampMixin, Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    
    status: Mapped[str] = mapped_column(
        SAEnum(
            "pending",
            "starting",
            "running",
            "completed",
            "failed",
            "stopped",
            name="experiment_run_status_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default="pending",
    )

    # Progress tracking
    current_tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_ticks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Results and error handling
    metrics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    results: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    experiment = relationship("ExperimentORM", back_populates="runs")
    participants = relationship("ExperimentParticipantORM", back_populates="run", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "scenario_id": self.scenario_id,
            "params": json.loads(self.params or "{}"),
            "status": self.status,
            "current_tick": self.current_tick,
            "total_ticks": self.total_ticks,
            "progress_percent": self.progress_percent,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metrics": json.loads(self.metrics or "{}") if self.metrics else {},
            "results": json.loads(self.results or "{}") if self.results else {},
            "error_message": self.error_message,
        }


class ExperimentParticipantORM(Base):
    __tablename__ = "experiment_run_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("experiment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    config_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    run = relationship("ExperimentRunORM", back_populates="participants")
    agent = relationship("AgentORM")

    __table_args__ = (
        UniqueConstraint("run_id", "agent_id", name="uq_run_agent"),
    )

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "role": self.role,
            "config_override": json.loads(self.config_override or "{}") if self.config_override else {},
            "created_at": self.created_at,
        }
