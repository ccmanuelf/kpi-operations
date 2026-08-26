"""The one live Decimal hazard converted in Batch R4 (`ops_contracts.py`):
GET /api/my-shift/stats reads `total_units` off `func.sum(ProductionEntry.
units_produced)`, and MariaDB's `SUM()` returns DECIMAL regardless of the
summed column's own `Integer` type -- the SUM-Integer-to-Decimal class from
`e2e-sweep-remediation`. `units_produced` forwards that value unmodified, and
`efficiency` (`total_units / total_target * 100`) can inherit the same
Decimal. This is the narrow value-type assertion the task brief requires:
feed the model real `Decimal` values (as MariaDB/SQLAlchemy would produce),
and assert the JSON-serialized fields decode as native numbers, never a
Decimal-as-string. The golden master cannot check this at all -- it compares
key sets, never value types, by design (see `capture.py`'s `is_loose`
docstring), so a field silently reverted to `Decimal` would leave the whole
suite green. See `test_decimal_response_serialization.py` for the identical
pattern applied to a different task's models.
"""

import json
from decimal import Decimal

from backend.schemas.ops_contracts import MyShiftStatsResponse


def test_my_shift_stats_decimal_units_and_efficiency_serialize_as_numbers():
    """`units_produced` and `efficiency` are the two fields
    `get_my_shift_stats` (routes/my_shift.py) never `int(...)`-casts before
    returning -- unlike `downtime_minutes`/`defect_count`, which already are.
    Declaring them `int`/`float` (not `Decimal`) is what closes the leak:
    Pydantic coerces a `Decimal` input into the declared numeric type on
    validation instead of forwarding it as-is.
    """
    raw = dict(
        date="2026-08-25",
        shift_id=1,
        units_produced=Decimal("150"),
        efficiency=Decimal("83.30"),
        downtime_incidents=2,
        downtime_minutes=15,
        quality_checks=5,
        defect_count=1,
    )

    dumped = json.loads(MyShiftStatsResponse(**raw).model_dump_json())

    for field in ("units_produced", "efficiency"):
        value = dumped[field]
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"MyShiftStatsResponse.{field} serialized as {value!r} ({type(value).__name__}), "
            "expected a JSON number -- a Decimal-typed field regressed back in."
        )

    assert dumped["units_produced"] == 150
    assert dumped["efficiency"] == 83.3
