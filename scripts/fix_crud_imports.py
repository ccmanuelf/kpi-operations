#!/usr/bin/env python3
"""
Fix schema imports in CRUD files
Changes 'from schemas.X import' to 'from backend.schemas.X import'
"""
import os
import re
from pathlib import Path

def fix_imports_in_file(filepath):
    """Fix imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace schema imports
        original_content = content
        content = re.sub(
            r'from schemas\.(\w+) import',
            r'from backend.schemas.\1 import',
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
    """Find and fix all Python files in backend/crud directory"""
    crud_dir = Path('/Users/mcampos.cerda/Documents/Programming/kpi-operations/backend/crud')
    if not crud_dir.exists():
        print(f"Directory not found: {crud_dir}")
        return

    fixed_count = 0
    for filepath in crud_dir.glob('*.py'):
        if fix_imports_in_file(filepath):
            print(f"Fixed: {filepath.name}")
            fixed_count += 1

    print(f"\nTotal CRUD files fixed: {fixed_count}")

if __name__ == '__main__':
    main()
