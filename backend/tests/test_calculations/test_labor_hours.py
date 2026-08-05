from datetime import date
from decimal import Decimal

import pytest

from backend.calculations.labor_hours import (
    available_for_efficiency_hours,
    billed_hours,
    effective_labor_class,
    summarize_labor_hours,
    validate_allocations,
    validate_ot_split,
)
from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
from backend.tests.fixtures.factories import TestDataFactory


class TestOTSplit:
    def test_all_none_is_unsplit(self):
        assert validate_ot_split(None, None, None, Decimal("8.00")) is None

    def test_partial_defaults_to_zero_and_must_sum(self):
        # normal=8 supplied alone against actual 8: double/triple default 0 -> 8+0+0 == 8 OK
        assert validate_ot_split(Decimal("8.00"), None, None, Decimal("8.00")) == (
            Decimal("8.00"),
            Decimal("0"),
            Decimal("0"),
        )

    def test_sum_mismatch_raises(self):
        with pytest.raises(ValueError, match="sum"):
            validate_ot_split(Decimal("8.00"), Decimal("1.00"), None, Decimal("8.00"))

    def test_split_without_actual_raises(self):
        with pytest.raises(ValueError, match="actual_hours"):
            validate_ot_split(Decimal("8.00"), None, None, None)

    def test_full_split_ok(self):
        assert validate_ot_split(Decimal("8.00"), Decimal("2.00"), Decimal("1.00"), Decimal("11.00")) == (
            Decimal("8.00"),
            Decimal("2.00"),
            Decimal("1.00"),
        )

    def test_explicit_zero_tier_preserves_scale(self):
        # Decimal("0.00") is falsy — an `or`-based default would collapse it to
        # Decimal("0"); identity check must preserve the submitted scale.
        result = validate_ot_split(Decimal("0.00"), Decimal("4.00"), Decimal("4.00"), Decimal("8.00"))
        assert result == (Decimal("0.00"), Decimal("4.00"), Decimal("4.00"))
        assert str(result[0]) == "0.00"


class TestAllocations:
    def test_duplicate_category_raises(self):
        with pytest.raises(ValueError, match="duplicate"):
            validate_allocations([("training", Decimal("1.00")), ("training", Decimal("2.00"))], Decimal("8.00"))

    def test_sum_over_actual_raises(self):
        with pytest.raises(ValueError, match="exceed"):
            validate_allocations([("billed_production", Decimal("9.00"))], Decimal("8.00"))

    def test_nonpositive_hours_raises(self):
        with pytest.raises(ValueError, match="hours"):
            validate_allocations([("meeting", Decimal("0"))], Decimal("8.00"))

    def test_partial_allocation_ok(self):
        validate_allocations([("billed_production", Decimal("5.00"))], Decimal("8.00"))

    def test_allocations_without_actual_hours_raises_dedicated_message(self):
        """Fix round 3, Minor: distinct from the "exceed" message — a 0/unset
        actual_hours means there was never a real value to exceed."""
        with pytest.raises(ValueError, match="^allocations require actual_hours$"):
            validate_allocations([("training", Decimal("1.00"))], Decimal("0"))

    def test_empty_allocations_against_zero_actual_hours_ok(self):
        """Clearing the ledger (empty list) must not trip the new require-actual_hours
        check — there's nothing to require actual_hours for."""
        validate_allocations([], Decimal("0"))


class TestDerived:
    def test_billed_hours_sums_billable_only(self):
        allocs = [
            ("billed_production", Decimal("5.00")),
            ("unbilled_production", Decimal("1.00")),
            ("training", Decimal("1.00")),
        ]
        assert billed_hours(allocs) == Decimal("5.00")

    def test_available_subtracts_only_allocated_nonproductive(self):
        # actual 8; allocated: 5 billed_prod (productive), 1 training + 0.5 meeting (non-productive);
        # 1.5 unallocated counts productive-unbilled -> available = 8 - 1.5 = 6.5
        allocs = [
            ("billed_production", Decimal("5.00")),
            ("training", Decimal("1.00")),
            ("meeting", Decimal("0.50")),
        ]
        assert available_for_efficiency_hours(Decimal("8.00"), allocs) == Decimal("6.50")

    def test_available_with_no_allocations_is_actual(self):
        assert available_for_efficiency_hours(Decimal("8.00"), []) == Decimal("8.00")

    def test_effective_labor_class_resolution(self):
        assert effective_labor_class("indirect", "direct") == "indirect"
        assert effective_labor_class(None, "direct") == "direct"
        assert effective_labor_class(None, None) is None


class TestSummarizeLaborHours:
    def test_summary_with_derivations(self, db_session):
        """Seed one client, 2 employees (E1 direct, E2 indirect), 3 entries:
        - A (E1, direct): scheduled 8, actual 10, split 8/2/0,
          allocations billed_production 7 + training 1
          -> billed 7, available 10-1=9
        - B (E2, indirect): scheduled 8, actual 8, unsplit,
          allocations billed_production 8 -> billed 8, available 8
        - C (E1 but labor_class_override='indirect'): scheduled 8, actual 8,
          split 8/0/0, NO allocations -> billed 0, available 8 (conservative)

        totals: scheduled 24, actual 26, normal 16, double 2, triple 0,
                billed 15, available 25
        by_labor_class: direct {actual 10, billed 7, available 9}   # only A
                        indirect {actual 16, billed 8, available 16} # B + C (override)
                        unclassified {actual 0, billed 0, available 0}
        by_category: {billed_production: 15, training: 1}
        entry_counts: {total 3, with_split 2, with_allocations 2}
        """
        client = TestDataFactory.create_client(db_session, client_id="LH-SUM-CL")
        shift = TestDataFactory.create_shift(db_session, client_id=client.client_id)

        e1 = TestDataFactory.create_employee(db_session, client_id=client.client_id, employee_name="E1 Direct")
        e1.labor_class = "direct"
        e2 = TestDataFactory.create_employee(db_session, client_id=client.client_id, employee_name="E2 Indirect")
        e2.labor_class = "indirect"
        db_session.flush()

        shift_date = date(2026, 8, 1)

        entry_a = TestDataFactory.create_attendance_entry(
            db_session,
            employee_id=e1.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("10.00"),
        )
        entry_a.normal_hours = Decimal("8.00")
        entry_a.double_hours = Decimal("2.00")
        entry_a.triple_hours = Decimal("0.00")
        entry_a.hour_allocations = [
            AttendanceHourAllocation(category="billed_production", hours=Decimal("7.00")),
            AttendanceHourAllocation(category="training", hours=Decimal("1.00")),
        ]

        entry_b = TestDataFactory.create_attendance_entry(
            db_session,
            employee_id=e2.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        entry_b.hour_allocations = [
            AttendanceHourAllocation(category="billed_production", hours=Decimal("8.00")),
        ]

        entry_c = TestDataFactory.create_attendance_entry(
            db_session,
            employee_id=e1.employee_id,
            client_id=client.client_id,
            shift_id=shift.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        entry_c.normal_hours = Decimal("8.00")
        entry_c.double_hours = Decimal("0.00")
        entry_c.triple_hours = Decimal("0.00")
        entry_c.labor_class_override = "indirect"

        db_session.commit()

        result = summarize_labor_hours(db_session, ["LH-SUM-CL"], shift_date, shift_date)

        assert result["totals"] == {
            "scheduled": Decimal("24.00"),
            "actual": Decimal("26.00"),
            "normal": Decimal("16.00"),
            "double": Decimal("2.00"),
            "triple": Decimal("0.00"),
            "billed": Decimal("15.00"),
            "available_for_efficiency": Decimal("25.00"),
        }
        assert result["by_labor_class"] == {
            "direct": {
                "actual": Decimal("10.00"),
                "billed": Decimal("7.00"),
                "available_for_efficiency": Decimal("9.00"),
            },
            "indirect": {
                "actual": Decimal("16.00"),
                "billed": Decimal("8.00"),
                "available_for_efficiency": Decimal("16.00"),
            },
            "unclassified": {
                "actual": Decimal("0"),
                "billed": Decimal("0"),
                "available_for_efficiency": Decimal("0"),
            },
        }
        assert result["by_category"] == {
            "billed_production": Decimal("15.00"),
            "training": Decimal("1.00"),
        }
        assert result["entry_counts"] == {"total": 3, "with_split": 2, "with_allocations": 2}

    def test_empty_window_returns_zeroed_totals(self, db_session):
        TestDataFactory.create_client(db_session, client_id="LH-EMPTY-CL")
        db_session.commit()

        result = summarize_labor_hours(db_session, ["LH-EMPTY-CL"], date(2026, 8, 1), date(2026, 8, 1))

        assert result["totals"] == {
            "scheduled": Decimal("0"),
            "actual": Decimal("0"),
            "normal": Decimal("0"),
            "double": Decimal("0"),
            "triple": Decimal("0"),
            "billed": Decimal("0"),
            "available_for_efficiency": Decimal("0"),
        }
        assert result["by_labor_class"] == {
            "direct": {"actual": Decimal("0"), "billed": Decimal("0"), "available_for_efficiency": Decimal("0")},
            "indirect": {"actual": Decimal("0"), "billed": Decimal("0"), "available_for_efficiency": Decimal("0")},
            "unclassified": {"actual": Decimal("0"), "billed": Decimal("0"), "available_for_efficiency": Decimal("0")},
        }
        assert result["by_category"] == {}
        assert result["entry_counts"] == {"total": 0, "with_split": 0, "with_allocations": 0}

    def test_client_ids_none_means_all_clients(self, db_session):
        client_one = TestDataFactory.create_client(db_session, client_id="LH-MULTI-ONE")
        client_two = TestDataFactory.create_client(db_session, client_id="LH-MULTI-TWO")
        shift_one = TestDataFactory.create_shift(db_session, client_id=client_one.client_id)
        shift_two = TestDataFactory.create_shift(db_session, client_id=client_two.client_id)
        emp_one = TestDataFactory.create_employee(db_session, client_id=client_one.client_id)
        emp_two = TestDataFactory.create_employee(db_session, client_id=client_two.client_id)

        shift_date = date(2026, 8, 1)
        TestDataFactory.create_attendance_entry(
            db_session,
            employee_id=emp_one.employee_id,
            client_id=client_one.client_id,
            shift_id=shift_one.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        TestDataFactory.create_attendance_entry(
            db_session,
            employee_id=emp_two.employee_id,
            client_id=client_two.client_id,
            shift_id=shift_two.shift_id,
            shift_date=shift_date,
            scheduled_hours=Decimal("8.00"),
            actual_hours=Decimal("8.00"),
        )
        db_session.commit()

        result_all = summarize_labor_hours(db_session, None, shift_date, shift_date)
        assert result_all["totals"]["actual"] == Decimal("16.00")
        assert result_all["entry_counts"]["total"] == 2

        result_filtered = summarize_labor_hours(db_session, ["LH-MULTI-ONE"], shift_date, shift_date)
        assert result_filtered["totals"]["actual"] == Decimal("8.00")
        assert result_filtered["entry_counts"]["total"] == 1
