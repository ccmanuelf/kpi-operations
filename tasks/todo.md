# Tasks

## NEXT: cross-tenant attendance rows (found 2026-08-30, verified)

`POST /api/attendance/bulk` accepts an employee belonging to a DIFFERENT client
and writes the row.

Reproduction, measured against the seeded contract database:

    body [{client_id: "DEMO-HOURLY", employee_id: 1, shift_date: <seed>, scheduled_hours: 8}]
    employee 1's client_id_assigned is 'DEMO-PIECE'
    -> 201, successful=1, failed=0
    -> ATTENDANCE_ENTRY row written with (client_id='DEMO-HOURLY', employee_id=1)

`bulk_create_attendance_records` performs no check that the employee belongs to
the row's client. FK enforcement would not catch it either: the mismatch is
COMPOSITE (both ids exist, they just do not belong together). Same tenancy
class as the uniform client-scope work in #144.

Found by the contract harness: the route only started running when write
capture gave it a body, and the id-consistency spec written to avoid the
mismatch is what made the acceptance visible.

PLAN (own PR, agreed):
  * per row, require the employee's `client_id_assigned` to contain the row's
    `client_id`; otherwise that row fails with a tenancy error. The route is
    per-row and answers 201 regardless, so this belongs in the per-row error
    list rather than as a whole-request 4xx.
  * test: a cross-tenant row is rejected and NOT written
  * test: a same-tenant row still succeeds (or the first test passes on a
    route that rejects everything)
  * check the sibling write paths in crud/attendance.py for the same gap
