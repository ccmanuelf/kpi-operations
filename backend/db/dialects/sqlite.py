"""
SQLite Dialect Adapter

Handles SQLite-specific SQL syntax and features.
"""
from typing import List, Optional

from backend.db.dialects.base import DialectAdapter


class SQLiteDialect(DialectAdapter):
    """SQLite dialect adapter.

    Handles SQLite-specific SQL syntax including:
    - last_insert_rowid() for auto-increment values
    - INSERT OR REPLACE for upserts
    - Integer booleans (0/1)
    - AUTOINCREMENT syntax
    """

    @property
    def dialect_name(self) -> str:
        """Return dialect identifier."""
        return "sqlite"

    def get_last_insert_id(self, table: str, column: str) -> str:
        """Return SQL to get last inserted ID.

        SQLite uses last_insert_rowid() function.

        Args:
            table: Table name (ignored in SQLite).
            column: Column name (ignored in SQLite).

        Returns:
            str: SQL statement.
        """
        return "SELECT last_insert_rowid()"

    def get_upsert_sql(
        self,
        table: str,
        columns: List[str],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None
    ) -> str:
        """Return SQLite upsert SQL using ON CONFLICT.

        SQLite 3.24+ supports INSERT ... ON CONFLICT DO UPDATE.

        Args:
            table: Target table name.
            columns: All columns to insert.
            conflict_columns: Columns that define uniqueness.
            update_columns: Columns to update on conflict.

        Returns:
            str: Upsert SQL statement.
        """
        cols = ", ".join(columns)
        placeholders = ", ".join(["?" for _ in columns])
        conflict = ", ".join(conflict_columns)

        # Determine columns to update
        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]

        if not update_columns:
            # No columns to update, just ignore conflicts
            return f"""
                INSERT INTO {table} ({cols})
                VALUES ({placeholders})
                ON CONFLICT ({conflict}) DO NOTHING
            """.strip()

        updates = ", ".join([f"{c} = excluded.{c}" for c in update_columns])
        return f"""
            INSERT INTO {table} ({cols})
            VALUES ({placeholders})
            ON CONFLICT ({conflict}) DO UPDATE SET {updates}
        """.strip()

    def get_boolean_literal(self, value: bool) -> str:
        """Return boolean literal.

        SQLite uses 1/0 for booleans.

        Args:
            value: Boolean value.

        Returns:
            str: '1' or '0'.
        """
        return "1" if value else "0"

    def get_auto_increment_def(self) -> str:
        """Return SQLite auto-increment definition.

        Returns:
            str: SQLite AUTOINCREMENT syntax.
        """
        return "INTEGER PRIMARY KEY AUTOINCREMENT"

    def supports_returning(self) -> bool:
        """SQLite 3.35+ supports RETURNING.

        Returns:
            bool: True (assuming SQLite 3.35+).
        """
        return True

    def get_placeholder(self) -> str:
        """Return SQLite placeholder style.

        Returns:
            str: '?' for SQLite.
        """
        return "?"

    def get_date_diff_sql(
        self,
        date1: str,
        date2: str,
        unit: str = "day"
    ) -> str:
        """Return SQLite date difference SQL.

        SQLite uses julianday() for date calculations.

        Args:
            date1: First date expression.
            date2: Second date expression.
            unit: Time unit.

        Returns:
            str: SQL expression.
        """
        if unit.lower() == "day":
            return f"CAST((julianday({date1}) - julianday({date2})) AS INTEGER)"
        elif unit.lower() == "hour":
            return f"CAST((julianday({date1}) - julianday({date2})) * 24 AS INTEGER)"
        elif unit.lower() == "minute":
            return f"CAST((julianday({date1}) - julianday({date2})) * 24 * 60 AS INTEGER)"
        elif unit.lower() == "second":
            return f"CAST((julianday({date1}) - julianday({date2})) * 24 * 60 * 60 AS INTEGER)"
        return f"CAST((julianday({date1}) - julianday({date2})) AS INTEGER)"

    def quote_identifier(self, identifier: str) -> str:
        """Quote identifier using double quotes.

        Args:
            identifier: Identifier to quote.

        Returns:
            str: Quoted identifier.
        """
        return f'"{identifier}"'

    def get_concat_sql(self, *args: str) -> str:
        """Return SQLite string concatenation.

        SQLite uses || operator for concatenation.

        Args:
            *args: String expressions.

        Returns:
            str: SQL expression.
        """
        return " || ".join(args)
