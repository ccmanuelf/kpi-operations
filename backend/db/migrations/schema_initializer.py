"""
Schema Initializer

Creates database schema on target database from SQLAlchemy models.
Used during migration to set up tables on the new database.
"""
from typing import Callable, Optional, List
import logging

from sqlalchemy import MetaData, Engine, text, inspect

logger = logging.getLogger(__name__)


class SchemaInitializer:
    """Initialize schema on target database from SQLAlchemy models.

    This class handles creating all tables defined in SQLAlchemy models
    on a target database, with provider-specific optimizations.
    """

    def __init__(self, target_engine: Engine, target_provider: str):
        """Initialize schema initializer.

        Args:
            target_engine: SQLAlchemy engine for target database.
            target_provider: Provider name ('mariadb', 'mysql', etc.).
        """
        self.engine = target_engine
        self.provider = target_provider

    def create_all_tables(
        self,
        base_metadata: MetaData,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[str]:
        """Create all tables from SQLAlchemy Base.metadata.

        Uses SQLAlchemy's built-in create_all with provider-specific
        table options for MariaDB/MySQL.

        Args:
            base_metadata: SQLAlchemy MetaData object (usually Base.metadata).
            progress_callback: Optional callback(table_name, current, total).

        Returns:
            List[str]: Names of tables created.
        """
        tables = list(base_metadata.tables.values())
        total = len(tables)

        # Apply provider-specific table options
        if self.provider in ("mariadb", "mysql"):
            for table in tables:
                # Ensure InnoDB engine and utf8mb4 charset
                table.kwargs.setdefault('mysql_engine', 'InnoDB')
                table.kwargs.setdefault('mysql_charset', 'utf8mb4')
                table.kwargs.setdefault('mysql_collate', 'utf8mb4_unicode_ci')

        logger.info(f"Creating {total} tables on {self.provider}")

        # Create tables
        created_tables = []
        for idx, table in enumerate(tables, 1):
            table_name = table.name
            if progress_callback:
                progress_callback(table_name, idx, total)

            try:
                table.create(bind=self.engine, checkfirst=True)
                created_tables.append(table_name)
                logger.debug(f"Created table: {table_name}")
            except Exception as e:
                logger.error(f"Failed to create table {table_name}: {e}")
                raise

        logger.info(f"Successfully created {len(created_tables)} tables")
        return created_tables

    def drop_all_tables(
        self,
        base_metadata: MetaData,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[str]:
        """Drop all tables (for fresh start).

        Warning: This is destructive and should only be used during migration.

        Args:
            base_metadata: SQLAlchemy MetaData object.
            progress_callback: Optional callback(table_name, current, total).

        Returns:
            List[str]: Names of tables dropped.
        """
        tables = list(reversed(base_metadata.sorted_tables))
        total = len(tables)

        logger.warning(f"Dropping {total} tables on {self.provider}")

        dropped_tables = []
        for idx, table in enumerate(tables, 1):
            table_name = table.name
            if progress_callback:
                progress_callback(table_name, idx, total)

            try:
                table.drop(bind=self.engine, checkfirst=True)
                dropped_tables.append(table_name)
                logger.debug(f"Dropped table: {table_name}")
            except Exception as e:
                logger.warning(f"Failed to drop table {table_name}: {e}")

        logger.info(f"Dropped {len(dropped_tables)} tables")
        return dropped_tables

    def get_existing_tables(self) -> List[str]:
        """Get list of existing tables in the database.

        Returns:
            List[str]: Names of existing tables.
        """
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def verify_schema(self, base_metadata: MetaData) -> dict:
        """Verify schema matches expected structure.

        Args:
            base_metadata: Expected SQLAlchemy MetaData.

        Returns:
            dict: Verification result with missing/extra tables.
        """
        expected_tables = set(base_metadata.tables.keys())
        existing_tables = set(self.get_existing_tables())

        missing = expected_tables - existing_tables
        extra = existing_tables - expected_tables

        return {
            "valid": len(missing) == 0,
            "expected_count": len(expected_tables),
            "existing_count": len(existing_tables),
            "missing_tables": list(missing),
            "extra_tables": list(extra),
        }

    def create_database_if_not_exists(self, database_name: str) -> bool:
        """Create database if it doesn't exist (MySQL/MariaDB only).

        Args:
            database_name: Name of database to create.

        Returns:
            bool: True if database was created or already exists.
        """
        if self.provider not in ("mariadb", "mysql"):
            logger.info("Database creation only supported for MySQL/MariaDB")
            return False

        try:
            # Use raw connection without database selection
            with self.engine.connect() as conn:
                conn.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
                conn.commit()
            logger.info(f"Database '{database_name}' ready")
            return True
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False
