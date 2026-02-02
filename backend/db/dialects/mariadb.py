"""
MariaDB Dialect Adapter

Handles MariaDB-specific SQL syntax and features.
"""
from typing import List, Optional

from backend.db.dialects.base import DialectAdapter


class MariaDBDialect(DialectAdapter):
    """MariaDB dialect adapter.

    Handles MariaDB-specific SQL syntax including:
    - LAST_INSERT_ID() for auto-increment values
    - INSERT ... ON DUPLICATE KEY UPDATE for upserts
    - TRUE/FALSE boolean literals
    - AUTO_INCREMENT syntax
    - RETURNING clause (MariaDB 10.5+)
    """

    @property
    def dialect_name(self) -> str:
        """Return dialect identifier."""
        return "mariadb"

    def get_last_insert_id(self, table: str, column: str) -> str:
        """Return SQL to get last inserted ID.

        MariaDB uses LAST_INSERT_ID() function.

        Args:
            table: Table name (ignored in MariaDB).
            column: Column name (ignored in MariaDB).

        Returns:
            str: SQL statement.
        """
        return "SELECT LAST_INSERT_ID()"

    def get_upsert_sql(
        self,
        table: str,
        columns: List[str],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None
    ) -> str:
        """Return MariaDB upsert SQL using ON DUPLICATE KEY UPDATE.

        Args:
            table: Target table name.
            columns: All columns to insert.
            conflict_columns: Columns that define uniqueness (used for reference).
            update_columns: Columns to update on conflict.

        Returns:
            str: Upsert SQL statement.
        """
        cols = ", ".join(columns)
        placeholders = ", ".join(["%s" for _ in columns])

        # Determine columns to update
        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]

        if not update_columns:
            # No updates needed, use INSERT IGNORE
            return f"""
                INSERT IGNORE INTO {table} ({cols})
                VALUES ({placeholders})
            """.strip()

        # Use VALUES() function to reference the new values
        updates = ", ".join([f"{c} = VALUES({c})" for c in update_columns])
        return f"""
            INSERT INTO {table} ({cols})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {updates}
        """.strip()

    def get_boolean_literal(self, value: bool) -> str:
        """Return boolean literal.

        MariaDB supports TRUE/FALSE keywords.

        Args:
            value: Boolean value.

        Returns:
            str: 'TRUE' or 'FALSE'.
        """
        return "TRUE" if value else "FALSE"

    def get_auto_increment_def(self) -> str:
        """Return MariaDB auto-increment definition.

        Returns:
            str: MariaDB AUTO_INCREMENT syntax.
        """
        return "INT UNSIGNED AUTO_INCREMENT PRIMARY KEY"

    def supports_returning(self) -> bool:
        """MariaDB 10.5+ supports RETURNING.

        Returns:
            bool: True (assuming MariaDB 10.5+).
        """
        return True

    def get_placeholder(self) -> str:
        """Return MariaDB placeholder style.

        Returns:
            str: '%s' for MariaDB/MySQL.
        """
        return "%s"

    def get_date_diff_sql(
        self,
        date1: str,
        date2: str,
        unit: str = "day"
    ) -> str:
        """Return MariaDB date difference SQL.

        Uses TIMESTAMPDIFF function.

        Args:
            date1: First date expression.
            date2: Second date expression.
            unit: Time unit.

        Returns:
            str: SQL expression.
        """
        return f"TIMESTAMPDIFF({unit.upper()}, {date2}, {date1})"

    def quote_identifier(self, identifier: str) -> str:
        """Quote identifier using backticks.

        MariaDB/MySQL use backticks for identifier quoting.

        Args:
            identifier: Identifier to quote.

        Returns:
            str: Quoted identifier.
        """
        return f"`{identifier}`"

    def get_concat_sql(self, *args: str) -> str:
        """Return MariaDB string concatenation.

        MariaDB uses CONCAT() function.

        Args:
            *args: String expressions.

        Returns:
            str: SQL expression.
        """
        return f"CONCAT({', '.join(args)})"

    def get_ifnull_sql(self, expr: str, default: str) -> str:
        """Return IFNULL expression.

        Args:
            expr: Expression that might be NULL.
            default: Default value if NULL.

        Returns:
            str: SQL expression.
        """
        return f"IFNULL({expr}, {default})"
