from datetime import date, datetime

from backend.calculations.otd import is_late
from backend.orm.work_order import WorkOrder

AS_OF = date(2026, 8, 1)


def _wo(**kwargs):
    return WorkOrder(
        work_order_id=kwargs.pop("work_order_id", "WO-LATE-T"),
        client_id="C1",
        style_model=kwargs.pop("style_model", "STYLE-1"),
        planned_quantity=kwargs.pop("planned_quantity", 100),
        status=kwargs.pop("status", "IN_PROGRESS"),
        **kwargs,
    )
    # Align with WorkOrder's NOT-NULL-without-default constructor fields
    # (work_order_id, client_id, style_model, planned_quantity) per Task 1's
    # _wo helper in test_delay_taxonomy.py.


def test_delivered_after_planned_is_late():
    wo = _wo(planned_ship_date=datetime(2026, 7, 10), actual_delivery_date=datetime(2026, 7, 15))
    assert is_late(wo, AS_OF) is True


def test_delivered_on_or_before_planned_is_not_late():
    wo = _wo(planned_ship_date=datetime(2026, 7, 10), actual_delivery_date=datetime(2026, 7, 10))
    assert is_late(wo, AS_OF) is False


def test_undelivered_past_due_is_late():
    wo = _wo(planned_ship_date=datetime(2026, 7, 10), actual_delivery_date=None)
    assert is_late(wo, AS_OF) is True


def test_undelivered_not_yet_due_is_not_late():
    wo = _wo(planned_ship_date=datetime(2026, 8, 20), actual_delivery_date=None)
    assert is_late(wo, AS_OF) is False


def test_falls_back_to_required_date():
    wo = _wo(planned_ship_date=None, required_date=datetime(2026, 7, 10), actual_delivery_date=datetime(2026, 7, 20))
    assert is_late(wo, AS_OF) is True


def test_no_inferable_date_is_not_late():
    wo = _wo(planned_ship_date=None, required_date=None, actual_delivery_date=datetime(2026, 7, 20))
    # inference_source == "none" (no calculated fallback inputs either) -> not late
    assert is_late(wo, AS_OF) is False


def test_undelivered_due_exactly_today_is_not_late():
    """Boundary pin: inferred date == midnight of as_of -> NOT late (strict <)."""
    wo = _wo(planned_ship_date=datetime(2026, 8, 1, 0, 0), actual_delivery_date=None)
    assert is_late(wo, AS_OF) is False


def test_single_lateness_definition_guard():
    """Spec §4: is_late in calculations/otd.py is the ONLY lateness definition.
    Both the update-path invariants and the metrics must import it."""
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parents[2]
    crud_src = (backend_root / "crud" / "work_order.py").read_text(encoding="utf-8")
    assert "from backend.calculations.otd import is_late" in crud_src
    otd_src = (backend_root / "calculations" / "otd.py").read_text(encoding="utf-8")
    assert otd_src.count("def is_late(") == 1
