# Backend Virtual Environment Setup

This document describes the Python virtual environment setup for the KPI Operations backend.

## Why Virtual Environment?

A virtual environment isolates the project's Python dependencies from the global system, preventing:
- Dependency conflicts with other projects or system packages
- Version mismatches between packages
- "Works on my machine" issues

## Setup Instructions

### Initial Setup (One-time)

```bash
# Navigate to the backend directory
cd backend

# Create virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # macOS/Linux
# OR
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Daily Development Workflow

```bash
# Always activate the virtual environment before working
cd backend
source venv/bin/activate

# Verify activation (should show venv path)
which python

# When done, deactivate
deactivate
```

### IDE Configuration

#### VS Code
1. Open Command Palette (Cmd+Shift+P)
2. Search "Python: Select Interpreter"
3. Choose `./venv/bin/python`

#### PyCharm
1. Go to Settings > Project > Python Interpreter
2. Add Interpreter > Existing Environment
3. Select `./venv/bin/python`

## Adding New Dependencies

```bash
# Activate environment first
source venv/bin/activate

# Install new package
pip install package-name

# Update requirements.txt
pip freeze > requirements.txt
```

## Troubleshooting

### "Command not found" errors
Ensure the virtual environment is activated (you should see `(venv)` in your terminal prompt).

### Dependency conflicts
```bash
# Verify no broken requirements
pip check

# Reinstall all dependencies from scratch
pip install -r requirements.txt --force-reinstall
```

### Recreate environment
```bash
# Remove existing venv
rm -rf venv

# Create fresh environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Backend

```bash
# Activate environment
source venv/bin/activate

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Git Ignore

The `venv/` directory is excluded from version control via `.gitignore`. Each developer creates their own local virtual environment.
