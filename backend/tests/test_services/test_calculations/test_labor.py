"""Phase 1 dual-view orchestrators: Absenteeism, Attendance, Bradford Factor."""

from decimal import Decimal

import pytest

from backend.services.calculations.labor import (
    AbsenteeismInputs,
    AttendanceInputs,
    BradfordInputs,
    calculate_absenteeism_rate,
    calculate_attendance_rate,
    calculate_bradford_factor,
)


class TestAbsenteeism:
    def test_standard_mode_textbook(self):
        # 8 absent / 160 scheduled = 5%
        inputs = AbsenteeismInputs(
            total_scheduled_hours=Decimal("160"),
            total_absent_hours=Decimal("8"),
        )
        assert calculate_absenteeism_rate(inputs).value == Decimal("5.00")

    def test_zero_scheduled_yields_zero(self):
        inputs = AbsenteeismInputs(total_scheduled_hours=Decimal("0"), total_absent_hours=Decimal("0"))
        assert calculate_absenteeism_rate(inputs).value == Decimal("0")

    def test_absent_exceeds_scheduled_raises(self):
        with pytest.raises(ValueError, match="total_absent_hours cannot exceed total_scheduled_hours"):
            calculate_absenteeism_rate(
                AbsenteeismInputs(
                    total_scheduled_hours=Decimal("100"),
                    total_absent_hours=Decimal("110"),
                )
            )


class TestAttendance:
    def test_standard_mode_textbook(self):
        # 18 / 20 = 90%
        result = calculate_attendance_rate(AttendanceInputs(days_present=18, total_scheduled_days=20))
        assert result.value == Decimal("90.00")

    def test_zero_scheduled_yields_zero(self):
        assert calculate_attendance_rate(AttendanceInputs(days_present=0, total_scheduled_days=0)).value == Decimal("0")


class TestBradfordFactor:
    def test_standard_mode_textbook(self):
        # 3 spells, 5 days → 9 × 5 = 45 (low risk)
        inputs = BradfordInputs(spells=3, total_days_absent=5)
        assert calculate_bradford_factor(inputs).value == 45

    def test_no_absences_yields_zero(self):
        assert calculate_bradford_factor(BradfordInputs(spells=0, total_days_absent=0)).value == 0

    def test_high_risk_band(self):
        # 5 spells, 10 days → 25 × 10 = 250 (formal action band)
        assert calculate_bradford_factor(BradfordInputs(spells=5, total_days_absent=10)).value == 250
