from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SimulationSnapshot(BaseModel):
    current_tick: Optional[int] = None
    simulation_time: Optional[str] = None
    last_update: Optional[str] = None
    uptime_seconds: Optional[int] = None
    products: Optional[Dict[str, Any]] = None
    competitors: Optional[Dict[str, Any]] = None
    market_summary: Optional[Dict[str, Any]] = None
    financial_summary: Optional[Dict[str, Any]] = None
    agents: Optional[Dict[str, Any]] = None
    command_stats: Optional[Dict[str, Any]] = None
    event_stats: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class EventFilter(BaseModel):
    event_type: Optional[str] = None
    limit: int = 20
    since_tick: Optional[int] = None


class SimulationConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tick_interval_seconds: float = Field(1.0)
    max_ticks: Optional[int] = None
    start_time: Optional[datetime] = None
    time_acceleration: float = Field(1.0)
    seed: Optional[int] = None
    base_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SimulationConfigUpdate(SimulationConfigCreate):
    name: Optional[str] = None  # type: ignore[assignment]


class SimulationConfigResponse(BaseModel):
    config_id: str
    name: str
    description: Optional[str]
    tick_interval_seconds: float
    max_ticks: Optional[int]
    start_time: Optional[datetime]
    time_acceleration: float
    seed: Optional[int]
    base_parameters: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SimulationStartRequest(BaseModel):
    config_id: str
    simulation_id: Optional[str] = None


class SimulationControlResponse(BaseModel):
    success: bool
    message: str
    simulation_id: Optional[str] = None
    status: Optional[Dict[str, Any]] = None


class SimulationStatusResponse(BaseModel):
    is_running: bool
    is_paused: bool
    current_tick: int
    real_time: str
    simulation_time: str
    config: Dict[str, Any]
    statistics: Dict[str, Any]
    simulation_id: Optional[str] = None
    message: Optional[str] = None


from sqlalchemy import Enum as SAEnum, ForeignKey, String  # noqa: E402
from sqlalchemy.orm import Mapped, mapped_column, relationship  # noqa: E402

from .base import Base, JSONEncoded, TimestampMixin  # noqa: E402


def websocket_topic(sim_id: str) -> str:
    return f"simulation-progress:{sim_id}"


class SimulationStatusEnum(str):
    pending = "pending"
    running = "running"
    stopped = "stopped"
    completed = "completed"
    failed = "failed"


class SimulationORM(TimestampMixin, Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4 string
    experiment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        SAEnum(
            SimulationStatusEnum.pending,
            SimulationStatusEnum.running,
            SimulationStatusEnum.stopped,
            SimulationStatusEnum.completed,
            SimulationStatusEnum.failed,
            name="simulation_status_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=SimulationStatusEnum.pending,
    )

    # IMPORTANT: attribute name 'metadata' is reserved by SQLAlchemy Declarative API.
    # Use a different Python attribute and map it to DB column 'metadata'.
    sim_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONEncoded, nullable=True, default=dict
    )

    # Relationships
    experiment = relationship("ExperimentORM", backref="simulations", lazy="joined")

    def to_dict_with_topic(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "status": self.status,
            "websocket_topic": websocket_topic(self.id),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.sim_metadata or {},
        }
