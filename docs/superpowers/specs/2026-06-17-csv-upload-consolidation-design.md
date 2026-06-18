# C2 — CSV-upload endpoint consolidation — Design

**Status:** Approved (brainstorm 2026-06-17). PR4 robustness slate, Run-7 audit debt (`endpoints/csv_upload.py` consolidation). Successor to C1/C1b.

## Goal

Remove the large-scale duplication in `backend/endpoints/csv_upload.py` (1181 lines, 11 near-identical CSV/XLSX upload endpoints) by extracting the shared per-row processing into one well-tested helper, while **preserving behavior** and **improving robustness uniformly** (declarative auth, consistent sanitization, a single correct error/response path). First add characterization tests for the currently-untested endpoints so the refactor is provably non-regressing.

## Background

`csv_upload.py` exposes 11 `POST /api/<entity>/upload/csv` endpoints (downtime, holds, attendance, coverage, quality, defects, work-orders, jobs, clients, employees, floating-pool). Each is ~80–110 lines and ~60–70% identical boilerplate:
- filename extension check + `_MAX_CSV_SIZE` (10 MB) check,
- `_read_upload_file()` (CSV/XLSX, already a shared helper),
- a `for row_num, row in enumerate(rows, start=2)` loop with `total/successful/failed/errors/created_ids` counters,
- an identical 3-way exception handler (`ValidationError` → `"Validation error in CSV row data"`; `SQLAlchemyError` → `"Database error processing row"`; `(ValueError, TypeError, KeyError, InvalidOperation)` → `"Data parsing error in CSV row"`),
- `errors[:100]` truncation and `CSVUploadResponse(total_rows, successful, failed, errors, created_entries)`.

The ~30% that legitimately differs per entity: route path, auth, the row→schema **mapping** (column aliases, date parsing, per-row `verify_client_access`, schema construction — 4 endpoints use a `.from_legacy_csv()` classmethod, 7 build the `*Create` schema inline), the `create_*` CRUD call, and the created-id attribute (`downtime_entry_id` … `pool_id`).

### Current-state audit (informs the design)
- **Auth:** 8 endpoints `Depends(get_current_active_supervisor)`; `clients` `Depends(get_current_admin)`. **Two express stricter auth via inline body checks** layered on the supervisor dependency: `employees` (`if role != ADMIN: 403`) and `floating-pool` (`if role not in [ADMIN, POWERUSER]: 403`).
- **Per-row tenant check (`verify_client_access`):** present on the 8 transactional endpoints; absent on `clients`/`employees`/`floating-pool` — confirmed NOT a security gap (all elevated-role-gated; none writes caller-`client_id`-scoped tenant data).
- **Test coverage:** the 29 existing tests (`tests/test_api/test_csv_upload_comprehensive.py`, `tests/test_endpoints/test_xlsx_upload.py`) effectively exercise only 2 routes (downtime, work-orders). **9 endpoints have no direct test.**

## Approach (chosen: A — thin endpoints + shared processor)

Keep all 11 `@router.post` functions (explicit routes, explicit auth dependency, docstrings, OpenAPI intact). Extract the duplicated boilerplate into one shared processor; each endpoint becomes: read+validate file → call the processor with a per-entity mapper/create_fn/id_getter. (Rejected: B, registry-driven dynamic routes — more DRY but obscures routes, complicates per-entity auth + OpenAPI, harder to review as behavior-preserving.)

## Architecture

### `backend/services/csv_upload_processor.py` (new)
```python
def process_csv_upload(
    rows: list[dict], db: Session, current_user: User, *,
    row_mapper,   # Callable[[dict, User], Any] -> validated *Create schema (or model_dump());
                  #   raises ValueError/ValidationError/etc. on a bad row; does any per-row verify_client_access
    create_fn,    # Callable[[Session, Any, User], Any] -> created ORM object
    id_getter,    # Callable[[Any], Any] -> created id
) -> CSVUploadResponse
```
Owns the byte-identical parts: the `enumerate(rows, start=2)` loop, counters, the **exact** 3-way exception handler with the **same** error strings, `errors[:100]`, and the `CSVUploadResponse` assembly. Pure function over already-parsed rows — unit-testable in isolation.

A tiny `read_upload(content: bytes, filename: str, sheet_name) -> list[dict]` helper centralizes the extension check + size check + `_read_upload_file` so each endpoint's pre-loop preamble is one call (it raises the same `400`/`413` HTTPExceptions as today). `sanitize_csv_value`, `_read_upload_file`, `_MAX_CSV_SIZE`, `_ALLOWED_EXTENSIONS` are reused unchanged.

### `backend/endpoints/csv_upload.py` (shrinks)
Each endpoint keeps its decorator/route/auth/docstring and reduces to ~10 lines:
```python
@router.post("/api/downtime/upload/csv", response_model=CSVUploadResponse)
async def upload_downtime_csv(file=File(...), sheet_name=Query(None), db=Depends(get_db),
                              current_user=Depends(get_current_active_supervisor)) -> CSVUploadResponse:
    rows = read_upload(await file.read(), file.filename, sheet_name)
    return process_csv_upload(rows, db, current_user,
        row_mapper=_map_downtime_row, create_fn=create_downtime_event,
        id_getter=lambda c: c.downtime_entry_id)
```
The per-entity `_map_<entity>_row(row, current_user)` functions live beside their routes and hold exactly the mapping that differs (column aliases, date parsing, per-row `verify_client_access`, `.from_legacy_csv()` vs inline `*Create(...)`).

## Phase 1 — characterization (golden-master) tests first

Before editing `csv_upload.py`, add characterization tests for the **9 untested endpoints** (holds, attendance, coverage, quality, defects, jobs, clients, employees, floating-pool) in `tests/test_api/`. Per endpoint:
- **happy path:** a valid CSV for that entity's real required/optional columns → assert `200`, expected `successful` count, `failed == 0`, `created_entries` populated;
- **invalid/mixed row:** a row that fails validation/parsing → assert the `failed` count and the error-entry shape (`{"row": N, "error": <one of the 3 strings>, "data": ...}`);
- **auth outcome:** correct role → 2xx; insufficient role → `403` (assert the **status code**, not the legacy detail string — see Robustness §1).

These run green on **current** code (golden master), then must stay green through Phase 2. Existing downtime/work-orders tests + `test_xlsx_upload.py` (XLSX path) remain the coverage for those.

## Phase 2 — extract, preserving behavior

Create the processor + `read_upload`; convert the 11 endpoints one at a time to thin wrappers + a `_map_<entity>_row`. No change to any route, status code, error string, response field, or column alias. The 1181-line file drops to the 11 route stubs + 11 small mappers; the shared loop lives once in the service.

## Robustness improvements (uniform, behavior-preserving)

1. **Declarative auth — remove inline role checks**, preserving exact effective access:
   - `employees`: `Depends(get_current_active_supervisor)` + inline `role != ADMIN` → **`Depends(get_current_admin)`**.
   - `floating-pool`: `Depends(get_current_active_supervisor)` + inline `role not in [ADMIN, POWERUSER]` → **`Depends(get_current_planner)`** (`PLANNER_ROLES` = admin/poweruser, verified to match).
   - The 9 others unchanged. **Who is allowed is identical**; only the 403 *detail message* normalizes to the dependency's standard message (an improvement — declarative, OpenAPI-visible, testable). Characterization asserts the 403 **status** before/after.
2. **Uniform CSV-injection sanitization:** the mapper path applies `sanitize_csv_value` to every written string field; verify no written string field is left unsanitized (a couple of endpoints sanitize fewer fields than they write).
3. **Single correct path:** the shared processor is one place for the loop/exception/response semantics across all 11 — the core reliability win and the home for any future fix.

## Behavior preservation contract

Identical after refactor: routes, HTTP methods, success status, `CSVUploadResponse` shape + field values, the 3 error strings, `errors[:100]`, row numbering (`start=2`), column aliases/date formats per entity, CRUD calls, created-id values, the per-row `verify_client_access` on the 8 transactional endpoints. **Changed intentionally (robustness):** inline auth checks → dependencies (same access, normalized 403 message); sanitization made uniform.

## Verification & success criteria

- `pytest tests/` from `backend/` green; coverage gate ≥75% — expected to **rise** (9 endpoints gain tests). Permissive-assertion rule respected (one expected status per assert; no `in [...]`).
- The Phase-1 characterization tests green **both** on current code and after extraction (no-regression proof).
- `process_csv_upload` covered by direct unit tests (happy + each exception branch).
- Smoke `/health/live`; CI's 4 required checks green; post-merge main CI + Render verified (local == GitHub == Render).

## Non-goals / out of scope

- No change to the CSV/XLSX **column schemas**, entity `*Create` models, or CRUD logic.
- No new upload endpoints; no registry/dynamic-route mechanism (Approach B rejected).
- No change to the frontend upload UI or the `/api/csv/*` template/validation endpoints (separate from these 11 ingestion routes).
- C3 (`main.py` lifespan) and C4/C5 remain separate/deferred.

## Delivery

One PR with sequenced commits: Phase 1 (characterization tests) as its own commit(s) verified green on current code, then Phase 2 extraction + per-endpoint conversions + robustness, each verified. Own brainstorm→spec→plan→execute→PR→merge-on-green cycle.
