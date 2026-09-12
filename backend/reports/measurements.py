"""Telling "measured zero" apart from "never measured".

Both generators averaged stored measurement columns with `float(x or 0)`, which
counts a NULL as a contributing zero. For `ProductionEntry.efficiency_percentage`
and `performance_percentage` that is every row in every deployment -- nothing
writes those columns except test fixtures -- so the comprehensive report printed
"0.0% / At Risk / Variance -85.0%" for two headline KPIs, which reads as a
catastrophic result rather than an absent measurement.

The pivot engine already draws this distinction and says so out loud: its
production dataset counts `excluded_entries` for rows it cannot compute from, and
its registry comment is explicit that a missing input is "counted, never
guessed". This module is that rule for the document generators.

It is also the rule the generators already follow elsewhere, just inconsistently:
the Excel OTD block omits itself when no orders were delivered, and the
labour-hours block omits itself when no attendance rows exist, both with tests.
A measurement nobody recorded deserves the same treatment as a window nobody
delivered in.
"""

from typing import Any, List, Sequence


def recorded(entries: Sequence[Any], attribute: str) -> List[float]:
    """The values actually present for `attribute`, with NULLs dropped.

    Averaging over this rather than over `len(entries)` matters when a column is
    only partly populated: the rows that carry no measurement did not measure
    zero, and including them as zeros drags the average toward a number nobody
    observed.
    """
    values = []
    for entry in entries:
        value = getattr(entry, attribute, None)
        if value is not None:
            values.append(float(value))
    return values


def absence_note(entries: Sequence[Any], attribute: str, label: str) -> dict:
    """What a detail block says when the rows exist but the measurement does not.

    Deliberately NOT the generators' existing "No data available for this period /
    Please ensure data has been entered for the selected date range". That
    sentence is false here and it blames the reader: the production entries were
    entered, and entering more of them would change nothing, because the column
    they would populate is one no write path in the application sets.
    """
    return {
        "Status": f"{label} was not recorded for this period",
        "Note": (
            f"{len(entries)} production entries cover this range, but none carry a"
            f" {label.lower()} measurement, so no average can be reported."
        ),
    }
