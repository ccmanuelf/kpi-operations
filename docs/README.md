# Manufacturing KPI Platform - Phase 1 MVP

Production tracking platform with real-time KPI calculations, featuring FastAPI backend, Vue 3 frontend, and MariaDB database.

## Features

### Phase 1 (MVP) - Production Entry Focus

- **Production Data Entry**: Excel-like grid interface for entering production metrics
- **KPI Calculations**:
  - KPI #3: Efficiency = (units_produced × ideal_cycle_time) / (employees_assigned × run_time_hours) × 100
  - KPI #9: Performance = (ideal_cycle_time × units_produced) / run_time_hours × 100
  - Quality Rate calculation
  - OEE (Overall Equipment Effectiveness)
- **Inference Engine**: Automatic ideal_cycle_time inference when not defined
- **Read-Back Confirmation**: Data validation workflow
- **CSV Bulk Upload**: Import production entries via CSV
- **Real-Time Dashboard**: Live KPI visualization with charts
- **PDF Reports**: Generate daily/weekly production reports
- **JWT Authentication**: Secure role-based access control

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database operations
- **MariaDB**: Production-grade database
- **JWT**: Token-based authentication
- **Pandas**: CSV processing
- **ReportLab**: PDF generation

### Frontend
- **Vue 3**: Progressive JavaScript framework
- **Vuetify 3**: Material Design component library
- **Pinia**: State management
- **Chart.js**: Data visualization
- **Axios**: HTTP client
- **Tailwind CSS**: Utility-first CSS

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- MariaDB 10.11+

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
mysql -u root -p < ../database/schema.sql
mysql -u root -p kpi_platform < ../database/seed_data.sql

# Run backend
uvicorn backend.main:app --reload
```

Backend will be available at: http://localhost:8000

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will be available at: http://localhost:5173

## Database Setup

### Create Database

```sql
CREATE DATABASE kpi_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'kpi_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON kpi_platform.* TO 'kpi_user'@'localhost';
FLUSH PRIVILEGES;
```

### Run Schema

```bash
mysql -u kpi_user -p kpi_platform < database/schema.sql
mysql -u kpi_user -p kpi_platform < database/seed_data.sql
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user

### Production Entries
- `POST /api/production` - Create production entry
- `GET /api/production` - List entries (with filters)
- `GET /api/production/{id}` - Get entry details
- `PUT /api/production/{id}` - Update entry
- `DELETE /api/production/{id}` - Delete entry (supervisor only)
- `POST /api/production/upload/csv` - Bulk CSV upload

### KPIs
- `GET /api/kpi/calculate/{id}` - Calculate KPIs for entry
- `GET /api/kpi/dashboard` - Get dashboard data

### Reports
- `GET /api/reports/daily/{date}` - Generate daily PDF report

### Reference Data
- `GET /api/products` - List products
- `GET /api/shifts` - List shifts

## Default Users (Seed Data)

| Username | Password | Role |
|----------|----------|------|
| admin | password123 | admin |
| supervisor1 | password123 | supervisor |
| operator1 | password123 | operator |
| operator2 | password123 | operator |

**⚠️ Change passwords in production!**

## CSV Upload Format

```csv
product_id,shift_id,production_date,work_order_number,units_produced,run_time_hours,employees_assigned,defect_count,scrap_count,notes
1,1,2025-12-31,WO-2025-001,250,7.5,3,5,2,Example entry
2,2,2025-12-31,WO-2025-002,180,7.0,2,3,1,Another example
```

## Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov=backend
```

### Frontend Tests

```bash
cd frontend
npm run test
```

## KPI Calculation Details

### Efficiency (KPI #3)

**Formula**: `(units_produced × ideal_cycle_time) / (employees_assigned × run_time_hours) × 100`

**Inference Engine**:
- If `ideal_cycle_time` is NULL for product, system uses:
  1. Historical average from last 10 entries of same product
  2. Default: 0.25 hours (15 minutes per unit)

**Example**:
- Units: 250
- Ideal cycle time: 0.25 hours
- Employees: 3
- Runtime: 7.5 hours
- Efficiency: (250 × 0.25) / (3 × 7.5) × 100 = 277.78% (capped at 150%)

### Performance (KPI #9)

**Formula**: `(ideal_cycle_time × units_produced) / run_time_hours × 100`

**Example**:
- Ideal cycle time: 0.25 hours
- Units: 200
- Runtime: 8.0 hours
- Performance: (0.25 × 200) / 8.0 × 100 = 625% (capped at 150%)

### Quality Rate

**Formula**: `((units_produced - defects - scrap) / units_produced) × 100`

### OEE (Overall Equipment Effectiveness)

**Formula**: `Availability × Performance × Quality`

**Phase 1 Note**: Availability assumed 100% (downtime tracking in Phase 2)

## Architecture

```
kpi-operations/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── config.py              # Settings
│   ├── database.py            # DB connection
│   ├── models/                # Pydantic models
│   ├── schemas/               # SQLAlchemy ORM
│   ├── crud/                  # CRUD operations
│   ├── calculations/          # KPI logic
│   ├── auth/                  # JWT auth
│   └── reports/               # PDF generation
├── frontend/
│   └── src/
│       ├── components/        # Vue components
│       ├── views/             # Page views
│       ├── stores/            # Pinia stores
│       ├── services/          # API client
│       └── router/            # Vue Router
├── database/
│   ├── schema.sql             # Database schema
│   └── seed_data.sql          # Sample data
├── tests/
│   ├── backend/               # Backend tests
│   └── frontend/              # Frontend tests
└── docs/
    └── README.md              # This file
```

## Deployment

### Production Configuration

1. **Backend**:
   - Set `DEBUG=False` in `.env`
   - Use production database credentials
   - Configure CORS origins
   - Set strong `SECRET_KEY`

2. **Frontend**:
   - Build for production: `npm run build`
   - Serve with nginx or similar

3. **Database**:
   - Enable MariaDB binary logging
   - Configure backups
   - Optimize indexes

### Docker Deployment

```bash
# Build and run with docker-compose
docker-compose up -d
```

## Future Phases

- **Phase 2**: Downtime tracking, WIP inventory
- **Phase 3**: Attendance tracking, labor metrics
- **Phase 4**: Quality control, defect analysis
- **Phase 5**: Advanced analytics, predictive maintenance

## Support

For issues and questions:
- GitHub Issues: [repo]/issues
- Documentation: `/docs`

## License

Proprietary - All rights reserved

---

**Version**: 1.0.0
**Last Updated**: 2025-12-31
