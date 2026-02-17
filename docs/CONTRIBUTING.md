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
