"""
Comprehensive Tests for Soft Delete Utility Module.

Note: The soft_delete utility module operates on generic entity objects via
hasattr/getattr patterns, not through real CRUD queries. Mocks are appropriate
here because we are testing the utility's branching logic (boolean vs integer
is_active, commit/rollback, missing fields, etc.), not real DB queries.

Real DB tests for soft delete *behavior* in CRUD operations are covered in the
individual CRUD test files (e.g., test_crud_integration.py delete tests).
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session


class TestSoftDelete:
    """Test the soft_delete function"""

    def test_soft_delete_with_boolean_field(self):
        """Test soft delete with boolean is_active field"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = True

        result = soft_delete(mock_db, mock_entity, commit=False)

        assert result is True
        assert mock_entity.is_active == False

    def test_soft_delete_with_integer_field(self):
        """Test soft delete with integer is_active field (SQLite style)"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = 1

        result = soft_delete(mock_db, mock_entity, commit=False)

        assert result is True
        assert mock_entity.is_active == 0

    def test_soft_delete_with_commit(self):
        """Test soft delete with commit=True"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = True

        result = soft_delete(mock_db, mock_entity, commit=True)

        assert result is True
        mock_db.commit.assert_called_once()

    def test_soft_delete_without_is_active_field(self):
        """Test soft delete on entity without is_active field"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock(spec=[])  # Empty spec means no attributes

        result = soft_delete(mock_db, mock_entity, commit=False)

        assert result is False

    def test_soft_delete_custom_field_name(self):
        """Test soft delete with custom is_active field name"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.active = True

        result = soft_delete(mock_db, mock_entity, is_active_field="active", commit=False)

        assert result is True
        assert mock_entity.active == False

    def test_soft_delete_explicit_inactive_value(self):
        """Test soft delete with explicit inactive_value=0"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = True

        result = soft_delete(mock_db, mock_entity, inactive_value=0, commit=False)

        assert result is True
        assert mock_entity.is_active == 0

    def test_soft_delete_exception_with_rollback(self):
        """Test soft delete handles exception and rollback"""
        from backend.utils.soft_delete import soft_delete

        mock_db = MagicMock(spec=Session)
        mock_db.commit.side_effect = Exception("Database error")
        mock_entity = MagicMock()
        mock_entity.is_active = True

        result = soft_delete(mock_db, mock_entity, commit=True)

        assert result is False
        mock_db.rollback.assert_called_once()


class TestSoftDeleteWithTimestamp:
    """Test the soft_delete_with_timestamp function"""

    def test_soft_delete_with_timestamp_basic(self):
        """Test soft delete with timestamp sets deleted_at"""
        from backend.utils.soft_delete import soft_delete_with_timestamp

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = True
        mock_entity.deleted_at = None
        mock_entity.deleted_by = None

        result = soft_delete_with_timestamp(mock_db, mock_entity, commit=False)

        assert result is True
        assert mock_entity.is_active == False
        assert mock_entity.deleted_at is not None

    def test_soft_delete_with_timestamp_and_user(self):
        """Test soft delete with timestamp and deleted_by user"""
        from backend.utils.soft_delete import soft_delete_with_timestamp

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = True
        mock_entity.deleted_at = None
        mock_entity.deleted_by = None

        result = soft_delete_with_timestamp(mock_db, mock_entity, deleted_by_value=123, commit=False)

        assert result is True
        assert mock_entity.deleted_by == 123

    def test_soft_delete_with_timestamp_no_deleted_at_field(self):
        """Test soft delete with timestamp when entity has no deleted_at field"""
        from backend.utils.soft_delete import soft_delete_with_timestamp

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock(spec=["is_active"])
        mock_entity.is_active = True

        result = soft_delete_with_timestamp(mock_db, mock_entity, commit=False)

        assert result is True

    def test_soft_delete_with_timestamp_commit(self):
        """Test soft delete with timestamp commits transaction"""
        from backend.utils.soft_delete import soft_delete_with_timestamp

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = True
        mock_entity.deleted_at = None

        result = soft_delete_with_timestamp(mock_db, mock_entity, commit=True)

        assert result is True
        mock_db.commit.assert_called()

    def test_soft_delete_with_timestamp_exception(self):
        """Test soft delete with timestamp handles exceptions"""
        from backend.utils.soft_delete import soft_delete_with_timestamp

        mock_db = MagicMock(spec=Session)
        mock_db.commit.side_effect = Exception("Commit failed")
        mock_entity = MagicMock()
        mock_entity.is_active = True
        mock_entity.deleted_at = None

        result = soft_delete_with_timestamp(mock_db, mock_entity, commit=True)

        assert result is False
        mock_db.rollback.assert_called_once()

    def test_soft_delete_with_timestamp_no_is_active(self):
        """Test soft delete with timestamp fails when no is_active field"""
        from backend.utils.soft_delete import soft_delete_with_timestamp

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock(spec=["deleted_at"])  # No is_active

        result = soft_delete_with_timestamp(mock_db, mock_entity, commit=False)

        assert result is False


class TestRestoreSoftDeleted:
    """Test the restore_soft_deleted function"""

    def test_restore_soft_deleted_boolean(self):
        """Test restore with boolean is_active field"""
        from backend.utils.soft_delete import restore_soft_deleted

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = False
        mock_entity.deleted_at = datetime.utcnow()
        mock_entity.deleted_by = 123

        result = restore_soft_deleted(mock_db, mock_entity, commit=False)

        assert result is True
        assert mock_entity.is_active == True
        assert mock_entity.deleted_at is None
        assert mock_entity.deleted_by is None

    def test_restore_soft_deleted_integer(self):
        """Test restore with integer is_active field"""
        from backend.utils.soft_delete import restore_soft_deleted

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = 0

        result = restore_soft_deleted(mock_db, mock_entity, commit=False)

        assert result is True
        assert mock_entity.is_active == 1

    def test_restore_soft_deleted_with_active_value(self):
        """Test restore with explicit active_value=1"""
        from backend.utils.soft_delete import restore_soft_deleted

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = False

        result = restore_soft_deleted(mock_db, mock_entity, active_value=1, commit=False)

        assert result is True
        assert mock_entity.is_active == 1

    def test_restore_soft_deleted_no_is_active(self):
        """Test restore fails when no is_active field"""
        from backend.utils.soft_delete import restore_soft_deleted

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock(spec=[])

        result = restore_soft_deleted(mock_db, mock_entity, commit=False)

        assert result is False

    def test_restore_soft_deleted_with_commit(self):
        """Test restore commits transaction"""
        from backend.utils.soft_delete import restore_soft_deleted

        mock_db = MagicMock(spec=Session)
        mock_entity = MagicMock()
        mock_entity.is_active = False

        result = restore_soft_deleted(mock_db, mock_entity, commit=True)

        assert result is True
        mock_db.commit.assert_called_once()

    def test_restore_soft_deleted_exception(self):
        """Test restore handles exception"""
        from backend.utils.soft_delete import restore_soft_deleted

        mock_db = MagicMock(spec=Session)
        mock_db.commit.side_effect = Exception("Commit failed")
        mock_entity = MagicMock()
        mock_entity.is_active = False

        result = restore_soft_deleted(mock_db, mock_entity, commit=True)

        assert result is False
        mock_db.rollback.assert_called_once()


class TestGetActiveQuery:
    """Test the get_active_query function"""

    def test_get_active_query_basic(self):
        """Test get_active_query returns filtered query"""
        from backend.utils.soft_delete import get_active_query

        mock_db = MagicMock(spec=Session)
        mock_model = MagicMock()
        mock_model.is_active = MagicMock()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        result = get_active_query(mock_db, mock_model)

        mock_db.query.assert_called_once_with(mock_model)
        mock_query.filter.assert_called_once()

    def test_get_active_query_no_is_active(self):
        """Test get_active_query with model without is_active"""
        from backend.utils.soft_delete import get_active_query

        mock_db = MagicMock(spec=Session)
        mock_model = MagicMock(spec=[])  # No is_active

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query

        result = get_active_query(mock_db, mock_model)

        mock_db.query.assert_called_once_with(mock_model)
        mock_query.filter.assert_not_called()

    def test_get_active_query_custom_field(self):
        """Test get_active_query with custom field name"""
        from backend.utils.soft_delete import get_active_query

        mock_db = MagicMock(spec=Session)
        mock_model = MagicMock()
        mock_model.active = MagicMock()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        result = get_active_query(mock_db, mock_model, is_active_field="active")

        mock_db.query.assert_called_once_with(mock_model)


class TestGetAllIncludingDeleted:
    """Test the get_all_including_deleted function"""

    def test_get_all_including_deleted(self):
        """Test get_all_including_deleted returns unfiltered query"""
        from backend.utils.soft_delete import get_all_including_deleted

        mock_db = MagicMock(spec=Session)
        mock_model = MagicMock()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query

        result = get_all_including_deleted(mock_db, mock_model)

        mock_db.query.assert_called_once_with(mock_model)
        assert result == mock_query


class TestFilterActive:
    """Test the filter_active function"""

    def test_filter_active_basic(self):
        """Test filter_active adds is_active filter"""
        from backend.utils.soft_delete import filter_active

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_model = MagicMock()
        mock_model.is_active = MagicMock()

        result = filter_active(mock_query, mock_model)

        mock_query.filter.assert_called_once()

    def test_filter_active_no_is_active(self):
        """Test filter_active with model without is_active"""
        from backend.utils.soft_delete import filter_active

        mock_query = MagicMock()
        mock_model = MagicMock(spec=[])

        result = filter_active(mock_query, mock_model)

        mock_query.filter.assert_not_called()
        assert result == mock_query

    def test_filter_active_custom_field(self):
        """Test filter_active with custom field name"""
        from backend.utils.soft_delete import filter_active

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_model = MagicMock()
        mock_model.active = MagicMock()

        result = filter_active(mock_query, mock_model, is_active_field="active")

        mock_query.filter.assert_called_once()


class TestSoftDeleteMixin:
    """Test the SoftDeleteMixin class"""

    def test_soft_delete_mixin_soft_delete(self):
        """Test SoftDeleteMixin.soft_delete method"""
        from backend.utils.soft_delete import SoftDeleteMixin

        mock_db = MagicMock(spec=Session)

        mixin_instance = MagicMock(spec=SoftDeleteMixin)
        mixin_instance.is_active = True
        mixin_instance.deleted_at = None
        mixin_instance.deleted_by = None

        with patch("backend.utils.soft_delete.soft_delete_with_timestamp") as mock_func:
            mock_func.return_value = True
            SoftDeleteMixin.soft_delete(mixin_instance, mock_db, deleted_by_user=123)
            mock_func.assert_called_once()

    def test_soft_delete_mixin_restore(self):
        """Test SoftDeleteMixin.restore method"""
        from backend.utils.soft_delete import SoftDeleteMixin

        mock_db = MagicMock(spec=Session)

        mixin_instance = MagicMock(spec=SoftDeleteMixin)
        mixin_instance.is_active = False

        with patch("backend.utils.soft_delete.restore_soft_deleted") as mock_func:
            mock_func.return_value = True
            SoftDeleteMixin.restore(mixin_instance, mock_db)
            mock_func.assert_called_once()

    def test_soft_delete_mixin_is_deleted_true(self):
        """Test SoftDeleteMixin.is_deleted property returns True"""
        from backend.utils.soft_delete import SoftDeleteMixin

        mixin_instance = MagicMock()
        mixin_instance.is_active = False

        result = SoftDeleteMixin.is_deleted.fget(mixin_instance)
        assert result is True

    def test_soft_delete_mixin_is_deleted_false(self):
        """Test SoftDeleteMixin.is_deleted property returns False"""
        from backend.utils.soft_delete import SoftDeleteMixin

        mixin_instance = MagicMock()
        mixin_instance.is_active = True

        result = SoftDeleteMixin.is_deleted.fget(mixin_instance)
        assert result is False

    def test_soft_delete_mixin_is_deleted_integer_zero(self):
        """Test SoftDeleteMixin.is_deleted with integer 0"""
        from backend.utils.soft_delete import SoftDeleteMixin

        mixin_instance = MagicMock()
        mixin_instance.is_active = 0

        result = SoftDeleteMixin.is_deleted.fget(mixin_instance)
        assert result is True

    def test_soft_delete_mixin_is_deleted_no_is_active(self):
        """Test SoftDeleteMixin.is_deleted when no is_active attribute"""
        from backend.utils.soft_delete import SoftDeleteMixin

        mixin_instance = MagicMock(spec=[])

        result = SoftDeleteMixin.is_deleted.fget(mixin_instance)
        assert result is False


class TestCreateSoftDeleteFunction:
    """Test the create_soft_delete_function factory"""

    def test_create_soft_delete_function_basic(self):
        """Test factory creates working delete function"""
        from backend.utils.soft_delete import create_soft_delete_function

        mock_model = MagicMock()

        delete_fn = create_soft_delete_function(mock_model, "id")

        assert callable(delete_fn)

    def test_create_soft_delete_function_entity_found(self):
        """Test created function soft deletes found entity"""
        from backend.utils.soft_delete import create_soft_delete_function

        mock_model = MagicMock()
        mock_entity = MagicMock()
        mock_entity.is_active = True

        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entity

        delete_fn = create_soft_delete_function(mock_model, "id")
        result = delete_fn(mock_db, 123)

        assert result is True
        assert mock_entity.is_active == False

    def test_create_soft_delete_function_entity_not_found(self):
        """Test created function returns False when entity not found"""
        from backend.utils.soft_delete import create_soft_delete_function

        mock_model = MagicMock()

        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        delete_fn = create_soft_delete_function(mock_model, "id")
        result = delete_fn(mock_db, 123)

        assert result is False

    def test_create_soft_delete_function_with_permission_check_pass(self):
        """Test created function passes permission check"""
        from backend.utils.soft_delete import create_soft_delete_function

        mock_model = MagicMock()
        mock_entity = MagicMock()
        mock_entity.is_active = True

        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entity

        mock_user = MagicMock()
        mock_user.role = "admin"

        permission_check = lambda user: user.role == "admin"

        delete_fn = create_soft_delete_function(mock_model, "id", permission_check=permission_check)
        result = delete_fn(mock_db, 123, current_user=mock_user)

        assert result is True

    def test_create_soft_delete_function_with_permission_check_fail(self):
        """Test created function fails permission check"""
        from backend.utils.soft_delete import create_soft_delete_function

        mock_model = MagicMock()

        mock_db = MagicMock(spec=Session)

        mock_user = MagicMock()
        mock_user.role = "viewer"

        permission_check = lambda user: user.role == "admin"

        delete_fn = create_soft_delete_function(mock_model, "id", permission_check=permission_check)
        result = delete_fn(mock_db, 123, current_user=mock_user)

        assert result is False

    def test_create_soft_delete_function_custom_is_active_field(self):
        """Test created function uses custom is_active field"""
        from backend.utils.soft_delete import create_soft_delete_function

        mock_model = MagicMock()
        mock_entity = MagicMock()
        mock_entity.active = True

        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entity

        delete_fn = create_soft_delete_function(mock_model, "id", is_active_field="active")
        result = delete_fn(mock_db, 123)

        assert result is True
        assert mock_entity.active == False
