"""
Persistence layer for WorldStore service.
Provides interfaces and implementations for saving/loading state snapshots.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class PersistenceBackend(Protocol):
    """
    Abstract interface for WorldStore persistence backends.
    Allows saving and loading the canonical state.
    """

    async def save_state(
        self, state: Dict[str, Any], timestamp: datetime, tick: Optional[int] = None
    ) -> str:
        """Saves a snapshot of the current world state."""
        ...

    async def load_latest_state(self) -> Optional[Dict[str, Any]]:
        """Loads the most recent world state snapshot."""
        ...

    async def load_state_by_id(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Loads a specific world state snapshot by its ID."""
        ...

    async def initialize(self):
        """Initializes the persistence backend (e.g., connects to DB)."""
        ...

    async def shutdown(self):
        """Shuts down the persistence backend."""
        ...


class InMemoryStorageBackend:
    """
    A simple in-memory storage backend for WorldStore state snapshots.
    NOT FOR PRODUCTION USE - primarily for testing and demonstration.
    """

    def __init__(self):
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._latest_snapshot_id: Optional[str] = None
        logger.info("InMemoryStorageBackend initialized.")

    async def initialize(self):
        logger.info(
            "InMemoryStorageBackend initialized - no external connection needed."
        )

    async def shutdown(self):
        logger.info("InMemoryStorageBackend shut down.")

    async def save_state(
        self, state: Dict[str, Any], timestamp: datetime, tick: Optional[int] = None
    ) -> str:
        import uuid

        snapshot_id = f"snapshot_{uuid.uuid4()!s}"
        snapshot_data = {
            "id": snapshot_id,
            "timestamp": timestamp.isoformat(),
            "tick": tick,
            "state": state,
        }
        self._snapshots[snapshot_id] = snapshot_data
        self._latest_snapshot_id = snapshot_id
        logger.info(f"Saved in-memory state snapshot: {snapshot_id} at tick {tick}")
        return snapshot_id

    async def load_latest_state(self) -> Optional[Dict[str, Any]]:
        if self._latest_snapshot_id and self._latest_snapshot_id in self._snapshots:
            logger.info(
                f"Loading latest in-memory state snapshot: {self._latest_snapshot_id}"
            )
            return self._snapshots[self._latest_snapshot_id]["state"]
        logger.info("No latest in-memory state snapshot found.")
        return None

    async def load_state_by_id(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        snapshot_data = self._snapshots.get(snapshot_id)
        if snapshot_data:
            logger.info(f"Loading in-memory state snapshot by ID: {snapshot_id}")
            return snapshot_data["state"]
        logger.warning(f"In-memory state snapshot {snapshot_id} not found.")
        return None


class JsonFileStorageBackend:
    """
    A file-based storage backend for WorldStore state snapshots using JSON files.
    More suitable for production than InMemoryStorageBackend for single-instance setups.
    """

    def __init__(self, snapshot_dir: str = "world_store_snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self._latest_snapshot_id: Optional[str] = None
        logger.info(
            f"JsonFileStorageBackend initialized with directory: {self.snapshot_dir}"
        )

    async def initialize(self):
        try:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                f"JsonFileStorageBackend ensured directory exists: {self.snapshot_dir}"
            )
            # Attempt to find the latest snapshot ID on startup
            await self._find_latest_snapshot_id()
        except (TypeError, AttributeError, OSError) as e:
            logger.error(
                f"Failed to initialize JsonFileStorageBackend directory: {e}",
                exc_info=True,
            )
            raise

    async def shutdown(self):
        logger.info("JsonFileStorageBackend shut down.")

    def _get_snapshot_path(self, snapshot_id: str) -> Path:
        return self.snapshot_dir / f"{snapshot_id}.json"

    async def _find_latest_snapshot_id(self):
        """Finds the ID of the latest snapshot based on modification time."""
        latest_mtime = 0
        latest_id = None
        try:
            for file_path in self.snapshot_dir.glob("*.json"):
                if file_path.is_file():
                    mtime = file_path.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_id = file_path.stem  # filename without extension
            self._latest_snapshot_id = latest_id
            if latest_id:
                logger.info(
                    f"JsonFileStorageBackend identified latest snapshot as: {latest_id}"
                )
            else:
                logger.info("JsonFileStorageBackend found no existing snapshots.")
        except (TypeError, AttributeError, OSError) as e:
            logger.error(
                f"Error finding latest snapshot ID in JsonFileStorageBackend: {e}",
                exc_info=True,
            )

    async def save_state(
        self, state: Dict[str, Any], timestamp: datetime, tick: Optional[int] = None
    ) -> str:
        snapshot_id = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_{tick or 'N'}"
        snapshot_data = {
            "id": snapshot_id,
            "timestamp": timestamp.isoformat(),
            "tick": tick,
            "state": state,
        }
        snapshot_path = self._get_snapshot_path(snapshot_id)
        try:
            with open(snapshot_path, "w") as f:
                json.dump(snapshot_data, f, indent=4)
            self._latest_snapshot_id = snapshot_id
            logger.info(f"Saved JSON state snapshot: {snapshot_id} to {snapshot_path}")
            return snapshot_id
        except (TypeError, AttributeError, OSError) as e:
            logger.error(
                f"Failed to save JSON state snapshot {snapshot_id}: {e}", exc_info=True
            )
            raise

    async def load_latest_state(self) -> Optional[Dict[str, Any]]:
        if not self._latest_snapshot_id:
            await self._find_latest_snapshot_id()  # Ensure we have tried to find it

        if self._latest_snapshot_id:
            return await self.load_state_by_id(self._latest_snapshot_id)
        logger.info("No latest JSON state snapshot found.")
        return None

    async def load_state_by_id(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        snapshot_path = self._get_snapshot_path(snapshot_id)
        try:
            if not snapshot_path.exists():
                logger.warning(
                    f"JSON state snapshot {snapshot_id} not found at {snapshot_path}."
                )
                return None
            with open(snapshot_path) as f:
                snapshot_data = json.load(f)
            logger.info(
                f"Loaded JSON state snapshot by ID: {snapshot_id} from {snapshot_path}"
            )
            return snapshot_data.get("state")
        except (TypeError, AttributeError, OSError) as e:
            logger.error(
                f"Failed to load JSON state snapshot {snapshot_id}: {e}", exc_info=True
            )
            return None
