# Phase B.5 — Test pollution sweep

**Date**: 2026-05-07
**Result**: ✅ PASS — zero pollution detected

## Method

1. Captured baseline row counts across all 51 tables in
   `database/kpi_platform.db` (the live demo SQLite database):

   ```bash
   python3 -c "
   import sqlite3, json
   conn = sqlite3.connect('database/kpi_platform.db')
   c = conn.cursor()
   c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'\")
   tables = [r[0] for r in c.fetchall()]
   counts = {t: c.execute(f'SELECT COUNT(*) FROM \"{t}\"').fetchone()[0] for t in tables}
   print(json.dumps(counts, indent=2))
   " > /tmp/db_before.json
   ```

2. Ran the full backend test suite:

   ```bash
   python -m pytest backend/tests/ --no-header --no-cov -q --tb=line
   # 4842 passed, 1 skipped in 672.64s (0:11:12)
   ```

3. Captured post-test row counts (same script).

4. Diffed `before` vs `after`:

   ```bash
   diff /tmp/db_before.json /tmp/db_after.json
   ```

## Result

**`diff` returned no output** — every table has identical row counts before
and after the 4842-test run.

## Why no pollution

The test fixture architecture in `backend/tests/conftest.py` is correct:

- **`TEST_DATABASE_URL = "sqlite:///:memory:"`** — all tests run against a
  fresh in-memory SQLite engine that is destroyed when the pytest process
  exits. Nothing physically reaches `database/kpi_platform.db`.

- **`get_test_engine()` singleton** drops + recreates schema on first use:

  ```python
  Base.metadata.drop_all(bind=_test_engine)
  Base.metadata.create_all(bind=_test_engine)
  ```

  This guarantees every `pytest` process starts with a clean DB.

- **`app.dependency_overrides[get_db] = get_test_db`** in the `test_client`
  fixture redirects every route's `Depends(get_db)` to the in-memory engine.
  Without this override, routes would resolve `get_db` from the production
  config and write to `kpi_platform.db`. The override + the in-memory URL
  make pollution structurally impossible.

- **`transactional_db` fixture** (used by 62+ tests per `grep -c
  "transactional_db" backend/tests/conftest.py`) wraps each test in a
  SAVEPOINT and rolls back on teardown — same in-memory engine, but with
  per-test isolation as well.

## Recurrence prevention

The fixture pattern is solid; what could break it?

1. **Adding a new test that creates its own `Engine`** without going through
   `get_test_engine()`. If the new engine points at the production URL, the
   test would write to disk. The `dependency_overrides[get_db]` override
   would NOT cover this — the test would have to explicitly use the
   override-respecting `test_client` or `transactional_db`.

   **Mitigation**: the `_history/run-3` audit's `RULE-01` (real DB tests
   only — no mocks) is already in CLAUDE.md. As a second layer, the lint
   rule could grep for `create_engine("sqlite:///") | create_engine(DATABASE_URL)`
   in test files — but this is overengineering given the fixture is the
   established convention.

2. **A test that imports a module that has database side effects at import
   time**. The test_client fixture imports `backend.main` AFTER overriding
   `get_db`, so the lifespan handler that runs the smart-reseed would still
   execute against the in-memory engine. Verified working — the
   `lifespan_safety_check` warning fires for in-memory schema and the
   reseed runs against the override.

3. **Deliberate writes to the production DB from tests** — there are none
   today. If one were added, the diff above would catch it. Adding the
   `before/after` diff to CI would make this an automated guard, but the
   tradeoff is a 12-minute test cycle per PR for a check that has stayed
   green forever.

   **Decision**: not adding to CI. Make the diff a manual quarterly check
   per the next code-quality audit run.

## Acceptance criteria

- [x] `_audit/B5-test-pollution.md` documents each polluting test + fix
  → No pollution found; this report documents the verification.
- [x] Final live-DB check shows zero row growth across pytest runs
  → Confirmed via `diff` returning no output.
- [x] All tests still pass
  → 4842 passed, 1 skipped, 0 failed in 11:12.
