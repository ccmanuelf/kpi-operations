import pytest

from backend.orm.delay_taxonomy import (
    SELECTABLE_DELAY_REASONS,
    DelayClassificationEnum,
    JustifiedDelayReasonEnum,
)
from backend.orm.work_order import WorkOrder


def test_classification_enum_has_exactly_two_members():
    assert {c.value for c in DelayClassificationEnum} == {"justified", "unjustified"}


def test_reason_enum_exact_members():
    assert {r.value for r in JustifiedDelayReasonEnum} == {
        "customer_request",
        "customer_change_order",
        "material_supplier_delay",
        "force_majeure",
        "upstream_hold",
        "other",
    }
    assert SELECTABLE_DELAY_REASONS == [r.value for r in JustifiedDelayReasonEnum]


def _wo(**kwargs):
    return WorkOrder(
        work_order_id=kwargs.pop("work_order_id", "WO-DLY-T1"),
        client_id="C1",
        style_model=kwargs.pop("style_model", "STYLE-1"),
        planned_quantity=kwargs.pop("planned_quantity", 100),
        status=kwargs.pop("status", "IN_PROGRESS"),
        **kwargs,
    )
    # NOTE: WorkOrder's NOT-NULL-without-default constructor columns are
    # work_order_id, client_id, style_model, planned_quantity (status has a
    # Python-level default). Included all four so this helper matches the
    # DowntimeEntry precedent (provide every required column explicitly).


def test_orm_rejects_invalid_classification_but_allows_none_and_valid():
    with pytest.raises(ValueError, match="delay_classification"):
        _wo(delay_classification="excused")
    assert _wo(work_order_id="WO-DLY-T2", delay_classification=None).delay_classification is None
    assert _wo(work_order_id="WO-DLY-T3", delay_classification="justified").delay_classification == "justified"


def test_orm_rejects_invalid_reason_but_allows_none_and_valid():
    with pytest.raises(ValueError, match="justified_delay_reason"):
        _wo(justified_delay_reason="because")
    assert (
        _wo(work_order_id="WO-DLY-T4", justified_delay_reason="force_majeure").justified_delay_reason == "force_majeure"
    )
