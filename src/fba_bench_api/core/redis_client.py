import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

# from fba_bench_core.config import get_settings # get_settings not available in core config
import os

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Async Redis client wrapper for FBA-Bench Enterprise.
    """

    def __init__(self):
        # settings = get_settings()
        # Use the environment variable or a default (matching docker-compose)
        # self.redis_url = settings.redis_url or "redis://:fba_dev_redis@localhost:6379/0"
        # Support both legacy REDIS_URL and repo-standard FBA_BENCH_REDIS_URL.
        # Compose files primarily set FBA_BENCH_REDIS_URL.
        self.redis_url = (
            os.getenv("REDIS_URL")
            or os.getenv("FBA_BENCH_REDIS_URL")
            or "redis://:fba_dev_redis@localhost:6379/0"
        )
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        """Establishes the Redis connection pool."""
        if not self._redis:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            # Avoid logging credentials embedded in URLs.
            logger.info("Connected to Redis")

    async def close(self):
        """Closes the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def publish(self, channel: str, message: Any):
        """Publishes a message to a Redis channel."""
        if not self._redis:
            await self.connect()

        if not isinstance(message, str):
            message = json.dumps(message)

        await self._redis.publish(channel, message)

    async def lpush(self, key: str, value: Any):
        """Pushes a value to the head of a list."""
        if not self._redis:
            await self.connect()

        if not isinstance(value, str):
            value = json.dumps(value)

        await self._redis.lpush(key, value)

    def __getattr__(self, name: str):
        """Delegate unknown attributes to the underlying Redis client."""
        if self._redis:
            return getattr(self._redis, name)
        raise AttributeError(
            f"'RedisClient' object has no attribute '{name}' (and not connected)"
        )


# Singleton instance
_redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency to get the Redis client instance."""
    if not _redis_client._redis:
        await _redis_client.connect()
    return _redis_client


async def close_redis() -> None:
    """Close the global Redis client connection."""
    await _redis_client.close()
