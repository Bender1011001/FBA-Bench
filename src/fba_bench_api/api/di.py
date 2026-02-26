from __future__ import annotations

"""
FastAPI dependency providers backed by the AppContainer (Dependency Injector).

Usage in route modules:
  from fastapi import Depends
  from fba_bench_api.api.di import get_event_bus, get_agent_manager, get_simulation_orchestrator

  @router.get("/status")
  async def status(bus = Depends(get_event_bus)):
      ...

These helpers resolve singletons/factories from app.state.container initialized in create_app().
"""

from fastapi import Depends, Request  # noqa: E402

from agent_runners.agent_manager import AgentManager  # noqa: E402
from fba_bench_api.core.container import AppContainer  # noqa: E402
from fba_events.bus import EventBus  # noqa: E402

# from simulation_orchestrator import SimulationOrchestrator


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("AppContainer not initialized on app.state.container")
    return container


def get_event_bus(container: AppContainer = Depends(get_container)) -> EventBus:
    # Singleton provider
    return container.event_bus()


def get_agent_manager(container: AppContainer = Depends(get_container)) -> AgentManager:
    # Factory provider (new instance per injection unless provider overridden to Singleton)
    return container.agent_manager()


# def get_simulation_orchestrator(
#     container: AppContainer = Depends(get_container),
# ) -> SimulationOrchestrator:
#     # Factory provider
#     return container.simulation_orchestrator()
