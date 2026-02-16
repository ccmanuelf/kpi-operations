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

## Testing

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend unit tests
cd frontend && npm test

# E2E (SQLite)
cd frontend && npm run test:e2e:sqlite
```

## Code Style

- Python: 4 spaces, 120 char line length
- JavaScript/Vue: 2 spaces
- See `.editorconfig` for details
