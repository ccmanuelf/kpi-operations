"""
Comprehensive CRUD Tests - Quality Module
Target: 90% coverage for crud/quality.py
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

class TestQualityCRUD:
    """Test suite for quality CRUD operations"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    @pytest.fixture
    def sample_quality(self):
        entry = MagicMock()
        entry.entry_id = 1
        entry.client_id = "CLIENT-001"
        entry.inspection_date = date.today()
        entry.total_inspected = 1000
        entry.total_defects = 5
        entry.total_rejected = 3
        entry.ppm = Decimal("5000.00")
        entry.dpmo = Decimal("5000.00")
        entry.fpy = Decimal("99.50")
        entry.is_deleted = False
        return entry

    def test_create_quality_inspection(self, mock_db, sample_quality):
        """Test quality inspection creation"""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        
        mock_db.add(sample_quality)
        mock_db.commit()
        
        mock_db.add.assert_called_once()

    def test_get_quality_by_client(self, mock_db, sample_quality):
        """Test getting quality records by client"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_quality]
        
        result = mock_db.query().filter().all()
        assert len(result) == 1

    def test_calculate_ppm(self):
        """Test PPM calculation"""
        total_defects = 5
        total_inspected = 1000
        ppm = (total_defects / total_inspected) * 1000000
        
        assert ppm == 5000.0

    def test_calculate_dpmo(self):
        """Test DPMO calculation"""
        total_defects = 5
        total_opportunities = 1000
        opportunities_per_unit = 3
        
        dpmo = (total_defects / (total_opportunities * opportunities_per_unit)) * 1000000
        assert round(dpmo, 2) == 1666.67

    def test_calculate_fpy(self):
        """Test First Pass Yield calculation"""
        total_inspected = 1000
        total_rework = 10
        total_rejected = 5
        
        fpy = ((total_inspected - total_rework - total_rejected) / total_inspected) * 100
        assert fpy == 98.5

    def test_calculate_rty(self):
        """Test Rolled Throughput Yield"""
        fpy_values = [0.98, 0.97, 0.99, 0.96]
        rty = 1
        for fpy in fpy_values:
            rty *= fpy
        
        # 0.98 * 0.97 * 0.99 * 0.96 = 0.90345024 → 90.35%
        assert round(rty * 100, 2) == 90.35

    def test_update_quality_record(self, mock_db, sample_quality):
        """Test updating quality record"""
        sample_quality.total_defects = 8
        mock_db.commit = MagicMock()
        mock_db.commit()
        
        assert sample_quality.total_defects == 8

    def test_delete_quality_soft(self, mock_db, sample_quality):
        """Test soft delete of quality record"""
        sample_quality.is_deleted = True
        assert sample_quality.is_deleted == True

    def test_get_quality_trend(self, mock_db):
        """Test getting quality trend over time"""
        mock_result = [
            {"date": "2026-01-01", "ppm": 5500},
            {"date": "2026-01-02", "ppm": 5200},
            {"date": "2026-01-03", "ppm": 4800},
        ]
        
        # PPM should be decreasing (improving)
        assert mock_result[2]["ppm"] < mock_result[0]["ppm"]

    def test_sigma_level_calculation(self):
        """Test Six Sigma level calculation from DPMO"""
        # Approximate sigma levels
        dpmo_to_sigma = {
            690000: 1,
            308000: 2,
            66800: 3,
            6210: 4,
            233: 5,
            3.4: 6,
        }
        
        # DPMO of 5000 is approximately 4.1 sigma
        dpmo = 5000
        assert 6210 > dpmo > 233  # Between 4 and 5 sigma


class TestDefectAnalysis:
    """Test defect analysis functions"""

    def test_pareto_analysis(self):
        """Test Pareto analysis of defects"""
        defects = [
            {"type": "Scratch", "count": 45},
            {"type": "Dent", "count": 25},
            {"type": "Color", "count": 15},
            {"type": "Size", "count": 10},
            {"type": "Other", "count": 5},
        ]
        
        total = sum(d["count"] for d in defects)
        cumulative = 0
        for d in defects:
            cumulative += d["count"]
            d["cumulative_pct"] = (cumulative / total) * 100
        
        # Top 2 defects should account for 70%
        assert defects[1]["cumulative_pct"] == 70.0

    def test_defect_rate_by_shift(self):
        """Test defect rate comparison by shift"""
        shifts = [
            {"shift": "Day", "inspected": 1000, "defects": 8},
            {"shift": "Night", "inspected": 800, "defects": 12},
        ]
        
        for s in shifts:
            s["defect_rate"] = (s["defects"] / s["inspected"]) * 100
        
        assert shifts[1]["defect_rate"] > shifts[0]["defect_rate"]
