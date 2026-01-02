# KPI Implementation Architecture & Decision Matrix

**Architect:** System Architecture Designer Agent
**Session ID:** swarm-1767238686161-ap0rkjkpz
**Date:** 2025-12-31
**Status:** ARCHITECTURAL REVIEW COMPLETE

---

## Executive Summary

### Current State Assessment

**Implementation Status:**
- ✅ **2 of 10 KPIs IMPLEMENTED** (20%)
  - KPI #3: Production Efficiency (COMPLETE with inference)
  - KPI #9: Performance (COMPLETE with inference)
- ❌ **8 of 10 KPIs MISSING** (80%)
  - 3 KPIs can be implemented with existing data (QUICK WINS)
  - 5 KPIs require new database tables (PHASE 2-4)

**Critical Finding:**
Despite having comprehensive Phase 2-4 data inventory specifications, the database schema only implements Phase 1 tables. This creates an 80% gap in KPI coverage.

**Good News:**
All 8 missing KPIs have pre-defined data structures in CSV inventories. Implementation is a matter of execution, not design.

---

## Architectural Decision Matrix

### KPI #1: WIP Aging (MISSING - Phase 2 Required)

**Current Status:** ❌ NOT IMPLEMENTED

**Data Requirements Analysis:**
```
Required Fields:
✅ job_planned_start_date     (Inventory: 03-Phase2, WORK_ORDER table)
✅ hold_duration               (Inventory: 03-Phase2, HOLD_ENTRY table)
✅ job_status                  (Inventory: 03-Phase2, WORK_ORDER table)

Current Implementation:
❌ No WORK_ORDER table
❌ No HOLD_ENTRY table
❌ No calculation module
```

**Implementation Options:**

#### Option A: Full Normalized Implementation (RECOMMENDED)
**Architecture:**
```sql
-- New tables required
CREATE TABLE work_order (
    work_order_id VARCHAR(50) PRIMARY KEY,
    job_planned_start_date DATE,
    job_actual_start_date DATE,
    job_status ENUM('IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED'),
    ...
);

CREATE TABLE hold_entry (
    hold_entry_id VARCHAR(50) PRIMARY KEY,
    work_order_id_fk VARCHAR(50),
    hold_date DATE,
    resume_date DATE,
    total_hold_duration_hours DECIMAL(10,2),
    ...
);
```

**Calculation Logic:**
```python
# /backend/calculations/wip_aging.py
def calculate_wip_aging(work_order_id: str) -> dict:
    """
    Calculate WIP aging excluding hold time.

    Formula: now() - start_date - sum(hold_duration)
    """
    # Get work order start date
    # Sum all hold durations for this WO
    # Calculate net aging
```

**Benefits:**
- ✅ Accurate real-time WIP tracking
- ✅ Hold/resume audit trail
- ✅ Supports complex scenarios (multiple holds per job)
- ✅ Aligns with Phase 2 specification

**Costs:**
- ⏱️ 12-16 hours development
  - 4 hours: Database schema + migrations
  - 4 hours: ORM models + repositories
  - 3 hours: Calculation logic + inference
  - 3 hours: API endpoints + testing
- 📦 2 new tables, 6 API endpoints
- 🧪 Requires comprehensive testing

#### Option B: Quick Win - Simplified Tracking (MVP Demo)
**Architecture:**
```sql
-- Minimal addition to existing production_entry table
ALTER TABLE production_entry
ADD COLUMN job_start_date DATE,
ADD COLUMN is_on_hold BOOLEAN DEFAULT FALSE,
ADD COLUMN hold_duration_hours DECIMAL(10,2) DEFAULT 0;
```

**Calculation Logic:**
```python
def calculate_simple_wip_aging(entry_id: int) -> float:
    """Simplified: Assume linear aging without granular hold tracking."""
    entry = get_production_entry(entry_id)
    if entry.is_on_hold:
        return 0  # Aging paused

    days_aging = (datetime.now().date() - entry.job_start_date).days
    return days_aging - (entry.hold_duration_hours / 24)
```

**Benefits:**
- ✅ Functional KPI in 2-3 hours
- ✅ Zero schema complexity
- ✅ Immediate dashboard visibility

**Costs:**
- ❌ No hold/resume audit trail
- ❌ Manual hold duration entry (prone to errors)
- ❌ Limited to single active hold per entry
- ⚠️ **Technical debt:** Must refactor for production use

#### Option C: Calculated View (Read-Only)
**NOT RECOMMENDED:** Cannot implement without underlying data.

**Decision:** Option A for production, Option B for Phase 1 MVP demo only.

**Timeline Estimate:**
- **MVP (Option B):** 3 hours
- **Production (Option A):** 16 hours (2 days)

---

### KPI #2: On-Time Delivery (MISSING - Phase 2 Required)

**Current Status:** ❌ NOT IMPLEMENTED

**Data Requirements Analysis:**
```
Required Fields:
✅ job_planned_ship_date       (Inventory: 03-Phase2, WORK_ORDER table)
✅ job_required_date            (Inventory: 03-Phase2, WORK_ORDER table)
✅ job_ideal_cycle_time         (Inventory: EXISTS in product table!)
✅ actual_delivery_date         (Inventory: 03-Phase2, WORK_ORDER table)

Current Implementation:
❌ No WORK_ORDER table with delivery tracking
❌ No calculation module
✅ ideal_cycle_time EXISTS in product table (reusable!)
```

**Implementation Options:**

#### Option A: Full Delivery Tracking (RECOMMENDED)
**Architecture:**
```sql
-- Extend WORK_ORDER table (from Phase 2 inventory)
ALTER TABLE work_order
ADD COLUMN job_planned_ship_date DATE,
ADD COLUMN job_required_date DATE,
ADD COLUMN actual_delivery_date DATE,
ADD COLUMN is_on_time BOOLEAN GENERATED ALWAYS AS (
    actual_delivery_date <= COALESCE(job_planned_ship_date, job_required_date)
);

CREATE INDEX idx_on_time_delivery
ON work_order(actual_delivery_date, job_planned_ship_date);
```

**Calculation Logic with Inference:**
```python
# /backend/calculations/otd.py
from calculations.inference import infer_delivery_date

def calculate_otd(start_date: date, end_date: date) -> dict:
    """
    Calculate On-Time Delivery percentage with inference.

    Formula: (count on time / total orders) × 100
    On time = actual_delivery <= promised_date (or inferred)
    """
    orders = get_orders_in_range(start_date, end_date)

    on_time_count = 0
    total_count = len(orders)

    for order in orders:
        # Use promised date if available, else infer
        promised_date = order.job_planned_ship_date or order.job_required_date

        if not promised_date:
            # INFERENCE: Calculate using cycle time
            promised_date = infer_delivery_date(
                order.job_start_date,
                order.units_required,
                order.product.ideal_cycle_time,
                shift_hours=9
            )

        if order.actual_delivery_date <= promised_date:
            on_time_count += 1

    return {
        "otd_percentage": (on_time_count / total_count) * 100 if total_count > 0 else 0,
        "on_time_count": on_time_count,
        "total_orders": total_count,
        "inferred_count": sum(1 for o in orders if not o.job_planned_ship_date)
    }

def infer_delivery_date(start_date, units, cycle_time, shift_hours=9):
    """
    Infer delivery date when promised date missing.

    Formula: start_date + ceil((units × ideal_time) / shift_hours)
    """
    if not cycle_time:
        cycle_time = 0.25  # Default 15 min/unit

    total_hours = units * cycle_time
    days_required = math.ceil(total_hours / shift_hours)

    return start_date + timedelta(days=days_required)
```

**Benefits:**
- ✅ Customer satisfaction metric
- ✅ Inference engine for missing promised dates
- ✅ Reuses existing ideal_cycle_time data
- ✅ Supports surrogate calculations

**Costs:**
- ⏱️ 10-14 hours development
  - 3 hours: WORK_ORDER table extensions
  - 4 hours: Calculation + inference logic
  - 3 hours: API endpoints
  - 2 hours: Dashboard integration
- 📦 Extends existing table, 3 API endpoints

#### Option B: Production Entry Extension (MVP)
**Architecture:**
```sql
-- Add delivery tracking to existing production_entry
ALTER TABLE production_entry
ADD COLUMN promised_delivery_date DATE,
ADD COLUMN actual_delivery_date DATE,
ADD COLUMN is_on_time BOOLEAN GENERATED ALWAYS AS (
    actual_delivery_date <= promised_delivery_date
);
```

**Benefits:**
- ✅ 3-4 hours implementation
- ✅ Uses existing table structure
- ✅ Can implement inference immediately

**Costs:**
- ❌ Less granular (per production entry, not per order)
- ❌ Doesn't track order lifecycle
- ⚠️ **Conceptual mismatch:** Delivery is order-level, not entry-level

**Decision:** Option A (wait for WORK_ORDER table), or skip for Phase 1.

**Timeline Estimate:**
- **MVP (Option B):** 4 hours (if acceptable)
- **Production (Option A):** 14 hours (requires Phase 2 WORK_ORDER table)

---

### KPI #4: Quality PPM (QUICK WIN! 🎯)

**Current Status:** ❌ NOT IMPLEMENTED (despite data existing!)

**Data Requirements Analysis:**
```
Required Fields:
✅ defect_count                (EXISTS in production_entry table!)
✅ units_produced              (EXISTS in production_entry table!)

Current Implementation:
✅ Data fields EXIST
❌ No calculation module
❌ Not displayed on dashboard
```

**THIS IS A QUICK WIN - Data exists, just needs calculation!**

#### Option A: Immediate Implementation (RECOMMENDED)
**Architecture:**
```python
# /backend/calculations/ppm.py (NEW FILE)
from decimal import Decimal

def calculate_ppm(defect_count: int, units_produced: int) -> Decimal:
    """
    Calculate Parts Per Million defects.

    Formula: (defect_count / units_produced) × 1,000,000

    Args:
        defect_count: Number of defective units found
        units_produced: Total units produced

    Returns:
        PPM value as Decimal (0 if units_produced = 0)
    """
    if units_produced == 0:
        return Decimal('0.00')

    ppm = (Decimal(defect_count) / Decimal(units_produced)) * Decimal('1000000')
    return ppm.quantize(Decimal('0.01'))
```

**Database Integration:**
```sql
-- Add calculated column to production_entry
ALTER TABLE production_entry
ADD COLUMN ppm_defects DECIMAL(10,2)
GENERATED ALWAYS AS (
    CASE
        WHEN units_produced > 0
        THEN (defect_count / units_produced) * 1000000
        ELSE 0
    END
);

-- Or use stored procedure (matches existing pattern)
DELIMITER $$
CREATE PROCEDURE sp_calculate_ppm(IN p_entry_id INT UNSIGNED)
BEGIN
    DECLARE v_defect_count INT;
    DECLARE v_units_produced INT;
    DECLARE v_ppm DECIMAL(10,2);

    SELECT defect_count, units_produced
    INTO v_defect_count, v_units_produced
    FROM production_entry
    WHERE entry_id = p_entry_id;

    IF v_units_produced > 0 THEN
        SET v_ppm = (v_defect_count / v_units_produced) * 1000000;
    ELSE
        SET v_ppm = 0;
    END IF;

    UPDATE production_entry
    SET ppm_defects = v_ppm
    WHERE entry_id = p_entry_id;
END$$
DELIMITER ;
```

**API Integration:**
```python
# /backend/api/endpoints/production.py
from calculations.ppm import calculate_ppm

@router.get("/production/entry/{entry_id}")
async def get_production_entry(entry_id: int):
    entry = get_entry_from_db(entry_id)

    # Calculate PPM on-the-fly
    ppm = calculate_ppm(entry.defect_count, entry.units_produced)

    return {
        **entry,
        "ppm_defects": ppm,
        "quality_metrics": {
            "defect_count": entry.defect_count,
            "units_produced": entry.units_produced,
            "ppm": ppm,
            "defect_rate_percentage": (entry.defect_count / entry.units_produced * 100)
                                      if entry.units_produced > 0 else 0
        }
    }
```

**Benefits:**
- ✅ **1-2 hours total implementation**
- ✅ Zero schema changes required (data exists!)
- ✅ Simple calculation (no inference needed)
- ✅ Immediate dashboard display
- ✅ Follows existing calculation pattern

**Costs:**
- None! This is pure value-add.

**Decision:** **IMPLEMENT IMMEDIATELY** - This is the lowest-hanging fruit.

**Timeline Estimate:**
- **Implementation:** 1-2 hours
  - 30 min: Create `/backend/calculations/ppm.py`
  - 30 min: Add to production entry response model
  - 30 min: Add stored procedure (optional)
  - 30 min: Update dashboard display

---

### KPI #5: Quality DPMO (QUICK WIN with caveat)

**Current Status:** ❌ NOT IMPLEMENTED

**Data Requirements Analysis:**
```
Required Fields:
✅ defect_count                (EXISTS in production_entry!)
✅ units_produced              (EXISTS in production_entry!)
❓ opportunities_per_unit      (Inventory: 05-Phase4, PART_OPPORTUNITIES table)

Current Implementation:
✅ Partial data exists (defects, units)
❌ No PART_OPPORTUNITIES table
❌ No calculation module
```

**Implementation Options:**

#### Option A: Full Implementation with PART_OPPORTUNITIES (Phase 4)
**Architecture:**
```sql
-- From Phase 4 inventory
CREATE TABLE part_opportunities (
    part_number VARCHAR(50) PRIMARY KEY,
    opportunities_per_unit INT NOT NULL,
    description VARCHAR(500),
    updated_by_user_id VARCHAR(20),
    updated_at TIMESTAMP,
    notes TEXT
);

-- Relate to product table
ALTER TABLE product
ADD COLUMN part_number VARCHAR(50),
ADD FOREIGN KEY (part_number) REFERENCES part_opportunities(part_number);
```

**Calculation Logic:**
```python
# /backend/calculations/dpmo.py
def calculate_dpmo(
    defect_count: int,
    units_produced: int,
    opportunities_per_unit: int = 1
) -> Decimal:
    """
    Calculate Defects Per Million Opportunities.

    Formula: (defects / (units × opportunities)) × 1,000,000

    Args:
        defect_count: Total defects found
        units_produced: Total units produced
        opportunities_per_unit: Ways a unit can fail (default: 1)

    Returns:
        DPMO value as Decimal
    """
    if units_produced == 0 or opportunities_per_unit == 0:
        return Decimal('0.00')

    total_opportunities = units_produced * opportunities_per_unit
    dpmo = (Decimal(defect_count) / Decimal(total_opportunities)) * Decimal('1000000')

    return dpmo.quantize(Decimal('0.01'))
```

**Benefits:**
- ✅ Industry-standard quality metric
- ✅ More accurate than PPM for complex products
- ✅ Supports per-product opportunity counts

**Costs:**
- ⏱️ 8-10 hours with PART_OPPORTUNITIES table
- 📦 1 new table, updates to product table

#### Option B: Quick Win with Default Opportunities (RECOMMENDED for Phase 1)
**Architecture:**
```python
# /backend/calculations/dpmo.py
def calculate_simple_dpmo(defect_count: int, units_produced: int) -> Decimal:
    """
    Simplified DPMO with opportunities_per_unit = 1.

    Note: This is equivalent to PPM when opportunities = 1.
    For true DPMO, use calculate_dpmo() with PART_OPPORTUNITIES table.
    """
    return calculate_dpmo(defect_count, units_produced, opportunities_per_unit=1)
```

**Inference Logic:**
```python
def infer_opportunities_per_unit(product_id: int) -> int:
    """
    Infer opportunities per unit if not defined.

    Returns:
        1 (default) if no PART_OPPORTUNITIES entry exists
    """
    opportunities = db.query(PartOpportunities).filter(
        PartOpportunities.part_number == get_product_part_number(product_id)
    ).first()

    return opportunities.opportunities_per_unit if opportunities else 1
```

**Benefits:**
- ✅ 2-3 hours implementation
- ✅ Works immediately with existing data
- ✅ Can upgrade to full DPMO when Phase 4 implemented
- ✅ Inference fallback to opportunities = 1

**Costs:**
- ⚠️ Less accurate than true DPMO (assumes 1 opportunity per unit)
- 📝 Requires documentation explaining limitation

**Decision:** Option B for Phase 1 (functional now), Option A for Phase 4 (accurate).

**Timeline Estimate:**
- **MVP (Option B):** 2-3 hours
- **Production (Option A):** 10 hours (requires PART_OPPORTUNITIES table)

---

### KPI #6: Quality FPY (First Pass Yield) - Phase 4 Required

**Current Status:** ❌ NOT IMPLEMENTED

**Data Requirements Analysis:**
```
Required Fields:
❌ units_inspected             (Inventory: 05-Phase4, QUALITY_ENTRY table)
❌ units_passed                 (Inventory: 05-Phase4, QUALITY_ENTRY table)
❌ units_requiring_rework       (Inventory: 05-Phase4, QUALITY_ENTRY table)
❌ units_requiring_repair       (Inventory: 05-Phase4, QUALITY_ENTRY table)

Current Implementation:
❌ No QUALITY_ENTRY table
❌ No rework/repair tracking
❌ Cannot infer from current data (defect_count ≠ first-pass failures)
```

**Critical Insight:**
Current `defect_count` field doesn't distinguish between:
- Units that **failed first pass** but passed after rework/repair
- Units that **never passed** (scrap)

FPY requires tracking inspection results, not just final defect counts.

**Implementation Options:**

#### Option A: Full Quality Inspection Tracking (RECOMMENDED - Phase 4)
**Architecture:**
```sql
-- From Phase 4 inventory
CREATE TABLE quality_entry (
    quality_entry_id VARCHAR(50) PRIMARY KEY,
    work_order_id_fk VARCHAR(50),
    operation_checked VARCHAR(50),
    units_inspected INT NOT NULL,
    units_passed INT NOT NULL,
    units_defective INT NOT NULL,
    units_requiring_rework INT,
    units_requiring_repair INT,
    ...
);
```

**Calculation Logic:**
```python
# /backend/calculations/fpy_rty.py
def calculate_fpy(quality_entry_id: str) -> Decimal:
    """
    Calculate First Pass Yield.

    Formula: (units_passed first time / units_inspected) × 100

    Excludes units that passed after rework/repair.
    """
    entry = get_quality_entry(quality_entry_id)

    if entry.units_inspected == 0:
        return Decimal('0.00')

    # First pass = passed without rework or repair
    units_first_pass = entry.units_passed

    fpy = (Decimal(units_first_pass) / Decimal(entry.units_inspected)) * 100
    return fpy.quantize(Decimal('0.01'))
```

**Benefits:**
- ✅ Accurate quality process metric
- ✅ Tracks inspection at each operation
- ✅ Supports root cause analysis

**Costs:**
- ⏱️ 14-18 hours development
  - 5 hours: QUALITY_ENTRY + DEFECT_DETAIL tables
  - 5 hours: Quality data entry UI
  - 4 hours: FPY calculation + API
  - 3 hours: Dashboard integration
- 📦 2 new tables, quality inspection workflow

#### Option B: Simplified Assumption-Based FPY (NOT RECOMMENDED)
**Architecture:**
```python
def calculate_estimated_fpy(defect_count: int, units_produced: int) -> Decimal:
    """
    ESTIMATE FPY using defect count (INACCURATE).

    Assumes: all defects caught at first pass (unrealistic).
    WARNING: Not true FPY - for estimation only.
    """
    units_passed_first = units_produced - defect_count
    return (units_passed_first / units_produced) * 100 if units_produced > 0 else 0
```

**Benefits:**
- ✅ 1 hour implementation

**Costs:**
- ❌ **Fundamentally inaccurate** (violates FPY definition)
- ❌ Cannot distinguish rework from scrap
- ❌ Misleading metric for process improvement
- ⚠️ **Not recommended** - creates false quality picture

#### Option C: Skip Until Phase 4 (RECOMMENDED)
**Decision:** Do not implement until QUALITY_ENTRY table exists. Placeholder only.

**Timeline Estimate:**
- **Production (Option A):** 18 hours (requires Phase 4 QUALITY_ENTRY table)
- **Not recommended before Phase 4**

---

### KPI #7: Quality RTY (Rolled Throughput Yield) - Phase 4 Required

**Current Status:** ❌ NOT IMPLEMENTED

**Data Requirements Analysis:**
```
Required Fields:
❌ Multi-operation tracking       (Inventory: 05-Phase4, QUALITY_ENTRY per operation)
❌ units_started                   (First operation input)
❌ units_completed_defect_free     (Final operation output)
❌ Defects tracked by operation    (QUALITY_ENTRY.operation_checked)

Current Implementation:
❌ No operation-level tracking
❌ No QUALITY_ENTRY table
❌ Cannot calculate without multi-step process data
```

**Critical Insight:**
RTY = Product of all operation yields (FPY₁ × FPY₂ × ... × FPYₙ)

Requires:
1. Multiple quality checkpoints across operations
2. Units tracked through entire process
3. Per-operation pass/fail data

**Implementation Options:**

#### Option A: Full Multi-Operation Tracking (RECOMMENDED - Phase 4)
**Architecture:**
```sql
-- Extend QUALITY_ENTRY with operation sequencing
ALTER TABLE quality_entry
ADD COLUMN operation_sequence INT,
ADD COLUMN is_final_operation BOOLEAN DEFAULT FALSE;

-- Create process flow tracking
CREATE TABLE operation_flow (
    flow_id VARCHAR(50) PRIMARY KEY,
    work_order_id_fk VARCHAR(50),
    operation_sequence INT,
    operation_name VARCHAR(50),
    units_input INT,
    units_output_passed INT,
    operation_fpy DECIMAL(5,2)
);
```

**Calculation Logic:**
```python
# /backend/calculations/fpy_rty.py
def calculate_rty(work_order_id: str) -> Decimal:
    """
    Calculate Rolled Throughput Yield across all operations.

    Formula: (completed defect-free / total started) × 100
    Or: FPY₁ × FPY₂ × ... × FPYₙ
    """
    operations = get_operations_for_wo(work_order_id)

    if not operations:
        return Decimal('0.00')

    # Method 1: Direct calculation
    first_op = operations[0]
    final_op = operations[-1]

    rty = (Decimal(final_op.units_output_passed) /
           Decimal(first_op.units_input)) * 100

    # Method 2: Product of FPYs (should match Method 1)
    rty_multiplicative = Decimal('1.00')
    for op in operations:
        op_fpy = calculate_operation_fpy(op.quality_entry_id)
        rty_multiplicative *= (op_fpy / 100)

    return rty.quantize(Decimal('0.01'))
```

**Benefits:**
- ✅ Comprehensive process quality metric
- ✅ Identifies bottleneck operations
- ✅ Supports continuous improvement

**Costs:**
- ⏱️ 16-20 hours development
  - 6 hours: Multi-operation schema design
  - 5 hours: Operation flow tracking UI
  - 5 hours: RTY calculation + validation
  - 4 hours: Dashboard visualization
- 📦 1-2 new tables, complex UI workflow

#### Option B: Single-Operation Assumption (NOT RTY)
**Not applicable.** RTY by definition requires multi-operation tracking.

**Decision:** Skip until Phase 4. RTY requires QUALITY_ENTRY + operation tracking.

**Timeline Estimate:**
- **Production (Option A):** 20 hours (requires Phase 4 multi-operation tracking)
- **Cannot implement before Phase 4**

---

### KPI #8: Availability (OEE Component) - Phase 2 Required

**Current Status:** ❌ NOT IMPLEMENTED (OEE assumes 100% availability!)

**Data Requirements Analysis:**
```
Required Fields:
❌ downtime_duration_minutes     (Inventory: 03-Phase2, DOWNTIME_ENTRY table)
❌ downtime_reason               (Inventory: 03-Phase2, DOWNTIME_ENTRY table)
❌ shift_hours_scheduled          (Exists in production_entry! ✅)

Current Implementation:
❌ No DOWNTIME_ENTRY table
✅ run_time_hours exists (but doesn't explain downtime)
⚠️ OEE calculation hardcoded to 100% availability
```

**Critical Issue:**
Current `/backend/calculations/performance.py:calculate_oee()` assumes:
```python
availability = 1.0  # 100% - Phase 2 will track downtime
```

This inflates OEE values and misleads decision-makers!

**Implementation Options:**

#### Option A: Full Downtime Tracking (RECOMMENDED - Phase 2)
**Architecture:**
```sql
-- From Phase 2 inventory
CREATE TABLE downtime_entry (
    downtime_entry_id VARCHAR(50) PRIMARY KEY,
    work_order_id_fk VARCHAR(50),
    shift_date DATE NOT NULL,
    shift_type ENUM(...),
    downtime_reason ENUM('EQUIPMENT_FAILURE', 'MATERIAL_SHORTAGE', ...),
    downtime_duration_minutes INT NOT NULL,
    downtime_start_time TIME,
    is_resolved BOOLEAN DEFAULT TRUE,
    ...
);

CREATE INDEX idx_downtime_date
ON downtime_entry(shift_date, shift_type);
```

**Calculation Logic:**
```python
# /backend/calculations/availability.py
def calculate_availability(
    shift_date: date,
    shift_type: str,
    planned_production_hours: Decimal
) -> Decimal:
    """
    Calculate Availability for OEE.

    Formula: 1 - (downtime_hours / planned_production_hours)
    Or: (planned_time - downtime) / planned_time

    Args:
        shift_date: Date of production
        shift_type: SHIFT_1ST, SHIFT_2ND, etc.
        planned_production_hours: Total shift hours scheduled

    Returns:
        Availability as Decimal 0.00-1.00
    """
    # Get all downtime entries for this shift
    downtime_entries = db.query(DowntimeEntry).filter(
        DowntimeEntry.shift_date == shift_date,
        DowntimeEntry.shift_type == shift_type
    ).all()

    total_downtime_minutes = sum(e.downtime_duration_minutes for e in downtime_entries)
    downtime_hours = Decimal(total_downtime_minutes) / 60

    if planned_production_hours == 0:
        return Decimal('0.00')

    availability = 1 - (downtime_hours / planned_production_hours)

    # Clamp to 0-1 range
    availability = max(Decimal('0.00'), min(Decimal('1.00'), availability))

    return availability.quantize(Decimal('0.0001'))

def calculate_oee_with_availability(entry_id: int) -> dict:
    """
    Calculate OEE with REAL availability (not 100%).

    OEE = Availability × Performance × Quality
    """
    entry = get_production_entry(entry_id)

    # Calculate availability from downtime
    availability = calculate_availability(
        entry.production_date,
        entry.shift.shift_name,
        Decimal(entry.shift.duration_hours)
    )

    # Performance (existing calculation)
    performance = calculate_performance(entry_id) / 100

    # Quality (1 - defect rate)
    quality = (Decimal('1.00') -
               (Decimal(entry.defect_count) / Decimal(entry.units_produced))
              ) if entry.units_produced > 0 else Decimal('0.00')

    oee = availability * performance * quality

    return {
        "oee_percentage": (oee * 100).quantize(Decimal('0.01')),
        "availability": (availability * 100).quantize(Decimal('0.01')),
        "performance": (performance * 100).quantize(Decimal('0.01')),
        "quality": (quality * 100).quantize(Decimal('0.01'))
    }
```

**Benefits:**
- ✅ **Accurate OEE calculation** (no longer inflated)
- ✅ Downtime root cause analysis
- ✅ Identifies improvement opportunities
- ✅ Tracks EQUIPMENT_FAILURE, MATERIAL_SHORTAGE, etc.

**Costs:**
- ⏱️ 10-14 hours development
  - 4 hours: DOWNTIME_ENTRY table + schema
  - 3 hours: Downtime data entry UI
  - 3 hours: Availability calculation
  - 2 hours: Update OEE calculation
  - 2 hours: Dashboard integration
- 📦 1 new table, downtime logging workflow

#### Option B: Quick Win - Calculate from Existing Data (MVP)
**Architecture:**
```python
def calculate_inferred_availability(entry_id: int) -> Decimal:
    """
    Infer availability from run_time vs shift_hours.

    Assumption: downtime = shift_hours - run_time
    WARNING: Doesn't explain WHY downtime occurred.
    """
    entry = get_production_entry(entry_id)

    shift_hours = get_shift_duration(entry.shift_id)
    run_time = entry.run_time_hours

    if shift_hours == 0:
        return Decimal('0.00')

    availability = run_time / shift_hours
    return availability.quantize(Decimal('0.0001'))
```

**Benefits:**
- ✅ 1-2 hours implementation
- ✅ Uses existing run_time_hours field
- ✅ Immediate fix to OEE inflation

**Costs:**
- ❌ No downtime reason tracking
- ❌ Cannot analyze root causes
- ❌ Less actionable than Option A

**Decision:** Option B for Phase 1 (functional now), Option A for Phase 2 (root cause analysis).

**Timeline Estimate:**
- **MVP (Option B):** 2 hours (infer from run_time)
- **Production (Option A):** 14 hours (requires DOWNTIME_ENTRY table)

---

### KPI #10: Absenteeism - Phase 3 Required

**Current Status:** ❌ NOT IMPLEMENTED

**Data Requirements Analysis:**
```
Required Fields:
❌ employee_id                   (Exists in user table, but not linked to attendance)
❌ scheduled_hours               (Inventory: 04-Phase3, ATTENDANCE_ENTRY table)
❌ absence_hours                 (Inventory: 04-Phase3, ATTENDANCE_ENTRY table)
❌ absence_type                  (Inventory: 04-Phase3, ATTENDANCE_ENTRY table)
❌ covered_by_floating_employee  (Inventory: 04-Phase3, COVERAGE_ENTRY table)

Current Implementation:
❌ No ATTENDANCE_ENTRY table
❌ No COVERAGE_ENTRY table
✅ employees_assigned exists in production_entry (count, not attendance)
```

**Critical Insight:**
`employees_assigned` counts staff, but doesn't track individual attendance. Absenteeism requires per-employee tracking.

**Implementation Options:**

#### Option A: Full Attendance Tracking (RECOMMENDED - Phase 3)
**Architecture:**
```sql
-- From Phase 3 inventory
CREATE TABLE attendance_entry (
    attendance_entry_id VARCHAR(50) PRIMARY KEY,
    employee_id_fk VARCHAR(20) NOT NULL,
    shift_date DATE NOT NULL,
    shift_type ENUM(...),
    scheduled_hours DECIMAL(10,2) NOT NULL,
    actual_hours DECIMAL(10,2),
    is_absent BOOLEAN NOT NULL,
    absence_type ENUM('UNSCHEDULED_ABSENCE', 'VACATION', 'MEDICAL_LEAVE', ...),
    absence_hours DECIMAL(10,2),
    covered_by_floating_employee_id VARCHAR(20),
    ...
);

CREATE TABLE coverage_entry (
    coverage_entry_id VARCHAR(50) PRIMARY KEY,
    absent_employee_id VARCHAR(20) NOT NULL,
    floating_employee_id VARCHAR(20) NOT NULL,
    shift_date DATE NOT NULL,
    coverage_duration_hours DECIMAL(10,2),
    ...
);
```

**Calculation Logic:**
```python
# /backend/calculations/absenteeism.py
def calculate_absenteeism(
    start_date: date,
    end_date: date,
    department: str = None
) -> dict:
    """
    Calculate Absenteeism percentage for period.

    Formula: (total_absence_hours / total_scheduled_hours) × 100

    Args:
        start_date: Start of reporting period
        end_date: End of reporting period
        department: Optional filter by department/line

    Returns:
        Absenteeism metrics including breakdown by absence type
    """
    query = db.query(AttendanceEntry).filter(
        AttendanceEntry.shift_date.between(start_date, end_date)
    )

    if department:
        query = query.join(Employee).filter(Employee.department == department)

    attendance_records = query.all()

    total_scheduled_hours = sum(r.scheduled_hours for r in attendance_records)
    total_absence_hours = sum(r.absence_hours or 0 for r in attendance_records)

    absenteeism_pct = (total_absence_hours / total_scheduled_hours) * 100 \
                      if total_scheduled_hours > 0 else 0

    # Breakdown by absence type
    absence_by_type = {}
    for record in attendance_records:
        if record.is_absent:
            type_name = record.absence_type or 'UNKNOWN'
            absence_by_type[type_name] = absence_by_type.get(type_name, 0) + record.absence_hours

    return {
        "absenteeism_percentage": round(absenteeism_pct, 2),
        "total_scheduled_hours": total_scheduled_hours,
        "total_absence_hours": total_absence_hours,
        "absence_by_type": absence_by_type,
        "floating_pool_coverage_hours": calculate_floating_coverage(start_date, end_date)
    }

def calculate_floating_coverage(start_date: date, end_date: date) -> Decimal:
    """Calculate total hours provided by floating pool."""
    coverage_entries = db.query(CoverageEntry).filter(
        CoverageEntry.shift_date.between(start_date, end_date)
    ).all()

    return sum(c.coverage_duration_hours for c in coverage_entries)
```

**Benefits:**
- ✅ Workforce availability metric
- ✅ Tracks absence types (vacation vs unscheduled)
- ✅ Floating pool coverage analysis
- ✅ Supports workforce planning

**Costs:**
- ⏱️ 16-20 hours development
  - 5 hours: ATTENDANCE_ENTRY + COVERAGE_ENTRY tables
  - 6 hours: Attendance data entry UI
  - 4 hours: Absenteeism calculation + API
  - 3 hours: Dashboard integration
- 📦 2 new tables, attendance workflow

#### Option B: Simplified Estimation (NOT RECOMMENDED)
**Architecture:**
```python
def estimate_absenteeism_from_employees_present(entry_id: int) -> Decimal:
    """
    ESTIMATE absenteeism using employees_present vs employees_assigned.

    WARNING: This is per-shift estimation, not true absenteeism tracking.
    """
    entry = get_production_entry(entry_id)

    if not entry.employees_present:
        return Decimal('0.00')  # Cannot calculate

    absent_count = entry.employees_assigned - entry.employees_present
    absent_pct = (absent_count / entry.employees_assigned) * 100

    return Decimal(absent_pct).quantize(Decimal('0.01'))
```

**Benefits:**
- ✅ 1 hour implementation

**Costs:**
- ❌ Only count-based (not hours-based)
- ❌ No absence type tracking
- ❌ No individual employee tracking
- ❌ Cannot track floating pool coverage
- ⚠️ **Inaccurate metric**

**Decision:** Skip until Phase 3. Do not estimate - creates false data.

**Timeline Estimate:**
- **Production (Option A):** 20 hours (requires Phase 3 ATTENDANCE_ENTRY table)
- **Not recommended before Phase 3**

---

## Implementation Roadmap

### Phase 1: Immediate Quick Wins (3-6 hours)

**Objective:** Maximize KPI coverage with existing data

| KPI | Action | Effort | Impact |
|-----|--------|--------|--------|
| #4 (PPM) | ✅ Implement calculation using existing defect_count | 1-2 hours | HIGH |
| #5 (DPMO) | ✅ Implement with opportunities=1 default | 2-3 hours | MEDIUM |
| #8 (Availability) | ✅ Infer from run_time_hours vs shift_hours | 1-2 hours | HIGH (fixes OEE inflation) |

**Deliverables:**
- 3 new KPIs functional (20% → 50% coverage)
- OEE calculation corrected
- Zero schema changes required

**Timeline:** 1 day (6 hours)

---

### Phase 2: Downtime & WIP Tracking (30-40 hours)

**Objective:** Implement Phase 2 data inventory (DOWNTIME_ENTRY, WORK_ORDER, HOLD_ENTRY)

| KPI | Action | Effort | Dependencies |
|-----|--------|--------|--------------|
| #8 (Availability) | Full downtime tracking with root cause | 14 hours | DOWNTIME_ENTRY table |
| #1 (WIP Aging) | Job tracking with hold/resume logging | 16 hours | WORK_ORDER, HOLD_ENTRY tables |
| #2 (OTD) | Delivery tracking with inference | 14 hours | WORK_ORDER table extensions |

**Database Schema:**
```sql
-- Implement tables from 03-Phase2_Downtime_WIP_Inventory.csv
CREATE TABLE work_order (...);
CREATE TABLE downtime_entry (...);
CREATE TABLE hold_entry (...);
```

**Deliverables:**
- 3 new KPIs functional (50% → 80% coverage)
- Accurate OEE with real availability
- Downtime root cause analysis
- WIP aging with hold exclusions

**Timeline:** 5-6 days (40 hours)

---

### Phase 3: Attendance & Scheduling (20-24 hours)

**Objective:** Implement Phase 3 data inventory (ATTENDANCE_ENTRY, COVERAGE_ENTRY)

| KPI | Action | Effort | Dependencies |
|-----|--------|--------|--------------|
| #10 (Absenteeism) | Per-employee attendance tracking | 20 hours | ATTENDANCE_ENTRY, COVERAGE_ENTRY tables |

**Database Schema:**
```sql
-- Implement tables from 04-Phase3_Attendance_Inventory.csv
CREATE TABLE attendance_entry (...);
CREATE TABLE coverage_entry (...);
```

**Deliverables:**
- 1 new KPI functional (80% → 90% coverage)
- Workforce availability metrics
- Floating pool coverage tracking

**Timeline:** 3-4 days (24 hours)

---

### Phase 4: Quality Inspection & Multi-Operation Tracking (40-50 hours)

**Objective:** Implement Phase 4 data inventory (QUALITY_ENTRY, DEFECT_DETAIL, PART_OPPORTUNITIES)

| KPI | Action | Effort | Dependencies |
|-----|--------|--------|--------------|
| #5 (DPMO) | Upgrade to true DPMO with opportunities | 10 hours | PART_OPPORTUNITIES table |
| #6 (FPY) | First-pass yield tracking | 18 hours | QUALITY_ENTRY table |
| #7 (RTY) | Multi-operation yield tracking | 20 hours | QUALITY_ENTRY + operation flow |

**Database Schema:**
```sql
-- Implement tables from 05-Phase4_Quality_Inventory.csv
CREATE TABLE quality_entry (...);
CREATE TABLE defect_detail (...);
CREATE TABLE part_opportunities (...);
```

**Deliverables:**
- 2 new KPIs functional (90% → 100% coverage)
- Comprehensive quality metrics
- Per-operation defect tracking
- Root cause analysis capability

**Timeline:** 6-7 days (50 hours)

---

## Total Implementation Estimates

### By Priority

| Priority | KPIs | Effort | Timeline | Coverage Gain |
|----------|------|--------|----------|---------------|
| **Quick Wins** | #4, #5 (simple), #8 (inferred) | 6 hours | 1 day | +30% (20% → 50%) |
| **Phase 2** | #1, #2, #8 (full) | 40 hours | 5-6 days | +30% (50% → 80%) |
| **Phase 3** | #10 | 24 hours | 3-4 days | +10% (80% → 90%) |
| **Phase 4** | #5 (full), #6, #7 | 50 hours | 6-7 days | +10% (90% → 100%) |

### Total Time to 100% KPI Coverage

**Optimistic (parallel development):** 10-12 weeks
**Realistic (sequential development):** 14-16 weeks
**Conservative (with testing & documentation):** 18-20 weeks

---

## Risk Assessment

### Technical Debt Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **OEE inflated to 100% availability** | 🔴 CRITICAL | Implement Phase 1 Quick Win for availability inference |
| **PPM/DPMO not calculated despite data existing** | 🟡 MODERATE | Implement Phase 1 Quick Win immediately |
| **No Phase 2-4 tables implemented** | 🟡 MODERATE | Follow phased roadmap, prioritize Phase 2 |
| **Inference engines missing for OTD** | 🟢 LOW | Documented in specifications, straightforward to implement |

### Scalability Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Multi-operation tracking complex** | 🟡 MODERATE | Use Phase 4 QUALITY_ENTRY design from inventory |
| **Downtime logging UI overhead** | 🟢 LOW | Provide supervisor-friendly mobile UI |
| **Floating pool coverage validation** | 🟡 MODERATE | Implement double-booking prevention logic |

### Data Quality Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Manual downtime entry errors** | 🟡 MODERATE | Implement validation rules, supervisor verification |
| **Missing opportunities_per_unit data** | 🟢 LOW | Default to 1, allow gradual population |
| **Attendance tracking adoption** | 🟡 MODERATE | Phased rollout, supervisor training |

---

## Architectural Decision Records (ADRs)

### ADR-001: Use Existing Calculation Pattern

**Decision:** Follow existing `/backend/calculations/` modular pattern for all new KPIs.

**Rationale:**
- ✅ Consistency with KPI #3 (Efficiency) and #9 (Performance)
- ✅ Separation of concerns (calculation logic isolated)
- ✅ Testable functions with clear inputs/outputs
- ✅ Inference engines reusable across KPIs

**Consequences:**
- All new KPIs will have dedicated `/backend/calculations/{kpi}.py` modules
- Database stored procedures will mirror Python logic (for triggers)
- API endpoints will call calculation functions, not embed logic

---

### ADR-002: Implement Quick Wins Before Phase 2-4 Tables

**Decision:** Prioritize PPM, DPMO (simple), and Availability (inferred) implementations immediately.

**Rationale:**
- ✅ Data already exists (defect_count, units_produced, run_time_hours)
- ✅ Provides immediate value to users (30% coverage gain)
- ✅ Fixes critical OEE inflation issue
- ✅ Demonstrates platform capability while awaiting Phase 2-4

**Consequences:**
- Some KPIs will have "MVP" and "Full" implementations
- Documentation must clearly state Phase 1 vs Phase 4 accuracy
- Technical debt tracking for DPMO upgrade (opportunities_per_unit)

---

### ADR-003: Do Not Implement FPY/RTY Until Phase 4

**Decision:** Do not implement estimated FPY/RTY using current defect_count field.

**Rationale:**
- ❌ FPY fundamentally requires first-pass vs rework distinction
- ❌ RTY requires multi-operation tracking (not single production_entry)
- ❌ Estimated metrics would be misleading and violate industry definitions
- ✅ Better to wait for proper QUALITY_ENTRY implementation

**Consequences:**
- FPY and RTY will remain "NOT IMPLEMENTED" until Phase 4
- Dashboard will show "Phase 4 Required" placeholder
- Users will understand limitation upfront (no false expectations)

---

### ADR-004: Reuse Inference Engine Pattern from Efficiency/Performance

**Decision:** Apply same inference pattern to OTD (delivery date) and DPMO (opportunities).

**Rationale:**
- ✅ Existing `infer_ideal_cycle_time()` is well-designed
- ✅ Transparency through `(value, was_inferred)` tuple return
- ✅ Fallback hierarchy: defined value → historical average → default
- ✅ Users trust inference when transparently documented

**Consequences:**
- All new KPIs with missing data will have inference functions
- API responses will include `was_inferred` flag for transparency
- Dashboard will visually distinguish inferred vs actual values

---

### ADR-005: Use Phase 2-4 CSV Inventory Specifications As-Is

**Decision:** Implement database schema exactly as defined in CSV inventories.

**Rationale:**
- ✅ Specifications are comprehensive and well-designed
- ✅ Field names, data types, enums already standardized
- ✅ Reduces design time (no reinventing)
- ✅ Aligns with original platform vision

**Consequences:**
- Direct translation of CSV specs to SQL DDL
- Enum values match exactly (SHIFT_1ST, EQUIPMENT_FAILURE, etc.)
- Foreign key relationships pre-defined
- Minimal schema design effort required

---

## Recommended Implementation Path

### Immediate Actions (This Week)

1. **Implement Quick Win KPIs (6 hours total)**
   ```bash
   # Create calculation modules
   touch backend/calculations/ppm.py
   touch backend/calculations/dpmo.py

   # Update availability.py (inferred version)
   # Update performance.py (fix OEE to use real availability)

   # Add to API responses
   # Update dashboard to display PPM, DPMO, corrected OEE
   ```

2. **Document Current Limitations**
   ```markdown
   # Update README.md
   ## Current KPI Coverage: 5 of 10 (50%)

   ✅ Implemented:
   - KPI #3: Production Efficiency
   - KPI #4: Quality PPM (NEW!)
   - KPI #5: Quality DPMO (simplified, opportunities=1)
   - KPI #8: Availability (inferred from run_time)
   - KPI #9: Performance

   ⏳ Phase 2 Required (Downtime & WIP):
   - KPI #1: WIP Aging
   - KPI #2: On-Time Delivery
   - KPI #8: Availability (full downtime tracking)

   ⏳ Phase 3 Required (Attendance):
   - KPI #10: Absenteeism

   ⏳ Phase 4 Required (Quality Inspection):
   - KPI #5: Quality DPMO (full with opportunities_per_unit)
   - KPI #6: Quality FPY
   - KPI #7: Quality RTY
   ```

3. **Fix OEE Misleading Value**
   ```python
   # /backend/calculations/performance.py
   def calculate_oee(entry_id: int) -> dict:
       """Calculate OEE with REAL availability."""
       from calculations.availability import calculate_inferred_availability

       # BEFORE (WRONG):
       # availability = 1.0  # Assumes 100%

       # AFTER (CORRECT):
       availability = calculate_inferred_availability(entry_id)

       performance = calculate_performance(entry_id) / 100
       quality = calculate_quality_rate(entry_id)

       return {
           "oee": availability * performance * quality * 100,
           "availability": availability * 100,
           "performance": performance * 100,
           "quality": quality * 100
       }
   ```

### Next Sprint (Phase 2 Preparation)

1. **Database Schema Design Review**
   - Review `03-Phase2_Downtime_WIP_Inventory.csv`
   - Create SQL migration scripts for WORK_ORDER, DOWNTIME_ENTRY, HOLD_ENTRY
   - Design ORM models matching CSV specifications

2. **UI/UX Design for Downtime Logging**
   - Simple supervisor form for logging downtime events
   - Dropdown for standardized downtime reasons
   - Mobile-friendly (supervisors on floor)

3. **Hold/Resume Workflow Design**
   - WIP status transitions (IN_PROGRESS → ON_HOLD → RESUMED)
   - Approval workflow for holds
   - Aging clock pause/resume logic

### Month 2-3 (Phase 2 Implementation)

- Implement DOWNTIME_ENTRY table and logging UI
- Implement WORK_ORDER and HOLD_ENTRY tables
- Build KPI #1 (WIP Aging) calculation module
- Build KPI #2 (OTD) calculation module with inference
- Upgrade KPI #8 (Availability) to use real downtime data
- Testing and validation

### Month 4-5 (Phase 3 Implementation)

- Implement ATTENDANCE_ENTRY and COVERAGE_ENTRY tables
- Build attendance logging UI
- Build KPI #10 (Absenteeism) calculation module
- Floating pool coverage validation logic
- Testing and validation

### Month 6-7 (Phase 4 Implementation)

- Implement QUALITY_ENTRY, DEFECT_DETAIL, PART_OPPORTUNITIES tables
- Build quality inspection UI workflow
- Build KPI #6 (FPY) calculation module
- Build KPI #7 (RTY) calculation module
- Upgrade KPI #5 (DPMO) with real opportunities_per_unit
- Multi-operation tracking and visualization
- Final testing and production deployment

---

## Success Metrics

### Phase 1 Success Criteria
- ✅ 50% KPI coverage (5 of 10)
- ✅ OEE no longer inflated (uses real availability)
- ✅ PPM and DPMO visible on dashboard
- ✅ Zero schema changes (uses existing data)

### Phase 2 Success Criteria
- ✅ 80% KPI coverage (8 of 10)
- ✅ Downtime root cause analysis operational
- ✅ WIP aging with hold exclusions accurate
- ✅ OTD with delivery date inference working
- ✅ Supervisor adoption of downtime logging

### Phase 3 Success Criteria
- ✅ 90% KPI coverage (9 of 10)
- ✅ Per-employee attendance tracking
- ✅ Floating pool coverage validation
- ✅ Absenteeism trends visible

### Phase 4 Success Criteria
- ✅ 100% KPI coverage (10 of 10)
- ✅ Per-operation quality tracking
- ✅ FPY and RTY accurate
- ✅ Root cause analysis for defects
- ✅ Complete manufacturing KPI platform

---

## Conclusion

**Current State:**
The platform has a solid foundation with 2 correctly implemented KPIs, but 80% of promised functionality is missing due to incomplete database schema.

**Root Cause:**
Phase 2-4 data inventory specifications exist but were never implemented. This is a **development execution gap**, not a design gap.

**Recommended Path:**
1. **Immediate (1 day):** Implement 3 quick-win KPIs using existing data
2. **Phase 2 (5-6 days):** Implement downtime/WIP tracking
3. **Phase 3 (3-4 days):** Implement attendance tracking
4. **Phase 4 (6-7 days):** Implement quality inspection tracking

**Total Time to 100% Coverage:** 14-16 weeks with dedicated resources

**Key Insight:**
All required data structures are already specified in CSV inventories. Implementation is straightforward execution following existing patterns. No architectural unknowns remain.

---

**Next Steps:**
1. Review this architectural analysis with stakeholders
2. Approve Phase 1 Quick Wins for immediate implementation
3. Prioritize Phase 2-4 based on business value
4. Allocate development resources for sequential implementation

**Report Generated:** 2025-12-31 by System Architecture Designer Agent
**Session ID:** swarm-1767238686161-ap0rkjkpz

---

## Appendix: Alternative Architectures Considered

### A1: Denormalized KPI Storage

**Concept:** Store all calculated KPIs in a single `kpi_snapshot` table.

**Pros:**
- Fast dashboard queries (no joins)
- Historical KPI trends easy to track

**Cons:**
- Redundant storage (duplicates production_entry data)
- Complex recalculation logic when data changes
- Breaks normalization principles

**Decision:** Rejected. Use calculated columns in production_entry + on-demand API calculations.

---

### A2: Real-Time Event Streaming for Downtime

**Concept:** Use message queue (RabbitMQ/Kafka) for real-time downtime events.

**Pros:**
- Real-time dashboard updates
- Scalable for high-frequency events

**Cons:**
- Overkill for current scale (manual supervisor entry)
- Added infrastructure complexity
- Not needed for daily/shift reporting

**Decision:** Rejected for Phase 2. Revisit for Phase 5 (real-time monitoring).

---

### A3: JSON Columns for Flexible Defect Tracking

**Concept:** Store defect details in JSON column instead of DEFECT_DETAIL table.

**Pros:**
- Schema flexibility (no migrations for new defect types)
- Fast initial implementation

**Cons:**
- Cannot index or query efficiently
- Loses referential integrity
- Difficult to aggregate (count defects by type)

**Decision:** Rejected. Use normalized DEFECT_DETAIL table as specified in Phase 4 inventory.

---

## Coordination Metadata

**Hooks Executed:**
```bash
npx claude-flow@alpha hooks pre-task --description "Provide architectural recommendations for KPI implementation"
npx claude-flow@alpha hooks session-restore --session-id "swarm-1767238686161-ap0rkjkpz"
```

**Memory Keys:**
- `swarm/architect/kpi-recommendations`
- `swarm/architect/decision-matrix`
- `swarm/architect/implementation-roadmap`

**Files Referenced:**
- `/docs/validation_report.md`
- `/database/schema.sql`
- `/backend/calculations/*.py`
- `02-Phase1_Production_Inventory.csv`
- `03-Phase2_Downtime_WIP_Inventory.csv`
- `04-Phase3_Attendance_Inventory.csv`
- `05-Phase4_Quality_Inventory.csv`

**Agent Coordination:**
- Analyst Agent: Provided validation report with current state
- Architect Agent: This document (implementation strategy)
- Next: Coder Agent (implement Phase 1 Quick Wins)
