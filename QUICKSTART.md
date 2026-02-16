# Manufacturing KPI Platform - Quick Start Guide

Get the platform running in 5 minutes!

## Prerequisites

- Python 3.11+
- Node.js 18+
- MariaDB 10.11+ (production) **OR** SQLite (demo/development — no install needed)

---

## Option A: SQLite Quick Start (Recommended for Development)

No database installation required. SQLite is included with Python.

### Step 1: Backend Setup

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database and seed demo data
cd ../database
python init_sqlite_schema.py
python generators/generate_demo_data.py
python create_demo_users.py
cd ../backend

# Start backend (PYTHONPATH required for module imports)
PYTHONPATH=.. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 2: Frontend Setup

Open a new terminal:

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

### Step 3: Login

Open **http://localhost:3000** and login with `operator1` / `password123`.

The SQLite database file is created at `database/kpi_platform.db`. Delete it and re-run the seed command to reset demo data at any time.

---

## Option B: MariaDB Setup (Production)

### Step 1: Database Setup (2 minutes)

```bash
# Create database and user
mysql -u root -p << 'EOF'
CREATE DATABASE kpi_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'kpi_user'@'localhost' IDENTIFIED BY 'kpi_password_123';
GRANT ALL PRIVILEGES ON kpi_platform.* TO 'kpi_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# Load schema and seed data
cd .
mysql -u kpi_user -p kpi_platform < database/schema.sql
# Password: kpi_password_123

mysql -u kpi_user -p kpi_platform < database/seed_data.sql
# Password: kpi_password_123
```

## Step 2: Backend Setup (1 minute)

```bash
cd ./backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
DATABASE_URL=mysql+pymysql://kpi_user:kpi_password_123@localhost:3306/kpi_platform
SECRET_KEY=dev-secret-key-change-in-production-min-32-chars-long
DEBUG=True
CORS_ORIGINS=http://localhost:3000
EOF

# Start backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will start at: **http://localhost:8000**

## Step 3: Frontend Setup (2 minutes)

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will start at: **http://localhost:3000**

## Step 4: Login & Test

1. Open browser: **http://localhost:3000**
2. Login with:
   - **Username**: `operator1`
   - **Password**: `password123`
3. Navigate to:
   - Dashboard: See sample data
   - Production Entry: Add new entries
   - KPI Dashboard: View charts

## Verify Installation

### Check Backend Health

```bash
curl http://localhost:8000/
# Should return: {"status":"healthy","service":"Manufacturing KPI Platform API",...}
```

### Check Database

```bash
mysql -u kpi_user -p kpi_platform -e "SELECT COUNT(*) FROM production_entry;"
# Should show sample entries (18+)
```

### API Documentation

Visit: **http://localhost:8000/docs** for interactive Swagger UI

## Available Users

| Username | Password | Role |
|----------|----------|------|
| admin | password123 | admin |
| supervisor1 | password123 | supervisor |
| operator1 | password123 | operator |
| operator2 | password123 | operator |

## Test the Features

### 1. View Dashboard
- Go to Dashboard
- See sample production data
- View KPI metrics

### 2. Add Production Entry
1. Click "Production Entry"
2. Click "Add Entry"
3. Fill in:
   - Product: Widget Standard
   - Shift: Morning
   - Date: Today
   - Units: 250
   - Runtime: 7.5 hours
   - Employees: 3
4. Save
5. See automatic KPI calculation!

### 3. Upload CSV
1. Download template
2. Edit with your data
3. Upload via drag-and-drop
4. See batch import results

### 4. View KPI Dashboard
- Real-time charts
- 30-day trends
- Performance metrics

## Troubleshooting

### Backend won't start

```bash
# Check Python version
python --version  # Should be 3.11+

# Check virtual environment
which python  # Should point to venv/bin/python

# Check database connection
mysql -u kpi_user -p kpi_platform -e "SHOW TABLES;"
```

### Frontend won't start

```bash
# Check Node version
node --version  # Should be 18+

# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Database issues

```bash
# Verify MariaDB is running
sudo systemctl status mariadb  # Linux
brew services list  # macOS

# Check database exists
mysql -u root -p -e "SHOW DATABASES LIKE 'kpi_platform';"

# Re-run schema if needed
mysql -u kpi_user -p kpi_platform < database/schema.sql
```

## Stop Services

```bash
# Stop backend: Ctrl+C in backend terminal

# Stop frontend: Ctrl+C in frontend terminal

# Stop MariaDB (if needed)
sudo systemctl stop mariadb  # Linux
brew services stop mariadb   # macOS
```

## Next Steps

1. **Explore Features**:
   - Try all CRUD operations
   - Upload CSV files
   - Generate PDF reports
   - Check KPI calculations

2. **Read Documentation**:
   - `/docs/README.md` - Full guide
   - `/docs/API_DOCUMENTATION.md` - API reference
   - `/docs/DEPLOYMENT.md` - Production setup

3. **Run Tests**:
   ```bash
   cd backend
   pytest tests/ -v
   ```

4. **Customize**:
   - Add your products in database
   - Configure shifts
   - Adjust KPI targets
   - Brand the frontend

## Production Deployment

For production setup, see `/docs/DEPLOYMENT.md` which includes:
- Nginx configuration
- HTTPS setup
- Systemd services
- Docker deployment
- Security checklist

## Support

- Documentation: `/docs/`
- API Docs: http://localhost:8000/docs
- Implementation Summary: `/docs/IMPLEMENTATION_SUMMARY.md`

---

**Ready to go!** Login at http://localhost:3000 with `operator1` / `password123`
