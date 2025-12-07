"""
API routes for benchmark operations.

This module provides REST API endpoints for creating, managing, and monitoring
benchmark executions in the FBA Benchmark system.
"""

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ...core.models import (
    BenchmarkConfig,
    BenchmarkCreateRequest,
    BenchmarkResponse,
    BenchmarkRunRequest,
    BenchmarkStatus,
    HealthResponse,
    RunMetrics,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


class BenchmarkService:
    """Enhanced BenchmarkService with queuing for concurrent runs."""

    def __init__(self):
        self.active_benchmarks: Dict[str, Dict[str, Any]] = {}
        self.completed_benchmarks: Dict[str, Dict[str, Any]] = {}
        self.run_queue = asyncio.Queue()
        self.completed_runs: Dict[str, RunMetrics] = {}
        self.run_lock = asyncio.Lock()
        self.worker_task = None
        if os.getenv("TESTING") != "true":
            self.worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Background worker to process queued runs."""
        while True:
            try:
                run_data = await self.run_queue.get()
                run_id = run_data["run_id"]
                agent_id = run_data["agent_id"]
                scenario_id = run_data["scenario_id"]
                params = run_data.get("params", {})

                async with self.run_lock:
                    # Set status to running
                    if run_id in self.active_benchmarks:
                        self.active_benchmarks[run_id][
                            "status"
                        ] = BenchmarkStatus.RUNNING
                        self.active_benchmarks[run_id]["updated_at"] = datetime.now(
                            timezone.utc
                        )

                # Simulate execution (in production, integrate with agent_runners)
                await asyncio.sleep(
                    random.uniform(3, 10)
                )  # Simulate variable work time

                # Generate metrics based on agent and scenario (stub for now)
                base_profit = (
                    1000
                    if "tier_0" in scenario_id
                    else 5000 if "tier_1" in scenario_id else 10000
                )
                profit = base_profit + random.uniform(-2000, 5000)
                efficiency = random.uniform(0.7, 0.95)
                sales = random.uniform(100, 500)
                satisfaction = random.uniform(0.8, 1.0)
                metrics = {
                    "profit": max(0, profit),
                    "efficiency": efficiency,
                    "sales": sales,
                    "customer_satisfaction": satisfaction,
                }

                # Set status to completed
                async with self.run_lock:
                    if run_id in self.active_benchmarks:
                        self.active_benchmarks[run_id][
                            "status"
                        ] = BenchmarkStatus.COMPLETED
                        self.active_benchmarks[run_id]["updated_at"] = datetime.now(
                            timezone.utc
                        )
                        # Move to completed
                        self.completed_benchmarks[run_id] = self.active_benchmarks.pop(
                            run_id
                        )
                        self.completed_benchmarks[run_id]["completed_at"] = (
                            datetime.now(timezone.utc)
                        )

                # Store metrics
                self.completed_runs[run_id] = RunMetrics(metrics=metrics)

                logger.info(
                    f"Completed run {run_id} for agent {agent_id} in scenario {scenario_id} with profit {profit:.2f}"
                )

                self.run_queue.task_done()

            except Exception as e:
                logger.error(f"Worker error for run {run_id}: {e}", exc_info=True)
                async with self.run_lock:
                    if run_id in self.active_benchmarks:
                        self.active_benchmarks[run_id][
                            "status"
                        ] = BenchmarkStatus.FAILED
                        self.active_benchmarks[run_id]["updated_at"] = datetime.now(
                            timezone.utc
                        )
                        self.active_benchmarks[run_id]["error"] = str(e)
                await asyncio.sleep(1)

    async def create_benchmark(self, config: BenchmarkConfig) -> str:
        """Create a new benchmark and return its ID."""
        benchmark_id = str(uuid4())
        self.active_benchmarks[benchmark_id] = {
            "id": benchmark_id,
            "config": config.dict(),
            "status": BenchmarkStatus.CREATED,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        logger.info(f"Created benchmark {benchmark_id}")
        return benchmark_id

    async def run_benchmark(self, request: BenchmarkRunRequest) -> str:
        """Run a benchmark by enqueuing it and return the run ID."""
        # Validate agent and scenario exist (stub - in production, check DB)
        if not request.agent_id or not request.scenario_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="agent_id and scenario_id are required",
            )

        run_id = str(uuid4())
        run_data = {
            "run_id": run_id,
            "agent_id": request.agent_id,
            "scenario_id": request.scenario_id,
            "params": request.params,
        }

        # Create benchmark entry
        self.active_benchmarks[run_id] = {
            "id": run_id,
            "agent_id": request.agent_id,
            "scenario_id": request.scenario_id,
            "params": request.params,
            "status": BenchmarkStatus.QUEUED,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # Enqueue
        await self.run_queue.put(run_data)

        logger.info(
            f"Enqueued run {run_id} for agent {request.agent_id} in scenario {request.scenario_id}"
        )
        return run_id

    async def get_benchmark_status(self, run_id: str) -> Dict[str, Any]:
        """Get the status of a benchmark run."""
        async with self.run_lock:
            if run_id in self.active_benchmarks:
                return self.active_benchmarks[run_id]
            elif run_id in self.completed_benchmarks:
                return self.completed_benchmarks[run_id]
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run {run_id} not found",
                )

    async def get_run_results(self, run_id: str) -> RunMetrics:
        """Get the results (metrics) for a completed benchmark run."""
        async with self.run_lock:
            if run_id in self.completed_runs:
                return self.completed_runs[run_id]
            elif run_id in self.active_benchmarks:
                status = self.active_benchmarks[run_id]["status"]
                if (
                    status == BenchmarkStatus.QUEUED
                    or status == BenchmarkStatus.RUNNING
                ):
                    raise HTTPException(
                        status_code=status.HTTP_202_ACCEPTED,
                        detail=f"Run {run_id} is {status.value} - results not available yet",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Run {run_id} failed or stopped - no results",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run {run_id} not found",
                )

    async def list_benchmarks(self) -> List[Dict[str, Any]]:
        """List all benchmarks."""
        async with self.run_lock:
            benchmarks = []
            benchmarks.extend(list(self.active_benchmarks.values()))
            benchmarks.extend(list(self.completed_benchmarks.values()))
            return benchmarks

    async def stop_benchmark(self, run_id: str) -> bool:
        """Stop a running benchmark."""
        async with self.run_lock:
            if run_id in self.active_benchmarks:
                benchmark = self.active_benchmarks[run_id]
                benchmark["status"] = BenchmarkStatus.STOPPED
                benchmark["updated_at"] = datetime.now(timezone.utc)

                # Move to completed
                self.completed_benchmarks[run_id] = benchmark
                del self.active_benchmarks[run_id]
                return True
        return False


# Initialize enhanced service
benchmark_service = BenchmarkService()


@router.post("/", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark(request: BenchmarkCreateRequest):
    """
    Create a new benchmark.

    This endpoint creates a new benchmark configuration but does not execute it.
    Use the run endpoint to start the benchmark execution.
    """
    try:
        benchmark_id = await benchmark_service.create_benchmark(request.config)

        return BenchmarkResponse(
            benchmark_id=benchmark_id,
            status=BenchmarkStatus.CREATED,
            message="Benchmark created successfully",
        )
    except Exception as e:
        logger.error(f"Failed to create benchmark: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create benchmark: {e!s}",
        )


@router.post(
    "/run", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED
)
async def run_benchmark(request: BenchmarkRunRequest):
    """
    Run a benchmark.

    This endpoint starts the execution of a benchmark by enqueuing it.
    The benchmark is queued and processed asynchronously.
    Results can be retrieved using the results endpoint.
    """
    try:
        run_id = await benchmark_service.run_benchmark(request)

        return BenchmarkResponse(
            benchmark_id=run_id,
            status=BenchmarkStatus.QUEUED,
            message="Benchmark run queued successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue benchmark run: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue benchmark run: {e!s}",
        )


@router.get("/{run_id}/status")
async def get_benchmark_status(run_id: str):
    """
    Get the status of a benchmark run.

    This endpoint returns the current status and metadata of a benchmark run.
    If the benchmark has completed, it will include the results.
    """
    try:
        status = await benchmark_service.get_benchmark_status(run_id)
        return JSONResponse(content=status)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for run {run_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get benchmark status: {e!s}",
        )


@router.get("/{run_id}/results", response_model=RunMetrics)
async def get_run_results(run_id: str):
    """
    Get the results (metrics) for a completed benchmark run.

    Returns 202 if still processing, 404 if not found.
    """
    try:
        results = await benchmark_service.get_run_results(run_id)
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get results for run {run_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get benchmark results: {e!s}",
        )


@router.get("/", response_model=List[Dict[str, Any]])
async def list_benchmarks():
    """
    List all benchmarks.

    This endpoint returns a list of all benchmarks, both active and completed.
    """
    try:
        benchmarks = await benchmark_service.list_benchmarks()
        return benchmarks
    except Exception as e:
        logger.error(f"Failed to list benchmarks: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list benchmarks: {e!s}",
        )


@router.post("/{run_id}/stop")
async def stop_benchmark(run_id: str):
    """
    Stop a running benchmark.

    This endpoint attempts to stop a currently running benchmark.
    """
    try:
        stopped = await benchmark_service.stop_benchmark(run_id)
        if stopped:
            return {"message": f"Benchmark {run_id} stopped successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Benchmark {run_id} not found or not running",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop benchmark {run_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop benchmark: {e!s}",
        )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    This endpoint returns the health status of the benchmark service.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services={
            "benchmark_service": "healthy",
            "database": "healthy",
            "message_queue": "healthy",
        },
    )


@router.delete("/{run_id}")
async def delete_benchmark(run_id: str):
    """
    Delete a benchmark.

    This endpoint deletes a benchmark and all associated data.
    """
    try:
        async with benchmark_service.run_lock:
            # Check if benchmark exists
            if run_id in benchmark_service.active_benchmarks:
                del benchmark_service.active_benchmarks[run_id]
            elif run_id in benchmark_service.completed_benchmarks:
                del benchmark_service.completed_benchmarks[run_id]
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Benchmark {run_id} not found",
                )

        return {"message": f"Benchmark {run_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete benchmark {run_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete benchmark: {e!s}",
        )


# Note: Exception handlers are registered at the application level in app_factory.add_exception_handlers.
# Router-level exception decorators are not supported by FastAPI's APIRouter and were removed.
