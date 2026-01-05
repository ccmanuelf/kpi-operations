#!/usr/bin/env python3
"""
Migration Verification Script
Comprehensive validation queries to confirm migration success
"""
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from sqlalchemy import create_engine, text, inspect
from config import settings
from tabulate import tabulate


def verify_migration():
    """Run comprehensive verification queries"""

    print("="*70)
    print("MIGRATION VERIFICATION QUERIES")
    print("="*70)

    engine = create_engine(settings.DATABASE_URL, echo=False)

    with engine.connect() as conn:
        inspector = inspect(engine)

        # Query 1: Check columns were added
        print("\n1️⃣  CLIENT_ID COLUMNS IN ALL TABLES")
        print("-"*70)

        tables = ['downtime_events', 'wip_holds', 'attendance_records',
                  'shift_coverage', 'quality_inspections', 'floating_pool']

        column_data = []
        for table in tables:
            columns = {col['name']: col for col in inspector.get_columns(table)}
            if 'client_id' in columns:
                col = columns['client_id']
                column_data.append([
                    table,
                    col['type'],
                    'YES' if col['nullable'] else 'NO',
                    'VARCHAR(50)'
                ])
            else:
                column_data.append([table, 'NOT FOUND', '-', '-'])

        print(tabulate(column_data,
                      headers=['Table Name', 'Data Type', 'Nullable', 'Column Type'],
                      tablefmt='grid'))

        # Query 2: Check foreign key constraints
        print("\n2️⃣  FOREIGN KEY CONSTRAINTS")
        print("-"*70)

        fk_data = []
        for table in tables:
            fks = inspector.get_foreign_keys(table)
            client_fks = [fk for fk in fks if 'client_id' in fk.get('constrained_columns', [])]

            for fk in client_fks:
                fk_data.append([
                    fk['name'],
                    table,
                    fk['referred_table'],
                    ', '.join(fk['constrained_columns']),
                    ', '.join(fk['referred_columns'])
                ])

        print(tabulate(fk_data,
                      headers=['Constraint Name', 'Table', 'References', 'Local Columns', 'Foreign Columns'],
                      tablefmt='grid'))

        # Query 3: Check indexes
        print("\n3️⃣  INDEXES ON CLIENT_ID COLUMNS")
        print("-"*70)

        index_data = []
        for table in tables:
            indexes = inspector.get_indexes(table)
            client_indexes = [idx for idx in indexes if any('client_id' in str(col) for col in idx.get('column_names', []))]

            for idx in client_indexes:
                index_data.append([
                    table,
                    idx['name'],
                    ', '.join(idx['column_names']),
                    'YES' if idx['unique'] else 'NO'
                ])

        print(tabulate(index_data,
                      headers=['Table Name', 'Index Name', 'Columns', 'Unique'],
                      tablefmt='grid'))

        # Query 4: Row counts (data integrity check)
        print("\n4️⃣  ROW COUNTS (DATA INTEGRITY)")
        print("-"*70)

        count_data = []
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table}"))
            count = result.fetchone()[0]

            # Check for NULL values in client_id
            null_result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table} WHERE client_id IS NULL"))
            null_count = null_result.fetchone()[0]

            count_data.append([
                table,
                count,
                null_count,
                'PASS' if null_count == 0 or table == 'floating_pool' else 'FAIL'
            ])

        print(tabulate(count_data,
                      headers=['Table Name', 'Total Rows', 'NULL client_id', 'Status'],
                      tablefmt='grid'))

        # Query 5: Sample data check
        print("\n5️⃣  SAMPLE DATA (First 3 rows from each table)")
        print("-"*70)

        for table in tables:
            print(f"\n{table.upper()}:")
            try:
                result = conn.execute(text(f"SELECT * FROM {table} LIMIT 3"))
                rows = result.fetchall()
                if rows:
                    columns = result.keys()
                    print(tabulate(rows, headers=columns, tablefmt='simple'))
                else:
                    print("  (empty table)")
            except Exception as e:
                print(f"  Error: {e}")

        print("\n" + "="*70)
        print("VERIFICATION COMPLETE")
        print("="*70)


if __name__ == "__main__":
    try:
        verify_migration()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        sys.exit(1)
