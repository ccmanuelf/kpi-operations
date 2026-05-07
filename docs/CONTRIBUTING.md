# Contributing to KPI Operations Platform

## Commit Messages

Use conventional commit format:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `refactor:` Code restructuring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

## What Not to Commit

- Binary files (`.xlsx`, `.db`, images)
- Coverage reports (`coverage.xml`, `htmlcov/`)
- Environment files (`.env`, `.env.local`)
- Test artifacts (`playwright-report/`, `test-results/`)
- IDE settings (`.vscode/`, `.idea/`)

## Development Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/init_demo_database.py

# Frontend
cd frontend
# --legacy-peer-deps required for eslint 10 + eslint-plugin-vue 10 peer conflicts
npm install --legacy-peer-deps
npm run dev
```

## Code Style

### Python (Backend)

- **Formatter**: [Black](https://github.com/psf/black) (v25.1) -- run `black .` from `backend/`
- **Line length**: 120 characters (configured in `pyproject.toml`)
- **Indentation**: 4 spaces
- **Type hints**: Required on all function signatures; use Pydantic models for request/response validation
- **Imports**: Standard library first, third-party second, local third; one blank line between groups
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants
- **Type checker**: mypy (v1.15) -- run `mypy backend/` for static analysis

### JavaScript / Vue (Frontend)

- **Linter**: [ESLint 10](https://eslint.org/) with flat config (`frontend/eslint.config.js`)
- **Rule set**: `flat/essential` from `eslint-plugin-vue` (not `flat/recommended`)
- **Indentation**: 2 spaces
- **SFC style**: `<script setup>` preferred for new Vue components
- **State management**: Pinia 3 stores only (no Vuex)
- **CSS**: Tailwind CSS 4 utility classes; `@import "tailwindcss"` in CSS files
- **Run lint**: `npm run lint` from `frontend/`

### Entry-UI Standard (mutation surfaces)

Any view or component whose primary job is to mutate backend records
(POST / PUT / DELETE) MUST follow the Spreadsheet Standard described
in [`docs/standards/entry-ui-standard.md`](standards/entry-ui-standard.md):

- Build on `frontend/src/components/grids/AGGridBase.vue` — no new
  `v-data-table` + per-cell form-field constructions, no new
  `v-form`-wrapped entry dialogs.
- Use the workbook-save pattern (Group D) or inline-edit autosave
  pattern (Group E / H); see the standard for canonical reference
  composables.
- Keep payloads aligned with the backend Pydantic schema — every
  payload-building helper needs a service-level test that asserts
  the exact body shape.
- Multi-tenant `client_id` resolves from `useAuthStore` →
  `useKPIStore` (never hardcode).

ESLint enforces a soft (warning) `vue/no-restricted-syntax` rule
that flags `<v-form>` in `src/views/**` and
`src/components/entries/**`. Files in the four permitted exception
buckets (login / admin config / filter dialog / confirmation) are
listed by path in `eslint.config.js`. To add a new exception,
update that list with a one-line justification.

### E2E Parity (mandatory for any view/component change)

When a PR migrates, replaces, or substantially restructures a Vue
view in `frontend/src/views/` or a grid/entry component in
`frontend/src/components/`, the corresponding Playwright spec in
`frontend/e2e/` MUST be updated **in the same PR** — not deferred,
not marked `test.describe.skip`, not "we'll do it later".

This rule exists because the entry-interface migration (Phase 3,
2026-05-02) shipped to `main` without updating ~83 e2e tests across
~10 spec files; the obsoleted selectors silently broke CI for 50+
consecutive commits and only surfaced when the rest of CI was
cleaned up. Recovering required a multi-session rewrite tracked as
`memory/ci-hygiene-tracker.md` Phase B.7.

**What "updated in the same PR" means:**

1. **If the change is a UI refactor** (form → grid, tabs → single
   surface, role/aria changes), every test in the affected spec file
   that touches the changed UI must be rewritten to match the new
   surface. Don't write tests against the old API and assume someone
   else will update them.

2. **If the change deletes a feature**, the corresponding spec
   describe block is deleted (not skipped). Leaving `test.describe(
   'X', ...)` for a feature that no longer exists is rot.

3. **If the change adds a feature**, new tests cover the user-facing
   contract. Coverage must not regress.

4. **`test.describe.skip(...)` is reserved for transient outages**
   (e.g., upstream library bug, environment-specific limitation) and
   MUST include either a linked GitHub issue or a `// FIXME(date)`
   comment with a target re-enable date. PRs that add a new skip
   without a tracking link will be rejected at review.

**Why the tests can't wait:**

- Skipped tests don't fail CI, so they hide regressions on the
  *non-skipped* tests too — pytest/Playwright runners surface a
  passing-suite signal that's actually misleading.
- "Rewrite later" never happens unless someone else makes it their
  problem. The PR author has the deepest context for the change and
  is the right person to do the test update.
- Stale specs become harder to rewrite over time as the gap between
  test selectors and current UI widens.

**Reviewer checklist:**

- If the diff includes `frontend/src/views/**` or
  `frontend/src/components/grids/**`, find the matching spec in
  `frontend/e2e/`. Verify it was updated in the same diff.
- If the diff adds a `test.describe.skip(`, ask: is there a linked
  issue? a target date? Reject if not.
- If a Vue surface was deleted, the spec describe should be deleted
  or rewritten — not left orphaned.

**Stable selectors (use these, in this order of preference):**

1. `a[href="/route"]` for navigation links — stable across i18n.
2. `data-testid="..."` attributes added to Vue components — most
   stable, immune to UI restyling. Prefer these over class/role
   selectors when adding new tests.
3. `getByRole('grid' | 'row' | 'cell' | ...)` for AG Grid surfaces —
   semantic and accessibility-friendly.
4. `text=...` / `getByText(...)` ONLY for static labels that are
   part of the user-visible contract; avoid for dynamic content,
   nav items (use `a[href]`), or anything localized.

**Never use:**

- `text=Foo` for nav items (matches *any* element with that text,
  including page content).
- `if (await x.isVisible()) { ... }` early-exit patterns that
  silently pass when the element is missing — use
  `await expect(x).toBeVisible()` and let it fail loud.
- Tautological assertions like `expect(value !== undefined)
  .toBeTruthy()` — these can only fail via timeout, never by
  contract violation.

### General

- See `.editorconfig` for editor-level settings
- Maximum file size target: 500 lines per file
- Prefer editing existing files over creating new ones

## Testing

### Running Tests

```bash
# Backend (pytest 8, real DB tests)
cd backend && python -m pytest tests/ -v

# Backend with coverage
cd backend && python -m pytest tests/ --cov=backend --cov-report=term-missing

# Frontend unit tests (Vitest 4)
cd frontend && npm test

# E2E tests (Playwright, SQLite backend)
cd frontend && npm run test:e2e:sqlite
```

### Testing Requirements

1. **Real database tests only for CRUD operations** -- never use mocks for anything that touches the database. Use the `transactional_db` fixture and `TestDataFactory` from `backend/tests/conftest.py`. Mock-based CRUD tests have historically hidden production bugs (non-existent columns, type mismatches).

2. **Test count only goes up** -- never remove or skip tests without replacing them. If a test is flaky, fix the root cause or rewrite it.

3. **Zero tolerance for flaky tests** -- every test must pass reliably. Known patterns to avoid:
   - `text=` selectors in E2E (ambiguous matches)
   - `form.isVisible()` without timeout (returns instantly)
   - `describe.serial` mode with independent `beforeEach` login

4. **Coverage thresholds** -- backend: 55% minimum (currently ~76%), frontend: 10/10/5/10 (lines/functions/branches/statements).

5. **E2E navigation patterns** -- use `a[href="/path"]` selectors, call `scrollIntoViewIfNeeded()`, verify URL changes with `waitForURL()`.

## Pull Request Process

1. **Branch naming**: `feat/description`, `fix/description`, `docs/description`, `chore/description`

2. **Before opening a PR**:
   - Run the full backend test suite: `cd backend && python -m pytest tests/ -v`
   - Run frontend lint and tests: `cd frontend && npm run lint && npm test`
   - Run E2E tests if touching frontend views: `cd frontend && npm run test:e2e:sqlite`
   - Ensure no new lint warnings or test failures

3. **PR description** must include:
   - Summary of changes (what and why)
   - Test plan (what was tested, any new tests added)
   - Breaking changes (if any)

4. **Review checklist**:
   - No hardcoded secrets or credentials
   - All database access filtered by `client_id` (multi-tenant isolation)
   - New endpoints have Pydantic request/response models
   - New features have corresponding tests
   - Documentation updated if public API changed

5. **Merge policy**: Squash merge to `main`; PR title becomes the commit message
