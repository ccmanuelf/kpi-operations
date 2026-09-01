"""The workforce data, asserted against a FULL seeded database.

Every one of these pins something that was WRONG at some point while this data
was being written, which is the only reason to write a dataset test rather
than trust the emitter:

  * shift_coverage counted one line's crew as the whole shift's -- all 224
    rows disagreed with the attendance they describe;
  * the same floater was handed two absences in the same shift, because the
    pool refilled for every line;
  * allocations had to sum to the hours actually worked, and never attach to
    an absence.
"""

from datetime import date

import pytest
from sqlalchemy import text

from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 21)


@pytest.fixture(scope="module")
def full_db(seed_engine_module):
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine_module.begin() as conn:
        materialize(conn, events, FULL)
    return seed_engine_module


def test_shift_coverage_reconciles_with_the_attendance_it_describes(full_db):
    """shift_coverage has no line column, so it must aggregate every line
    working that shift. Emitting per line made all 224 rows disagree."""
    with full_db.begin() as conn:
        wrong = conn.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT sc.coverage_id"
                "    FROM shift_coverage sc"
                "    JOIN (SELECT client_id, shift_id, DATE(shift_date) AS d,"
                "                 COUNT(*) AS req,"
                "                 SUM(CASE WHEN is_absent = 0 THEN 1 ELSE 0 END) AS act"
                "            FROM ATTENDANCE_ENTRY"
                "           GROUP BY client_id, shift_id, DATE(shift_date)) a"
                "      ON a.client_id = sc.client_id AND a.shift_id = sc.shift_id"
                "     AND a.d = DATE(sc.coverage_date)"
                "   WHERE sc.required_employees <> a.req OR sc.actual_employees <> a.act"
                ") AS mismatched"
            )
        ).scalar_one()
    assert wrong == 0, f"{wrong} shift_coverage rows disagree with attendance"


def test_no_floater_covers_two_absences_in_the_same_shift(full_db):
    """A person cannot cover two lines at once. The assignment sits inside the
    LINE loop, so without tracking commitments the pool refills per line."""
    with full_db.begin() as conn:
        double_booked = conn.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT floating_employee_id, DATE(shift_date) AS d, shift_id"
                "    FROM COVERAGE_ENTRY"
                "   GROUP BY floating_employee_id, DATE(shift_date), shift_id"
                "  HAVING COUNT(*) > 1"
                ") AS clashes"
            )
        ).scalar_one()
    assert double_booked == 0, f"{double_booked} floaters are in two places at once"


def test_coverage_only_ever_explains_a_real_absence(full_db):
    with full_db.begin() as conn:
        bogus = conn.execute(
            text(
                "SELECT COUNT(*) FROM COVERAGE_ENTRY c"
                "  JOIN ATTENDANCE_ENTRY e"
                "    ON e.employee_id = c.covered_employee_id"
                "   AND DATE(e.shift_date) = DATE(c.shift_date)"
                "   AND e.shift_id = c.shift_id"
                " WHERE e.is_absent = 0"
            )
        ).scalar_one()
    assert bogus == 0, "coverage names an employee the attendance stream marked present"


def test_the_labour_ledger_balances_and_never_books_an_absence(full_db):
    with full_db.begin() as conn:
        unbalanced = conn.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT e.attendance_entry_id, e.actual_hours AS worked,"
                "         SUM(al.hours) AS booked"
                "    FROM ATTENDANCE_ENTRY e"
                "    JOIN ATTENDANCE_HOUR_ALLOCATION al"
                "      ON al.attendance_entry_id = e.attendance_entry_id"
                "   GROUP BY e.attendance_entry_id, e.actual_hours"
                ") AS ledger"
                " WHERE ABS(ledger.worked - ledger.booked) > 0.001"
            )
        ).scalar_one()
        on_absent = conn.execute(
            text(
                "SELECT COUNT(*) FROM ATTENDANCE_HOUR_ALLOCATION al"
                "  JOIN ATTENDANCE_ENTRY e ON e.attendance_entry_id = al.attendance_entry_id"
                " WHERE e.is_absent = 1"
            )
        ).scalar_one()
        categories = {r[0] for r in conn.execute(text("SELECT DISTINCT category FROM ATTENDANCE_HOUR_ALLOCATION"))}
    assert unbalanced == 0, f"{unbalanced} entries whose allocations do not sum to hours worked"
    assert on_absent == 0, "hours booked against a day nobody worked"
    # BILLABLE_CATEGORIES and PRODUCTIVE_CATEGORIES are different subsets of
    # HourCategoryEnum; a day booked entirely to billed_production makes both
    # ratios 100% and demonstrates neither.
    assert len(categories) >= 3, f"only {sorted(categories)} allocated"
