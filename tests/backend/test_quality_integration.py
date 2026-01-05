"""
Integration Tests for Quality Inspection API Endpoints
Tests all 7 quality endpoints, FPY/PPM/DPMO calculations, and defect tracking
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.quality import QualityInspection
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.user import User
from backend.crud.quality import (
    create_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
    delete_quality_inspection
)
from backend.calculations.ppm import calculate_ppm
from backend.calculations.dpmo import calculate_dpmo
from backend.calculations.fpy_rty import calculate_fpy, calculate_rty


@pytest.fixture
def test_product(test_db: Session):
    """Create test product"""
    product = Product(
        product_code="QUAL-TEST-001",
        product_name="Quality Test Product",
        ideal_cycle_time=Decimal("0.25"),
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def test_shift(test_db: Session):
    """Create test shift"""
    shift = Shift(
        shift_name="Quality Test Shift",
        start_time="08:00",
        end_time="16:00",
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def test_user(test_db: Session):
    """Create test user"""
    user = User(
        username="quality_inspector",
        email="inspector@test.com",
        password_hash="hashed_password",
        full_name="Quality Inspector",
        role="SUPERVISOR",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestQualityCreate:
    """Test POST /api/quality - Create quality inspection"""

    def test_create_perfect_quality(self, test_db, test_product, test_shift, test_user):
        """Should create quality inspection with zero defects"""
        from backend.models.quality import QualityInspectionCreate

        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=100,
            units_failed=0,
            inspection_stage="FINAL",
            defect_count=0
        )

        result = create_quality_inspection(test_db, inspection_data, test_user)

        assert result is not None
        assert result.units_passed == 100
        assert result.units_failed == 0
        assert result.defect_count == 0

    def test_create_with_defects(self, test_db, test_product, test_shift, test_user):
        """Should create quality inspection with defects"""
        from backend.models.quality import QualityInspectionCreate

        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="IN_PROCESS",
            defect_count=8,
            defect_category="STITCHING"
        )

        result = create_quality_inspection(test_db, inspection_data, test_user)

        assert result.units_failed == 5
        assert result.defect_count == 8
        assert result.defect_category == "STITCHING"

    def test_create_multiple_inspection_stages(self, test_db, test_product, test_shift, test_user):
        """Should create inspections for different stages"""
        from backend.models.quality import QualityInspectionCreate

        stages = ["INCOMING", "IN_PROCESS", "FINAL"]

        for stage in stages:
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=100,
                units_passed=98,
                units_failed=2,
                inspection_stage=stage,
                defect_count=2
            )
            result = create_quality_inspection(test_db, inspection_data, test_user)
            assert result.inspection_stage == stage


class TestQualityRead:
    """Test GET /api/quality - List quality inspections"""

    def test_list_all_inspections(self, test_db, test_product, test_shift, test_user):
        """Should list all quality inspections"""
        from backend.models.quality import QualityInspectionCreate

        # Create multiple inspections
        for i in range(3):
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=100,
                units_passed=95 + i,
                units_failed=5 - i,
                inspection_stage="FINAL",
                defect_count=5 - i
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        result = get_quality_inspections(test_db, test_user)

        assert len(result) == 3

    def test_filter_by_date_range(self, test_db, test_product, test_shift, test_user):
        """Should filter inspections by date range"""
        from backend.models.quality import QualityInspectionCreate

        # Create inspections for different dates
        dates = [date.today() - timedelta(days=i) for i in range(7)]
        for d in dates:
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=d,
                units_inspected=100,
                units_passed=95,
                units_failed=5,
                inspection_stage="FINAL",
                defect_count=5
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        start_date = date.today() - timedelta(days=3)
        end_date = date.today()

        result = get_quality_inspections(
            test_db, test_user,
            start_date=start_date,
            end_date=end_date
        )

        assert len(result) == 4  # Today + 3 days back

    def test_filter_by_inspection_stage(self, test_db, test_product, test_shift, test_user):
        """Should filter by inspection stage"""
        from backend.models.quality import QualityInspectionCreate

        stages = ["INCOMING", "IN_PROCESS", "FINAL"]
        for stage in stages:
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=100,
                units_passed=95,
                units_failed=5,
                inspection_stage=stage,
                defect_count=5
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        result = get_quality_inspections(
            test_db, test_user,
            inspection_stage="FINAL"
        )

        assert len(result) == 1
        assert result[0].inspection_stage == "FINAL"

    def test_filter_by_defect_category(self, test_db, test_product, test_shift, test_user):
        """Should filter by defect category"""
        from backend.models.quality import QualityInspectionCreate

        categories = ["STITCHING", "FABRIC", "SIZING"]
        for category in categories:
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=100,
                units_passed=95,
                units_failed=5,
                inspection_stage="FINAL",
                defect_count=5,
                defect_category=category
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        result = get_quality_inspections(
            test_db, test_user,
            defect_category="STITCHING"
        )

        assert len(result) == 1
        assert result[0].defect_category == "STITCHING"


class TestQualityGetById:
    """Test GET /api/quality/{inspection_id} - Get inspection by ID"""

    def test_get_existing_inspection(self, test_db, test_product, test_shift, test_user):
        """Should get quality inspection by ID"""
        from backend.models.quality import QualityInspectionCreate

        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5
        )

        created = create_quality_inspection(test_db, inspection_data, test_user)
        result = get_quality_inspection(test_db, created.inspection_id, test_user)

        assert result is not None
        assert result.inspection_id == created.inspection_id

    def test_get_nonexistent_inspection(self, test_db, test_user):
        """Should return None for nonexistent inspection"""
        result = get_quality_inspection(test_db, 99999, test_user)
        assert result is None


class TestQualityUpdate:
    """Test PUT /api/quality/{inspection_id} - Update inspection"""

    def test_update_defect_count(self, test_db, test_product, test_shift, test_user):
        """Should update defect count"""
        from backend.models.quality import QualityInspectionCreate, QualityInspectionUpdate

        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5
        )
        created = create_quality_inspection(test_db, inspection_data, test_user)

        update_data = QualityInspectionUpdate(defect_count=8)
        updated = update_quality_inspection(test_db, created.inspection_id, update_data, test_user)

        assert updated.defect_count == 8

    def test_update_passed_failed_units(self, test_db, test_product, test_shift, test_user):
        """Should update passed/failed units"""
        from backend.models.quality import QualityInspectionCreate, QualityInspectionUpdate

        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5
        )
        created = create_quality_inspection(test_db, inspection_data, test_user)

        update_data = QualityInspectionUpdate(
            units_passed=90,
            units_failed=10
        )
        updated = update_quality_inspection(test_db, created.inspection_id, update_data, test_user)

        assert updated.units_passed == 90
        assert updated.units_failed == 10


class TestQualityDelete:
    """Test DELETE /api/quality/{inspection_id} - Delete inspection"""

    def test_delete_inspection_as_supervisor(self, test_db, test_product, test_shift, test_user):
        """Should delete quality inspection as supervisor"""
        from backend.models.quality import QualityInspectionCreate

        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5
        )
        created = create_quality_inspection(test_db, inspection_data, test_user)

        success = delete_quality_inspection(test_db, created.inspection_id, test_user)

        assert success is True

        # Verify deleted
        result = get_quality_inspection(test_db, created.inspection_id, test_user)
        assert result is None


class TestPPMCalculation:
    """Test GET /api/kpi/ppm - Calculate Parts Per Million defects"""

    def test_calculate_ppm_zero_defects(self, test_db, test_product, test_shift, test_user):
        """Should calculate PPM = 0 for zero defects"""
        from backend.models.quality import QualityInspectionCreate

        # Create perfect quality inspections
        for _ in range(5):
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=1000,
                units_passed=1000,
                units_failed=0,
                inspection_stage="FINAL",
                defect_count=0
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        ppm, inspected, defects = calculate_ppm(
            test_db,
            test_product.product_id,
            test_shift.shift_id,
            date.today(),
            date.today()
        )

        assert ppm == Decimal("0.0")
        assert inspected == 5000
        assert defects == 0

    def test_calculate_ppm_with_defects(self, test_db, test_product, test_shift, test_user):
        """Should calculate correct PPM with defects"""
        from backend.models.quality import QualityInspectionCreate

        # Create inspections with defects
        # 10,000 units inspected, 50 defects
        # PPM = (50 / 10,000) * 1,000,000 = 5,000
        for _ in range(10):
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=1000,
                units_passed=995,
                units_failed=5,
                inspection_stage="FINAL",
                defect_count=5
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        ppm, inspected, defects = calculate_ppm(
            test_db,
            test_product.product_id,
            test_shift.shift_id,
            date.today(),
            date.today()
        )

        assert inspected == 10000
        assert defects == 50
        # PPM = (50 / 10,000) * 1,000,000 = 5,000
        assert ppm == Decimal("5000.00")


class TestDPMOCalculation:
    """Test GET /api/kpi/dpmo - Calculate Defects Per Million Opportunities"""

    def test_calculate_dpmo_and_sigma(self, test_db, test_product, test_shift, test_user):
        """Should calculate DPMO and Sigma level"""
        from backend.models.quality import QualityInspectionCreate

        # Create inspections
        # 1,000 units * 10 opportunities = 10,000 opportunities
        # 20 defects
        # DPMO = (20 / 10,000) * 1,000,000 = 2,000
        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=1000,
            units_passed=980,
            units_failed=20,
            inspection_stage="FINAL",
            defect_count=20
        )
        create_quality_inspection(test_db, inspection_data, test_user)

        dpmo, sigma, units, defects = calculate_dpmo(
            test_db,
            test_product.product_id,
            test_shift.shift_id,
            date.today(),
            date.today(),
            opportunities_per_unit=10
        )

        assert units == 1000
        assert defects == 20
        assert dpmo == Decimal("2000.00")
        # Sigma level should be around 4.5 for DPMO = 2,000
        assert sigma >= Decimal("4.0")


class TestFPYCalculation:
    """Test GET /api/kpi/fpy-rty - Calculate First Pass Yield"""

    def test_calculate_fpy_perfect(self, test_db, test_product, test_shift, test_user):
        """Should calculate FPY = 100% for perfect quality"""
        from backend.models.quality import QualityInspectionCreate

        # All units pass first time
        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=1000,
            units_passed=1000,
            units_failed=0,
            inspection_stage="FINAL",
            defect_count=0
        )
        create_quality_inspection(test_db, inspection_data, test_user)

        fpy, good, total = calculate_fpy(
            test_db,
            test_product.product_id,
            date.today(),
            date.today()
        )

        assert fpy == Decimal("100.00")
        assert good == 1000
        assert total == 1000

    def test_calculate_fpy_with_failures(self, test_db, test_product, test_shift, test_user):
        """Should calculate correct FPY with failures"""
        from backend.models.quality import QualityInspectionCreate

        # 950 passed, 50 failed
        # FPY = (950 / 1000) * 100 = 95%
        inspection_data = QualityInspectionCreate(
            product_id=test_product.product_id,
            shift_id=test_shift.shift_id,
            inspection_date=date.today(),
            units_inspected=1000,
            units_passed=950,
            units_failed=50,
            inspection_stage="FINAL",
            defect_count=50
        )
        create_quality_inspection(test_db, inspection_data, test_user)

        fpy, good, total = calculate_fpy(
            test_db,
            test_product.product_id,
            date.today(),
            date.today()
        )

        assert fpy == Decimal("95.00")
        assert good == 950
        assert total == 1000


class TestRTYCalculation:
    """Test GET /api/kpi/fpy-rty - Calculate Rolled Throughput Yield"""

    def test_calculate_rty_multiple_stages(self, test_db, test_product, test_shift, test_user):
        """Should calculate RTY across multiple inspection stages"""
        from backend.models.quality import QualityInspectionCreate

        # Create inspections for different stages
        # Stage 1 (INCOMING): 98% FPY
        # Stage 2 (IN_PROCESS): 97% FPY
        # Stage 3 (FINAL): 99% FPY
        # RTY = 0.98 * 0.97 * 0.99 = 94.11%

        stages_data = [
            ("INCOMING", 980, 20),
            ("IN_PROCESS", 970, 30),
            ("FINAL", 990, 10)
        ]

        for stage, passed, failed in stages_data:
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=1000,
                units_passed=passed,
                units_failed=failed,
                inspection_stage=stage,
                defect_count=failed
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        rty, steps = calculate_rty(
            test_db,
            test_product.product_id,
            date.today(),
            date.today()
        )

        assert len(steps) == 3
        # RTY should be around 94%
        assert rty >= Decimal("93.00")
        assert rty <= Decimal("95.00")


class TestDefectTracking:
    """Test defect categorization and tracking"""

    def test_track_defects_by_category(self, test_db, test_product, test_shift, test_user):
        """Should track defects grouped by category"""
        from backend.models.quality import QualityInspectionCreate

        categories = {
            "STITCHING": 30,
            "FABRIC": 20,
            "SIZING": 15,
            "COLOR": 10
        }

        for category, defect_count in categories.items():
            inspection_data = QualityInspectionCreate(
                product_id=test_product.product_id,
                shift_id=test_shift.shift_id,
                inspection_date=date.today(),
                units_inspected=100,
                units_passed=100 - defect_count,
                units_failed=defect_count,
                inspection_stage="FINAL",
                defect_count=defect_count,
                defect_category=category
            )
            create_quality_inspection(test_db, inspection_data, test_user)

        # Query defects by category
        all_inspections = get_quality_inspections(test_db, test_user)

        category_totals = {}
        for inspection in all_inspections:
            cat = inspection.defect_category or "UNCATEGORIZED"
            category_totals[cat] = category_totals.get(cat, 0) + inspection.defect_count

        assert category_totals["STITCHING"] == 30
        assert category_totals["FABRIC"] == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
