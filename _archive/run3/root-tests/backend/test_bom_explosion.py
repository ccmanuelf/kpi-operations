"""
BOM Explosion Algorithm Tests
Comprehensive tests for the BOM explosion functionality.

Phase C.1: Capacity Planning Module - BOM Tests
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch

from backend.services.capacity.bom_service import (
    BOMService, BOMComponent, BOMExplosionResult
)
from backend.schemas.capacity.bom import CapacityBOMHeader, CapacityBOMDetail
from backend.exceptions.domain_exceptions import BOMExplosionError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def sample_bom():
    """Create sample BOM with 3 components for testing."""
    header = MagicMock(spec=CapacityBOMHeader)
    header.id = 1
    header.client_id = "TEST_CLIENT"
    header.parent_item_code = "STYLE001"
    header.parent_item_description = "Basic T-Shirt"
    header.style_code = "STYLE001"
    header.revision = "1.0"
    header.is_active = True

    details = []

    # Component 1: Fabric (no waste)
    fabric = MagicMock(spec=CapacityBOMDetail)
    fabric.id = 1
    fabric.header_id = 1
    fabric.client_id = "TEST_CLIENT"
    fabric.component_item_code = "FABRIC001"
    fabric.component_description = "Jersey Cotton"
    fabric.quantity_per = Decimal("0.5")
    fabric.waste_percentage = Decimal("0")
    fabric.unit_of_measure = "M"
    fabric.component_type = "FABRIC"
    details.append(fabric)

    # Component 2: Thread (2% waste)
    thread = MagicMock(spec=CapacityBOMDetail)
    thread.id = 2
    thread.header_id = 1
    thread.client_id = "TEST_CLIENT"
    thread.component_item_code = "THREAD001"
    thread.component_description = "White Thread"
    thread.quantity_per = Decimal("50")
    thread.waste_percentage = Decimal("2")
    thread.unit_of_measure = "M"
    thread.component_type = "TRIM"
    details.append(thread)

    # Component 3: Label (no waste)
    label = MagicMock(spec=CapacityBOMDetail)
    label.id = 3
    label.header_id = 1
    label.client_id = "TEST_CLIENT"
    label.component_item_code = "LABEL001"
    label.component_description = "Care Label"
    label.quantity_per = Decimal("1")
    label.waste_percentage = Decimal("0")
    label.unit_of_measure = "EA"
    label.component_type = "ACCESSORY"
    details.append(label)

    return {"header": header, "details": details}


@pytest.fixture
def sample_bom_with_waste():
    """Create sample BOM with waste percentages for testing."""
    header = MagicMock(spec=CapacityBOMHeader)
    header.id = 2
    header.client_id = "TEST_CLIENT"
    header.parent_item_code = "STYLE_WASTE"
    header.parent_item_description = "Style with Waste"
    header.style_code = "STYLE_WASTE"
    header.revision = "1.0"
    header.is_active = True

    details = []

    # Fabric with 5% waste
    fabric = MagicMock(spec=CapacityBOMDetail)
    fabric.id = 10
    fabric.header_id = 2
    fabric.client_id = "TEST_CLIENT"
    fabric.component_item_code = "FABRIC001"
    fabric.component_description = "Cotton Jersey"
    fabric.quantity_per = Decimal("2")
    fabric.waste_percentage = Decimal("5")
    fabric.unit_of_measure = "M"
    fabric.component_type = "FABRIC"
    details.append(fabric)

    return {"header": header, "details": details}


@pytest.fixture
def inactive_bom():
    """Create inactive BOM for testing."""
    header = MagicMock(spec=CapacityBOMHeader)
    header.id = 3
    header.client_id = "TEST_CLIENT"
    header.parent_item_code = "INACTIVE_STYLE"
    header.parent_item_description = "Inactive Style"
    header.style_code = "INACTIVE_STYLE"
    header.revision = "1.0"
    header.is_active = False

    return {"header": header, "details": []}


@pytest.fixture
def multi_order_bom():
    """Create multiple BOMs that share a component."""
    # BOM 1 - uses THREAD001
    header1 = MagicMock(spec=CapacityBOMHeader)
    header1.id = 4
    header1.client_id = "TEST_CLIENT"
    header1.parent_item_code = "STYLE001"
    header1.is_active = True

    detail1 = MagicMock(spec=CapacityBOMDetail)
    detail1.component_item_code = "THREAD001"
    detail1.quantity_per = Decimal("50")
    detail1.waste_percentage = Decimal("0")

    # BOM 2 - also uses THREAD001
    header2 = MagicMock(spec=CapacityBOMHeader)
    header2.id = 5
    header2.client_id = "TEST_CLIENT"
    header2.parent_item_code = "STYLE002"
    header2.is_active = True

    detail2 = MagicMock(spec=CapacityBOMDetail)
    detail2.component_item_code = "THREAD001"
    detail2.quantity_per = Decimal("75")
    detail2.waste_percentage = Decimal("0")

    return {
        "bom1": {"header": header1, "details": [detail1]},
        "bom2": {"header": header2, "details": [detail2]}
    }


# =============================================================================
# BOM Explosion Tests
# =============================================================================

class TestBOMExplosion:
    """Test BOM explosion algorithm."""

    def test_simple_explosion(self, mock_db_session, sample_bom):
        """
        Given a BOM with 3 components
        When I explode for quantity 100
        Then I get 3 components with correct quantities.

        Performance target: <10ms for simple explosion
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            # Setup header query
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            # Setup details query
            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            mock_query.side_effect = [header_mock, details_mock]

            result = service.explode_bom(
                client_id="TEST_CLIENT",
                parent_item_code="STYLE001",
                quantity=Decimal("100"),
                emit_event=False
            )

            assert result.parent_item_code == "STYLE001"
            assert result.quantity_requested == Decimal("100")
            assert len(result.components) == 3
            assert result.total_components == 3
            assert result.explosion_depth == 1

    def test_waste_percentage_calculation(self, mock_db_session, sample_bom_with_waste):
        """
        Given component with 5% waste
        When I need 100 gross units
        Then net_required = 100 * qty_per * (1 + waste/100)

        For qty_per=2, waste=5%:
        gross = 100 * 2 = 200
        net = 200 * 1.05 = 210
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom_with_waste["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom_with_waste["details"]

            mock_query.side_effect = [header_mock, details_mock]

            result = service.explode_bom(
                client_id="TEST_CLIENT",
                parent_item_code="STYLE_WASTE",
                quantity=Decimal("100"),
                emit_event=False
            )

            fabric_component = next(
                c for c in result.components
                if c.component_item_code == "FABRIC001"
            )

            assert fabric_component.waste_percentage == Decimal("5")
            assert fabric_component.gross_required == Decimal("200")  # 100 * 2
            assert fabric_component.net_required == Decimal("210")    # 200 * 1.05

    def test_explosion_aggregation(self, mock_db_session, multi_order_bom):
        """
        Given 2 orders using same component
        When I aggregate requirements
        Then total is sum of individual requirements.
        """
        service = BOMService(mock_db_session)

        # Create two explosion results manually
        result1 = BOMExplosionResult(
            parent_item_code="STYLE001",
            quantity_requested=Decimal("100"),
            components=[
                BOMComponent(
                    component_item_code="THREAD001",
                    component_description="Thread",
                    gross_required=Decimal("5000"),
                    net_required=Decimal("5000"),
                    waste_percentage=Decimal("0"),
                    unit_of_measure="M",
                    component_type="TRIM"
                )
            ],
            total_components=1
        )

        result2 = BOMExplosionResult(
            parent_item_code="STYLE002",
            quantity_requested=Decimal("50"),
            components=[
                BOMComponent(
                    component_item_code="THREAD001",
                    component_description="Thread",
                    gross_required=Decimal("3750"),
                    net_required=Decimal("3750"),
                    waste_percentage=Decimal("0"),
                    unit_of_measure="M",
                    component_type="TRIM"
                )
            ],
            total_components=1
        )

        aggregated = service.aggregate_component_requirements([result1, result2])

        # THREAD001 used by both styles: 5000 + 3750 = 8750
        assert "THREAD001" in aggregated
        assert aggregated["THREAD001"] == Decimal("8750")


class TestBOMExplosionEdgeCases:
    """Edge case tests for BOM explosion."""

    def test_explosion_zero_quantity(self, mock_db_session, sample_bom):
        """
        Exploding with quantity 0 returns 0 for all components.

        Edge case: Planning with zero quantity should not fail.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            mock_query.side_effect = [header_mock, details_mock]

            result = service.explode_bom(
                client_id="TEST_CLIENT",
                parent_item_code="STYLE001",
                quantity=Decimal("0"),
                emit_event=False
            )

            for comp in result.components:
                assert comp.net_required == Decimal("0")
                assert comp.gross_required == Decimal("0")

    def test_explosion_missing_bom(self, mock_db_session):
        """
        Missing BOM raises BOMExplosionError.

        Given non-existent item code
        When I attempt explosion
        Then BOMExplosionError is raised with clear message.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(BOMExplosionError) as exc_info:
                service.explode_bom(
                    client_id="TEST_CLIENT",
                    parent_item_code="NONEXISTENT",
                    quantity=Decimal("100")
                )

            assert "No active BOM found" in str(exc_info.value)
            assert exc_info.value.parent_item == "NONEXISTENT"

    def test_explosion_inactive_bom(self, mock_db_session, inactive_bom):
        """
        Inactive BOM is not used.

        Given an inactive BOM
        When I attempt explosion
        Then BOMExplosionError is raised.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            # Return None because query filters is_active == True
            mock_query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(BOMExplosionError):
                service.explode_bom(
                    client_id="TEST_CLIENT",
                    parent_item_code="INACTIVE_STYLE",
                    quantity=Decimal("100")
                )

    def test_explosion_decimal_precision(self, mock_db_session, sample_bom_with_waste):
        """
        Test decimal precision is maintained through calculations.

        Verify fractional quantities and waste percentages are calculated precisely.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom_with_waste["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom_with_waste["details"]

            mock_query.side_effect = [header_mock, details_mock]

            result = service.explode_bom(
                client_id="TEST_CLIENT",
                parent_item_code="STYLE_WASTE",
                quantity=Decimal("33"),
                emit_event=False
            )

            fabric = next(c for c in result.components if c.component_item_code == "FABRIC001")

            # gross = 33 * 2 = 66
            # net = 66 * 1.05 = 69.3
            assert fabric.gross_required == Decimal("66")
            assert fabric.net_required == Decimal("69.30")

    def test_explosion_large_quantity(self, mock_db_session, sample_bom):
        """
        Test explosion with large quantities.

        Performance target: Should handle orders of 100,000+ units.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            mock_query.side_effect = [header_mock, details_mock]

            result = service.explode_bom(
                client_id="TEST_CLIENT",
                parent_item_code="STYLE001",
                quantity=Decimal("100000"),
                emit_event=False
            )

            # Verify no overflow or precision loss
            assert result.quantity_requested == Decimal("100000")
            for comp in result.components:
                assert comp.gross_required > 0
                assert comp.net_required >= comp.gross_required

    def test_explosion_multiple_orders_same_style(self, mock_db_session, sample_bom):
        """
        Test exploding multiple orders for same style aggregates correctly.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            # Multiple explosion calls will reuse the mock setup
            mock_query.side_effect = [
                header_mock, details_mock,
                header_mock, details_mock,
                header_mock, details_mock
            ]

            # Explode 3 orders of same style
            results = []
            for qty in [100, 200, 150]:
                r = service.explode_bom(
                    client_id="TEST_CLIENT",
                    parent_item_code="STYLE001",
                    quantity=Decimal(str(qty)),
                    emit_event=False
                )
                results.append(r)

            # Aggregate
            aggregated = service.aggregate_component_requirements(results)

            # FABRIC001: qty_per=0.5, total_qty=450 -> 225
            # With 0% waste: 225 * 1.0 = 225
            # Note: Based on sample_bom fixture, FABRIC001 has 0% waste
            assert aggregated["FABRIC001"] == Decimal("225")

    def test_explosion_bom_no_components(self, mock_db_session):
        """
        Test BOM with header but no components raises error.
        """
        service = BOMService(mock_db_session)

        header = MagicMock(spec=CapacityBOMHeader)
        header.id = 99
        header.client_id = "TEST_CLIENT"
        header.parent_item_code = "EMPTY_BOM"
        header.is_active = True

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = header

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = []  # No components

            mock_query.side_effect = [header_mock, details_mock]

            with pytest.raises(BOMExplosionError) as exc_info:
                service.explode_bom(
                    client_id="TEST_CLIENT",
                    parent_item_code="EMPTY_BOM",
                    quantity=Decimal("100")
                )

            assert "has no components" in str(exc_info.value)


class TestBOMExplosionMultipleBOMs:
    """Test scenarios with multiple BOMs."""

    def test_explode_multiple_orders(self, mock_db_session):
        """
        Test explode_multiple_orders method.

        Given multiple orders with different styles
        When I explode all
        Then I get results keyed by style code.
        """
        service = BOMService(mock_db_session)

        # Create mock BOMs for two styles
        header1 = MagicMock(spec=CapacityBOMHeader)
        header1.id = 1
        header1.parent_item_code = "STYLE001"
        header1.is_active = True

        detail1 = MagicMock(spec=CapacityBOMDetail)
        detail1.component_item_code = "COMP1"
        detail1.quantity_per = Decimal("1")
        detail1.waste_percentage = Decimal("0")
        detail1.component_description = "Component 1"
        detail1.unit_of_measure = "EA"
        detail1.component_type = "TRIM"

        header2 = MagicMock(spec=CapacityBOMHeader)
        header2.id = 2
        header2.parent_item_code = "STYLE002"
        header2.is_active = True

        detail2 = MagicMock(spec=CapacityBOMDetail)
        detail2.component_item_code = "COMP2"
        detail2.quantity_per = Decimal("2")
        detail2.waste_percentage = Decimal("0")
        detail2.component_description = "Component 2"
        detail2.unit_of_measure = "EA"
        detail2.component_type = "FABRIC"

        orders = [
            {"style_code": "STYLE001", "quantity": 100},
            {"style_code": "STYLE002", "quantity": 50}
        ]

        with patch.object(service, 'explode_bom') as mock_explode:
            mock_explode.side_effect = [
                BOMExplosionResult(
                    parent_item_code="STYLE001",
                    quantity_requested=Decimal("100"),
                    components=[
                        BOMComponent("COMP1", "Component 1", Decimal("100"),
                                   Decimal("100"), Decimal("0"), "EA", "TRIM")
                    ],
                    total_components=1
                ),
                BOMExplosionResult(
                    parent_item_code="STYLE002",
                    quantity_requested=Decimal("50"),
                    components=[
                        BOMComponent("COMP2", "Component 2", Decimal("100"),
                                   Decimal("100"), Decimal("0"), "EA", "FABRIC")
                    ],
                    total_components=1
                )
            ]

            results = service.explode_multiple_orders("TEST_CLIENT", orders)

            assert "STYLE001" in results
            assert "STYLE002" in results
            assert results["STYLE001"].quantity_requested == Decimal("100")
            assert results["STYLE002"].quantity_requested == Decimal("50")


class TestBOMExplosionEvents:
    """Test BOM explosion event emission."""

    def test_explosion_emits_event(self, mock_db_session, sample_bom):
        """
        Test BOMExploded event is emitted on successful explosion.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            mock_query.side_effect = [header_mock, details_mock]

            with patch('backend.services.capacity.bom_service.event_bus') as mock_bus:
                service.explode_bom(
                    client_id="TEST_CLIENT",
                    parent_item_code="STYLE001",
                    quantity=Decimal("100"),
                    emit_event=True
                )

                mock_bus.collect.assert_called_once()
                event = mock_bus.collect.call_args[0][0]
                assert event.parent_item_code == "STYLE001"
                assert event.quantity_requested == Decimal("100")
                assert event.components_count == 3

    def test_explosion_no_event_when_disabled(self, mock_db_session, sample_bom):
        """
        Test event not emitted when emit_event=False.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            mock_query.side_effect = [header_mock, details_mock]

            with patch('backend.services.capacity.bom_service.event_bus') as mock_bus:
                service.explode_bom(
                    client_id="TEST_CLIENT",
                    parent_item_code="STYLE001",
                    quantity=Decimal("100"),
                    emit_event=False
                )

                mock_bus.collect.assert_not_called()


class TestBOMStructure:
    """Test get_bom_structure method."""

    def test_get_bom_structure(self, mock_db_session, sample_bom):
        """
        Test getting BOM structure without explosion.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            header_mock = MagicMock()
            header_mock.filter.return_value.first.return_value = sample_bom["header"]

            details_mock = MagicMock()
            details_mock.filter.return_value.all.return_value = sample_bom["details"]

            mock_query.side_effect = [header_mock, details_mock]

            structure = service.get_bom_structure(
                client_id="TEST_CLIENT",
                parent_item_code="STYLE001"
            )

            assert structure is not None
            assert structure["parent_item_code"] == "STYLE001"
            assert len(structure["components"]) == 3
            assert structure["is_active"] == True

    def test_get_bom_structure_not_found(self, mock_db_session):
        """
        Test get_bom_structure returns None for non-existent BOM.
        """
        service = BOMService(mock_db_session)

        with patch.object(service.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = None

            structure = service.get_bom_structure(
                client_id="TEST_CLIENT",
                parent_item_code="NONEXISTENT"
            )

            assert structure is None
