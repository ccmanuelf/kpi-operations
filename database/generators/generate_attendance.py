#!/usr/bin/env python3
"""
Generate realistic attendance sample data for KPI #10 (Absenteeism)
Creates employees and 100+ attendance records with absences and coverage
"""

import random
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'kpi_operations',
    'user': 'root',
    'password': 'root'
}

CLIENTS = ['BOOT-LINE-A', 'CLIENT-B', 'CLIENT-C']

# Employee names for sample data
EMPLOYEE_NAMES = [
    'John Smith', 'Maria Garcia', 'Ahmed Hassan', 'Linda Chen', 'Carlos Rodriguez',
    'Sarah Johnson', 'David Kim', 'Emma Williams', 'Michael Brown', 'Sophia Martinez',
    'James Wilson', 'Olivia Taylor', 'Robert Anderson', 'Isabella Thomas', 'William Jackson',
    'Mia White', 'Joseph Harris', 'Charlotte Martin', 'Charles Thompson', 'Amelia Garcia',
    'Thomas Moore', 'Harper Lee', 'Daniel Martin', 'Evelyn Clark', 'Matthew Lewis'
]

FLOATING_POOL_NAMES = [
    'Alex Float-001', 'Jamie Float-002', 'Taylor Float-003', 'Jordan Float-004', 'Morgan Float-005'
]

ABSENCE_TYPES = {
    'UNSCHEDULED_ABSENCE': 0.50,  # 50% of absences
    'MEDICAL_LEAVE': 0.25,         # 25%
    'PERSONAL_DAY': 0.15,          # 15%
    'VACATION': 0.08,              # 8%
    'SUSPENDED': 0.02              # 2%
}


def generate_employees():
    """Generate employee records"""
    employees = []

    # Regular employees
    for i, name in enumerate(EMPLOYEE_NAMES, start=1):
        employee = {
            'employee_code': f'EMP-{i:03d}',
            'full_name': name,
            'email': f"{name.lower().replace(' ', '.')}@company.com",
            'client_assigned': random.choice(CLIENTS),
            'is_floating_pool': 0
        }
        employees.append(employee)

    # Floating pool employees
    for i, name in enumerate(FLOATING_POOL_NAMES, start=len(EMPLOYEE_NAMES) + 1):
        employee = {
            'employee_code': f'FLOAT-{i:03d}',
            'full_name': name,
            'email': f"{name.lower().replace(' ', '.')}@company.com",
            'client_assigned': None,  # Floating - no fixed assignment
            'is_floating_pool': 1
        }
        employees.append(employee)

    return employees


def insert_employees(employees):
    """Insert employees into database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO employee (
                employee_code, full_name, email, client_assigned, is_floating_pool
            ) VALUES (
                %(employee_code)s, %(full_name)s, %(email)s, %(client_assigned)s, %(is_floating_pool)s
            )
        """

        cursor.executemany(insert_query, employees)
        connection.commit()

        print(f"✅ Successfully inserted {cursor.rowcount} employees")

        cursor.close()
        connection.close()

        return True

    except Error as e:
        print(f"❌ Database error inserting employees: {e}")
        return False


def generate_attendance_entries(employee_count=25, floating_count=5, days=90):
    """Generate realistic attendance entries"""
    entries = []
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # Generate attendance for each day
    current_date = start_date
    while current_date <= end_date:
        # Skip Sundays (most companies don't work Sundays)
        if current_date.weekday() == 6:
            current_date += timedelta(days=1)
            continue

        # For each regular employee
        for emp_id in range(1, employee_count + 1):
            # Determine shift (mostly 1st shift, some 2nd shift, rare weekend OT)
            if current_date.weekday() == 5:  # Saturday
                shift_id = random.choice([1, 1, 1, 3])  # Mostly skip, some SAT_OT
                if shift_id == 3:  # SAT_OT has shorter hours
                    scheduled_hours = 8.0
                else:
                    continue  # Skip this Saturday for this employee
            else:
                shift_id = random.choices([1, 2], weights=[0.85, 0.15])[0]
                scheduled_hours = 9.0 if shift_id == 1 else 9.0

            # Determine if absent (10% absence rate)
            is_absent = random.random() < 0.10

            if is_absent:
                # Select absence type
                absence_type = random.choices(
                    list(ABSENCE_TYPES.keys()),
                    weights=list(ABSENCE_TYPES.values())
                )[0]

                absence_hours = scheduled_hours
                actual_hours = 0

                # 60% of absences get covered by floating pool
                covered_by = None
                coverage_confirmed = False
                if random.random() < 0.60 and floating_count > 0:
                    covered_by = random.randint(employee_count + 1, employee_count + floating_count)
                    coverage_confirmed = random.choice([True, False])  # 50% confirmed

                notes = {
                    'UNSCHEDULED_ABSENCE': 'Called in sick - no prior notice',
                    'MEDICAL_LEAVE': 'Doctor appointment - approved medical leave',
                    'PERSONAL_DAY': 'Personal emergency - supervisor approved',
                    'VACATION': 'Scheduled vacation day',
                    'SUSPENDED': 'Disciplinary suspension'
                }.get(absence_type, 'Absence recorded')

            else:
                # Present - calculate actual hours
                # 90% work full shift, 10% leave early or arrive late
                if random.random() < 0.90:
                    actual_hours = scheduled_hours
                else:
                    actual_hours = round(scheduled_hours - random.uniform(0.5, 2.0), 2)

                absence_type = None
                absence_hours = None
                covered_by = None
                coverage_confirmed = False
                notes = None

            # Recorded by supervisor (user 2)
            recorded_by = 2

            # 80% verified
            verified_by = 2 if random.random() < 0.80 else None

            entry = {
                'employee_id': emp_id,
                'client_name': CLIENTS[(emp_id - 1) % len(CLIENTS)],
                'shift_date': current_date,
                'shift_id': shift_id,
                'scheduled_hours': scheduled_hours,
                'actual_hours': actual_hours,
                'is_absent': 1 if is_absent else 0,
                'absence_type': absence_type,
                'absence_hours': absence_hours,
                'covered_by_floating_employee_id': covered_by,
                'coverage_confirmed': 1 if coverage_confirmed else 0,
                'recorded_by_user_id': recorded_by,
                'verified_by_user_id': verified_by,
                'notes': notes
            }

            entries.append(entry)

        current_date += timedelta(days=1)

    return entries


def insert_attendance_entries(entries):
    """Insert attendance entries into database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO attendance_entry (
                employee_id, client_name, shift_date, shift_id, scheduled_hours,
                actual_hours, is_absent, absence_type, absence_hours,
                covered_by_floating_employee_id, coverage_confirmed,
                recorded_by_user_id, verified_by_user_id, notes
            ) VALUES (
                %(employee_id)s, %(client_name)s, %(shift_date)s, %(shift_id)s, %(scheduled_hours)s,
                %(actual_hours)s, %(is_absent)s, %(absence_type)s, %(absence_hours)s,
                %(covered_by_floating_employee_id)s, %(coverage_confirmed)s,
                %(recorded_by_user_id)s, %(verified_by_user_id)s, %(notes)s
            )
        """

        cursor.executemany(insert_query, entries)
        connection.commit()

        print(f"✅ Successfully inserted {cursor.rowcount} attendance entries")

        # Statistics
        total_scheduled = sum(e['scheduled_hours'] for e in entries)
        total_absent = sum(e['absence_hours'] for e in entries if e['absence_hours'])
        absenteeism_rate = (total_absent / total_scheduled * 100) if total_scheduled > 0 else 0

        absences = sum(1 for e in entries if e['is_absent'])
        covered = sum(1 for e in entries if e['covered_by_floating_employee_id'])

        print(f"\n📊 Statistics:")
        print(f"   Total scheduled hours: {total_scheduled:.2f}")
        print(f"   Total absence hours: {total_absent:.2f}")
        print(f"   Absenteeism rate: {absenteeism_rate:.2f}%")
        print(f"   Total absences: {absences}")
        print(f"   Covered by floating pool: {covered} ({covered/absences*100:.1f}% if absences > 0 else 0)")

        cursor.close()
        connection.close()

    except Error as e:
        print(f"❌ Database error: {e}")


if __name__ == "__main__":
    print("👥 Generating employee and attendance sample data...")

    # Generate and insert employees
    employees = generate_employees()
    if insert_employees(employees):
        print(f"   Regular employees: {len(EMPLOYEE_NAMES)}")
        print(f"   Floating pool: {len(FLOATING_POOL_NAMES)}")

        # Generate and insert attendance
        entries = generate_attendance_entries(
            employee_count=len(EMPLOYEE_NAMES),
            floating_count=len(FLOATING_POOL_NAMES),
            days=90
        )
        insert_attendance_entries(entries)

    print("✅ Attendance data generation complete!")
