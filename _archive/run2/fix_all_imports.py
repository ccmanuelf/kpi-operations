#!/usr/bin/env python3
"""
Comprehensive import fixer for the entire backend codebase
"""
import re
from pathlib import Path

def fix_all_imports(filepath):
    """Fix all import patterns in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Fix: from models.X import -> from backend.schemas.X import
        content = re.sub(r'from models\.(\w+) import', r'from backend.schemas.\1 import', content)

        # Fix: from schemas.X import -> from backend.schemas.X import
        content = re.sub(r'(?<!backend\.)from schemas\.(\w+) import', r'from backend.schemas.\1 import', content)

        # Fix: from config import -> from backend.config import
        content = re.sub(r'(?<!backend\.)from config import', r'from backend.config import', content)

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error: {filepath}: {e}")
        return False

def main():
    backend_dir = Path('/Users/mcampos.cerda/Documents/Programming/kpi-operations/backend')
    fixed = 0

    for filepath in backend_dir.rglob('*.py'):
        if 'venv' in str(filepath):
            continue
        if fix_all_imports(filepath):
            print(f"Fixed: {filepath.relative_to(backend_dir.parent)}")
            fixed += 1

    print(f"\nTotal files fixed: {fixed}")

if __name__ == '__main__':
    main()
