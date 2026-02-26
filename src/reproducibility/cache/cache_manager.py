"""
Cache Manager for Reproducibility

This module provides a centralized cache management system for storing
and retrieving computational results with configurable policies.
"""

import hashlib
import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union


class CacheManager:
    """
    A cache manager that handles storage and retrieval of computational results
    with support for multiple backends and configurable policies.
    """

    def __init__(
        self,
        cache_dir: Union[str, Path] = ".cache",
        max_size_mb: int = 1024,
        default_ttl_seconds: int = 86400,  # 24 hours
        enable_disk_cache: bool = True,
        enable_memory_cache: bool = True,
    ):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory for disk-based caching
            max_size_mb: Maximum size of the cache in megabytes
            default_ttl_seconds: Default time-to-live for cache entries
            enable_disk_cache: Whether to enable disk-based caching
            enable_memory_cache: Whether to enable in-memory caching
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        self.enable_disk_cache = enable_disk_cache
        self.enable_memory_cache = enable_memory_cache

        # Create cache directory if it doesn't exist
        if self.enable_disk_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self.memory_cache: Dict[str, Dict[str, Any]] = {}

        # Cache statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        Generate a unique cache key based on function name and arguments.

        Args:
            func_name: Name of the function being cached
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            A unique cache key string
        """
        # Create a dictionary representation of the arguments
        key_data = {
            "func_name": func_name,
            "args": args,
            "kwargs": kwargs,
        }

        # Serialize to JSON and create a hash
        json_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """
        Get the file path for a cache key.

        Args:
            key: Cache key

        Returns:
            Path to the cache file
        """
        # Use first two characters of the key as subdirectory for better organization
        sub_dir = self.cache_dir / key[:2]
        sub_dir.mkdir(exist_ok=True)
        return sub_dir / f"{key}.cache"

    def _is_cache_entry_valid(self, entry: Dict[str, Any]) -> bool:
        """
        Check if a cache entry is still valid based on its TTL.

        Args:
            entry: Cache entry dictionary

        Returns:
            True if the entry is still valid, False otherwise
        """
        if "timestamp" not in entry or "ttl" not in entry:
            return False

        age = time.time() - entry["timestamp"]
        return age < entry["ttl"]

    def _enforce_size_limit(self):
        """
        Enforce the cache size limit by evicting the least recently used entries.
        """
        if not self.enable_disk_cache:
            return

        # Get all cache files with their access times
        cache_files = []
        for cache_file in self.cache_dir.rglob("*.cache"):
            try:
                stat = cache_file.stat()
                cache_files.append((cache_file, stat.st_atime, stat.st_size))
            except OSError:
                # Skip files that can't be accessed
                continue

        # Sort by access time (oldest first)
        cache_files.sort(key=lambda x: x[1])

        # Remove files until we're under the size limit
        total_size = sum(size for _, _, size in cache_files)
        while total_size > self.max_size_bytes and cache_files:
            cache_file, _, size = cache_files.pop(0)
            try:
                cache_file.unlink()
                total_size -= size
                self.evictions += 1
            except OSError:
                # Skip files that can't be removed
                continue

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        # Check memory cache first
        if self.enable_memory_cache and key in self.memory_cache:
            entry = self.memory_cache[key]
            if self._is_cache_entry_valid(entry):
                self.hits += 1
                return entry["value"]
            else:
                # Remove expired entry
                del self.memory_cache[key]

        # Check disk cache
        if self.enable_disk_cache:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                try:
                    with open(cache_path) as f:
                        entry = json.load(f)

                    if self._is_cache_entry_valid(entry):
                        # Update access time
                        cache_path.touch()

                        # Store in memory cache if enabled
                        if self.enable_memory_cache:
                            self.memory_cache[key] = entry

                        self.hits += 1
                        return entry["value"]
                    else:
                        # Remove expired entry
                        cache_path.unlink()
                except (pickle.PickleError, OSError):
                    # Skip corrupted files
                    pass

        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Store a value in the cache.

        Args:
            key: Cache key
            value: Value to store
            ttl_seconds: Time-to-live in seconds, uses default if None

        Returns:
            True if successful, False otherwise
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds

        entry = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl_seconds,
        }

        # Store in memory cache
        if self.enable_memory_cache:
            self.memory_cache[key] = entry

        # Store in disk cache
        if self.enable_disk_cache:
            cache_path = self._get_cache_path(key)
            try:
                with open(cache_path, "w") as f:
                    json.dump(entry, f, default=str)

                # Enforce size limit
                self._enforce_size_limit()
                return True
            except (pickle.PickleError, OSError):
                return False

        return True

    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if the key was found and deleted, False otherwise
        """
        deleted = False

        # Delete from memory cache
        if self.enable_memory_cache and key in self.memory_cache:
            del self.memory_cache[key]
            deleted = True

        # Delete from disk cache
        if self.enable_disk_cache:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                    deleted = True
                except OSError:
                    pass

        return deleted

    def clear(self) -> bool:
        """
        Clear all entries from the cache.

        Returns:
            True if successful, False otherwise
        """
        # Clear memory cache
        if self.enable_memory_cache:
            self.memory_cache.clear()

        # Clear disk cache
        if self.enable_disk_cache:
            try:
                for cache_file in self.cache_dir.rglob("*.cache"):
                    cache_file.unlink()
                return True
            except OSError:
                return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        stats = {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
        }

        # Calculate hit rate
        total_requests = self.hits + self.misses
        if total_requests > 0:
            stats["hit_rate"] = self.hits / total_requests  # type: ignore[assignment]
        else:
            stats["hit_rate"] = 0.0  # type: ignore[assignment]

        # Calculate cache size
        if self.enable_disk_cache:
            try:
                cache_size = 0
                file_count = 0
                for cache_file in self.cache_dir.rglob("*.cache"):
                    cache_size += cache_file.stat().st_size
                    file_count += 1
                stats["disk_size_bytes"] = cache_size
                stats["disk_size_mb"] = cache_size / (1024 * 1024)  # type: ignore[assignment]
                stats["file_count"] = file_count
            except OSError:
                stats["disk_size_bytes"] = 0
                stats["disk_size_mb"] = 0
                stats["file_count"] = 0

        if self.enable_memory_cache:
            stats["memory_entries"] = len(self.memory_cache)

        return stats

    def cache_decorator(self, ttl_seconds: Optional[int] = None):
        """
        Decorator for caching function results.

        Args:
            ttl_seconds: Time-to-live in seconds, uses default if None

        Returns:
            Decorator function
        """

        def decorator(func):
            def wrapper(*args, **kwargs):
                # Generate cache key
                key = self._generate_key(func.__name__, args, kwargs)

                # Try to get from cache
                result = self.get(key)
                if result is not None:
                    return result

                # Call function and cache result
                result = func(*args, **kwargs)
                self.set(key, result, ttl_seconds)
                return result

            return wrapper

        return decorator
