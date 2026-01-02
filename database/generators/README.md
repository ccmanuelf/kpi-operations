# Sample Data Generators

This directory contains scripts to generate realistic sample data for validating all 10 KPIs.

## Usage

1. **Apply database schema extensions:**
   ```bash
   sqlite3 ../kpi_platform.db < ../schema_phase2_4_extension.sql
   ```

2. **Generate sample data:**
   ```bash
   python3 generate_sample_data.py
   ```

3. **Verify data generation:**
   The script will output statistics for all generated data:
   - Work Orders (150)
   - Downtime Entries (~90)
   - Hold Entries (~45)
   - Employees (50)
   - Attendance Entries (~1,500)
   - Quality Entries (200)
   - Part Opportunities (5)

## Generated Data Distribution

### Work Orders
- 150 work orders across 3 clients
- 5 different styles (T-SHIRT, POLO, JACKET, PANTS, DRESS)
- Status: 50% COMPLETED, 30% ACTIVE, 10% ON_HOLD, 5% CANCELLED, 5% REJECTED
- Date range: Last 90 days
- 70% on-time delivery, 30% late (for OTD validation)

### Downtime Entries
- ~90 entries (60% of work orders have downtime)
- Reasons: Equipment Failure (25%), Material Shortage (20%), Setup (30%), Quality Hold (15%), Maintenance (10%)
- Duration: 15 minutes to 4 hours

### Hold Entries
- ~45 entries (30% of work orders experience holds)
- 70% RESUMED, 30% still ON_HOLD
- Hold duration: 1-10 days

### Employees
- 50 employees
- 10% in floating pool
- Codes: EMP-0001 through EMP-0050

### Attendance
- ~1,500 entries (30 days × 50 employees)
- 15% absenteeism rate (industry typical)
- Absence types: Unscheduled (40%), Vacation (30%), Medical (20%), Personal (10%)

### Quality Entries
- 200 inspection entries
- Quality distribution:
  - 85% good quality (0 defects)
  - 10% minor defects (2-10% defective)
  - 5% major defects (10-30% defective)
- Opportunities per unit vary by style (8-25)

## KPIs Validated

After running this generator, all 8 pending KPIs should PASS:

✅ **KPI #1: WIP Aging** - Work orders with hold data
✅ **KPI #2: On-Time Delivery** - 70% on-time rate
✅ **KPI #4: Quality PPM** - Defects per million units
✅ **KPI #5: Quality DPMO** - Defects per million opportunities
✅ **KPI #6: Quality FPY** - First pass yield percentage
✅ **KPI #7: Quality RTY** - Rolled throughput yield
✅ **KPI #8: Availability** - Based on downtime entries
✅ **KPI #10: Absenteeism** - 15% target rate

## Data Quality

- All dates in ISO 8601 format (YYYY-MM-DD)
- All foreign keys properly referenced
- Multi-tenant isolation (client_id in all records)
- Realistic distributions matching industry standards
- Edge cases included (zero downtime, 100% defects, etc.)
