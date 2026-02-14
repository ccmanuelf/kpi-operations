"""
Abstract Base Dialect Adapter

Defines the interface for handling SQL dialect differences between databases.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional


class DialectAdapter(ABC):
    """Abstract base for SQL dialect differences.

    Provides a consistent interface for generating SQL that works
    across different database backends.
    """

    @property
    @abstractmethod
    def dialect_name(self) -> str:
        """Return dialect identifier.

        Returns:
            str: Dialect name (sqlite, mariadb, mysql, postgresql).
        """
        pass

    @abstractmethod
    def get_last_insert_id(self, table: str, column: str) -> str:
        """Return SQL to get last inserted ID.

        Args:
            table: Table name (may be ignored by some dialects).
            column: Column name (may be ignored by some dialects).

        Returns:
            str: SQL statement to retrieve last insert ID.
        """
        pass

    @abstractmethod
    def get_upsert_sql(
        self, table: str, columns: List[str], conflict_columns: List[str], update_columns: Optional[List[str]] = None
    ) -> str:
        """Return upsert (INSERT ... ON CONFLICT) SQL.

        Args:
            table: Target table name.
            columns: All columns to insert.
            conflict_columns: Columns that define uniqueness.
            update_columns: Columns to update on conflict (default: non-conflict columns).

        Returns:
            str: Upsert SQL statement with placeholders.
        """
        pass

    @abstractmethod
    def get_boolean_literal(self, value: bool) -> str:
        """Return boolean literal for this dialect.

        Args:
            value: Boolean value.

        Returns:
            str: SQL literal representation.
        """
        pass

    @abstractmethod
    def get_auto_increment_def(self) -> str:
        """Return auto-increment column definition.

        Returns:
            str: SQL fragment for auto-increment primary key.
        """
        pass

    @abstractmethod
    def supports_returning(self) -> bool:
        """Whether RETURNING clause is supported.

        Returns:
            bool: True if RETURNING is supported.
        """
        pass

    @abstractmethod
    def get_placeholder(self) -> str:
        """Return parameter placeholder style.

        Returns:
            str: Placeholder character ('?' for SQLite, '%s' for MySQL).
        """
        pass

    def get_current_timestamp(self) -> str:
        """Return SQL for current timestamp.

        Returns:
            str: SQL function for current timestamp.
        """
        return "CURRENT_TIMESTAMP"

    def get_date_diff_sql(self, date1: str, date2: str, unit: str = "day") -> str:
        """Return SQL for date difference.

        Default implementation for most dialects.

        Args:
            date1: First date expression.
            date2: Second date expression.
            unit: Time unit (day, hour, minute, second).

        Returns:
            str: SQL expression for date difference.
        """
        return f"TIMESTAMPDIFF({unit.upper()}, {date2}, {date1})"

    def quote_identifier(self, identifier: str) -> str:
        """Quote an identifier (table/column name).

        Args:
            identifier: Identifier to quote.

        Returns:
            str: Quoted identifier.
        """
        return f'"{identifier}"'

    def get_concat_sql(self, *args: str) -> str:
        """Return SQL for string concatenation.

        Args:
            *args: String expressions to concatenate.

        Returns:
            str: SQL expression for concatenation.
        """
        return f"CONCAT({', '.join(args)})"
