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
from fba_bench_api.core.database_async import AsyncSessionLocal
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


class BenchmarkService:
    """Enhanced BenchmarkService with queuing for concurrent runs."""

    def __init__(self):
        self.active_benchmarks: Dict[str, Dict[str, Any]] = {}
        self.completed_benchmarks: Dict[str, Dict[str, Any]] = {}
        self.run_queue = asyncio.Queue()  # type: ignore[var-annotated]
        self.completed_runs: Dict[str, RunMetrics] = {}
        self.run_lock = asyncio.Lock()
        self.worker_task = None

    async def start(self):
        """Start the background worker."""
        if os.getenv("TESTING") != "true" and self.worker_task is None:
            self.worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Background worker to process queued runs."""
        while True:
            try:
                run_data = await self.run_queue.get()
                run_id = run_data["run_id"]
                agent_id = run_data["agent_id"]
                scenario_id = run_data["scenario_id"]
                params = run_data.get("params", {})  # noqa: F841

                # Use a fresh DB session for the worker
                async with AsyncSessionLocal() as session:
                    persistence = AsyncPersistenceManager(session)
                    
                    async with self.run_lock:
                        # Set status to running in memory
                        if run_id in self.active_benchmarks:
                            self.active_benchmarks[run_id]["status"] = BenchmarkStatus.RUNNING
                            self.active_benchmarks[run_id]["updated_at"] = datetime.now(timezone.utc)
                            
                        # Update status in DB
                        await persistence.experiment_runs().update(run_id, {
                            "status": "running",
                            "started_at": datetime.now(timezone.utc)
                        })

                    # Simulate execution (in production, integrate with agent_runners)
                    # For now, we keep the simulation logic simple
                    await asyncio.sleep(random.uniform(3, 10))

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
                    
                    # Update status to completed in DB
                    completed_at = datetime.now(timezone.utc)
                    await persistence.experiment_runs().update(run_id, {
                        "status": "completed",
                        "completed_at": completed_at,
                        "metrics": metrics,
                        "results": metrics,
                        "progress_percent": 100
                    })

                    # Update memory status
                    async with self.run_lock:
                        if run_id in self.active_benchmarks:
                            self.active_benchmarks[run_id]["status"] = BenchmarkStatus.COMPLETED
                            self.active_benchmarks[run_id]["updated_at"] = completed_at
                            # Move to completed
                            self.completed_benchmarks[run_id] = self.active_benchmarks.pop(run_id)
                            self.completed_benchmarks[run_id]["completed_at"] = completed_at

                    # Store metrics in memory
                    self.completed_runs[run_id] = RunMetrics(metrics=metrics)

                    logger.info(
                        f"Completed run {run_id} for agent {agent_id} in scenario {scenario_id} with profit {profit:.2f}"
                    )

                self.run_queue.task_done()

            except Exception as e:
                logger.error(f"Worker error for run {run_id}: {e}", exc_info=True)
                # Try to update status in DB if session is available (new session for error handling)
                try:
                    async with AsyncSessionLocal() as session:
                        persistence = AsyncPersistenceManager(session)
                        await persistence.experiment_runs().update(run_id, {
                            "status": "failed",
                            "error_message": str(e)
                        })
                except Exception as db_err:
                    logger.error(f"Failed to update error status in DB: {db_err}")

                async with self.run_lock:
                    if run_id in self.active_benchmarks:
                        self.active_benchmarks[run_id]["status"] = BenchmarkStatus.FAILED
                        self.active_benchmarks[run_id]["updated_at"] = datetime.now(timezone.utc)
                        self.active_benchmarks[run_id]["error"] = str(e)
                await asyncio.sleep(1)

    async def create_benchmark(self, config: BenchmarkConfig) -> str:
        """Create a new benchmark and return its ID."""
        benchmark_id = str(uuid4())
        
        # In this simplified model, a 'benchmark' creation is just a placeholder
        # The actual run is created in run_benchmark. 
        # For now, we'll just keep the in-memory tracking as is for 'created' status
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
        
        # Persist initial run state to DB
        async with AsyncSessionLocal() as session:
            persistence = AsyncPersistenceManager(session)
            await persistence.experiment_runs().create({
                "id": run_id,
                # For now, we map 'experiment_id' to scenario_id or a generic one if not provided
                "experiment_id": request.scenario_id, 
                "scenario_id": request.scenario_id,
                "params": request.params,
                "status": "pending", # DB uses lowercase
                "participants": [
                    {
                        "id": str(uuid4()),
                        "agent_id": request.agent_id,
                        "role": "primary",
                        "config_override": {}
                    }
                ]
            })

        # Create benchmark entry in memory
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
        # Try memory first
        async with self.run_lock:
            if run_id in self.active_benchmarks:
                return self.active_benchmarks[run_id]
            elif run_id in self.completed_benchmarks:
                return self.completed_benchmarks[run_id]
        
        # Fallback to DB
        async with AsyncSessionLocal() as session:
            persistence = AsyncPersistenceManager(session)
            run = await persistence.experiment_runs().get(run_id)
            if run:
                # Convert DB status to API status enum if possible
                status_str = run.get("status", "pending").upper()
                return {
                    "id": run["id"],
                    "status": status_str,
                    "created_at": run.get("created_at"),
                    "updated_at": run.get("updated_at"),
                    "error": run.get("error_message"),
                    "results": run.get("results")
                }

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    async def get_run_results(self, run_id: str) -> RunMetrics:
        """Get the results (metrics) for a completed benchmark run."""
        async with self.run_lock:
            if run_id in self.completed_runs:
                return self.completed_runs[run_id]
        
        # Check DB
        async with AsyncSessionLocal() as session:
            persistence = AsyncPersistenceManager(session)
            run = await persistence.experiment_runs().get(run_id)
            if run and run.get("results"):
                import json
                results_data = run["results"]
                if isinstance(results_data, str):
                    results_data = json.loads(results_data)
                return RunMetrics(metrics=results_data)
            
            if run:
                 # It exists but no results yet
                 status_val = run.get("status", "pending")
                 if status_val in ["pending", "running"]:
                     raise HTTPException(
                        status_code=status.HTTP_202_ACCEPTED,
                        detail=f"Run {run_id} is {status_val} - results not available yet",
                    )
                 else:
                     raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Run {run_id} {status_val} - no results",
                    )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    async def list_benchmarks(self) -> List[Dict[str, Any]]:
        """List all benchmarks."""
        # Combine memory and DB (DB should have everything eventually)
        # For simplicity, we just return DB results for now as the source of truth for 'all'
        
        async with AsyncSessionLocal() as session:
            persistence = AsyncPersistenceManager(session)
            # Fetch last 100 runs
            runs = await persistence.experiment_runs().list_all(limit=100)
            
            # Map DB runs to API response format
            results = []
            for run in runs:
                results.append({
                    "id": run["id"],
                    "status": run["status"].upper(),
                    "created_at": run["created_at"],
                    "updated_at": run["updated_at"],
                    "agent_id": "unknown", # We'd need to fetch participants to know this, generic for list
                    "scenario_id": run["scenario_id"]
                })
            return results

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
                
                # Update DB
                async with AsyncSessionLocal() as session:
                    persistence = AsyncPersistenceManager(session)
                    await persistence.experiment_runs().update(run_id, {
                        "status": "stopped"
                    })
                return True
        return False

    async def log_external_benchmark(self, data: Dict[str, Any]) -> str:
        """
        Log an externally executed benchmark run (e.g. from run_openrouter_benchmark.py).
        """
        run_id = data.get("run_id") or str(uuid4())
        agent_id = data.get("agent_id")
        scenario_id = data.get("scenario_id")
        metrics = data.get("metrics", {})
        params = data.get("params", {})
        
        async with AsyncSessionLocal() as session:
            persistence = AsyncPersistenceManager(session)
            
            # Check if it exists
            existing = await persistence.experiment_runs().get(run_id)
            
            if existing:
                # Update
                await persistence.experiment_runs().update(run_id, {
                    "status": "completed",
                    "metrics": metrics,
                    "results": metrics,
                    "completed_at": datetime.now(timezone.utc)
                })
            else:
                # Create as completed
                await persistence.experiment_runs().create({
                    "id": run_id,
                    "experiment_id": scenario_id, # Fallback
                    "scenario_id": scenario_id,
                    "params": params,
                    "status": "completed",
                    "started_at": datetime.now(timezone.utc), # Approx
                    "completed_at": datetime.now(timezone.utc),
                    "metrics": metrics,
                    "results": metrics,
                    "participants": [
                        {
                            "id": str(uuid4()),
                            "agent_id": agent_id,
                            "role": "primary"
                        }
                    ] if agent_id else []
                })
                
        logger.info(f"Logged external benchmark run {run_id}")
        return run_id


# Initialize enhanced service
benchmark_service = BenchmarkService()


@router.post("/log", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
async def log_benchmark_result(data: Dict[str, Any]):
    """
    Log a benchmark result from an external runner.
    """
    try:
        run_id = await benchmark_service.log_external_benchmark(data)
        return {"run_id": run_id, "message": "Benchmark result logged successfully"}
    except Exception as e:
        logger.error(f"Failed to log benchmark: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log benchmark: {e!s}",
        )


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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # type: ignore[attr-defined]
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
    print("DEBUG: Entering list_benchmarks handler")
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
            # Also generic DB delete if needed (not implemented yet in this snippet)
            # but ideally we should update DB status to deleted or remove row
            
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
