import pytest
from pydantic import ValidationError

from backend.schemas.downtime import DowntimeEventCreate, DowntimeEventUpdate

BASE = {
    "client_id": "C1",
    "shift_date": "2026-07-01",
    "downtime_reason": "MATERIAL_SHORTAGE",
    "downtime_duration_minutes": 30,
}


def test_create_autodefaults_category_from_reason():
    m = DowntimeEventCreate(**BASE)
    assert m.root_cause_category is not None
    assert m.root_cause_category.value == "materials"


def test_create_explicit_category_is_preserved():
    m = DowntimeEventCreate(**BASE, root_cause_category="scheduling")
    assert m.root_cause_category.value == "scheduling"


def test_create_rejects_unknown_category_with_422_style_error():
    with pytest.raises(ValidationError):
        DowntimeEventCreate(**BASE, root_cause_category="Breakdown")


def test_create_accepts_uncategorized_for_csv_backcompat():
    m = DowntimeEventCreate(**BASE, root_cause_category="uncategorized")
    assert m.root_cause_category.value == "uncategorized"


def test_update_none_means_no_change_not_autodefault():
    u = DowntimeEventUpdate(downtime_reason="MAINTENANCE")
    assert u.root_cause_category is None


def test_from_legacy_csv_maps_operator_unavailable_reason():
    """Final-review Finding 2: category_mapping lacked the OPERATOR_UNAVAILABLE
    enum member, so a legacy CSV row with downtime_reason=OPERATOR_UNAVAILABLE
    silently coerced to OTHER/other instead of OPERATOR_UNAVAILABLE/attendance."""
    m = DowntimeEventCreate.from_legacy_csv(
        {
            "client_id": "C1",
            "shift_date": "2026-07-01",
            "downtime_reason": "OPERATOR_UNAVAILABLE",
            "downtime_duration_minutes": 30,
        }
    )
    assert m.downtime_reason.value == "OPERATOR_UNAVAILABLE"
    assert m.root_cause_category.value == "attendance"
