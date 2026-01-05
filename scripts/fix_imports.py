#!/usr/bin/env python3
"""
Fix database imports across all backend files
Changes 'from database import' to 'from backend.database import'
"""
import os
import re
from pathlib import Path

def fix_imports_in_file(filepath):
    """Fix imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the import
        original_content = content
        content = re.sub(
            r'from database import',
            'from backend.database import',
            content
        )

        # Only write if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Find and fix all Python files in backend directory"""
    backend_dir = Path('/Users/mcampos.cerda/Documents/Programming/kpi-operations/backend')
    fixed_count = 0

    for filepath in backend_dir.rglob('*.py'):
        # Skip venv directory
        if 'venv' in str(filepath):
            continue

        if fix_imports_in_file(filepath):
            print(f"Fixed: {filepath.relative_to(backend_dir.parent)}")
            fixed_count += 1

    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == '__main__':
    main()
