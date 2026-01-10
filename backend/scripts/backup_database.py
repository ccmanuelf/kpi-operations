#!/usr/bin/env python3
"""
Automated SQLite Database Backup Script
=======================================
Supports: Local backup, rotation, compression, logging

Usage:
    Manual: python backup_database.py
    Cron:   0 2 * * * cd /path/to/backend && python scripts/backup_database.py

Features:
    - Creates timestamped compressed backups (.db.gz)
    - Rotates backups keeping last N daily backups (default: 7)
    - Logs all operations to backup.log
    - Validates backup integrity after creation
    - Returns exit code 0 on success, 1 on failure
"""

import os
import sys
import gzip
import shutil
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
DEFAULT_BACKUP_DIR = "backups"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_LOG_FILE = "backup.log"
BACKUP_PREFIX = "kpi_platform_backup"
BACKUP_EXTENSION = ".db.gz"


def setup_logging(log_dir: Path) -> logging.Logger:
    """
    Configure logging for backup operations.

    Args:
        log_dir: Directory for log file

    Returns:
        Configured logger instance
    """
    log_file = log_dir / DEFAULT_LOG_FILE

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configure logger
    logger = logging.getLogger("backup")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_database_path() -> Path:
    """
    Get the SQLite database path from configuration.

    Returns:
        Path to the SQLite database file

    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    # Try to import from config
    try:
        from backend.config import settings
        db_url = settings.DATABASE_URL
    except ImportError:
        # Default fallback
        db_url = "sqlite:///../database/kpi_platform.db"

    # Parse SQLite URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")

        # Handle relative paths
        if not os.path.isabs(db_path):
            base_dir = Path(__file__).parent.parent
            db_path = (base_dir / db_path).resolve()
        else:
            db_path = Path(db_path).resolve()
    else:
        raise ValueError(f"Unsupported database URL format: {db_url}")

    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    return db_path


def create_backup_directory(backup_dir: Path) -> None:
    """
    Create backup directory if it doesn't exist.

    Args:
        backup_dir: Path to backup directory
    """
    backup_dir.mkdir(parents=True, exist_ok=True)


def generate_backup_filename() -> str:
    """
    Generate timestamped backup filename.

    Returns:
        Backup filename with timestamp (e.g., kpi_platform_backup_20260109_020000.db.gz)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{BACKUP_PREFIX}_{timestamp}{BACKUP_EXTENSION}"


def create_backup(
    db_path: Path,
    backup_path: Path,
    logger: logging.Logger
) -> Tuple[bool, Optional[str]]:
    """
    Create compressed backup of SQLite database.

    Uses SQLite's backup API for a consistent snapshot, then compresses with gzip.

    Args:
        db_path: Path to source database
        backup_path: Path for compressed backup file
        logger: Logger instance

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    temp_backup = backup_path.with_suffix("")  # Remove .gz for temp file

    try:
        # Step 1: Create SQLite backup using backup API
        logger.info(f"Creating database backup from: {db_path}")

        # Connect to source database
        source_conn = sqlite3.connect(str(db_path))

        # Create backup connection
        backup_conn = sqlite3.connect(str(temp_backup))

        # Use SQLite backup API for consistent snapshot
        source_conn.backup(backup_conn)

        # Close connections
        backup_conn.close()
        source_conn.close()

        logger.debug(f"SQLite backup created: {temp_backup}")

        # Step 2: Compress with gzip
        logger.info("Compressing backup with gzip...")

        with open(temp_backup, "rb") as f_in:
            with gzip.open(backup_path, "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove uncompressed temp file
        temp_backup.unlink()

        # Get file sizes for logging
        original_size = db_path.stat().st_size
        compressed_size = backup_path.stat().st_size
        compression_ratio = (1 - compressed_size / original_size) * 100

        logger.info(
            f"Backup created: {backup_path.name} "
            f"(Original: {original_size:,} bytes, "
            f"Compressed: {compressed_size:,} bytes, "
            f"Ratio: {compression_ratio:.1f}% reduction)"
        )

        return True, None

    except Exception as e:
        error_msg = f"Backup creation failed: {str(e)}"
        logger.error(error_msg)

        # Clean up temp file if it exists
        if temp_backup.exists():
            temp_backup.unlink()

        return False, error_msg


def validate_backup(
    backup_path: Path,
    logger: logging.Logger
) -> Tuple[bool, Optional[str]]:
    """
    Validate backup integrity by checking gzip structure and SQLite header.

    Args:
        backup_path: Path to compressed backup file
        logger: Logger instance

    Returns:
        Tuple of (valid: bool, error_message: Optional[str])
    """
    try:
        logger.info(f"Validating backup: {backup_path.name}")

        # Decompress and check SQLite header
        with gzip.open(backup_path, "rb") as f:
            # Read SQLite header (first 16 bytes)
            header = f.read(16)

            # SQLite files start with "SQLite format 3\x00"
            if not header.startswith(b"SQLite format 3"):
                return False, "Invalid SQLite header in backup"

        logger.info("Backup validation successful")
        return True, None

    except gzip.BadGzipFile:
        error_msg = "Invalid gzip format"
        logger.error(f"Validation failed: {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Validation failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def get_existing_backups(backup_dir: Path) -> List[Path]:
    """
    Get list of existing backup files sorted by modification time (oldest first).

    Args:
        backup_dir: Backup directory path

    Returns:
        List of backup file paths sorted by age (oldest first)
    """
    pattern = f"{BACKUP_PREFIX}_*{BACKUP_EXTENSION}"
    backups = list(backup_dir.glob(pattern))

    # Sort by modification time (oldest first)
    backups.sort(key=lambda p: p.stat().st_mtime)

    return backups


def rotate_backups(
    backup_dir: Path,
    retention_count: int,
    logger: logging.Logger
) -> int:
    """
    Delete old backups, keeping only the most recent N backups.

    Args:
        backup_dir: Backup directory path
        retention_count: Number of backups to retain
        logger: Logger instance

    Returns:
        Number of backups deleted
    """
    backups = get_existing_backups(backup_dir)
    deleted_count = 0

    # Calculate how many to delete
    delete_count = len(backups) - retention_count

    if delete_count <= 0:
        logger.info(f"No rotation needed. {len(backups)} backups exist, retention is {retention_count}")
        return 0

    # Delete oldest backups
    for backup in backups[:delete_count]:
        try:
            backup.unlink()
            logger.info(f"Deleted old backup: {backup.name}")
            deleted_count += 1
        except Exception as e:
            logger.error(f"Failed to delete {backup.name}: {e}")

    logger.info(f"Rotation complete. Deleted {deleted_count} old backups")
    return deleted_count


def get_backup_summary(backup_dir: Path) -> dict:
    """
    Get summary of current backup state.

    Args:
        backup_dir: Backup directory path

    Returns:
        Dictionary with backup statistics
    """
    backups = get_existing_backups(backup_dir)

    if not backups:
        return {
            "count": 0,
            "total_size_bytes": 0,
            "oldest": None,
            "newest": None
        }

    total_size = sum(b.stat().st_size for b in backups)
    oldest = backups[0]
    newest = backups[-1]

    return {
        "count": len(backups),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "oldest": {
            "name": oldest.name,
            "date": datetime.fromtimestamp(oldest.stat().st_mtime).isoformat()
        },
        "newest": {
            "name": newest.name,
            "date": datetime.fromtimestamp(newest.stat().st_mtime).isoformat()
        }
    }


def run_backup(
    retention_days: int = DEFAULT_RETENTION_DAYS,
    backup_dir: Optional[str] = None
) -> Tuple[bool, dict]:
    """
    Run complete backup process: create, validate, rotate.

    Args:
        retention_days: Number of daily backups to keep
        backup_dir: Optional custom backup directory

    Returns:
        Tuple of (success: bool, result_dict: dict)
    """
    # Determine backup directory
    base_dir = Path(__file__).parent.parent
    if backup_dir:
        backup_path = Path(backup_dir)
    else:
        backup_path = base_dir / DEFAULT_BACKUP_DIR

    # Setup logging
    create_backup_directory(backup_path)
    logger = setup_logging(backup_path)

    logger.info("=" * 60)
    logger.info("Starting database backup process")
    logger.info("=" * 60)

    result = {
        "timestamp": datetime.now().isoformat(),
        "backup_dir": str(backup_path),
        "retention_days": retention_days,
        "success": False,
        "backup_file": None,
        "error": None,
        "deleted_backups": 0
    }

    try:
        # Get database path
        db_path = get_database_path()
        logger.info(f"Database path: {db_path}")

        # Generate backup filename
        backup_filename = generate_backup_filename()
        full_backup_path = backup_path / backup_filename

        # Create backup
        success, error = create_backup(db_path, full_backup_path, logger)
        if not success:
            result["error"] = error
            return False, result

        # Validate backup
        valid, error = validate_backup(full_backup_path, logger)
        if not valid:
            result["error"] = error
            # Delete invalid backup
            full_backup_path.unlink()
            return False, result

        result["backup_file"] = backup_filename

        # Rotate old backups
        deleted = rotate_backups(backup_path, retention_days, logger)
        result["deleted_backups"] = deleted

        # Get summary
        summary = get_backup_summary(backup_path)
        result["summary"] = summary

        result["success"] = True
        logger.info("Backup process completed successfully")
        logger.info(f"Current backups: {summary['count']}, Total size: {summary['total_size_mb']} MB")

        return True, result

    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(error_msg)
        result["error"] = error_msg
        return False, result

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        result["error"] = error_msg
        return False, result


def restore_backup(
    backup_path: Path,
    target_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> Tuple[bool, Optional[str]]:
    """
    Restore database from a backup file.

    Args:
        backup_path: Path to compressed backup file
        target_path: Optional target path (defaults to original database location)
        logger: Optional logger instance

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    if logger is None:
        logger = logging.getLogger("backup")

    try:
        # Determine target path
        if target_path is None:
            target_path = get_database_path()

        logger.info(f"Restoring backup: {backup_path} -> {target_path}")

        # Create backup of current database before restore
        if target_path.exists():
            restore_backup_path = target_path.with_suffix(".db.pre_restore")
            shutil.copy2(target_path, restore_backup_path)
            logger.info(f"Created pre-restore backup: {restore_backup_path}")

        # Decompress and restore
        with gzip.open(backup_path, "rb") as f_in:
            with open(target_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Validate restored database
        conn = sqlite3.connect(str(target_path))
        conn.execute("SELECT 1")  # Simple query to verify
        conn.close()

        logger.info("Restore completed successfully")
        return True, None

    except Exception as e:
        error_msg = f"Restore failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


if __name__ == "__main__":
    """
    Main entry point for command-line execution.

    Exit codes:
        0: Success
        1: Failure
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Automated SQLite Database Backup Script"
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Number of backups to keep (default: {DEFAULT_RETENTION_DAYS})"
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=None,
        help=f"Backup directory (default: {DEFAULT_BACKUP_DIR})"
    )
    parser.add_argument(
        "--restore",
        type=str,
        default=None,
        help="Path to backup file to restore"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing backups"
    )

    args = parser.parse_args()

    # Determine backup directory
    base_dir = Path(__file__).parent.parent
    backup_dir = Path(args.backup_dir) if args.backup_dir else base_dir / DEFAULT_BACKUP_DIR

    if args.list:
        # List existing backups
        create_backup_directory(backup_dir)
        backups = get_existing_backups(backup_dir)

        if not backups:
            print("No backups found")
        else:
            print(f"\nExisting backups in {backup_dir}:")
            print("-" * 70)
            for b in backups:
                size_mb = b.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(b.stat().st_mtime)
                print(f"  {b.name} ({size_mb:.2f} MB) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

            summary = get_backup_summary(backup_dir)
            print("-" * 70)
            print(f"Total: {summary['count']} backups, {summary['total_size_mb']} MB")

        sys.exit(0)

    if args.restore:
        # Restore from backup
        restore_path = Path(args.restore)
        if not restore_path.exists():
            print(f"Error: Backup file not found: {restore_path}")
            sys.exit(1)

        create_backup_directory(backup_dir)
        logger = setup_logging(backup_dir)

        success, error = restore_backup(restore_path, logger=logger)
        if success:
            print("Database restored successfully")
            sys.exit(0)
        else:
            print(f"Restore failed: {error}")
            sys.exit(1)

    # Run backup
    success, result = run_backup(
        retention_days=args.retention,
        backup_dir=args.backup_dir
    )

    if success:
        print(f"\nBackup successful: {result['backup_file']}")
        if result.get("summary"):
            print(f"Total backups: {result['summary']['count']}")
        sys.exit(0)
    else:
        print(f"\nBackup failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
