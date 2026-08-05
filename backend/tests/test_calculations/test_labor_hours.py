from decimal import Decimal

import pytest

from backend.calculations.labor_hours import (
    available_for_efficiency_hours,
    billed_hours,
    effective_labor_class,
    validate_allocations,
    validate_ot_split,
)


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
