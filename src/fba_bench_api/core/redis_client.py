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
        self.redis_url = os.getenv("REDIS_URL", "redis://:fba_dev_redis@localhost:6379/0")
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        """Establishes the Redis connection pool."""
        if not self._redis:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Connected to Redis at {self.redis_url}")

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
