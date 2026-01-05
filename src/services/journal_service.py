"""Journal Service - Immutable Event Store for Simulation Replay.

This module provides persistent storage for simulation events, enabling:
- Deterministic replay: Run simulation twice with same seed = identical results
- Audit trail: Every event is recorded for forensic analysis
- State reconstruction: Rebuild any point in time from event history

The journal uses SQLite for local development and is designed for 
Postgres compatibility in production environments.

Usage:
    from services.journal_service import JournalService
    
    journal = JournalService(db_path="simulation.db")
    await journal.initialize()
    
    # Record events
    await journal.append(event)
    
    # Replay history
    events = await journal.get_history(simulation_id, until_tick=100)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union
from uuid import UUID, uuid4

from fba_bench_core.core.events import (
    AnyGameEvent,
    GameEvent,
    deserialize_event,
)

logger = logging.getLogger(__name__)


class JournalError(Exception):
    """Raised when journal operations fail."""
    pass


class JournalService:
    """Persistent event store for simulation replay.
    
    Events are written to an append-only journal that can be queried by:
    - simulation_id: Filter events for a specific simulation run
    - tick: Filter events up to a specific tick for replay
    - event_type: Filter by event category
    
    The journal is designed to be immutable - events are never updated or deleted
    during normal operation (only via explicit maintenance operations).
    
    Attributes:
        db_path: Path to SQLite database file (None for in-memory).
        simulation_id: Current simulation run identifier.
    """
    
    # SQLite schema for events table
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            tick INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            category TEXT NOT NULL,
            agent_id TEXT,
            payload TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_events_simulation_tick 
            ON events(simulation_id, tick);
        CREATE INDEX IF NOT EXISTS idx_events_simulation_type 
            ON events(simulation_id, event_type);
        CREATE INDEX IF NOT EXISTS idx_events_tick 
            ON events(tick);
    """
    
    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        simulation_id: Optional[str] = None,
        in_memory: bool = False,
    ):
        """Initialize the journal service.
        
        Args:
            db_path: Path to SQLite database. If None and in_memory=False, 
                    uses 'simulation_journal.db' in current directory.
            simulation_id: Identifier for current simulation run. 
                          If None, generates a new UUID.
            in_memory: If True, use in-memory SQLite database (for tests).
        """
        if in_memory:
            self._db_path = ":memory:"
        elif db_path:
            self._db_path = str(db_path)
        else:
            self._db_path = "simulation_journal.db"
            
        self._simulation_id = simulation_id or f"sim-{uuid4()}"
        self._connection: Optional[sqlite3.Connection] = None
        self._initialized = False
        self._event_count = 0
        
    @property
    def simulation_id(self) -> str:
        """Current simulation run identifier."""
        return self._simulation_id
    
    @property
    def event_count(self) -> int:
        """Number of events recorded in current session."""
        return self._event_count
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    async def initialize(self) -> None:
        """Initialize the journal database schema.
        
        This creates the events table and indexes if they don't exist.
        Should be called once at simulation startup.
        """
        if self._initialized:
            return
            
        conn = self._get_connection()
        try:
            conn.executescript(self.SCHEMA)
            conn.commit()
            self._initialized = True
            logger.info(
                f"Journal initialized: db={self._db_path}, sim_id={self._simulation_id}"
            )
        except sqlite3.Error as e:
            raise JournalError(f"Failed to initialize journal schema: {e}") from e
    
    async def append(self, event: GameEvent) -> None:
        """Append an event to the journal.
        
        Events are immutable once written. The journal is append-only.
        
        Args:
            event: The event to record.
            
        Raises:
            JournalError: If write fails.
        """
        if not self._initialized:
            await self.initialize()
            
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO events 
                    (id, simulation_id, tick, timestamp, event_type, 
                     category, agent_id, payload, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_id),
                    self._simulation_id,
                    event.tick,
                    event.timestamp.isoformat(),
                    event.event_type,
                    event.category.value,
                    event.agent_id,
                    json.dumps(event.payload),
                    json.dumps(event.metadata),
                )
            )
            conn.commit()
            self._event_count += 1
        except sqlite3.Error as e:
            raise JournalError(f"Failed to append event {event.event_id}: {e}") from e
    
    async def append_batch(self, events: List[GameEvent]) -> None:
        """Append multiple events to the journal in a single transaction.
        
        More efficient than calling append() for each event.
        
        Args:
            events: List of events to record.
        """
        if not events:
            return
            
        if not self._initialized:
            await self.initialize()
            
        conn = self._get_connection()
        try:
            conn.executemany(
                """
                INSERT INTO events 
                    (id, simulation_id, tick, timestamp, event_type, 
                     category, agent_id, payload, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(e.event_id),
                        self._simulation_id,
                        e.tick,
                        e.timestamp.isoformat(),
                        e.event_type,
                        e.category.value,
                        e.agent_id,
                        json.dumps(e.payload),
                        json.dumps(e.metadata),
                    )
                    for e in events
                ]
            )
            conn.commit()
            self._event_count += len(events)
        except sqlite3.Error as e:
            raise JournalError(f"Failed to append batch of {len(events)} events: {e}") from e
    
    async def get_history(
        self,
        simulation_id: Optional[str] = None,
        until_tick: Optional[int] = None,
        event_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[GameEvent]:
        """Retrieve event history for replay.
        
        Args:
            simulation_id: Filter by simulation run. Defaults to current.
            until_tick: Include events up to and including this tick.
            event_types: Filter by event types (e.g., ["ORDER_PLACED", "SALE_COMPLETED"]).
            limit: Maximum number of events to return.
            
        Returns:
            List of events in chronological order (by tick, then insertion).
        """
        if not self._initialized:
            await self.initialize()
            
        sim_id = simulation_id or self._simulation_id
        
        query = "SELECT * FROM events WHERE simulation_id = ?"
        params: List[Any] = [sim_id]
        
        if until_tick is not None:
            query += " AND tick <= ?"
            params.append(until_tick)
            
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend(event_types)
            
        query += " ORDER BY tick ASC, rowid ASC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
            
        conn = self._get_connection()
        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            events = []
            for row in rows:
                event_data = {
                    "event_id": row["id"],
                    "tick": row["tick"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "category": row["category"],
                    "agent_id": row["agent_id"],
                    "payload": json.loads(row["payload"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                }
                events.append(deserialize_event(event_data))
            
            return events
            
        except sqlite3.Error as e:
            raise JournalError(f"Failed to retrieve event history: {e}") from e
    
    async def get_latest_tick(
        self,
        simulation_id: Optional[str] = None,
    ) -> int:
        """Get the latest tick number in the journal.
        
        Returns:
            The highest tick number, or -1 if no events.
        """
        if not self._initialized:
            await self.initialize()
            
        sim_id = simulation_id or self._simulation_id
        
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT MAX(tick) FROM events WHERE simulation_id = ?",
            (sim_id,)
        )
        result = cursor.fetchone()
        return result[0] if result[0] is not None else -1
    
    async def get_event_count(
        self,
        simulation_id: Optional[str] = None,
    ) -> int:
        """Get total number of events in journal.
        
        Returns:
            Event count for the specified simulation.
        """
        if not self._initialized:
            await self.initialize()
            
        sim_id = simulation_id or self._simulation_id
        
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM events WHERE simulation_id = ?",
            (sim_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0
    
    async def export_to_csv(
        self,
        filepath: Union[str, Path],
        simulation_id: Optional[str] = None,
    ) -> int:
        """Export journal to CSV for audit purposes.
        
        This is used for the "Audit Test" - export to Excel and verify
        debits == credits.
        
        Args:
            filepath: Path to output CSV file.
            simulation_id: Filter by simulation run.
            
        Returns:
            Number of events exported.
        """
        import csv
        
        events = await self.get_history(simulation_id=simulation_id)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'event_id', 'tick', 'timestamp', 'event_type', 
                'category', 'agent_id', 'payload', 'metadata'
            ])
            
            # Data
            for event in events:
                writer.writerow([
                    str(event.event_id),
                    event.tick,
                    event.timestamp.isoformat(),
                    event.event_type,
                    event.category.value,
                    event.agent_id or '',
                    json.dumps(event.payload),
                    json.dumps(event.metadata),
                ])
        
        logger.info(f"Exported {len(events)} events to {filepath}")
        return len(events)
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            self._initialized = False
            logger.info("Journal connection closed")
    
    async def clear_simulation(
        self,
        simulation_id: Optional[str] = None,
    ) -> int:
        """Clear all events for a simulation (for testing/maintenance).
        
        WARNING: This violates the append-only principle and should only
        be used for testing or explicit maintenance operations.
        
        Args:
            simulation_id: Simulation to clear. Defaults to current.
            
        Returns:
            Number of events deleted.
        """
        sim_id = simulation_id or self._simulation_id
        
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM events WHERE simulation_id = ?",
            (sim_id,)
        )
        conn.commit()
        deleted = cursor.rowcount
        self._event_count = 0
        
        logger.warning(f"Cleared {deleted} events for simulation {sim_id}")
        return deleted
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get journal statistics for monitoring."""
        conn = self._get_connection()
        
        # Count by event type
        cursor = conn.execute("""
            SELECT event_type, COUNT(*) as count
            FROM events 
            WHERE simulation_id = ?
            GROUP BY event_type
            ORDER BY count DESC
        """, (self._simulation_id,))
        
        type_counts = {row["event_type"]: row["count"] for row in cursor.fetchall()}
        
        # Get tick range
        cursor = conn.execute("""
            SELECT MIN(tick) as min_tick, MAX(tick) as max_tick
            FROM events
            WHERE simulation_id = ?
        """, (self._simulation_id,))
        range_row = cursor.fetchone()
        
        return {
            "simulation_id": self._simulation_id,
            "db_path": self._db_path,
            "total_events": self._event_count,
            "event_types": type_counts,
            "min_tick": range_row["min_tick"] if range_row else None,
            "max_tick": range_row["max_tick"] if range_row else None,
            "initialized": self._initialized,
        }
