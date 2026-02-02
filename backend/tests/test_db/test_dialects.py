"""
Unit Tests for Dialect Adapters

Tests for SQLiteDialect, MariaDBDialect, and MySQLDialect.
"""
import pytest

from backend.db.dialects.base import DialectAdapter
from backend.db.dialects.sqlite import SQLiteDialect
from backend.db.dialects.mariadb import MariaDBDialect
from backend.db.dialects.mysql import MySQLDialect


class TestSQLiteDialect:
    """Tests for SQLiteDialect."""

    def test_dialect_name(self):
        """Test dialect name is 'sqlite'."""
        dialect = SQLiteDialect()
        assert dialect.dialect_name == "sqlite"

    def test_get_last_insert_id(self):
        """Test last insert ID SQL."""
        dialect = SQLiteDialect()
        sql = dialect.get_last_insert_id("users", "id")
        assert "last_insert_rowid" in sql

    def test_get_boolean_literal_true(self):
        """Test boolean literal for True."""
        dialect = SQLiteDialect()
        assert dialect.get_boolean_literal(True) == "1"

    def test_get_boolean_literal_false(self):
        """Test boolean literal for False."""
        dialect = SQLiteDialect()
        assert dialect.get_boolean_literal(False) == "0"

    def test_supports_returning(self):
        """Test RETURNING support (SQLite 3.35+)."""
        dialect = SQLiteDialect()
        assert dialect.supports_returning() is True

    def test_get_placeholder(self):
        """Test placeholder is '?'."""
        dialect = SQLiteDialect()
        assert dialect.get_placeholder() == "?"

    def test_get_auto_increment_def(self):
        """Test auto-increment definition."""
        dialect = SQLiteDialect()
        sql = dialect.get_auto_increment_def()
        assert "AUTOINCREMENT" in sql
        assert "PRIMARY KEY" in sql

    def test_get_upsert_sql(self):
        """Test upsert SQL generation."""
        dialect = SQLiteDialect()
        sql = dialect.get_upsert_sql(
            "users",
            ["id", "name", "email"],
            ["id"]
        )

        assert "INSERT INTO users" in sql
        assert "ON CONFLICT (id)" in sql
        assert "DO UPDATE SET" in sql
        assert "name = excluded.name" in sql
        assert "email = excluded.email" in sql

    def test_get_upsert_sql_with_do_nothing(self):
        """Test upsert SQL when all columns are conflict columns."""
        dialect = SQLiteDialect()
        sql = dialect.get_upsert_sql(
            "users",
            ["id"],
            ["id"]
        )

        assert "ON CONFLICT (id) DO NOTHING" in sql

    def test_get_upsert_sql_custom_update_columns(self):
        """Test upsert with custom update columns."""
        dialect = SQLiteDialect()
        sql = dialect.get_upsert_sql(
            "users",
            ["id", "name", "email", "updated_at"],
            ["id"],
            update_columns=["name", "updated_at"]
        )

        assert "name = excluded.name" in sql
        assert "updated_at = excluded.updated_at" in sql
        assert "email = excluded.email" not in sql

    def test_get_date_diff_sql_day(self):
        """Test date diff for days."""
        dialect = SQLiteDialect()
        sql = dialect.get_date_diff_sql("date1", "date2", "day")
        assert "julianday(date1)" in sql
        assert "julianday(date2)" in sql

    def test_get_date_diff_sql_hour(self):
        """Test date diff for hours."""
        dialect = SQLiteDialect()
        sql = dialect.get_date_diff_sql("date1", "date2", "hour")
        assert "* 24" in sql

    def test_quote_identifier(self):
        """Test identifier quoting with double quotes."""
        dialect = SQLiteDialect()
        assert dialect.quote_identifier("table") == '"table"'

    def test_get_concat_sql(self):
        """Test concatenation with || operator."""
        dialect = SQLiteDialect()
        sql = dialect.get_concat_sql("a", "b", "c")
        assert sql == "a || b || c"


class TestMariaDBDialect:
    """Tests for MariaDBDialect."""

    def test_dialect_name(self):
        """Test dialect name is 'mariadb'."""
        dialect = MariaDBDialect()
        assert dialect.dialect_name == "mariadb"

    def test_get_last_insert_id(self):
        """Test last insert ID SQL."""
        dialect = MariaDBDialect()
        sql = dialect.get_last_insert_id("users", "id")
        assert "LAST_INSERT_ID" in sql

    def test_get_boolean_literal_true(self):
        """Test boolean literal for True."""
        dialect = MariaDBDialect()
        assert dialect.get_boolean_literal(True) == "TRUE"

    def test_get_boolean_literal_false(self):
        """Test boolean literal for False."""
        dialect = MariaDBDialect()
        assert dialect.get_boolean_literal(False) == "FALSE"

    def test_supports_returning(self):
        """Test RETURNING support (MariaDB 10.5+)."""
        dialect = MariaDBDialect()
        assert dialect.supports_returning() is True

    def test_get_placeholder(self):
        """Test placeholder is '%s'."""
        dialect = MariaDBDialect()
        assert dialect.get_placeholder() == "%s"

    def test_get_auto_increment_def(self):
        """Test auto-increment definition."""
        dialect = MariaDBDialect()
        sql = dialect.get_auto_increment_def()
        assert "AUTO_INCREMENT" in sql
        assert "PRIMARY KEY" in sql

    def test_get_upsert_sql(self):
        """Test upsert SQL generation."""
        dialect = MariaDBDialect()
        sql = dialect.get_upsert_sql(
            "users",
            ["id", "name", "email"],
            ["id"]
        )

        assert "INSERT INTO users" in sql
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "name = VALUES(name)" in sql
        assert "email = VALUES(email)" in sql

    def test_get_upsert_sql_insert_ignore(self):
        """Test upsert with INSERT IGNORE when no update columns."""
        dialect = MariaDBDialect()
        sql = dialect.get_upsert_sql(
            "users",
            ["id"],
            ["id"]
        )

        assert "INSERT IGNORE INTO users" in sql

    def test_quote_identifier(self):
        """Test identifier quoting with backticks."""
        dialect = MariaDBDialect()
        assert dialect.quote_identifier("table") == "`table`"

    def test_get_concat_sql(self):
        """Test concatenation with CONCAT()."""
        dialect = MariaDBDialect()
        sql = dialect.get_concat_sql("a", "b", "c")
        assert sql == "CONCAT(a, b, c)"

    def test_get_date_diff_sql(self):
        """Test date diff with TIMESTAMPDIFF."""
        dialect = MariaDBDialect()
        sql = dialect.get_date_diff_sql("date1", "date2", "day")
        assert "TIMESTAMPDIFF(DAY" in sql

    def test_get_ifnull_sql(self):
        """Test IFNULL expression."""
        dialect = MariaDBDialect()
        sql = dialect.get_ifnull_sql("column", "'default'")
        assert sql == "IFNULL(column, 'default')"


class TestMySQLDialect:
    """Tests for MySQLDialect."""

    def test_dialect_name(self):
        """Test dialect name is 'mysql'."""
        dialect = MySQLDialect()
        assert dialect.dialect_name == "mysql"

    def test_get_last_insert_id(self):
        """Test last insert ID SQL."""
        dialect = MySQLDialect()
        sql = dialect.get_last_insert_id("users", "id")
        assert "LAST_INSERT_ID" in sql

    def test_get_boolean_literal(self):
        """Test boolean literals."""
        dialect = MySQLDialect()
        assert dialect.get_boolean_literal(True) == "TRUE"
        assert dialect.get_boolean_literal(False) == "FALSE"

    def test_supports_returning(self):
        """Test RETURNING support (False for broad MySQL compat)."""
        dialect = MySQLDialect()
        # MySQL 8.0.21+ has limited support, but we default to False
        assert dialect.supports_returning() is False

    def test_get_placeholder(self):
        """Test placeholder is '%s'."""
        dialect = MySQLDialect()
        assert dialect.get_placeholder() == "%s"

    def test_get_upsert_sql(self):
        """Test upsert SQL generation."""
        dialect = MySQLDialect()
        sql = dialect.get_upsert_sql(
            "users",
            ["id", "name"],
            ["id"]
        )

        assert "INSERT INTO users" in sql
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "name = VALUES(name)" in sql

    def test_quote_identifier(self):
        """Test identifier quoting with backticks."""
        dialect = MySQLDialect()
        assert dialect.quote_identifier("table") == "`table`"


class TestDialectAdapterInterface:
    """Test all dialects implement the interface correctly."""

    @pytest.fixture(params=[SQLiteDialect, MariaDBDialect, MySQLDialect])
    def dialect(self, request):
        """Provide each dialect for testing."""
        return request.param()

    def test_has_dialect_name(self, dialect):
        """Test dialect has name."""
        assert isinstance(dialect.dialect_name, str)
        assert len(dialect.dialect_name) > 0

    def test_has_last_insert_id(self, dialect):
        """Test dialect has last_insert_id method."""
        sql = dialect.get_last_insert_id("table", "col")
        assert isinstance(sql, str)

    def test_has_boolean_literal(self, dialect):
        """Test dialect has boolean_literal method."""
        assert isinstance(dialect.get_boolean_literal(True), str)
        assert isinstance(dialect.get_boolean_literal(False), str)

    def test_has_auto_increment_def(self, dialect):
        """Test dialect has auto_increment_def method."""
        sql = dialect.get_auto_increment_def()
        assert isinstance(sql, str)

    def test_has_upsert_sql(self, dialect):
        """Test dialect has upsert_sql method."""
        sql = dialect.get_upsert_sql("t", ["a", "b"], ["a"])
        assert isinstance(sql, str)

    def test_has_placeholder(self, dialect):
        """Test dialect has placeholder method."""
        placeholder = dialect.get_placeholder()
        assert placeholder in ("?", "%s")

    def test_has_supports_returning(self, dialect):
        """Test dialect has supports_returning method."""
        assert isinstance(dialect.supports_returning(), bool)

    def test_has_quote_identifier(self, dialect):
        """Test dialect has quote_identifier method."""
        quoted = dialect.quote_identifier("test")
        assert isinstance(quoted, str)
        assert "test" in quoted
