# Attendance Entry — Surface Brief

**Route:** `/data-entry/attendance`
**Wrapper view:** `frontend/src/views/AttendanceEntry.vue`
**Grid component:** `frontend/src/components/grids/AttendanceEntryGrid.vue`
**Composable:** `frontend/src/composables/useAttendanceGridData.ts`
**Backend canonical schema:** `backend/schemas/attendance.py` `AttendanceRecordCreate`
**Backend ORM:** `backend/orm/attendance_entry.py` (`ATTENDANCE_ENTRY` table)
**Backend route:** `backend/routes/attendance.py` (mounted at `/api/attendance`)

This surface migrated from a `v-form`-based component (`components/entries/AttendanceEntry.vue`) to the AG Grid spreadsheet pattern on 2026-05-01 as Surface #3 of the entry-interface audit (`docs/audit/entry-surface-migration-plan.md`, Group A).

---

## UX shape

Different from Quality and Holds: Attendance is **roster-driven**, not free-row entry. The wrapper view exposes top-level **shift_date / shift / line** selectors and a "Load Employees" button that populates the grid with one row per employee on the selected shift. Operators then mark each row's `status` and (for Late entries) `clock_in` / `clock_out`.

`shift_date` and `shift_id` are **implicit** — set once at the composable level via `selectedDate` / `selectedShift`. Per-row paste from Excel may override `shift_date` if a column is supplied.

---

## Column set

| Column | Backend field | Editor | Constraints |
|---|---|---|---|
| Employee ID | `employee_id` | read-only | populated by Load Employees |
| Employee Name | (display only) | read-only | populated from `/employees` endpoint |
| Department | (display only) | read-only | populated from `/employees` endpoint |
| Status | `status` (UI) → `is_absent`/`absence_type`/`is_late` | `agSelectCellEditor` | values: `Present` / `Absent` / `Late` / `Half Day` / `Leave` / `Vacation` / `Medical` |
| Clock In | (HH:MM string) → `arrival_time` ISO datetime | `TimePickerCellEditor` | optional; combined with shift_date on save |
| Clock Out | (HH:MM string) → `departure_time` ISO datetime | `TimePickerCellEditor` | optional; combined with shift_date on save |
| Scheduled Hours | `scheduled_hours` | `agNumberCellEditor` | required (gt 0, le 24); default 8 |
| Actual Hours | `actual_hours` | `agNumberCellEditor` | optional (ge 0, le 24); auto-derived from status + scheduled if not set |
| Absence Reason | `absence_reason` | `agSelectCellEditor` | values: Sick Leave / Personal Leave / Family Emergency / Medical Appointment / No Show / Unauthorized / Vacation / Other |
| Notes | `notes` | `agLargeTextCellEditor` (popup) | optional free text |

**Dropped vs the legacy form/grid:** `late_minutes` and `is_excused` were vestigial — the backend has no equivalent fields. `is_late` is now derived automatically from the status (Late ⇒ 1, otherwise 0).

`client_id` is derived from `useAuthStore().user.client_id_assigned` (operators) or `useKPIStore().selectedClient` (admin). Save aborts with `grids.attendance.errors.noClient` if neither is set.

---

## Status translation

UI status string maps to backend (`is_absent`, `absence_type`, `is_late`, `actualHoursFactor`) via `translateStatus()` (composable export):

| UI Status | `is_absent` | `absence_type` | `is_late` | actual_hours factor |
|---|---|---|---|---|
| Present | 0 | null | 0 | 1.0 |
| Absent | 1 | `UNSCHEDULED_ABSENCE` | 0 | 0 |
| Late | 0 | null | 1 | 1.0 |
| Half Day | 0 | null | 0 | 0.5 |
| Leave | 1 | `PERSONAL_LEAVE` | 0 | 0 |
| Vacation | 1 | `VACATION` | 0 | 0 |
| Medical | 1 | `MEDICAL_LEAVE` | 0 | 0 |

The mapping mirrors `backend/schemas/attendance.py from_legacy_csv`. Half Day is not a backend concept — represented as Present with 0.5 × scheduled_hours of actual work; the operator can override `actual_hours` directly.

---

## Datetime conversion

`clock_in` / `clock_out` are HH:MM strings entered via the time-picker editor. On save, `combineDateTime(shift_date, clock_in)` produces an ISO datetime (`YYYY-MM-DDTHH:MM:00`) for `arrival_time` / `departure_time`. Empty or malformed time values become `undefined` (not sent).

The reverse conversion runs in `loadEmployees`: existing attendance records returned from the backend have ISO `arrival_time` / `departure_time` datetimes; the composable strips back to HH:MM for the editor.

---

## Validation rules

1. **Per-cell editor constraints** — typed editors (`agSelectCellEditor`, `agNumberCellEditor`, `TimePickerCellEditor`).
2. **Pre-save check** — `saveAttendance` aborts with snackbar error if no `client_id` is resolvable from auth/kpi stores or no shift_date+shift selected for `loadEmployees`.
3. **Backend Pydantic** — `AttendanceRecordCreate` requires `client_id` (1–50 chars), `employee_id` (>0), `shift_date`, `scheduled_hours` (>0, ≤24). All other fields optional.

---

## CSV format

CSV import is wired into the wrapper view's header via `frontend/src/components/CSVUploadDialogAttendance.vue`. The dialog uses the canonical backend schema for column names. Backend endpoint: `POST /attendance/upload/csv` (multipart/form-data).

Excel-style **clipboard paste** uses `frontend/src/utils/clipboardParser.ts` `attendance:` schema:

```
shift_date (required, date)
scheduled_hours (number, 0–24)
actual_hours (number, 0–24)
```

Renamed in this migration: `attendance_date` → `shift_date`, `worked_hours` → `actual_hours`.

---

## Tests

- `frontend/src/composables/__tests__/useAttendanceGridData.spec.ts` — 30 tests covering `translateStatus` (9 status mappings), `combineDateTime` (6 datetime cases), column-shape conformance to backend schema (verifies absence of legacy `late_minutes` / `is_excused` columns + presence of `scheduled_hours` / `actual_hours`), `statusCounts` aggregation (Vacation/Medical roll into Leave bucket), and initial state.
- No legacy form spec to delete — the form had no test file. Net: +30 tests.
