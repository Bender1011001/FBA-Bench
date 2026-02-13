"""FBA-Bench API Models package.

Exports ORM models for database operations and Pydantic schemas for API validation.
"""

# ORM Models (SQLAlchemy)
from .agent import AgentORM, FrameworkEnum
from .base import Base, JSONEncoded, TimestampMixin, utcnow
from .experiment import ExperimentORM, ExperimentStatusEnum
from .simulation import SimulationORM, SimulationStatusEnum, websocket_topic
from .contact_message import ContactMessageORM
from .user import User

# Pydantic Schemas for API
from .scenarios import (
    Scenario,
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioList,
    ScenarioService,
    get_scenario_service,
)
from .simulation import (
    SimulationSnapshot,
    EventFilter,
    SimulationConfigCreate,
    SimulationConfigUpdate,
    SimulationConfigResponse,
    SimulationStartRequest,
    SimulationControlResponse,
    SimulationStatusResponse,
)
from .agents import (
    AgentConfigurationResponse,
    AgentValidationRequest,
    AgentValidationResponse,
    FrameworksResponse,
)
from .api import (
    AgentSnapshot,
    KpiSnapshot,
    SimulationSnapshot as RealtimeSimulationSnapshot,
    RecentEventsResponse,
)

__all__ = [
    # ORM Models
    "AgentORM",
    "FrameworkEnum",
    "Base",
    "JSONEncoded",
    "TimestampMixin",
    "utcnow",
    "ExperimentORM",
    "ExperimentStatusEnum",
    "SimulationORM",
    "SimulationStatusEnum",
    "websocket_topic",
    "ContactMessageORM",
    "User",
    # Scenario Schemas
    "Scenario",
    "ScenarioCreate",
    "ScenarioUpdate",
    "ScenarioList",
    "ScenarioService",
    "get_scenario_service",
    # Simulation Schemas
    "SimulationSnapshot",
    "EventFilter",
    "SimulationConfigCreate",
    "SimulationConfigUpdate",
    "SimulationConfigResponse",
    "SimulationStartRequest",
    "SimulationControlResponse",
    "SimulationStatusResponse",
    # Agent Schemas
    "AgentConfigurationResponse",
    "AgentValidationRequest",
    "AgentValidationResponse",
    "FrameworksResponse",
    # Realtime API Schemas
    "AgentSnapshot",
    "KpiSnapshot",
    "RealtimeSimulationSnapshot",
    "RecentEventsResponse",
]
