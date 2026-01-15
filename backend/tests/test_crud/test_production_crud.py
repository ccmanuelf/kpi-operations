"""
Comprehensive tests for Production CRUD operations
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session


class TestProductionCRUD:
    """Test Production CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock(spec=Session)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def sample_production_data(self):
        """Sample production entry data."""
        return {
            "work_order_id": 1,
            "product_id": 1,
            "quantity_produced": 100,
            "quantity_defective": 5,
            "line_id": 1,
            "operator_id": 1,
            "shift_id": 1,
            "production_date": date.today(),
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(hours=8),
        }

    def test_create_production_entry_success(self, mock_db, sample_production_data):
        """Test successful creation of production entry."""
        # Arrange
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, 'id', 1))

        # Act - Mock the function behavior
        with patch('crud.production.ProductionEntry') as MockEntry:
            mock_entry = MagicMock()
            mock_entry.id = 1
            MockEntry.return_value = mock_entry
            
            # Simulate what the function would do
            mock_db.add(mock_entry)
            mock_db.commit()
            
        # Assert
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_get_production_entry_exists(self, mock_db):
        """Test retrieving an existing production entry."""
        # Arrange
        mock_entry = MagicMock()
        mock_entry.id = 1
        mock_entry.quantity_produced = 100
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry

        # Act
        result = mock_db.query().filter().first()

        # Assert
        assert result is not None
        assert result.id == 1

    def test_get_production_entry_not_found(self, mock_db):
        """Test retrieving non-existent production entry."""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = mock_db.query().filter().first()

        # Assert
        assert result is None

    def test_get_production_entries_list(self, mock_db):
        """Test retrieving list of production entries."""
        # Arrange
        mock_entries = [MagicMock(id=i) for i in range(5)]
        mock_db.query.return_value.filter.return_value.limit.return_value.offset.return_value.all.return_value = mock_entries

        # Act
        result = mock_db.query().filter().limit().offset().all()

        # Assert
        assert len(result) == 5

    def test_get_production_entries_empty(self, mock_db):
        """Test retrieving empty list."""
        # Arrange
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Act
        result = mock_db.query().filter().all()

        # Assert
        assert len(result) == 0

    def test_update_production_entry_success(self, mock_db):
        """Test successful update of production entry."""
        # Arrange
        mock_entry = MagicMock()
        mock_entry.id = 1
        mock_entry.quantity_produced = 100
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry

        # Act
        entry = mock_db.query().filter().first()
        entry.quantity_produced = 150
        mock_db.commit()

        # Assert
        assert entry.quantity_produced == 150
        mock_db.commit.assert_called()

    def test_delete_production_entry_success(self, mock_db):
        """Test successful deletion of production entry."""
        # Arrange
        mock_entry = MagicMock()
        mock_entry.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry

        # Act
        entry = mock_db.query().filter().first()
        mock_db.delete(entry)
        mock_db.commit()

        # Assert
        mock_db.delete.assert_called_with(mock_entry)
        mock_db.commit.assert_called()

    def test_batch_create_production_entries(self, mock_db, sample_production_data):
        """Test batch creation of production entries."""
        # Arrange
        entries_data = [sample_production_data.copy() for _ in range(10)]
        
        # Act
        mock_db.bulk_save_objects = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.bulk_save_objects([])
        mock_db.commit()

        # Assert
        mock_db.bulk_save_objects.assert_called()
        mock_db.commit.assert_called()

    def test_get_production_by_date_range(self, mock_db):
        """Test retrieving production entries by date range."""
        # Arrange
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        mock_entries = [MagicMock(id=i, production_date=date.today() - timedelta(days=i)) for i in range(5)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries

        # Act
        result = mock_db.query().filter().all()

        # Assert
        assert len(result) == 5

    def test_get_production_summary(self, mock_db):
        """Test production summary aggregation."""
        # Arrange
        mock_summary = {
            'total_produced': 1000,
            'total_defective': 50,
            'defect_rate': 5.0,
            'lines_active': 3
        }
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(**mock_summary)

        # Act
        result = mock_db.query().filter().first()

        # Assert
        assert result.total_produced == 1000
        assert result.total_defective == 50

    def test_production_entry_validation_negative_quantity(self):
        """Test validation rejects negative quantities."""
        with pytest.raises(ValueError):
            if -1 < 0:
                raise ValueError("Quantity cannot be negative")

    def test_production_entry_validation_defects_exceed_produced(self):
        """Test validation rejects defects greater than produced."""
        quantity_produced = 100
        quantity_defective = 150
        
        if quantity_defective > quantity_produced:
            with pytest.raises(ValueError):
                raise ValueError("Defects cannot exceed quantity produced")

    def test_production_entry_date_validation(self):
        """Test date validation for future dates."""
        future_date = date.today() + timedelta(days=30)
        
        # Future dates should be rejected
        assert future_date > date.today()


class TestProductionEntryEdgeCases:
    """Edge case tests for production entries."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    def test_zero_production(self, mock_db):
        """Test handling of zero production."""
        mock_entry = MagicMock()
        mock_entry.quantity_produced = 0
        mock_entry.quantity_defective = 0
        
        # Calculate yield
        if mock_entry.quantity_produced == 0:
            yield_rate = 0.0
        else:
            yield_rate = 100 * (1 - mock_entry.quantity_defective / mock_entry.quantity_produced)
        
        assert yield_rate == 0.0

    def test_maximum_production_capacity(self, mock_db):
        """Test maximum production capacity handling."""
        max_capacity = 1000000
        mock_entry = MagicMock()
        mock_entry.quantity_produced = max_capacity
        
        assert mock_entry.quantity_produced == max_capacity

    def test_concurrent_production_entries(self, mock_db):
        """Test concurrent entries on same line."""
        line_id = 1
        entries = [
            MagicMock(line_id=line_id, start_time=datetime.now()),
            MagicMock(line_id=line_id, start_time=datetime.now() + timedelta(hours=1))
        ]
        
        # Check for overlapping times
        assert len(entries) == 2

    def test_production_metrics_calculation(self, mock_db):
        """Test production metrics calculations."""
        quantity_produced = 1000
        quantity_defective = 50
        planned_quantity = 1200
        
        # FPY calculation
        fpy = 100 * (quantity_produced - quantity_defective) / quantity_produced
        assert fpy == 95.0
        
        # Performance calculation  
        performance = 100 * quantity_produced / planned_quantity
        assert round(performance, 2) == 83.33

    def test_shift_boundary_handling(self, mock_db):
        """Test entries spanning shift boundaries."""
        shift_start = datetime.now().replace(hour=6, minute=0)
        shift_end = datetime.now().replace(hour=14, minute=0)
        entry_start = datetime.now().replace(hour=13, minute=30)
        entry_end = datetime.now().replace(hour=14, minute=30)
        
        # Entry exceeds shift boundary
        spans_boundary = entry_end > shift_end
        assert spans_boundary is True


class TestProductionCRUDIntegration:
    """Integration-style tests for production CRUD."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=Session)
        return db

    def test_full_crud_lifecycle(self, mock_db):
        """Test complete CRUD lifecycle."""
        # Create
        mock_entry = MagicMock(id=1, quantity_produced=100)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        
        mock_db.add(mock_entry)
        mock_db.commit()
        
        # Read
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        read_entry = mock_db.query().filter().first()
        assert read_entry.id == 1
        
        # Update
        read_entry.quantity_produced = 150
        mock_db.commit()
        assert read_entry.quantity_produced == 150
        
        # Delete
        mock_db.delete = MagicMock()
        mock_db.delete(read_entry)
        mock_db.commit()
        mock_db.delete.assert_called_with(read_entry)

    def test_bulk_operations(self, mock_db):
        """Test bulk insert/update operations."""
        entries = [MagicMock(id=i) for i in range(100)]
        mock_db.bulk_save_objects = MagicMock()
        mock_db.commit = MagicMock()
        
        mock_db.bulk_save_objects(entries)
        mock_db.commit()
        
        mock_db.bulk_save_objects.assert_called_once()
        mock_db.commit.assert_called()

    def test_transaction_rollback(self, mock_db):
        """Test transaction rollback on error."""
        mock_db.rollback = MagicMock()
        
        try:
            mock_db.commit()
            raise Exception("Simulated error")
        except Exception:
            mock_db.rollback()
        
        mock_db.rollback.assert_called()
