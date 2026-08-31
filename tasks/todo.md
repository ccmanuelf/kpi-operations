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


## FOUND, not fixed: unauthenticated SMTP connection attempt in production

`EmailService` connects to SMTP_HOST and attempts a send even when it has NO
credentials. Read from the code, and demonstrated by removing the contract
harness's stub -- the suite then logged "SMTP test email delivery failed" and
"SMTP delivery failed", i.e. it really did try.

    SMTP_USER = ""   SMTP_PASSWORD = ""   SENDGRID_API_KEY = ""
    SMTP_HOST = set, defaulting to smtp.gmail.com

    services/email_service.py:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:   # connects
            if self.smtp_user and self.smtp_password:                  # merely SKIPS
                server.login(...)                                      # the login

The routes' own "email service not configured" branch is reached on
ImportError alone, never on absent credentials, so it does not cover this.

CONSEQUENCE: a caller of POST /api/reports/email-config/test or
POST /api/reports/send-manual on a deployment without mail configured causes an
outbound connection to smtp.gmail.com that can only fail -- a slow 500 rather
than a fast, honest "not configured", and an egress attempt from the API host.

The contract harness stubs the transport, so the TEST SUITE is unaffected. That
stub does not change production behaviour and was never meant to.

DECISION NEEDED, since it changes outward behaviour: should `EmailService`
report "not configured" when it has no credentials instead of connecting?
That looks obviously right -- an unauthenticated send to a public relay cannot
succeed -- but it changes what a deployed API returns, so it is the user's call
rather than a silent fix.
