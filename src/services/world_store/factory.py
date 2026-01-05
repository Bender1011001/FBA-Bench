"""
Global instance management for WorldStore.
Provides singleton access to the WorldStore instance.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import WorldStore

from .persistence import JsonFileStorageBackend, PersistenceBackend

logger = logging.getLogger(__name__)

_world_store_instance: Optional[WorldStore] = None


def get_world_store(storage_backend: Optional[PersistenceBackend] = None) -> WorldStore:
    """
    Get the global WorldStore instance.
    Allows specifying a storage_backend on first call.
    If no backend is provided on the first call, defaults to JsonFileStorageBackend.
    """
    global _world_store_instance
    if _world_store_instance is None:
        # If a storage_backend is provided, use it; otherwise, default to JsonFileStorageBackend.
        # This makes JsonFileStorageBackend the default for production-readiness.
        backend_to_use = (
            storage_backend if storage_backend is not None else JsonFileStorageBackend()
        )
        _world_store_instance = WorldStore(storage_backend=backend_to_use)
        logger.info(
            f"Global WorldStore instance created with backend: {type(backend_to_use).__name__}"
        )
    elif storage_backend is not None:
        logger.warning(
            "Global WorldStore instance already exists. Provided storage_backend is ignored."
        )
    return _world_store_instance


def set_world_store(world_store: WorldStore):
    """Set the global WorldStore instance."""
    global _world_store_instance
    _world_store_instance = world_store
    logger.info("Global WorldStore instance has been set.")
