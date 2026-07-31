import pytest
from backend.orm.downtime_taxonomy import (
    DEFAULT_CATEGORY_BY_REASON,
    PLANNED_DOWNTIME_REASONS,
    SELECTABLE_CATEGORIES,
    DowntimeCategoryEnum,
    DowntimeReasonEnum,
)
from backend.orm.downtime_entry import DowntimeEntry


def test_reason_enum_has_eight_members_including_operator_unavailable():
    assert {r.value for r in DowntimeReasonEnum} == {
        "EQUIPMENT_FAILURE",
        "MATERIAL_SHORTAGE",
        "SETUP_CHANGEOVER",
        "QUALITY_HOLD",
        "MAINTENANCE",
        "POWER_OUTAGE",
        "OTHER",
        "OPERATOR_UNAVAILABLE",
    }
    assert len(list(DowntimeReasonEnum)) == 8


def test_category_enum_values():
    assert {c.value for c in DowntimeCategoryEnum} == {
        "machine",
        "materials",
        "scheduling",
        "attendance",
        "other",
        "uncategorized",
    }


def test_selectable_categories_exclude_uncategorized():
    assert "uncategorized" not in SELECTABLE_CATEGORIES
    assert len(SELECTABLE_CATEGORIES) == 5


def test_default_mapping_covers_every_reason_and_targets_valid_categories():
    assert set(DEFAULT_CATEGORY_BY_REASON) == {r.value for r in DowntimeReasonEnum}
    valid = {c.value for c in DowntimeCategoryEnum}
    assert set(DEFAULT_CATEGORY_BY_REASON.values()) <= valid
    assert "uncategorized" not in DEFAULT_CATEGORY_BY_REASON.values()


def test_default_mapping_exact_values():
    assert DEFAULT_CATEGORY_BY_REASON == {
        "EQUIPMENT_FAILURE": "machine",
        "MAINTENANCE": "machine",
        "MATERIAL_SHORTAGE": "materials",
        "SETUP_CHANGEOVER": "scheduling",
        "OPERATOR_UNAVAILABLE": "attendance",
        "QUALITY_HOLD": "other",
        "POWER_OUTAGE": "other",
        "OTHER": "other",
    }


def test_planned_reasons():
    assert PLANNED_DOWNTIME_REASONS == frozenset({"MAINTENANCE", "SETUP_CHANGEOVER"})


def test_orm_rejects_invalid_reason():
    with pytest.raises(ValueError, match="downtime_reason"):
        DowntimeEntry(
            downtime_entry_id="DT-T-0001",
            client_id="C1",
            shift_date=__import__("datetime").datetime(2026, 7, 1, 6, 0),
            downtime_reason="CHANGEOVER",  # the old seeder rogue value
            downtime_duration_minutes=30,
        )


def test_orm_rejects_invalid_category_but_allows_none():
    from datetime import datetime

    with pytest.raises(ValueError, match="root_cause_category"):
        DowntimeEntry(
            downtime_entry_id="DT-T-0002",
            client_id="C1",
            shift_date=datetime(2026, 7, 1, 6, 0),
            downtime_reason="OTHER",
            downtime_duration_minutes=30,
            root_cause_category="Breakdown",  # phantom legacy value
        )
    ok = DowntimeEntry(
        downtime_entry_id="DT-T-0003",
        client_id="C1",
        shift_date=datetime(2026, 7, 1, 6, 0),
        downtime_reason="OTHER",
        downtime_duration_minutes=30,
        root_cause_category=None,
    )
    assert ok.root_cause_category is None


def test_orm_accepts_uncategorized_and_all_valid_pairs():
    from datetime import datetime

    for i, (reason, category) in enumerate(list(DEFAULT_CATEGORY_BY_REASON.items()) + [("OTHER", "uncategorized")]):
        e = DowntimeEntry(
            downtime_entry_id=f"DT-T-1{i:03d}",
            client_id="C1",
            shift_date=datetime(2026, 7, 1, 6, 0),
            downtime_reason=reason,
            downtime_duration_minutes=15,
            root_cause_category=category,
        )
        assert e.root_cause_category == category
