"""
MySQL Dialect Adapter

Handles MySQL-specific SQL syntax and features.
Very similar to MariaDB with minor differences.
"""

from typing import List, Optional

from backend.db.dialects.base import DialectAdapter


class MySQLDialect(DialectAdapter):
    """MySQL dialect adapter.

    Handles MySQL-specific SQL syntax. Very similar to MariaDB,
    but with some differences in features and syntax.

    Note: MySQL 8.0+ supports RETURNING-like functionality via
    last_insert_id() after INSERT.
    """

    @property
    def dialect_name(self) -> str:
        """Return dialect identifier."""
        return "mysql"

    def get_last_insert_id(self, table: str, column: str) -> str:
        """Return SQL to get last inserted ID.

        MySQL uses LAST_INSERT_ID() function.

        Args:
            table: Table name (ignored in MySQL).
            column: Column name (ignored in MySQL).

        Returns:
            str: SQL statement.
        """
        return "SELECT LAST_INSERT_ID()"

    def get_upsert_sql(
        self, table: str, columns: List[str], conflict_columns: List[str], update_columns: Optional[List[str]] = None
    ) -> str:
        """Return MySQL upsert SQL using ON DUPLICATE KEY UPDATE.

        Args:
            table: Target table name.
            columns: All columns to insert.
            conflict_columns: Columns that define uniqueness.
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

        # MySQL 8.0.19+ uses alias syntax, but VALUES() still works
        updates = ", ".join([f"{c} = VALUES({c})" for c in update_columns])
        return f"""
            INSERT INTO {table} ({cols})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {updates}
        """.strip()

    def get_boolean_literal(self, value: bool) -> str:
        """Return boolean literal.

        MySQL supports TRUE/FALSE keywords.

        Args:
            value: Boolean value.

        Returns:
            str: 'TRUE' or 'FALSE'.
        """
        return "TRUE" if value else "FALSE"

    def get_auto_increment_def(self) -> str:
        """Return MySQL auto-increment definition.

        Returns:
            str: MySQL AUTO_INCREMENT syntax.
        """
        return "INT UNSIGNED AUTO_INCREMENT PRIMARY KEY"

    def supports_returning(self) -> bool:
        """MySQL 8.0.21+ has limited RETURNING support.

        For broad compatibility, we assume RETURNING is not available.

        Returns:
            bool: False for broad MySQL compatibility.
        """
        # MySQL 8.0.21+ supports RETURNING for some operations
        # but for compatibility we default to False
        return False

    def get_placeholder(self) -> str:
        """Return MySQL placeholder style.

        Returns:
            str: '%s' for MySQL.
        """
        return "%s"

    def get_date_diff_sql(self, date1: str, date2: str, unit: str = "day") -> str:
        """Return MySQL date difference SQL.

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

        MySQL uses backticks for identifier quoting.

        Args:
            identifier: Identifier to quote.

        Returns:
            str: Quoted identifier.
        """
        return f"`{identifier}`"

    def get_concat_sql(self, *args: str) -> str:
        """Return MySQL string concatenation.

        MySQL uses CONCAT() function.

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
