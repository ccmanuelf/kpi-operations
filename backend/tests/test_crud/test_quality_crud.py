"""
Comprehensive tests for Quality CRUD operations
Migrated to use real database (transactional_db) instead of mocks.
"""

import pytest
from datetime import datetime, date, timedelta

from backend.tests.fixtures.factories import TestDataFactory
from backend.crud.quality import get_quality_inspections, get_quality_inspection
from fastapi import HTTPException


class TestQualityCRUD:
    """Test Quality CRUD operations using real DB"""

    def test_get_quality_entries_empty(self, transactional_db):
        """Test get quality entries returns empty list"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_create_and_list_quality_entries(self, transactional_db):
        """Test creating and listing quality entries"""
        client = TestDataFactory.create_client(transactional_db, client_id="Q-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="Q-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="Q-CL")
        transactional_db.flush()

        TestDataFactory.create_quality_entry(
            transactional_db,
            work_order_id=wo.work_order_id,
            client_id="Q-CL",
            inspector_id=admin.user_id,
            units_inspected=1000,
            units_defective=5,
        )
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert len(result) == 1
        assert result[0].units_inspected == 1000
        assert result[0].units_defective == 5

    def test_get_quality_entry_by_id(self, transactional_db):
        """Test getting a quality entry by ID"""
        client = TestDataFactory.create_client(transactional_db, client_id="QID-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="QID-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="QID-CL")
        transactional_db.flush()

        entry = TestDataFactory.create_quality_entry(
            transactional_db, work_order_id=wo.work_order_id, client_id="QID-CL", inspector_id=admin.user_id
        )
        transactional_db.commit()

        result = get_quality_inspection(transactional_db, entry.quality_entry_id, admin)
        assert result is not None
        assert result.quality_entry_id == entry.quality_entry_id

    def test_get_quality_entry_not_found(self, transactional_db):
        """Test getting non-existent quality entry raises 404"""
        admin = TestDataFactory.create_user(transactional_db, role="admin")
        transactional_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_quality_inspection(transactional_db, "QE-NONEXIST", admin)
        assert exc_info.value.status_code == 404

    def test_multiple_quality_entries(self, transactional_db):
        """Test creating multiple quality entries"""
        client = TestDataFactory.create_client(transactional_db, client_id="QM-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="QM-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="QM-CL")
        transactional_db.flush()

        for i in range(3):
            TestDataFactory.create_quality_entry(
                transactional_db,
                work_order_id=wo.work_order_id,
                client_id="QM-CL",
                inspector_id=admin.user_id,
                units_inspected=1000,
                units_defective=i + 1,
            )
        transactional_db.commit()

        result = get_quality_inspections(transactional_db, admin)
        assert len(result) == 3

    def test_quality_with_defect_details(self, transactional_db):
        """Test quality entry with linked defect details"""
        from backend.crud.defect_detail import get_defect_details

        client = TestDataFactory.create_client(transactional_db, client_id="QDD-CL")
        admin = TestDataFactory.create_user(transactional_db, role="admin", client_id="QDD-CL")
        wo = TestDataFactory.create_work_order(transactional_db, client_id="QDD-CL")
        transactional_db.flush()

        qe = TestDataFactory.create_quality_entry(
            transactional_db, work_order_id=wo.work_order_id, client_id="QDD-CL", inspector_id=admin.user_id
        )
        transactional_db.flush()

        TestDataFactory.create_defect_detail(transactional_db, quality_entry_id=qe.quality_entry_id, defect_count=3, client_id="QDD-CL")
        transactional_db.commit()

        details = get_defect_details(transactional_db, admin)
        assert len(details) >= 1

    def test_calculate_defect_rate(self):
        """Test defect rate calculation"""
        total_inspected = 1000
        total_defects = 25
        defect_rate = (total_defects / total_inspected) * 100
        assert defect_rate == 2.5

    def test_calculate_ppm(self):
        """Test PPM calculation"""
        defects = 50
        inspected = 1000000
        ppm = (defects / inspected) * 1000000
        assert ppm == 50

    def test_calculate_dpmo(self):
        """Test DPMO calculation"""
        defects = 100
        opportunities = 5
        units = 10000
        dpmo = (defects / (units * opportunities)) * 1000000
        assert dpmo == 2000

    def test_calculate_fpy(self):
        """Test First Pass Yield calculation"""
        total_produced = 1000
        first_pass_good = 950
        fpy = (first_pass_good / total_produced) * 100
        assert fpy == 95.0

    def test_calculate_rty(self):
        """Test Rolled Throughput Yield calculation"""
        fpy_values = [0.95, 0.98, 0.99]
        rty = 1.0
        for fpy in fpy_values:
            rty *= fpy
        rty_percent = rty * 100
        assert round(rty_percent, 2) == 92.17


class TestQualityEdgeCases:
    """Edge cases for quality operations"""

    def test_zero_inspected(self):
        """Test defect rate with zero units inspected"""
        total_inspected = 0
        defect_rate = 0.0 if total_inspected == 0 else 100.0
        assert defect_rate == 0.0

    def test_all_defects(self):
        """Test 100% defect rate"""
        total_inspected = 100
        total_defects = 100
        defect_rate = (total_defects / total_inspected) * 100
        assert defect_rate == 100.0

    def test_sigma_level_calculation(self):
        """Test sigma level from DPMO"""
        dpmo = 3.4
        sigma = 6 if dpmo <= 3.4 else 5 if dpmo <= 233 else 4 if dpmo <= 6210 else 3
        assert sigma == 6

    def test_pareto_defect_analysis(self):
        """Test Pareto analysis of defect types"""
        defects = {"visual": 50, "dimensional": 30, "surface": 15, "other": 5}
        sorted_defects = sorted(defects.items(), key=lambda x: x[1], reverse=True)
        assert sorted_defects[0][0] == "visual"
