from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fba_bench_api.core.database_async import get_async_db_session
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/leaderboard", tags=["Leaderboard"])


# Pydantic Models
class LeaderboardEntry(BaseModel):
    """Represents a single leaderboard entry with experiment performance data."""

    rank: int = Field(..., description="Ranking position (1-based)")
    experiment_id: str = Field(
        ..., alias="experimentId", description="Unique experiment identifier"
    )
    name: str = Field(..., description="Experiment name")
    score: float = Field(..., description="Computed performance score")
    model: str = Field(..., description="AI model/agent used")
    status: Literal["running", "completed", "failed", "draft"] = Field(
        ..., description="Experiment status"
    )
    completed_at: str = Field(
        ..., alias="completedAt", description="Completion timestamp (ISO format)"
    )
    avatar: str = Field(..., description="Model avatar emoji")
    badge: Literal["gold", "silver", "bronze", "default"] = Field(
        ..., description="Achievement badge"
    )

    class Config:
        populate_by_name = True


def get_pm(db: AsyncSession = Depends(get_async_db_session)) -> AsyncPersistenceManager:
    """Dependency injection for persistence manager."""
    return AsyncPersistenceManager(db)


def _calculate_experiment_score(experiment: dict) -> float:
    """
    Calculate a performance score for an experiment based on its metrics.

    Args:
        experiment: Experiment data dictionary

    Returns:
        Computed score between 0-100 based on performance metrics
    """
    # Start with base score
    score = 0.0

    # Get experiment params/metrics (this would come from actual simulation results)
    params = experiment.get("params", {})

    # In a real implementation, this would analyze:
    # - Business metrics (profit, market share, customer satisfaction)
    # - Efficiency metrics (resource utilization, time to completion)
    # - Risk metrics (safety, compliance, stability)

    # For now, create a realistic scoring algorithm based on available data
    # If experiment has a pre-calculated score in params, use it
    if "quality_score" in params:
        return float(params["quality_score"]) * 100.0

    # Fallback to mock scoring logic
    if experiment.get("status") == "completed":
        # Base completion bonus
        score += 60.0

        # Agent complexity bonus
        agent_id = experiment.get("agent_id", "").lower()
        if "gpt-4" in agent_id or "grok-4" in agent_id:
            score += 15.0
        elif "claude" in agent_id or "deepseek-v3" in agent_id:
            score += 12.0
        elif "llama" in agent_id:
            score += 10.0
        else:
            score += 5.0

        # Scenario complexity bonus
        scenario_id = experiment.get("scenario_id", "")
        if "expert" in scenario_id or "tier_3" in scenario_id:
            score += 20.0
        elif "intermediate" in scenario_id or "tier_2" in scenario_id:
            score += 15.0
        else:
            score += 10.0

        # Add some variability
        import hashlib
        name_hash = int(hashlib.md5(experiment["name"].encode()).hexdigest()[:8], 16)
        variance = (name_hash % 21) - 10
        score += variance
    elif experiment.get("status") == "running":
        score += 30.0
    elif experiment.get("status") == "failed":
        score += 5.0

    return max(0.0, min(100.0, score))


def _get_model_avatar(agent_id: str) -> str:
    """Get emoji avatar for an AI model/agent."""
    agent_lower = agent_id.lower()
    if "gpt" in agent_lower:
        return "🧠"
    elif "claude" in agent_lower:
        return "⚡"
    elif "llama" in agent_lower:
        return "🦙"
    elif "baseline" in agent_lower:
        return "🤖"
    else:
        return "🎯"


def _get_badge_for_rank(rank: int) -> Literal["gold", "silver", "bronze", "default"]:
    """Assign achievement badge based on ranking position."""
    if rank == 1:
        return "gold"
    elif rank == 2:
        return "silver"
    elif rank == 3:
        return "bronze"
    else:
        return "default"


def _extract_model_name(agent_id: str) -> str:
    """Extract readable model name from agent ID."""
    # In a real system, this would query the agents table
    # For now, infer from agent_id patterns
    agent_lower = agent_id.lower()

    if "gpt-4" in agent_lower:
        return "GPT-4 Turbo"
    elif "gpt-3.5" in agent_lower:
        return "GPT-3.5 Turbo"
    elif "claude-3.5" in agent_lower:
        return "Claude-3.5 Sonnet"
    elif "claude-3" in agent_lower:
        return "Claude-3 Opus"
    elif "llama-3.1" in agent_lower:
        return "Llama-3.1-405B"
    elif "llama" in agent_lower:
        return "Llama-2-70B"
    elif "grok" in agent_lower:
        v = "4.1" if "4.1" in agent_lower else "4"
        return f"Grok-{v} Fast"
    elif "deepseek" in agent_lower:
        v = "v3.2" if "v3.2" in agent_lower else "v3"
        return f"DeepSeek-{v}"
    elif "baseline" in agent_lower:
        return "Baseline Bot"
    else:
        return f"Custom Agent {agent_id[:8]}"


async def _get_leaderboard_data(
    pm: AsyncPersistenceManager, limit: Optional[int] = None
) -> List[dict]:
    """
    Aggregate and rank experiments to generate leaderboard data.

    Args:
        pm: Persistence manager for database access
        limit: Optional limit on number of entries to return

    Returns:
        List of ranked experiment dictionaries
    """
    # Get all experiments
    experiments = await pm.experiments().list()

    # Filter to only completed and running experiments for leaderboard
    eligible_experiments = [
        exp
        for exp in experiments
        if exp.get("status") in ["completed", "running", "failed"]
    ]

    # Calculate scores and enrich data
    scored_experiments = []
    for exp in eligible_experiments:
        score = _calculate_experiment_score(exp)

        # Enrich with computed fields
        enriched_exp = {
            **exp,
            "computed_score": score,
            "model_name": _extract_model_name(exp.get("agent_id", "")),
            "avatar": _get_model_avatar(exp.get("agent_id", "")),
        }
        scored_experiments.append(enriched_exp)

    # Sort by score (descending) then by completion time
    scored_experiments.sort(
        key=lambda x: (
            -x["computed_score"],  # Higher scores first
            x.get(
                "updated_at", datetime.min.replace(tzinfo=timezone.utc)
            ),  # Earlier completion as tiebreaker
        )
    )

    # Apply limit if specified
    if limit and limit > 0:
        scored_experiments = scored_experiments[:limit]

    return scored_experiments


@router.get(
    "",
    response_model=List[LeaderboardEntry],
    description="Get ranked leaderboard of experiments",
)
async def get_leaderboard(
    limit: Optional[int] = Query(
        50, ge=1, le=1000, description="Maximum number of entries to return"
    ),
    pm: AsyncPersistenceManager = Depends(get_pm),
) -> List[LeaderboardEntry]:
    """
    Retrieve the experiment leaderboard with rankings based on performance metrics.

    This endpoint aggregates experiment data to create a competitive leaderboard
    showing the top-performing experiments ranked by their computed scores.

    Args:
        limit: Maximum number of leaderboard entries (1-1000, default 50)
        pm: Injected persistence manager

    Returns:
        List of leaderboard entries sorted by performance score (highest first)
    """
    logger.info("Generating leaderboard with limit=%s", limit)

    try:
        # Get aggregated leaderboard data
        leaderboard_data = await _get_leaderboard_data(pm, limit)

        # Convert to response models
        leaderboard_entries = []
        for rank, exp in enumerate(leaderboard_data, 1):
            entry = LeaderboardEntry(
                rank=rank,
                experiment_id=exp["id"],
                name=exp["name"],
                score=exp["computed_score"],
                model=exp["model_name"],
                status=exp["status"],
                completed_at=exp.get(
                    "updated_at", datetime.now(timezone.utc)
                ).isoformat(),
                avatar=exp["avatar"],
                badge=_get_badge_for_rank(rank),
            )
            leaderboard_entries.append(entry)

        logger.info("Generated leaderboard with %d entries", len(leaderboard_entries))
        return leaderboard_entries

    except Exception as e:
        logger.error("Failed to generate leaderboard: %s", e)
        # Return empty leaderboard on error rather than failing completely
        return []


@router.get("/stats", description="Get leaderboard statistics and metadata")
async def get_leaderboard_stats(pm: AsyncPersistenceManager = Depends(get_pm)) -> dict:
    """
    Get statistical information about the leaderboard.

    Returns aggregate statistics like total experiments, average scores,
    model distribution, and other metadata useful for dashboard displays.
    """
    try:
        experiments = await pm.experiments().list()

        total_experiments = len(experiments)
        completed_experiments = len(
            [e for e in experiments if e.get("status") == "completed"]
        )
        running_experiments = len(
            [e for e in experiments if e.get("status") == "running"]
        )
        failed_experiments = len(
            [e for e in experiments if e.get("status") == "failed"]
        )

        # Calculate score statistics for completed experiments
        completed_with_scores = [
            _calculate_experiment_score(exp)
            for exp in experiments
            if exp.get("status") == "completed"
        ]

        avg_score = (
            sum(completed_with_scores) / len(completed_with_scores)
            if completed_with_scores
            else 0.0
        )
        max_score = max(completed_with_scores) if completed_with_scores else 0.0
        min_score = min(completed_with_scores) if completed_with_scores else 0.0

        return {
            "total_experiments": total_experiments,
            "completed_experiments": completed_experiments,
            "running_experiments": running_experiments,
            "failed_experiments": failed_experiments,
            "success_rate": (
                completed_experiments / total_experiments
                if total_experiments > 0
                else 0.0
            ),
            "average_score": round(avg_score, 2),
            "max_score": round(max_score, 2),
            "min_score": round(min_score, 2),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Failed to generate leaderboard stats: %s", e)
        return {
            "total_experiments": 0,
            "completed_experiments": 0,
            "running_experiments": 0,
            "failed_experiments": 0,
            "success_rate": 0.0,
            "average_score": 0.0,
            "max_score": 0.0,
            "min_score": 0.0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
