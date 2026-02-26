from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, JSONEncoded, TimestampMixin


class ExperimentStatusEnum(str):
    draft = "draft"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExperimentORM(TimestampMixin, Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4 string
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scenario_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    params: Mapped[dict] = mapped_column(JSONEncoded, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(
        SAEnum(
            ExperimentStatusEnum.draft,
            ExperimentStatusEnum.running,
            ExperimentStatusEnum.completed,
            ExperimentStatusEnum.failed,
            name="experiment_status_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=ExperimentStatusEnum.draft,
    )

    # Relationships
    agent = relationship("AgentORM", backref="experiments", lazy="joined")
    runs = relationship("ExperimentRunORM", back_populates="experiment", cascade="all, delete-orphan")

    # Indexes for frequent queries
    __table_args__ = (
        Index("ix_experiments_status", status),
        Index("ix_experiments_created_at", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_id": self.agent_id,
            "scenario_id": self.scenario_id,
            "params": self.params or {},
            "status": self.status,
            "created_at": self.created_at,
        }
