"""
ExperimentRunStore - Redis-backed experiment run storage with in-memory fallback.

This module provides persistent storage for experiment runs, ensuring data survives
server restarts. It uses Redis as the primary store with an in-memory cache for
performance, falling back to pure in-memory storage for development environments.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# TTL for experiment runs in Redis (7 days)
EXPERIMENT_RUN_TTL_SECONDS = 7 * 24 * 60 * 60


class ExperimentRunStore:
    """
    Redis-backed experiment run storage with in-memory fallback.
    
    Features:
    - Primary storage in Redis for persistence across restarts
    - Local cache for fast reads
    - Automatic fallback to in-memory if Redis unavailable
    - TTL-based expiration for old runs
    """
    
    def __init__(self, redis_client: Optional[Any] = None):
        """
        Initialize the experiment run store.
        
        Args:
            redis_client: Optional Redis client. If None, uses in-memory storage only.
        """
        self._redis = redis_client
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._redis_available = redis_client is not None
        
    @classmethod
    async def create(cls) -> "ExperimentRunStore":
        """
        Factory method to create an ExperimentRunStore with Redis connection.
        
        Returns:
            ExperimentRunStore instance with Redis if available.
        """
        redis_client = None
        try:
            from fba_bench_api.core.redis_client import get_redis
            redis_client = await get_redis()
            logger.info("ExperimentRunStore initialized with Redis backend")
        except Exception as e:
            logger.warning(
                "Redis not available for ExperimentRunStore, using in-memory only: %s", e
            )
        return cls(redis_client)
    
    def _make_key(self, run_id: str) -> str:
        """Generate Redis key for a run."""
        return f"experiment_run:{run_id}"
    
    def _make_experiment_index_key(self, experiment_id: str) -> str:
        """Generate Redis key for experiment's run index."""
        return f"experiment_runs_index:{experiment_id}"
    
    async def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an experiment run by ID.
        
        Args:
            run_id: The run ID to retrieve.
            
        Returns:
            Run data dict if found, None otherwise.
        """
        # Check local cache first
        if run_id in self._local_cache:
            return self._local_cache[run_id]
        
        # Try Redis
        if self._redis_available and self._redis:
            try:
                key = self._make_key(run_id)
                data = await self._redis.get(key)
                if data:
                    run_data = json.loads(data)
                    self._local_cache[run_id] = run_data
                    return run_data
            except Exception as e:
                logger.warning("Redis get failed for run %s: %s", run_id, e)
        
        return None
    
    async def set(self, run_id: str, run_data: Dict[str, Any]) -> None:
        """
        Store an experiment run.
        
        Args:
            run_id: The run ID.
            run_data: The run data to store.
        """
        # Ensure serializable
        serializable_data = self._make_serializable(run_data)
        
        # Update local cache
        self._local_cache[run_id] = serializable_data
        
        # Persist to Redis
        if self._redis_available and self._redis:
            try:
                key = self._make_key(run_id)
                await self._redis.set(
                    key,
                    json.dumps(serializable_data),
                    ex=EXPERIMENT_RUN_TTL_SECONDS,
                )
                
                # Add to experiment index
                experiment_id = run_data.get("experiment_id")
                if experiment_id:
                    index_key = self._make_experiment_index_key(experiment_id)
                    await self._redis.sadd(index_key, run_id)
                    await self._redis.expire(index_key, EXPERIMENT_RUN_TTL_SECONDS)
                    
            except Exception as e:
                logger.warning("Redis set failed for run %s: %s", run_id, e)
    
    async def update(self, run_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing experiment run.
        
        Args:
            run_id: The run ID to update.
            updates: Fields to update.
            
        Returns:
            Updated run data if found, None otherwise.
        """
        run_data = await self.get(run_id)
        if run_data is None:
            return None
        
        run_data.update(self._make_serializable(updates))
        run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await self.set(run_id, run_data)
        return run_data
    
    async def delete(self, run_id: str) -> bool:
        """
        Delete an experiment run.
        
        Args:
            run_id: The run ID to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        if run_id in self._local_cache:
            experiment_id = self._local_cache[run_id].get("experiment_id")
            del self._local_cache[run_id]
            
            if self._redis_available and self._redis:
                try:
                    key = self._make_key(run_id)
                    await self._redis.delete(key)
                    
                    if experiment_id:
                        index_key = self._make_experiment_index_key(experiment_id)
                        await self._redis.srem(index_key, run_id)
                except Exception as e:
                    logger.warning("Redis delete failed for run %s: %s", run_id, e)
            
            return True
        return False
    
    async def list_by_experiment(self, experiment_id: str) -> List[Dict[str, Any]]:
        """
        List all runs for an experiment.
        
        Args:
            experiment_id: The experiment ID.
            
        Returns:
            List of run data dicts.
        """
        runs = []
        
        # Try Redis index first
        if self._redis_available and self._redis:
            try:
                index_key = self._make_experiment_index_key(experiment_id)
                run_ids = await self._redis.smembers(index_key)
                for run_id in run_ids:
                    run_data = await self.get(run_id)
                    if run_data:
                        runs.append(run_data)
            except Exception as e:
                logger.warning("Redis list failed for experiment %s: %s", experiment_id, e)
        
        # Fallback to cache scan
        if not runs:
            for run_id, run_data in self._local_cache.items():
                if run_data.get("experiment_id") == experiment_id:
                    runs.append(run_data)
        
        return runs
    
    async def get_active_run(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the active (running) run for an experiment.
        
        Args:
            experiment_id: The experiment ID.
            
        Returns:
            Active run data if found, None otherwise.
        """
        runs = await self.list_by_experiment(experiment_id)
        for run in runs:
            if run.get("status") in ("pending", "starting", "running"):
                return run
        return None
    
    def _make_serializable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert data to JSON-serializable format."""
        result = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, BaseModel):
                result[key] = value.model_dump()
            elif isinstance(value, list):
                result[key] = [
                    (v.model_dump() if isinstance(v, BaseModel) else v)
                    for v in value
                ]
            else:
                result[key] = value
        return result


# Global store instance (initialized lazily)
_store_instance: Optional[ExperimentRunStore] = None


async def get_experiment_store() -> ExperimentRunStore:
    """
    Get or create the global ExperimentRunStore instance.
    
    Returns:
        ExperimentRunStore instance.
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = await ExperimentRunStore.create()
    return _store_instance
