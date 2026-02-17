"""
Provider State Manager

Manages database provider state and migration locking with file-based
persistence for cross-process coordination.
"""

import os
import json
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class MigrationState:
    """Represents the current state of a migration operation.

    Attributes:
        status: Current status ('idle', 'in_progress', 'completed', 'failed')
        source_provider: Provider being migrated from
        target_provider: Provider being migrated to
        started_at: ISO timestamp when migration started
        completed_at: ISO timestamp when migration completed
        tables_migrated: Number of tables successfully migrated
        total_tables: Total number of tables to migrate
        current_table: Currently processing table name
        current_step: Human-readable current step description
        error_message: Error message if migration failed
    """

    status: str = "idle"
    source_provider: Optional[str] = None
    target_provider: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    tables_migrated: int = 0
    total_tables: int = 0
    current_table: Optional[str] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ProviderState:
    """Persistent state for database provider configuration.

    Attributes:
        current_provider: Active provider name ('sqlite', 'mariadb', etc.)
        database_url: Connection URL for the current provider
        last_migration: Timestamp of last successful migration
        migration_history: List of past migrations
    """

    current_provider: str = "sqlite"
    database_url: str = ""
    last_migration: Optional[str] = None
    migration_history: list = field(default_factory=list)


class ProviderStateManager:
    """Manages database provider state and migration locking.

    Uses file-based locking to coordinate migrations across processes
    and persists state to JSON for reliability.
    """

    def __init__(self, state_dir: str = "database"):
        """Initialize state manager.

        Args:
            state_dir: Directory for state files (relative to project root).
        """
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "provider_state.json"
        self.lock_file = self.state_dir / ".migration.lock"
        self._lock_fd = None

        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def get_current_provider(self) -> str:
        """Get current active provider from state file.

        Returns:
            str: Provider name ('sqlite', 'mariadb', 'mysql', 'postgresql').
        """
        state = self._load_state()
        return state.get("current_provider", "sqlite")

    def get_database_url(self) -> Optional[str]:
        """Get current database URL from state file.

        Returns:
            Optional[str]: Database URL or None if not configured.
        """
        state = self._load_state()
        return state.get("database_url")

    def set_current_provider(self, provider: str) -> None:
        """Set current active provider.

        Args:
            provider: Provider name to set as current.
        """
        state = self._load_state()
        state["current_provider"] = provider
        state["last_migration"] = datetime.now(tz=timezone.utc).isoformat()
        self._save_state(state)
        logger.info(f"Provider set to: {provider}")

    def set_database_url(self, url: str) -> None:
        """Set database URL for the current provider.

        Args:
            url: Database connection URL.
        """
        state = self._load_state()
        state["database_url"] = url
        self._save_state(state)

    def acquire_migration_lock(self) -> bool:
        """Acquire exclusive migration lock.

        Uses file-based locking for cross-process coordination.

        Returns:
            bool: True if lock acquired, False if already locked.
        """
        try:
            self._lock_fd = open(self.lock_file, "w")
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(f"locked_at: {datetime.now(tz=timezone.utc).isoformat()}\n")
            self._lock_fd.flush()
            logger.info("Migration lock acquired")
            return True
        except (IOError, OSError) as e:
            logger.warning(f"Failed to acquire migration lock: {e}")
            if self._lock_fd:
                self._lock_fd.close()
                self._lock_fd = None
            return False

    def release_migration_lock(self) -> None:
        """Release migration lock.

        Safe to call even if lock not held.
        """
        if self._lock_fd:
            try:
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")
            finally:
                self._lock_fd = None

            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                except Exception:
                    pass
            logger.info("Migration lock released")

    def is_migration_locked(self) -> bool:
        """Check if migration is currently locked.

        Returns:
            bool: True if migration lock is held.
        """
        if not self.lock_file.exists():
            return False
        try:
            with open(self.lock_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return False  # Lock was available
        except (IOError, OSError):
            return True  # Lock is held

    def update_migration_state(self, state: MigrationState) -> None:
        """Update migration state file.

        Args:
            state: MigrationState object with current status.
        """
        current = self._load_state()
        current["migration"] = asdict(state)
        self._save_state(current)
        logger.debug(f"Migration state updated: {state.status}")

    def get_migration_state(self) -> Optional[MigrationState]:
        """Get current migration state.

        Returns:
            Optional[MigrationState]: Current migration state or None.
        """
        state = self._load_state()
        if "migration" in state:
            return MigrationState(**state["migration"])
        return None

    def clear_migration_state(self) -> None:
        """Clear migration state (after completion or cancellation)."""
        current = self._load_state()
        current.pop("migration", None)
        self._save_state(current)

    def add_migration_history(self, source: str, target: str, success: bool, error: Optional[str] = None) -> None:
        """Add entry to migration history.

        Args:
            source: Source provider name.
            target: Target provider name.
            success: Whether migration succeeded.
            error: Error message if failed.
        """
        state = self._load_state()
        history = state.get("migration_history", [])
        history.append(
            {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "source": source,
                "target": target,
                "success": success,
                "error": error,
            }
        )
        state["migration_history"] = history[-10:]  # Keep last 10
        self._save_state(state)

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file.

        Returns:
            Dict[str, Any]: State dictionary.
        """
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}")
        return {"current_provider": "sqlite"}

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save state to file.

        Args:
            state: State dictionary to save.
        """
        try:
            self.state_file.write_text(json.dumps(state, indent=2))
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")
            raise

    def get_full_status(self) -> Dict[str, Any]:
        """Get complete status information.

        Returns:
            Dict[str, Any]: Full status including provider, migration state, etc.
        """
        state = self._load_state()
        return {
            "current_provider": state.get("current_provider", "sqlite"),
            "database_url": state.get("database_url"),
            "last_migration": state.get("last_migration"),
            "migration_locked": self.is_migration_locked(),
            "migration": state.get("migration"),
            "migration_history": state.get("migration_history", []),
        }
