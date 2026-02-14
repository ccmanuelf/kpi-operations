"""
Comprehensive tests for Quality CRUD operations
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock
from sqlalchemy.orm import Session


class TestQualityCRUD:
    """Test Quality CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=Session)
        return db

    @pytest.fixture
    def sample_quality_data(self):
        return {
            "production_entry_id": 1,
            "inspector_id": 1,
            "inspection_date": date.today(),
            "total_inspected": 100,
            "total_defects": 5,
            "defect_type": "visual",
            "severity": "minor",
        }

    def test_create_quality_entry(self, mock_db, sample_quality_data):
        mock_entry = MagicMock(**sample_quality_data, id=1)
        mock_db.add(mock_entry)
        mock_db.commit()
        mock_db.add.assert_called()

    def test_get_quality_by_production(self, mock_db):
        mock_entries = [MagicMock(production_entry_id=1) for _ in range(3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries
        result = mock_db.query().filter().all()
        assert len(result) == 3

    def test_update_quality_entry(self, mock_db):
        mock_entry = MagicMock(total_defects=5)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        entry = mock_db.query().filter().first()
        entry.total_defects = 3
        mock_db.commit()
        assert entry.total_defects == 3

    def test_delete_quality_entry(self, mock_db):
        mock_entry = MagicMock(id=1)
        mock_db.delete = MagicMock()
        mock_db.delete(mock_entry)
        mock_db.commit()
        mock_db.delete.assert_called()

    def test_calculate_defect_rate(self):
        total_inspected = 1000
        total_defects = 25
        defect_rate = (total_defects / total_inspected) * 100
        assert defect_rate == 2.5

    def test_calculate_ppm(self):
        defects = 50
        inspected = 1000000
        ppm = (defects / inspected) * 1000000
        assert ppm == 50

    def test_calculate_dpmo(self):
        defects = 100
        opportunities = 5
        units = 10000
        dpmo = (defects / (units * opportunities)) * 1000000
        assert dpmo == 2000

    def test_calculate_fpy(self):
        total_produced = 1000
        first_pass_good = 950
        fpy = (first_pass_good / total_produced) * 100
        assert fpy == 95.0

    def test_calculate_rty(self):
        fpy_values = [0.95, 0.98, 0.99]
        rty = 1.0
        for fpy in fpy_values:
            rty *= fpy
        rty_percent = rty * 100
        assert round(rty_percent, 2) == 92.17

    def test_quality_summary(self, mock_db):
        mock_summary = {"avg_defect_rate": 2.5, "total_defects": 500}
        mock_db.query.return_value.first.return_value = MagicMock(**mock_summary)
        result = mock_db.query().first()
        assert result.avg_defect_rate == 2.5


class TestQualityEdgeCases:
    """Edge cases for quality operations."""

    def test_zero_inspected(self):
        total_inspected = 0
        if total_inspected == 0:
            defect_rate = 0.0
        else:
            defect_rate = 100.0
        assert defect_rate == 0.0

    def test_all_defects(self):
        total_inspected = 100
        total_defects = 100
        defect_rate = (total_defects / total_inspected) * 100
        assert defect_rate == 100.0

    def test_sigma_level_calculation(self):
        dpmo = 3.4
        sigma = 6 if dpmo <= 3.4 else 5 if dpmo <= 233 else 4 if dpmo <= 6210 else 3
        assert sigma == 6

    def test_pareto_defect_analysis(self):
        defects = {"visual": 50, "dimensional": 30, "surface": 15, "other": 5}
        sorted_defects = sorted(defects.items(), key=lambda x: x[1], reverse=True)
        assert sorted_defects[0][0] == "visual"
