from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from fba_bench_api.models.scenarios import (
    Scenario,
    ScenarioCreate,
    ScenarioList,
    ScenarioUpdate,
    get_scenario_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scenarios", tags=["Scenarios"])


@router.get(
    "",
    response_model=ScenarioList,
    description="List available scenarios with pagination",
)
async def list_scenarios(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(
        20, ge=1, le=100, description="Number of scenarios per page"
    ),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    difficulty_tier: Optional[int] = Query(
        None, ge=0, le=3, description="Filter by difficulty tier"
    ),
):
    """
    Retrieve a paginated list of available scenarios.

    Supports filtering by:
    - tags: scenario categorization tags
    - difficulty_tier: difficulty level (0=beginner, 1=moderate, 2=advanced, 3=expert)

    Returns scenarios sorted by difficulty tier then name.
    """
    try:
        scenario_service = get_scenario_service()
        return scenario_service.list_scenarios(
            page=page, page_size=page_size, tags=tags, difficulty_tier=difficulty_tier
        )
    except Exception as e:
        logger.error("Failed to list scenarios: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scenarios",
        )


@router.get(
    "/{scenario_id}",
    response_model=Scenario,
    description="Get specific scenario details",
)
async def get_scenario(scenario_id: str):
    """
    Retrieve detailed information for a specific scenario.

    Returns complete scenario configuration including:
    - Basic metadata (name, description, difficulty)
    - Success criteria and objectives
    - Market conditions and external events
    - Agent constraints and default parameters
    """
    try:
        scenario_service = get_scenario_service()
        scenario = scenario_service.get_scenario(scenario_id)

        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario '{scenario_id}' not found",
            )

        return scenario
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scenario %s: %s", scenario_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scenario",
        )


@router.get("/{scenario_id}/validate", description="Validate scenario configuration")
async def validate_scenario(scenario_id: str):
    """
    Validate a scenario's configuration for consistency and completeness.

    Performs comprehensive validation including:
    - Required field presence
    - Parameter value ranges
    - Logical consistency between components
    - Market conditions alignment with difficulty tier
    """
    try:
        scenario_service = get_scenario_service()
        scenario = scenario_service.get_scenario(scenario_id)

        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario '{scenario_id}' not found",
            )

        is_valid = scenario_service.validate_scenario(scenario_id)

        return {
            "scenario_id": scenario_id,
            "valid": is_valid,
            "message": (
                "Scenario validation passed"
                if is_valid
                else "Scenario validation failed"
            ),
            "timestamp": scenario.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to validate scenario %s: %s", scenario_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate scenario",
        )


@router.post(
    "",
    response_model=Scenario,
    status_code=status.HTTP_201_CREATED,
    description="Create a new scenario",
)
async def create_scenario(payload: ScenarioCreate):
    """
    Create a new scenario configuration.

    Validates the input data and writes the scenario to a YAML file.
    The scenario ID is generated from the name (lowercase, spaces to underscores).
    """
    try:
        scenario_service = get_scenario_service()
        created = scenario_service.create_scenario(payload)

        # Validate the created scenario
        if not scenario_service.validate_scenario(created.id):
            # If validation fails, delete the created file
            scenario_service.delete_scenario(created.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Created scenario '{created.id}' failed validation",
            )

        logger.info("Created scenario: %s", created.id)
        return created

    except ValueError as e:
        logger.error("Failed to create scenario: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to create scenario: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scenario",
        )


@router.patch(
    "/{scenario_id}", response_model=Scenario, description="Update an existing scenario"
)
async def update_scenario(scenario_id: str, payload: ScenarioUpdate):
    """
    Update an existing scenario configuration.

    Partial updates are supported (only provided fields are updated).
    Re-validates the scenario after update.
    """
    try:
        scenario_service = get_scenario_service()
        if not scenario_service.get_scenario(scenario_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario '{scenario_id}' not found",
            )

        updated = scenario_service.update_scenario(scenario_id, payload)

        # Validate the updated scenario
        if not scenario_service.validate_scenario(scenario_id):
            logger.warning("Updated scenario '%s' failed validation", scenario_id)
            # Note: In production, consider rollback or marking invalid; here return with warning
            updated.valid = False  # Add flag if needed

        logger.info("Updated scenario: %s", scenario_id)
        return updated

    except ValueError as e:
        logger.error("Failed to update scenario %s: %s", scenario_id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to update scenario %s: %s", scenario_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scenario",
        )


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete a scenario",
)
async def delete_scenario(scenario_id: str):
    """
    Delete a scenario configuration.

    Removes the corresponding YAML file and clears from cache.
    """
    try:
        scenario_service = get_scenario_service()
        if not scenario_service.delete_scenario(scenario_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario '{scenario_id}' not found",
            )

        logger.info("Deleted scenario: %s", scenario_id)
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete scenario %s: %s", scenario_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scenario",
        )
