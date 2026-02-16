#!/usr/bin/env python3
"""
Create Demo Users for KPI Platform
Adds users with bcrypt-hashed passwords to the SQLite database
"""

import sqlite3
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from passlib.context import CryptContext
except ImportError:
    print("Installing passlib...")
    os.system("pip3 install passlib bcrypt")
    from passlib.context import CryptContext

# Password hashing context (same as backend)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'kpi_platform.db')

print("🔐 Creating Demo Users for KPI Platform")
print("=" * 60)
print(f"Database: {DB_PATH}")
print()

if not os.path.exists(DB_PATH):
    print("❌ Database not found! Run init_sqlite_schema.py first.")
    sys.exit(1)

# Demo users to create
# Password: admin123 for admin, password123 for others
# NOTE: Demo passwords intentionally simple. This script is for local development
# only. Production deployments MUST use strong passwords via environment variables.
# See docs/SECURITY.md for production password policy.
DEMO_USERS = [
    {
        'user_id': 'USR-ADMIN-001',
        'username': 'admin',
        'email': 'admin@kpiplatform.local',
        'password': 'admin123',
        'full_name': 'System Administrator',
        'role': 'ADMIN',
        'client_id_assigned': None
    },
    {
        'user_id': 'USR-POWER-001',
        'username': 'poweruser',
        'email': 'poweruser@kpiplatform.local',
        'password': 'password123',
        'full_name': 'Power User',
        'role': 'POWERUSER',
        'client_id_assigned': None
    },
    {
        'user_id': 'USR-LEADER-001',
        'username': 'leader',
        'email': 'leader@kpiplatform.local',
        'password': 'password123',
        'full_name': 'Team Leader',
        'role': 'LEADER',
        'client_id_assigned': 'BOOT-LINE-A'
    },
    {
        'user_id': 'USR-OPER-001',
        'username': 'operator',
        'email': 'operator@kpiplatform.local',
        'password': 'password123',
        'full_name': 'Line Operator',
        'role': 'OPERATOR',
        'client_id_assigned': 'BOOT-LINE-A'
    },
    {
        'user_id': 'USR-OPER-002',
        'username': 'operator2',
        'email': 'operator2@kpiplatform.local',
        'password': 'password123',
        'full_name': 'Second Operator',
        'role': 'OPERATOR',
        'client_id_assigned': 'APPAREL-B'
    },
    # Supervisor role (maps to admin/supervisor in frontend)
    {
        'user_id': 'USR-SUPER-001',
        'username': 'supervisor',
        'email': 'supervisor@kpiplatform.local',
        'password': 'password123',
        'full_name': 'Production Supervisor',
        'role': 'LEADER',  # Using LEADER as supervisor equivalent
        'client_id_assigned': 'BOOT-LINE-A,APPAREL-B'
    }
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("👤 Creating demo users...")
print()

created = 0
updated = 0
errors = []

for user in DEMO_USERS:
    # Hash the password
    password_hash = pwd_context.hash(user['password'])
    
    try:
        # Check if user exists
        cursor.execute("SELECT user_id FROM USER WHERE username = ?", (user['username'],))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing user
            cursor.execute("""
                UPDATE USER 
                SET password_hash = ?, 
                    email = ?,
                    full_name = ?,
                    role = ?,
                    client_id_assigned = ?,
                    is_active = 1,
                    updated_at = datetime('now')
                WHERE username = ?
            """, (
                password_hash,
                user['email'],
                user['full_name'],
                user['role'],
                user['client_id_assigned'],
                user['username']
            ))
            updated += 1
            print(f"   ✓ Updated: {user['username']} (password: {user['password']})")
        else:
            # Insert new user
            cursor.execute("""
                INSERT INTO USER (
                    user_id, username, email, password_hash, full_name, 
                    role, client_id_assigned, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            """, (
                user['user_id'],
                user['username'],
                user['email'],
                password_hash,
                user['full_name'],
                user['role'],
                user['client_id_assigned']
            ))
            created += 1
            print(f"   ✓ Created: {user['username']} (password: {user['password']})")
            
    except Exception as e:
        errors.append(f"{user['username']}: {str(e)}")
        print(f"   ❌ Error with {user['username']}: {e}")

conn.commit()
conn.close()

print()
print("=" * 60)
print(f"✅ Demo users setup complete!")
print(f"   Created: {created}")
print(f"   Updated: {updated}")
if errors:
    print(f"   Errors: {len(errors)}")
    for err in errors:
        print(f"      - {err}")

print()
print("📝 Login Credentials:")
print("-" * 40)
print("Username       | Password     | Role")
print("-" * 40)
print("admin          | admin123     | ADMIN")
print("poweruser      | password123  | POWERUSER")
print("supervisor     | password123  | LEADER")
print("leader         | password123  | LEADER")
print("operator       | password123  | OPERATOR")
print("operator2      | password123  | OPERATOR")
print("-" * 40)
