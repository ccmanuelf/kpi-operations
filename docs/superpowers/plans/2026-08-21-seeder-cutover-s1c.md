# Seeder Cutover (S1c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `backend/seed` the only demo seeder — repoint the boot path, CI, e2e and smoke checks at it, retire ~5,900 lines of the old seeder, and fix the two `--reset` hazards first, because the cutover is what makes them reachable.

**Architecture:** Two PRs. PR-1 fixes `_reset` while it is still wired to nothing. PR-2 repoints every caller, retires the destructive boot path, and deletes the old seeder. Recovery on boot changes from `rebuild_schema()` (drops every table) to `seed(reset=True)` (clears four allowlisted tenants).

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 Core, Alembic, FastAPI, pytest, GitHub Actions, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-21-seeder-cutover-s1c-design.md`

## Global Constraints

- **Permissive assertions are forbidden.** Never `assert x in [...]`. One exact expected value per assertion.
- **Every new or changed assertion needs a named single-line source change that breaks it**, run, with real pasted output. A guard that only ever passes is treated as absent.
- Files stay under 500 lines.
- **Never create or drop schema.** Alembic is the single mechanism; `test_no_create_all_outside_alembic` enforces it. S1c adds no revisions.
- The `DEMO_MODE` check stays the **first statement** in `_auto_seed_demo_data` (Run 7 C-1).
- The seeder import in `lifecycle.py` stays **deferred inside the function**. `test_importing_the_app_pulls_in_no_seed_module` must stay green unchanged.
- Backend tests run from `backend/` with `pytest tests/ --no-cov -q`. **Foreground, never backgrounded.**
- Mutation hygiene: absolute paths, purge `__pycache__` around each write, restore, confirm `git diff HEAD` empty.
- No `--no-verify`, no `SKIP=`.
- Allowlist is `DEMO-PIECE`, `DEMO-HOURLY`, `DEMO-HYBRID`, `SAMPLE_REF`. Seeded users are `demo_admin`, `demo_planner`, `demo_leader`, `demo_supervisor`, `demo_operator`, `demo_viewer`, password `DemoSeed#2026`.

---

# PR-1 — `--reset` hazard fixes

Branch off `main`. Touches `backend/seed/cli.py` and its tests only. No live impact.

### Task 1: Nullable-tenant children are swept by parent

**Files:**
- Modify: `backend/seed/cli.py` (add derivation + a fourth pass in `_reset`)
- Test: `backend/tests/test_seed/test_cli.py`

**Interfaces:**
- Produces: `NULLABLE_TENANT_SWEEPS: tuple[tuple[str, str, str, str, str], ...]` — `(child, child_fk_col, child_scope_col, parent, parent_pk)`
- Consumes: `CLIENT_SCOPED_TABLES` (existing)

**Context.** `_reset` filters each swept table by its own tenant column. A child whose tenant column is NULLABLE and NULL is never selected, then RESTRICTs its parent. Derived from live metadata, exactly two edges exist:

```
FLOATING_POOL.employee_id -> EMPLOYEE.employee_id   (tenant col 'client_id' nullable, ondelete=None)
ALERT.work_order_id       -> WORK_ORDER.work_order_id (tenant col 'client_id' nullable, ondelete=None)
```

`backend/crud/floating_pool/assignments.py` builds `FloatingPool(...)` with `client_id` omitted, so every `POST /api/floating-pool/assign` writes such a row.

- [ ] **Step 1: Write the failing reproduction**

```python
def test_reset_clears_a_null_tenant_child_that_would_block_its_parent(seed_engine):
    """A FLOATING_POOL row with client_id NULL is invisible to the scoped DELETE
    and RESTRICTs EMPLOYEE. Reachable in ordinary use: the floating-pool assign
    endpoint omits client_id entirely."""
    from sqlalchemy import insert, select, func
    from backend.database import Base
    from backend.seed.cli import seed, ALLOWLIST

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    pool = Base.metadata.tables["FLOATING_POOL"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(insert(pool).values(employee_id=emp_id, client_id=None))

    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        orphans = conn.execute(
            select(func.count()).select_from(pool).where(pool.c.employee_id == emp_id)
        ).scalar_one()
    assert orphans == 0
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd backend && python -m pytest tests/test_seed/test_cli.py::test_reset_clears_a_null_tenant_child_that_would_block_its_parent --no-cov -q`
Expected: FAIL with `sqlite3.IntegrityError: FOREIGN KEY constraint failed` on the `DELETE FROM "EMPLOYEE"`.

- [ ] **Step 3: Add the derivation to `backend/seed/cli.py`**

Place immediately after `SELF_REFERENTIAL_SWEEPS`:

```python
def _nullable_tenant_children() -> tuple:
    """Swept children whose OWN tenant column is nullable and which hold a
    ForeignKey into another swept table, as
    (child, child fk column, child scope column, parent, parent pk).

    A row here with a NULL tenant matches no IN clause, so the scoped DELETE
    never selects it -- and it then RESTRICTs its parent. No sweep ORDER can fix
    that, because the row is never visited at all, which is why
    test_reset_ordering.py cannot see this class either.

    Derived rather than listed: two edges exist today (FLOATING_POOL.employee_id
    -> EMPLOYEE, ALERT.work_order_id -> WORK_ORDER) and a third added later is
    handled without a code change here.
    """
    found = set()
    for name, scope in CLIENT_SCOPED_TABLES.items():
        table = Base.metadata.tables[name]
        if not table.columns[scope].nullable:
            continue
        for column in table.columns:
            if column.name == scope:
                continue
            for fk in column.foreign_keys:
                parent = fk.column.table.name
                if parent in CLIENT_SCOPED_TABLES and parent != name:
                    found.add((name, column.name, scope, parent, fk.column.name))
    return tuple(sorted(found))


#: Children invisible to the scoped sweep because their own tenant column is NULL.
NULLABLE_TENANT_SWEEPS = _nullable_tenant_children()
```

Add `or_` to the sqlalchemy import at the top of the file.

- [ ] **Step 4: Add the sweep pass in `_reset`**

Insert after the `DEPENDENT_SWEEPS` loop and before `SELF_REFERENTIAL_SWEEPS`:

```python
    for child_name, child_column, child_scope, parent_name, parent_pk in NULLABLE_TENANT_SWEEPS:
        child = Base.metadata.tables[child_name]
        parent = Base.metadata.tables[parent_name]
        parent_scope = CLIENT_SCOPED_TABLES[parent_name]
        # Selected by PARENT in scope, not by own tenant -- that is the whole
        # point. The second predicate keeps a row explicitly owned by another
        # tenant safe even when it points at a demo parent.
        conn.execute(
            delete(child).where(
                child.c[child_column].in_(
                    select(parent.c[parent_pk]).where(parent.c[parent_scope].in_(client_ids))
                ),
                or_(child.c[child_scope].is_(None), child.c[child_scope].in_(client_ids)),
            )
        )
```

- [ ] **Step 5: Run the test and confirm it passes**

Run: `cd backend && python -m pytest tests/test_seed/test_cli.py::test_reset_clears_a_null_tenant_child_that_would_block_its_parent --no-cov -q`
Expected: PASS

- [ ] **Step 6: Add the foreign-tenant safety test**

```python
def test_reset_leaves_a_null_tenant_childs_foreign_owner_alone(seed_engine):
    """The parent-subquery sweep must not reach a row explicitly owned by
    another tenant, even when it points at a demo parent."""
    from sqlalchemy import insert, select, func
    from backend.database import Base
    from backend.seed.cli import seed

    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(insert(client).values(
            client_id="REAL-CUSTOMER", client_name="Real", client_type="Hourly Rate", is_active=True))

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    pool = Base.metadata.tables["FLOATING_POOL"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(insert(pool).values(employee_id=emp_id, client_id="REAL-CUSTOMER"))

    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        survivors = conn.execute(
            select(func.count()).select_from(pool).where(pool.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
    assert survivors == 1
```

- [ ] **Step 7: Add the anti-rot guard**

```python
def test_the_nullable_tenant_sweep_set_is_exactly_the_known_two():
    """Pinned so a third such edge fails the build instead of silently
    stranding a tenant's rows or RESTRICTing a reset on a customer VM."""
    from backend.seed.cli import NULLABLE_TENANT_SWEEPS

    assert NULLABLE_TENANT_SWEEPS == (
        ("ALERT", "work_order_id", "client_id", "WORK_ORDER", "work_order_id"),
        ("FLOATING_POOL", "employee_id", "client_id", "EMPLOYEE", "employee_id"),
    )
```

- [ ] **Step 8: Run the mutation and paste the output**

Mutation: in `_nullable_tenant_children`, change `if not table.columns[scope].nullable:` to `if True:` (returns an empty tuple).
Run: `cd backend && python -m pytest tests/test_seed/ --no-cov -q`
Expected: the reproduction test FAILS with the FK IntegrityError and the guard FAILS on the empty tuple. Restore; confirm `git diff HEAD` is empty.

- [ ] **Step 9: Run the seed suite and commit**

```bash
cd backend && python -m pytest tests/test_seed/ --no-cov -q
git add backend/seed/cli.py backend/tests/test_seed/test_cli.py
git commit -m "fix(seed): sweep null-tenant children by parent so --reset cannot strand them"
```

---

### Task 2: Shared employees survive a reset

**Files:**
- Modify: `backend/seed/cli.py`
- Test: `backend/tests/test_seed/test_cli.py`

**Interfaces:**
- Produces: `CASCADE_CHILDREN_OF_EMPLOYEE: tuple[str, ...]` — child table names whose `employee_id` FK to `EMPLOYEE` declares `ondelete=CASCADE`
- Consumes: `CLIENT_SCOPED_TABLES`, `NULLABLE_TENANT_SWEEPS` (Task 1)

**Context.** `EMPLOYEE` is swept by its bare `client_id_assigned`, and **two** children cascade off it:

```
EMPLOYEE_CLIENT_ASSIGNMENT.employee_id -> EMPLOYEE   (ondelete=CASCADE, own client_id)
EMPLOYEE_LINE_ASSIGNMENT.employee_id   -> EMPLOYEE   (ondelete=CASCADE, own client_id)
```

An employee whose `client_id_assigned` names a demo tenant but who also holds a client or line assignment for a real one loses that real row when the demo employee is deleted — silently, with no error and no row count to notice. `EMPLOYEE` is the only swept table with this shape, because it is the only one whose children can belong to a different tenant than the parent.

- [ ] **Step 1: Write the failing test**

```python
def test_reset_does_not_delete_an_employee_shared_with_a_foreign_tenant(seed_engine):
    """CASCADE makes this silent rather than loud: deleting a demo employee
    removes a real tenant's assignment with no error and no row count."""
    from sqlalchemy import insert, select, func
    from backend.database import Base
    from backend.seed.cli import seed

    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(insert(client).values(
            client_id="REAL-CUSTOMER", client_name="Real", client_type="Hourly Rate", is_active=True))

    kwargs = dict(client_ids=("DEMO-PIECE",), profile_name="smoke", seed_value=1234, as_of=date(2026, 8, 18))
    seed(seed_engine, reset=False, **kwargs)

    employee = Base.metadata.tables["EMPLOYEE"]
    eca = Base.metadata.tables["EMPLOYEE_CLIENT_ASSIGNMENT"]
    with seed_engine.begin() as conn:
        emp_id = conn.execute(
            select(employee.c.employee_id).where(employee.c.client_id_assigned == "DEMO-PIECE").limit(1)
        ).scalar_one()
        conn.execute(insert(eca).values(employee_id=emp_id, client_id="REAL-CUSTOMER"))

    seed(seed_engine, reset=True, **kwargs)

    with seed_engine.connect() as conn:
        kept = conn.execute(
            select(func.count()).select_from(eca).where(eca.c.client_id == "REAL-CUSTOMER")
        ).scalar_one()
    assert kept == 1
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd backend && python -m pytest tests/test_seed/test_cli.py::test_reset_does_not_delete_an_employee_shared_with_a_foreign_tenant --no-cov -q`
Expected: FAIL with `assert 0 == 1` — the cascade removed the real tenant's row silently.

- [ ] **Step 3: Add the derivation**

```python
def _cascade_children_of_employee() -> tuple:
    """Child tables whose employee_id FK to EMPLOYEE declares ondelete=CASCADE.

    EMPLOYEE is the only swept table whose children can belong to a DIFFERENT
    tenant than the parent -- an employee may be shared across clients, whereas
    a work order, hold or production line belongs to exactly one. So it is the
    only table where deleting a demo row can silently remove a real tenant's
    data. Two such children exist today.
    """
    found = set()
    for name in CLIENT_SCOPED_TABLES:
        table = Base.metadata.tables[name]
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "EMPLOYEE" and fk.ondelete == "CASCADE":
                    found.add(name)
    return tuple(sorted(found))


CASCADE_CHILDREN_OF_EMPLOYEE = _cascade_children_of_employee()
```

- [ ] **Step 4: Protect shared employees in `_reset`**

Before the `reversed(INSERT_ORDER)` loop:

```python
    # An employee shared with a tenant outside the sweep must survive: both of
    # its cascade children carry their own client_id, so deleting the employee
    # would remove a REAL tenant's assignment with no error at all. Their demo
    # assignment rows are still cleared by the scoped sweep below, which is the
    # correct outcome; only the shared EMPLOYEE row is spared.
    shared_employee_ids: set = set()
    for child_name in CASCADE_CHILDREN_OF_EMPLOYEE:
        child = Base.metadata.tables[child_name]
        shared_employee_ids.update(
            conn.execute(
                select(child.c.employee_id).where(child.c.client_id.notin_(client_ids))
            ).scalars().all()
        )
```

Then inside the sweep loop, after building the delete:

```python
        statement = delete(table).where(table.c[column].in_(client_ids))
        if name == "EMPLOYEE" and shared_employee_ids:
            statement = statement.where(table.c.employee_id.notin_(shared_employee_ids))
        conn.execute(statement)
```

- [ ] **Step 5: Run the test and confirm it passes**

Run: `cd backend && python -m pytest tests/test_seed/test_cli.py::test_reset_does_not_delete_an_employee_shared_with_a_foreign_tenant --no-cov -q`
Expected: PASS

- [ ] **Step 6: Add the line-assignment variant and the anti-rot guard**

Repeat the Step 1 test against `EMPLOYEE_LINE_ASSIGNMENT` (insert requires `client_id`, `employee_id` and a `line_id` from a seeded `PRODUCTION_LINE` for `DEMO-PIECE`), asserting the `REAL-CUSTOMER` row survives. Then:

```python
def test_the_employee_cascade_children_are_exactly_the_known_two():
    """A third cascade child of EMPLOYEE must fail the build: it would be a new
    way for a reset to silently delete a real tenant's rows."""
    from backend.seed.cli import CASCADE_CHILDREN_OF_EMPLOYEE

    assert CASCADE_CHILDREN_OF_EMPLOYEE == ("EMPLOYEE_CLIENT_ASSIGNMENT", "EMPLOYEE_LINE_ASSIGNMENT")
```

- [ ] **Step 7: Run the mutation and paste the output**

Mutation: in `_reset`, change `if name == "EMPLOYEE" and shared_employee_ids:` to `if False:`.
Run: `cd backend && python -m pytest tests/test_seed/ --no-cov -q`
Expected: both shared-employee tests FAIL with `assert 0 == 1`. Restore; confirm `git diff HEAD` is empty.

- [ ] **Step 8: Full suite, mypy, commit**

```bash
cd backend && python -m pytest tests/ --tb=short -q      # foreground
cd .. && python -m mypy backend
git add backend/seed/cli.py backend/tests/test_seed/test_cli.py
git commit -m "fix(seed): spare employees shared with a tenant outside the sweep"
```

- [ ] **Step 9: Open PR-1**

Run `/cross-review`, then `gh pr create`. Body states both hazards, both mutations, and that neither is live yet.

---

# PR-2 — the cutover

Branch off `main` **after PR-1 merges**.

### Task 3: Boot path stops being able to destroy a database

**Files:**
- Modify: `backend/bootstrap/lifecycle.py:130-200`
- Test: `backend/tests/test_bootstrap/test_lifecycle_seed_path.py` (create)

**Interfaces:**
- Consumes: `backend.seed.cli.ALLOWLIST`, `backend.seed.cli.seed` (both imported **inside** the function)

- [ ] **Step 1: Write the failing tests**

```python
def test_expected_clients_is_the_seeder_allowlist():
    """Derived, not literal. A hardcoded set that names different clients than
    the seeder produces makes every boot decide the demo is incomplete and
    re-seed forever -- and with the old destructive rebuild in front of it, that
    was an infinite data-loss loop."""
    import backend.bootstrap.lifecycle as lifecycle
    from backend.seed.cli import ALLOWLIST

    assert lifecycle._expected_clients() == set(ALLOWLIST)


def test_the_boot_path_cannot_reach_rebuild_schema():
    """The destructive path is gone by construction, not by configuration.

    Asserted against the AST, not the raw source: a substring check would also
    match COMMENTS, forbidding the explanatory note this removal deserves and
    training the next reader to delete the comment to make the test pass. This
    checks what actually executes -- no import of rebuild_schema, no call to it.
    """
    import ast
    import inspect
    import backend.bootstrap.lifecycle as lifecycle

    tree = ast.parse(inspect.getsource(lifecycle))
    imported = {
        alias.name.split(".")[-1] if alias.asname is None else alias.asname
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called = {
        ast.unparse(node.func).split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }

    assert "rebuild_schema" not in imported
    assert "rebuild_schema" not in called
```

- [ ] **Step 2: Run and confirm both fail**

Run: `cd backend && python -m pytest tests/test_bootstrap/test_lifecycle_seed_path.py --no-cov -q`
Expected: FAIL — `_expected_clients` does not exist; `rebuild_schema` is still in the source.

- [ ] **Step 3: Rewrite the seed branch**

Replace the `EXPECTED_CLIENTS` literal with:

```python
def _expected_clients() -> set:
    """The demo is complete when the seeder's own allowlist is present.

    Derived from backend.seed.cli.ALLOWLIST rather than restated: a literal set
    naming different clients than the seeder produces is what made this an
    infinite re-seed loop. Imported inside the function so backend.seed stays
    out of the application import graph -- test_importing_the_app_pulls_in_no_
    seed_module enforces that.
    """
    from backend.seed.cli import ALLOWLIST

    return set(ALLOWLIST)
```

In `_auto_seed_demo_data`, delete the `rebuild_schema` import and call, the `client_count > 0` guard, and the `SchemaRebuildError` re-raise. Replace the seeding call with:

```python
            from datetime import date

            from backend.database import engine
            from backend.seed.cli import ALLOWLIST, seed

            # reset=True is the whole recovery story now: scoped to the
            # allowlist, it clears a partial demo and re-seeds it. On an empty
            # database the reset is a no-op. Alembic owns schema (C5), so
            # nothing here creates or drops one.
            seed(
                engine,
                client_ids=tuple(ALLOWLIST),
                profile_name="full",
                seed_value=1234,
                as_of=date.today(),
                reset=True,
            )
```

- [ ] **Step 4: Run and confirm both pass**

Run: `cd backend && python -m pytest tests/test_bootstrap/test_lifecycle_seed_path.py --no-cov -q`
Expected: PASS

- [ ] **Step 5: Confirm the purity gate is still green**

Run: `cd backend && python -m pytest tests/test_seed/test_seed_gates.py::test_importing_the_app_pulls_in_no_seed_module --no-cov -q`
Expected: PASS — the deferred import keeps `backend.seed` out of `sys.modules` after `import backend.main`. If this fails, the import was hoisted to module level; move it back inside the function.

- [ ] **Step 6: Mutation**

Mutation: hoist `from backend.seed.cli import ALLOWLIST, seed` to the top of `lifecycle.py`.
Expected: `test_importing_the_app_pulls_in_no_seed_module` FAILS. Restore.

- [ ] **Step 7: Commit**

```bash
git add backend/bootstrap/lifecycle.py backend/tests/test_bootstrap/test_lifecycle_seed_path.py
git commit -m "feat(seed): boot path seeds via backend.seed and can no longer drop the database"
```

---

### Task 4: The C-1 gate proves the real property

**Files:**
- Modify: `backend/tests/test_demo_seed_gate.py`

**Context.** This guards the Run 7 C-1 remediation. The tempting shortcut during a retirement is to assert the old import no longer exists — that passes while proving nothing.

- [ ] **Step 1: Repoint the four tests**

Replace `import backend.scripts.init_demo_database as seeder_mod` with a patch of `backend.seed.cli.seed`, and assert on call count:

```python
def test_auto_seed_skipped_when_demo_mode_off(monkeypatch):
    """DEMO_MODE off must return BEFORE any database access. Proven by patching
    the seeder and asserting it is never called -- not by asserting an import is
    absent, which would pass while proving nothing."""
    calls = []
    import backend.seed.cli as seed_cli

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(seed_cli, "seed", lambda *a, **kw: calls.append(kw))
    session_calls, _ = _install_recorders(monkeypatch, [])

    _auto_seed_demo_data()

    assert calls == []
    assert session_calls == []
```

`test_demo_mode_incomplete_data_reseeds` drops its `rebuild_schema` sequencing entirely and instead asserts `calls[0]["reset"] is True`.

- [ ] **Step 2: Run and commit**

```bash
cd backend && python -m pytest tests/test_demo_seed_gate.py --no-cov -q
git add backend/tests/test_demo_seed_gate.py
git commit -m "test(seed): C-1 gate proves the seeder is not called, not that an import is gone"
```

- [ ] **Step 3: Mutation**

Mutation: move the `DEMO_MODE` check below the `SessionLocal()` call in `_auto_seed_demo_data`.
Expected: `test_auto_seed_skipped_when_demo_mode_off` FAILS on `session_calls`. Restore.

---

### Task 5: Audit suppression tests repoint

**Files:**
- Modify: `backend/tests/test_audit/test_suppression_sites.py`

- [ ] **Step 1: Repoint both tests at `backend.seed.cli.seed`**

Replace the two seeder-specific tests with a single one driving `backend.seed.cli.seed` under `audit_suppressed()`, keeping the contract at **zero `AUDIT_ENTRY` rows**. Update the module docstring: the suppression now covers one seeder, not two. Note in the docstring that S2 changes this contract to "every audit row is one the materializer authored".

- [ ] **Step 2: Run and commit**

```bash
cd backend && python -m pytest tests/test_audit/ --no-cov -q
git add backend/tests/test_audit/test_suppression_sites.py
git commit -m "test(audit): repoint suppression sites at backend.seed.cli.seed"
```

---

### Task 6: CI, smoke and e2e call sites

**Files:**
- Modify: `.github/workflows/ci.yml`, `deploy/smoke/compose-smoke.sh`, `frontend/e2e/helpers.ts`, `frontend/e2e/attendance-labor-allocation.spec.ts`
- Test: `backend/tests/test_ci_workflow_gates.py`

- [ ] **Step 1: Replace the e2e-sqlite seeding step**

The old seeder created schema **and** seeded; the new one only seeds. So one command becomes two:

```yaml
      - name: Seed the demo database
        # The old seeder created the schema AND seeded it; backend.seed only
        # seeds, because Alembic owns schema (C5). One command becomes two.
        working-directory: .
        run: |
          PYTHONPATH=. python -c "from backend.db.migrate import upgrade_to_head; upgrade_to_head()"
          PYTHONPATH=. python -m backend.seed.cli --profile full
```

`backend/db/migrate.py` exposes `upgrade_to_head(url=None)` and **no CLI** — verified, so
`python -m backend.db.migrate` would fail. The `python -c` form reuses the helper that already
resolves the Alembic config from `backend/alembic.ini`, which is what the test fixtures use;
calling `alembic` directly would bypass that resolution.

- [ ] **Step 2: Swap the four smoke URLs**

`client_id=ACME-MFG` → `client_id=DEMO-PIECE` at the four `check "http://localhost:8001/api/..."` lines.

- [ ] **Step 3: Swap compose-smoke and the e2e fixtures**

`deploy/smoke/compose-smoke.sh`: `CLIENT_ID="${CLIENT_ID:-DEMO-PIECE}"` plus the two header comments.
`frontend/e2e/helpers.ts`: `operator: { user: 'demo_operator', pass: 'DemoSeed#2026' }`, `leader: { user: 'demo_leader', pass: 'DemoSeed#2026' }`.
`frontend/e2e/attendance-labor-allocation.spec.ts`: `client_id: 'DEMO-PIECE'` and the comment on line 38.

- [ ] **Step 4: Extend the workflow gate**

Add to `test_ci_workflow_gates.py` an assertion that no step in `ci.yml` references `init_demo_database`, with the anti-vacuity control that the parser found a non-zero number of `run:` blocks.

- [ ] **Step 5: Run and commit**

```bash
cd backend && python -m pytest tests/test_ci_workflow_gates.py --no-cov -q
git add .github/workflows/ci.yml deploy/smoke/compose-smoke.sh frontend/e2e/ backend/tests/test_ci_workflow_gates.py
git commit -m "chore(seed): repoint CI, smoke and e2e at the new seeder and DEMO-PIECE"
```

---

### Task 7: Retire the old seeder

**Files:**
- Delete: `backend/scripts/init_demo_database.py`, `backend/scripts/_seed_capacity.py`, `_seed_common.py`, `_seed_master.py`, `_seed_operations.py`, `_seed_reference.py`, `_seed_simulation.py`, `backend/scripts/seed_sample_client.py`, `scripts/deploy.sh`, `backend/tests/test_scripts/test_init_demo_database.py`, `backend/tests/test_scripts/test_seed_sample_client.py`
- Modify: `backend/seed/cli.py`, `backend/seed/materialize.py`, `backend/pivot/hooks.py`, `backend/tests/test_audit/test_no_bulk_writes_on_audited_tables.py` (comment rewording only)

- [ ] **Step 1: Confirm nothing imports them**

```bash
grep -rn "init_demo_database\|seed_sample_client\|_seed_operations\|_seed_master\|_seed_reference\|_seed_capacity\|_seed_common\|_seed_simulation" backend --include="*.py" | grep -v __pycache__
```
Expected: only comment lines in `backend/seed/*.py`, `pivot/hooks.py` and `test_no_bulk_writes_on_audited_tables.py`. `test_create_admin.py` is unrelated and stays.

- [ ] **Step 2: Delete**

```bash
git rm backend/scripts/init_demo_database.py backend/scripts/_seed_*.py \
       backend/scripts/seed_sample_client.py scripts/deploy.sh \
       backend/tests/test_scripts/test_init_demo_database.py \
       backend/tests/test_scripts/test_seed_sample_client.py
```

- [ ] **Step 3: Reword the comments that now cite a deleted file**

In `backend/seed/cli.py` and `materialize.py`, change "the retiring `seed_sample_client.py`" to "`seed_sample_client.py` (removed in S1c)" — the rationale it carries (the salvaged `CLIENT_SCOPE_COLUMN` map, the `RESET_TABLE_ORDER` lineage, why `USER` is never deleted) is load-bearing for future readers and must survive. Same in `pivot/hooks.py` and `test_no_bulk_writes_on_audited_tables.py`.

- [ ] **Step 4: Full suite, mypy, commit**

```bash
cd backend && python -m pytest tests/ --tb=short -q      # foreground
cd .. && python -m mypy backend
git add -A
git commit -m "chore(seed): retire the old seeder (~5,900 lines)"
```

---

### Task 8: Runbook

**Files:**
- Modify: `docs/deployment/vm-deploy-runbook.md`

- [ ] **Step 1: Repoint the seeding section and add credentials**

In Phase 6, replace `python -m backend.scripts.seed_sample_client --days 90` with `python -m backend.seed.cli --profile full`. Document the six seeded users and `DEMO_PASSWORD`. Record the periodic re-seed follow-up: the seeded window ends at seed-run date, so an un-reseeded VM goes stale exactly as it does today.

- [ ] **Step 2: Commit and open PR-2**

```bash
git add docs/deployment/vm-deploy-runbook.md
git commit -m "docs(deploy): runbook seeds via backend.seed.cli"
```

Then `/cross-review` and `gh pr create`.

---

## Post-merge: the one manual step

~~After PR-2 merges and main is green, **drop the Render demo database once** so Alembic plus the new seeder repopulate it clean. Until then Render serves nine clients — four new and five stale legacy ones that `--reset` cannot see, because it is scoped to the allowlist.~~

**CORRECTED 2026-08-24, before merge — there is no manual step, and the premise was wrong.**

Two things checked against reality rather than carried forward:

1. **Render has no persistent disk.** `render.yaml` says so in its own header ("No persistent disk: DB recreates on each deploy") and carries no `disk:` block; `DATABASE_URL` is `sqlite:////app/database/kpi_platform.db`, a path inside an immutable container. So the merge's auto-deploy starts a fresh container with an empty database, `RUN_MIGRATIONS=true` runs `alembic upgrade head`, and `DEMO_MODE=true` triggers the boot-path seed. The clean repopulation this step describes happens by itself.

2. **It serves five clients, not nine.** Measured against the live demo before merging: `ACME-MFG`, `FASHION-WORKS`, `GLOBAL-APPAREL`, `QUALITY-STITCH`, `TEXTILE-PRO` — the legacy five from the still-deployed old seeder, and none of the new four. The "four new and five stale" figure assumed both seeders had run against one surviving database, which an ephemeral filesystem makes impossible.

What remains is a **verification**, not an action: after the deploy, confirm the demo serves exactly the four allowlisted clients and that `demo_admin` / `DemoSeed#2026` logs in. If it still shows the legacy five, the deploy did not pick up the merge — that is the real failure mode worth watching for, and it is not fixed by dropping a database.

Verify afterwards: exactly four clients, the demo renders, and `/health/live` returns 200.

The VM needs no action: it already runs the four new client ids with `DEMO_MODE=false`, so the boot-path change is dormant there. Re-verify health, frontend and the bogus-login DB probe (401, not 503) after its next deploy.
