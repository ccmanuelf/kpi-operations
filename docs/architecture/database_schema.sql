-- ============================================================================
-- MANUFACTURING KPI PLATFORM - COMPLETE DATABASE SCHEMA
-- ============================================================================
-- Database: MariaDB 10.6+
-- Purpose: Multi-tenant manufacturing KPI tracking platform
-- Author: System Architect
-- Date: 2025-12-31
-- Version: 1.0 (Phase 1 MVP)
-- ============================================================================

-- ============================================================================
-- DATABASE CONFIGURATION
-- ============================================================================

-- Set timezone to UTC for all timestamps
SET time_zone = '+00:00';

-- Enable strict mode for data integrity
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- ============================================================================
-- CORE TABLES (ALL PHASES)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: CLIENT
-- Purpose: Multi-tenant isolation - each client is a separate business unit/production line
-- Key Features: Soft delete (is_active), timezone support, supervisor assignments
-- ----------------------------------------------------------------------------
CREATE TABLE CLIENT (
    -- Primary Key
    client_id VARCHAR(20) PRIMARY KEY COMMENT 'Unique client code (e.g., BOOT-PROD-A, SOCK-FACILITY-B)',

    -- Required Fields
    client_name VARCHAR(100) NOT NULL COMMENT 'Full client/business unit name',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Active status - soft delete flag',

    -- Contact Information
    client_contact VARCHAR(100) DEFAULT NULL COMMENT 'Primary contact person',
    client_email VARCHAR(100) DEFAULT NULL COMMENT 'Primary email contact',
    client_phone VARCHAR(20) DEFAULT NULL COMMENT 'Primary phone contact',

    -- Location & Assignment
    location VARCHAR(100) DEFAULT NULL COMMENT 'Physical location (Building A - Line 1)',
    timezone VARCHAR(10) DEFAULT 'America/Mexico_City' COMMENT 'IANA timezone for scheduling',

    -- Staff Assignments (for escalations and approvals)
    supervisor_id VARCHAR(20) DEFAULT NULL COMMENT 'FK to EMPLOYEE - primary supervisor',
    planner_id VARCHAR(20) DEFAULT NULL COMMENT 'FK to EMPLOYEE - primary planner/customer service',
    engineering_id VARCHAR(20) DEFAULT NULL COMMENT 'FK to EMPLOYEE - primary engineer',

    -- Client Type Classification
    client_type ENUM('Hourly Rate', 'Piece Rate', 'Hybrid', 'Service', 'Other')
        DEFAULT 'Hourly Rate' COMMENT 'Management tracking classification',

    -- Audit Trail
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp (UTC)',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp (UTC)',

    -- Constraints
    CONSTRAINT chk_client_id_format CHECK (LENGTH(client_id) >= 3 AND LENGTH(client_id) <= 20),
    CONSTRAINT chk_client_name_length CHECK (LENGTH(client_name) >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Multi-tenant client/business unit master table';

-- ----------------------------------------------------------------------------
-- TABLE: EMPLOYEE
-- Purpose: Staff directory for operators, supervisors, support staff
-- Key Features: Floating pool flag, department tracking, soft delete
-- ----------------------------------------------------------------------------
CREATE TABLE EMPLOYEE (
    -- Primary Key
    employee_id VARCHAR(20) PRIMARY KEY COMMENT 'Unique employee identifier (EMP-001, OP-12345)',

    -- Required Fields
    employee_name VARCHAR(100) NOT NULL COMMENT 'Full employee name',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Active status - soft delete flag',

    -- Classification
    department VARCHAR(50) DEFAULT NULL COMMENT 'Department/area (CUTTING, SEWING, QC, ASSEMBLY)',
    is_floating_pool BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Part of floating/shared resource pool',
    is_support_billed BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Support staff directly assigned to client (non-operational)',
    is_support_included BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Support pool (engineering, purchasing, compliance)',

    -- Assignment
    client_id_assigned VARCHAR(20) DEFAULT NULL COMMENT 'Primary client assignment (NULL if floating)',

    -- Financial (Optional)
    hourly_rate DECIMAL(10,2) DEFAULT NULL COMMENT 'Hourly wage for cost tracking',

    -- Audit Trail
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp (UTC)',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp (UTC)',

    -- Foreign Keys
    CONSTRAINT fk_employee_client FOREIGN KEY (client_id_assigned)
        REFERENCES CLIENT(client_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_employee_name_length CHECK (LENGTH(employee_name) >= 1),
    CONSTRAINT chk_floating_logic CHECK (
        (is_floating_pool = TRUE AND client_id_assigned IS NULL) OR
        (is_floating_pool = FALSE)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Employee master directory';

-- ----------------------------------------------------------------------------
-- TABLE: USER
-- Purpose: System authentication and authorization
-- Key Features: 4-tier RBAC, multi-client access support, audit trail
-- ----------------------------------------------------------------------------
CREATE TABLE USER (
    -- Primary Key
    user_id VARCHAR(20) PRIMARY KEY COMMENT 'Unique system user identifier (USR-001)',

    -- Required Fields
    username VARCHAR(50) UNIQUE NOT NULL COMMENT 'Login username (5-50 chars, no spaces)',
    full_name VARCHAR(100) NOT NULL COMMENT 'Full name for display',
    role ENUM('OPERATOR_DATAENTRY', 'LEADER_DATACONFIG', 'POWERUSER', 'ADMIN') NOT NULL
        COMMENT 'Permission level - determines system access',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Active status - soft delete flag',

    -- Contact
    email VARCHAR(100) DEFAULT NULL COMMENT 'Email for notifications and reports',

    -- Access Control
    client_id_assigned VARCHAR(20) DEFAULT NULL COMMENT 'Single client or comma-separated list for multi-client access',

    -- Security (password hash stored in separate auth table for security)
    last_login TIMESTAMP NULL DEFAULT NULL COMMENT 'Last successful login timestamp (UTC)',

    -- Audit Trail
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp (UTC)',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp (UTC)',

    -- Constraints
    CONSTRAINT chk_username_length CHECK (LENGTH(username) >= 5 AND LENGTH(username) <= 50),
    CONSTRAINT chk_username_no_spaces CHECK (username NOT LIKE '% %'),
    CONSTRAINT chk_full_name_length CHECK (LENGTH(full_name) >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='System user authentication and authorization';

-- ----------------------------------------------------------------------------
-- TABLE: WORK_ORDER
-- Purpose: Top-level job tracking for customer orders
-- Key Features: Status workflow, OTD date tracking, ideal cycle time for KPIs
-- ----------------------------------------------------------------------------
CREATE TABLE WORK_ORDER (
    -- Primary Key
    work_order_id VARCHAR(50) PRIMARY KEY COMMENT 'Unique WO identifier (YYYY-MM-DD-MODEL-PARTNUM or manual ID)',

    -- Required Fields
    client_id_fk VARCHAR(20) NOT NULL COMMENT 'Client ownership - data isolation',
    planned_quantity INT NOT NULL COMMENT 'Total quantity ordered',
    status ENUM('ACTIVE', 'ON_HOLD', 'COMPLETED', 'REJECTED', 'CANCELLED') NOT NULL DEFAULT 'ACTIVE'
        COMMENT 'Current work order status',

    -- Product Information
    style_model VARCHAR(100) DEFAULT NULL COMMENT 'Style/Model designation (ROPER-BOOT, CREW-SOCK)',

    -- Date Tracking
    planned_start_date DATE DEFAULT NULL COMMENT 'Planned start from production schedule',
    actual_start_date DATE DEFAULT NULL COMMENT 'Actual start (captured from first production entry)',
    planned_ship_date DATE DEFAULT NULL COMMENT 'Promised/contracted ship date (REQUIRED for OTD KPI)',
    required_date DATE DEFAULT NULL COMMENT 'Alternative to planned_ship_date (fallback for OTD)',
    receipt_date DATE DEFAULT NULL COMMENT 'Date customer PO was received',
    acknowledged_date DATE DEFAULT NULL COMMENT 'Date Production Planner acknowledged order',

    -- KPI Critical Fields
    ideal_cycle_time DECIMAL(10,4) DEFAULT NULL COMMENT 'Standard time per unit in hours (REQUIRED for Efficiency/Performance)',

    -- Classification
    priority_level ENUM('RUSH', 'STANDARD', 'LOW') DEFAULT 'STANDARD' COMMENT 'Priority designation',

    -- Reference
    po_number VARCHAR(50) DEFAULT NULL COMMENT 'Customer purchase order number',

    -- Notes
    notes TEXT DEFAULT NULL COMMENT 'General notes (special packaging, rush order, quality hold)',

    -- Audit Trail
    created_by VARCHAR(20) DEFAULT NULL COMMENT 'FK to USER - who created this WO',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp (UTC)',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp (UTC)',

    -- Foreign Keys
    CONSTRAINT fk_workorder_client FOREIGN KEY (client_id_fk)
        REFERENCES CLIENT(client_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_workorder_user FOREIGN KEY (created_by)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_workorder_quantity CHECK (planned_quantity > 0),
    CONSTRAINT chk_workorder_dates CHECK (
        actual_start_date IS NULL OR
        planned_start_date IS NULL OR
        actual_start_date >= planned_start_date - INTERVAL 30 DAY
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Work order master table for customer orders';

-- ----------------------------------------------------------------------------
-- TABLE: JOB
-- Purpose: Line items within work orders (one WO can have multiple jobs/SKUs)
-- Key Features: Completion tracking, scrap tracking, part number linkage
-- ----------------------------------------------------------------------------
CREATE TABLE JOB (
    -- Primary Key
    job_id VARCHAR(50) PRIMARY KEY COMMENT 'Unique job identifier (WO_ID + line number)',

    -- Required Fields
    work_order_id_fk VARCHAR(50) NOT NULL COMMENT 'Parent work order',
    part_number VARCHAR(50) NOT NULL COMMENT 'Part/SKU number',
    quantity_ordered INT NOT NULL COMMENT 'Quantity for this job/line item',

    -- Optional Fields
    job_number VARCHAR(50) DEFAULT NULL COMMENT 'Job number from customer/planner (if provided)',

    -- Progress Tracking
    quantity_completed INT DEFAULT 0 COMMENT 'Quantity successfully completed (no rework, no scrap)',
    quantity_scrapped INT DEFAULT 0 COMMENT 'Quantity determined unrecoverable',

    -- Classification
    priority_level ENUM('RUSH', 'STANDARD', 'LOW') DEFAULT 'STANDARD' COMMENT 'Priority designation',

    -- Notes
    notes TEXT DEFAULT NULL COMMENT 'Job-specific notes (special material, custom embroidery)',

    -- Foreign Keys
    CONSTRAINT fk_job_workorder FOREIGN KEY (work_order_id_fk)
        REFERENCES WORK_ORDER(work_order_id) ON DELETE CASCADE ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_job_quantity CHECK (quantity_ordered > 0),
    CONSTRAINT chk_job_progress CHECK (quantity_completed >= 0 AND quantity_scrapped >= 0),
    CONSTRAINT chk_job_total CHECK (quantity_completed + quantity_scrapped <= quantity_ordered)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Job line items within work orders';

-- ----------------------------------------------------------------------------
-- TABLE: FLOATING_POOL
-- Purpose: Track floating/shared resource assignments across clients
-- Key Features: Prevents double-assignment, assignment history, audit trail
-- ----------------------------------------------------------------------------
CREATE TABLE FLOATING_POOL (
    -- Primary Key
    floating_pool_id VARCHAR(50) PRIMARY KEY COMMENT 'Unique assignment record (employee_id + timestamp)',

    -- Required Fields
    employee_id_fk VARCHAR(20) NOT NULL COMMENT 'Employee (must have is_floating_pool = TRUE)',
    status ENUM('AVAILABLE', 'ASSIGNED_CLIENT_A', 'ASSIGNED_CLIENT_B', 'ASSIGNED_CLIENT_C',
                'ASSIGNED_CLIENT_D', 'ASSIGNED_CLIENT_E') NOT NULL
        COMMENT 'Current availability status',
    last_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        COMMENT 'Timestamp of last status change (detect stale assignments)',

    -- Assignment Details
    assigned_to_client VARCHAR(20) DEFAULT NULL COMMENT 'Client where employee is currently working (NULL if available)',
    assigned_by_user_id VARCHAR(20) DEFAULT NULL COMMENT 'Supervisor who made the assignment',

    -- Notes
    notes TEXT DEFAULT NULL COMMENT 'Assignment notes (covering vacation until 2025-12-15)',

    -- Foreign Keys
    CONSTRAINT fk_floatingpool_employee FOREIGN KEY (employee_id_fk)
        REFERENCES EMPLOYEE(employee_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_floatingpool_client FOREIGN KEY (assigned_to_client)
        REFERENCES CLIENT(client_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_floatingpool_user FOREIGN KEY (assigned_by_user_id)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_floating_assignment CHECK (
        (status = 'AVAILABLE' AND assigned_to_client IS NULL) OR
        (status != 'AVAILABLE' AND assigned_to_client IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Floating pool resource assignment tracking';

-- ----------------------------------------------------------------------------
-- TABLE: PART_OPPORTUNITIES
-- Purpose: Quality defect opportunity counts per part (for DPMO calculation)
-- Key Features: Engineering-maintained reference data
-- ----------------------------------------------------------------------------
CREATE TABLE PART_OPPORTUNITIES (
    -- Primary Key
    part_number VARCHAR(50) PRIMARY KEY COMMENT 'Part/SKU identifier (matches JOB.part_number)',

    -- Required Fields
    opportunities_per_unit INT NOT NULL COMMENT 'Number of defect opportunities per unit for DPMO',

    -- Optional Fields
    description VARCHAR(200) DEFAULT NULL COMMENT 'Description of part and opportunities',

    -- Audit Trail
    updated_by VARCHAR(20) DEFAULT NULL COMMENT 'FK to USER - who last updated (Quality/Engineering)',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        COMMENT 'Last update timestamp (UTC)',

    -- Foreign Keys
    CONSTRAINT fk_part_opportunities_user FOREIGN KEY (updated_by)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_opportunities CHECK (opportunities_per_unit > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Part defect opportunity counts for quality calculations';

-- ============================================================================
-- PHASE 1: PRODUCTION TRACKING (MVP)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: PRODUCTION_ENTRY
-- Purpose: Daily/shift production data entry - feeds Efficiency & Performance KPIs
-- Key Features: CSV upload support, verification workflow, inference-ready
-- ----------------------------------------------------------------------------
CREATE TABLE PRODUCTION_ENTRY (
    -- Primary Key
    production_entry_id VARCHAR(50) PRIMARY KEY COMMENT 'System-generated UUID or timestamp-based ID',

    -- Required Foreign Keys
    work_order_id_fk VARCHAR(50) NOT NULL COMMENT 'Work order being produced',
    job_id_fk VARCHAR(50) DEFAULT NULL COMMENT 'Specific job/line item (optional if aggregating entire WO)',
    client_id_fk VARCHAR(20) NOT NULL COMMENT 'Client ownership - data isolation',

    -- Required Time Dimension
    shift_date DATE NOT NULL COMMENT 'Date production occurred (YYYY-MM-DD)',
    shift_type ENUM('SHIFT_1ST', 'SHIFT_2ND', 'SAT_OT', 'SUN_OT', 'OTHER') NOT NULL
        COMMENT 'Shift classification (1st: 7am-5pm, 2nd: 9pm-6am, OT: 7am-3pm)',

    -- Optional Operation Tracking (future granularity)
    operation_id VARCHAR(50) DEFAULT NULL COMMENT 'Operation/stage (CUTTING, SEWING, ASSEMBLY, QC, PACKING)',

    -- Production Metrics (REQUIRED for KPIs)
    units_produced INT NOT NULL DEFAULT 0 COMMENT 'Total units produced this entry',
    units_defective INT NOT NULL DEFAULT 0 COMMENT 'Units with defects (for quality KPIs)',
    run_time_hours DECIMAL(10,2) NOT NULL COMMENT 'Actual production time (shift hours minus downtime)',
    employees_assigned INT NOT NULL COMMENT 'Number of employees assigned',

    -- Optional Metrics
    employees_present INT DEFAULT NULL COMMENT 'Employees actually present (for absenteeism tracking)',
    shift_hours_scheduled DECIMAL(10,2) DEFAULT NULL COMMENT 'Total shift hours (for validation)',
    downtime_total_minutes INT DEFAULT 0 COMMENT 'Total downtime summary (auto-calculated or manual)',

    -- Target References
    efficiency_target DECIMAL(5,2) DEFAULT NULL COMMENT 'Target efficiency % for this entry (e.g., 90.0)',
    performance_target DECIMAL(5,2) DEFAULT NULL COMMENT 'Target performance % for this entry (e.g., 90.0)',

    -- Data Collection Metadata
    data_collector_id VARCHAR(20) NOT NULL COMMENT 'FK to USER - who entered this data',
    entry_method ENUM('MANUAL_ENTRY', 'CSV_UPLOAD', 'QR_SCAN', 'API', 'SYSTEM_IMPORT')
        DEFAULT 'MANUAL_ENTRY' COMMENT 'How data was entered (track quality by method)',
    timestamp TIMESTAMP NULL DEFAULT NULL COMMENT 'Exact entry time (for hourly tracking, time-series analysis)',

    -- Verification Workflow
    verified_by VARCHAR(20) DEFAULT NULL COMMENT 'FK to USER - supervisor who verified (optional)',
    verified_at TIMESTAMP NULL DEFAULT NULL COMMENT 'Verification timestamp',

    -- Notes
    notes TEXT DEFAULT NULL COMMENT 'Free-form notes (material shortage, new operator, quality hold)',

    -- Audit Trail
    created_by VARCHAR(20) NOT NULL COMMENT 'FK to USER - system creator',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp (UTC)',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        COMMENT 'Last update timestamp (tracks edits after creation)',

    -- Foreign Keys
    CONSTRAINT fk_production_workorder FOREIGN KEY (work_order_id_fk)
        REFERENCES WORK_ORDER(work_order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_production_job FOREIGN KEY (job_id_fk)
        REFERENCES JOB(job_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_production_client FOREIGN KEY (client_id_fk)
        REFERENCES CLIENT(client_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_production_collector FOREIGN KEY (data_collector_id)
        REFERENCES USER(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_production_verifier FOREIGN KEY (verified_by)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_production_creator FOREIGN KEY (created_by)
        REFERENCES USER(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_production_units CHECK (units_produced >= 0 AND units_defective >= 0),
    CONSTRAINT chk_production_defects CHECK (units_defective <= units_produced),
    CONSTRAINT chk_production_runtime CHECK (run_time_hours >= 0 AND run_time_hours <= 24),
    CONSTRAINT chk_production_employees CHECK (employees_assigned > 0),
    CONSTRAINT chk_production_present CHECK (employees_present IS NULL OR employees_present <= employees_assigned),
    CONSTRAINT chk_production_downtime CHECK (downtime_total_minutes >= 0),
    CONSTRAINT chk_production_targets CHECK (
        (efficiency_target IS NULL OR (efficiency_target >= 0 AND efficiency_target <= 200)) AND
        (performance_target IS NULL OR (performance_target >= 0 AND performance_target <= 200))
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Phase 1 - Production entry data for Efficiency & Performance KPIs';

-- ============================================================================
-- PHASE 2: DOWNTIME & HOLD TRACKING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: DOWNTIME_ENTRY
-- Purpose: Track equipment/process downtime - feeds Availability KPI
-- ----------------------------------------------------------------------------
CREATE TABLE DOWNTIME_ENTRY (
    -- Primary Key
    downtime_entry_id VARCHAR(50) PRIMARY KEY,

    -- Required Foreign Keys
    work_order_id_fk VARCHAR(50) NOT NULL,
    client_id_fk VARCHAR(20) NOT NULL,

    -- Required Time Dimension
    shift_date DATE NOT NULL,
    shift_type ENUM('SHIFT_1ST', 'SHIFT_2ND', 'SAT_OT', 'SUN_OT', 'OTHER') NOT NULL,

    -- Downtime Details
    downtime_reason ENUM('EQUIPMENT_FAILURE', 'MATERIAL_SHORTAGE', 'CHANGEOVER_SETUP',
                         'LACK_OF_ORDERS', 'MAINTENANCE_SCHEDULED', 'QC_HOLD',
                         'MISSING_SPECIFICATION', 'OTHER') NOT NULL,
    downtime_reason_detail TEXT DEFAULT NULL,
    downtime_duration_minutes INT NOT NULL,
    downtime_start_time TIME DEFAULT NULL,

    -- Responsibility & Resolution
    responsible_person_id VARCHAR(20) DEFAULT NULL,
    is_resolved BOOLEAN DEFAULT TRUE,
    resolution_notes TEXT DEFAULT NULL,

    -- Audit Trail
    reported_by_user_id VARCHAR(20) NOT NULL,
    reported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT fk_downtime_workorder FOREIGN KEY (work_order_id_fk)
        REFERENCES WORK_ORDER(work_order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_downtime_client FOREIGN KEY (client_id_fk)
        REFERENCES CLIENT(client_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_downtime_reporter FOREIGN KEY (reported_by_user_id)
        REFERENCES USER(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_downtime_creator FOREIGN KEY (created_by)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_downtime_duration CHECK (downtime_duration_minutes > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Phase 2 - Downtime tracking for Availability KPI';

-- ----------------------------------------------------------------------------
-- TABLE: HOLD_ENTRY
-- Purpose: Track work order holds/pauses - feeds WIP Aging KPI
-- ----------------------------------------------------------------------------
CREATE TABLE HOLD_ENTRY (
    -- Primary Key
    hold_entry_id VARCHAR(50) PRIMARY KEY,

    -- Required Foreign Keys
    work_order_id_fk VARCHAR(50) NOT NULL,
    job_id_fk VARCHAR(50) DEFAULT NULL,
    client_id_fk VARCHAR(20) NOT NULL,

    -- Hold Status
    hold_status ENUM('ON_HOLD', 'RESUMED', 'CANCELLED') NOT NULL,

    -- Hold Details
    hold_date DATE DEFAULT NULL,
    hold_time TIME DEFAULT NULL,
    hold_reason ENUM('MATERIAL_INSPECTION', 'QUALITY_ISSUE', 'ENGINEERING_REVIEW',
                     'CUSTOMER_REQUEST', 'MISSING_SPECIFICATION', 'EQUIPMENT_UNAVAILABLE',
                     'CAPACITY_CONSTRAINT', 'OTHER') NOT NULL,
    hold_reason_detail TEXT NOT NULL,

    -- Approval Workflow
    hold_approved_by_user_id VARCHAR(20) NOT NULL,
    hold_approved_at TIMESTAMP NOT NULL,

    -- Resume Details
    resume_date DATE DEFAULT NULL,
    resume_time TIME DEFAULT NULL,
    resume_approved_by_user_id VARCHAR(20) DEFAULT NULL,
    resume_approved_at TIMESTAMP NULL DEFAULT NULL,

    -- Duration Calculation
    total_hold_duration_hours DECIMAL(10,2) DEFAULT NULL,

    -- Notes
    hold_notes TEXT DEFAULT NULL,

    -- Audit Trail
    created_by VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT fk_hold_workorder FOREIGN KEY (work_order_id_fk)
        REFERENCES WORK_ORDER(work_order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_hold_job FOREIGN KEY (job_id_fk)
        REFERENCES JOB(job_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_hold_client FOREIGN KEY (client_id_fk)
        REFERENCES CLIENT(client_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_hold_approver FOREIGN KEY (hold_approved_by_user_id)
        REFERENCES USER(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_hold_resumer FOREIGN KEY (resume_approved_by_user_id)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_hold_resume CHECK (
        (hold_status = 'ON_HOLD' AND resume_date IS NULL) OR
        (hold_status IN ('RESUMED', 'CANCELLED'))
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Phase 2 - Hold/Resume tracking for WIP Aging KPI';

-- ============================================================================
-- PHASE 3: ATTENDANCE TRACKING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: ATTENDANCE_ENTRY
-- Purpose: Track employee attendance and absenteeism - feeds Absenteeism KPI
-- ----------------------------------------------------------------------------
CREATE TABLE ATTENDANCE_ENTRY (
    -- Primary Key
    attendance_entry_id VARCHAR(50) PRIMARY KEY,

    -- Required Foreign Keys
    employee_id_fk VARCHAR(20) NOT NULL,
    client_id_fk VARCHAR(20) NOT NULL,

    -- Required Time Dimension
    shift_date DATE NOT NULL,
    shift_type ENUM('SHIFT_1ST', 'SHIFT_2ND', 'SAT_OT', 'SUN_OT', 'OTHER') NOT NULL,

    -- Attendance Details
    scheduled_hours DECIMAL(10,2) NOT NULL,
    actual_hours DECIMAL(10,2) DEFAULT NULL,
    is_absent BOOLEAN NOT NULL,

    -- Absence Details
    absence_type ENUM('UNSCHEDULED_ABSENCE', 'VACATION', 'MEDICAL_LEAVE',
                      'PERSONAL_DAY', 'SUSPENDED', 'OTHER') DEFAULT NULL,
    absence_hours DECIMAL(10,2) DEFAULT NULL,

    -- Coverage Tracking
    covered_by_floating_employee_id VARCHAR(20) DEFAULT NULL,
    coverage_confirmed BOOLEAN DEFAULT FALSE,

    -- Audit Trail
    recorded_by_user_id VARCHAR(20) NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_by_user_id VARCHAR(20) DEFAULT NULL,
    verified_at TIMESTAMP NULL DEFAULT NULL,
    notes TEXT DEFAULT NULL,
    created_by VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id_fk)
        REFERENCES EMPLOYEE(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_attendance_client FOREIGN KEY (client_id_fk)
        REFERENCES CLIENT(client_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_attendance_coverage FOREIGN KEY (covered_by_floating_employee_id)
        REFERENCES EMPLOYEE(employee_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_attendance_recorder FOREIGN KEY (recorded_by_user_id)
        REFERENCES USER(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_attendance_verifier FOREIGN KEY (verified_by_user_id)
        REFERENCES USER(user_id) ON DELETE SET NULL ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_attendance_hours CHECK (scheduled_hours > 0),
    CONSTRAINT chk_attendance_absence CHECK (
        (is_absent = FALSE AND absence_type IS NULL) OR
        (is_absent = TRUE AND absence_type IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Phase 3 - Attendance tracking for Absenteeism KPI';

-- ============================================================================
-- PHASE 4: QUALITY TRACKING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: QUALITY_ENTRY
-- Purpose: Track quality inspections and defects - feeds PPM, DPMO, FPY, RTY KPIs
-- ----------------------------------------------------------------------------
CREATE TABLE QUALITY_ENTRY (
    -- Primary Key
    quality_entry_id VARCHAR(50) PRIMARY KEY,

    -- Required Foreign Keys
    work_order_id_fk VARCHAR(50) NOT NULL,
    job_id_fk VARCHAR(50) DEFAULT NULL,
    client_id_fk VARCHAR(20) NOT NULL,

    -- Required Time Dimension
    shift_date DATE NOT NULL,
    shift_type ENUM('SHIFT_1ST', 'SHIFT_2ND', 'SAT_OT', 'SUN_OT', 'OTHER') NOT NULL,

    -- Inspection Details
    operation_checked VARCHAR(50) NOT NULL,
    units_inspected INT NOT NULL,
    units_passed INT NOT NULL,
    units_defective INT NOT NULL,
    units_requiring_rework INT DEFAULT NULL,
    units_requiring_repair INT DEFAULT NULL,
    total_defects_count INT NOT NULL,

    -- Inspection Metadata
    inspection_method ENUM('VISUAL', 'MEASUREMENT', 'FUNCTIONAL_TEST',
                           'SAMPLE_CHECK', '100_PERCENT_INSPECTION', 'OTHER') DEFAULT NULL,
    sample_size_percent DECIMAL(5,2) DEFAULT NULL,

    -- Audit Trail
    qc_inspector_id VARCHAR(20) NOT NULL,
    recorded_by_user_id VARCHAR(20) NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT DEFAULT NULL,
    created_by VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT fk_quality_workorder FOREIGN KEY (work_order_id_fk)
        REFERENCES WORK_ORDER(work_order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_quality_job FOREIGN KEY (job_id_fk)
        REFERENCES JOB(job_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_quality_client FOREIGN KEY (client_id_fk)
        REFERENCES CLIENT(client_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_quality_inspector FOREIGN KEY (qc_inspector_id)
        REFERENCES EMPLOYEE(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_quality_recorder FOREIGN KEY (recorded_by_user_id)
        REFERENCES USER(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,

    -- Constraints
    CONSTRAINT chk_quality_inspected CHECK (units_inspected > 0),
    CONSTRAINT chk_quality_totals CHECK (units_passed + units_defective <= units_inspected),
    CONSTRAINT chk_quality_defects CHECK (total_defects_count >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Phase 4 - Quality inspection tracking for quality KPIs';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Core Table Indexes
CREATE INDEX idx_client_active ON CLIENT(is_active);
CREATE INDEX idx_employee_active ON EMPLOYEE(is_active);
CREATE INDEX idx_employee_floating ON EMPLOYEE(is_floating_pool, is_active);
CREATE INDEX idx_employee_client ON EMPLOYEE(client_id_assigned);
CREATE INDEX idx_user_active ON USER(is_active);
CREATE INDEX idx_user_role ON USER(role);

-- Work Order Indexes (critical for WIP queries)
CREATE INDEX idx_workorder_client_status ON WORK_ORDER(client_id_fk, status);
CREATE INDEX idx_workorder_status ON WORK_ORDER(status);
CREATE INDEX idx_workorder_dates ON WORK_ORDER(actual_start_date, planned_ship_date);
CREATE INDEX idx_job_workorder ON JOB(work_order_id_fk);
CREATE INDEX idx_job_part ON JOB(part_number);

-- Production Entry Indexes (critical for 3-month reporting)
CREATE INDEX idx_production_client_date ON PRODUCTION_ENTRY(client_id_fk, shift_date);
CREATE INDEX idx_production_workorder ON PRODUCTION_ENTRY(work_order_id_fk);
CREATE INDEX idx_production_shift ON PRODUCTION_ENTRY(shift_date, shift_type);
CREATE INDEX idx_production_collector ON PRODUCTION_ENTRY(data_collector_id);

-- Downtime & Hold Indexes
CREATE INDEX idx_downtime_client_date ON DOWNTIME_ENTRY(client_id_fk, shift_date);
CREATE INDEX idx_downtime_workorder ON DOWNTIME_ENTRY(work_order_id_fk);
CREATE INDEX idx_hold_client_status ON HOLD_ENTRY(client_id_fk, hold_status);
CREATE INDEX idx_hold_workorder ON HOLD_ENTRY(work_order_id_fk);

-- Attendance Indexes
CREATE INDEX idx_attendance_client_date ON ATTENDANCE_ENTRY(client_id_fk, shift_date);
CREATE INDEX idx_attendance_employee ON ATTENDANCE_ENTRY(employee_id_fk, shift_date);

-- Quality Indexes
CREATE INDEX idx_quality_client_date ON QUALITY_ENTRY(client_id_fk, shift_date);
CREATE INDEX idx_quality_workorder ON QUALITY_ENTRY(work_order_id_fk);

-- Floating Pool Index
CREATE INDEX idx_floatingpool_employee ON FLOATING_POOL(employee_id_fk);
CREATE INDEX idx_floatingpool_client ON FLOATING_POOL(assigned_to_client);
CREATE INDEX idx_floatingpool_status ON FLOATING_POOL(status);

-- ============================================================================
-- SAMPLE SEED DATA (for development & testing)
-- ============================================================================

-- Seed Client
INSERT INTO CLIENT (client_id, client_name, location, timezone, is_active) VALUES
('BOOT-LINE-A', 'Western Boot Production Line A', 'Building A - Line 1', 'America/Mexico_City', TRUE),
('SOCK-FAC-B', 'Sock Manufacturing Unit 2', 'Building B - Facility 2', 'America/Chicago', TRUE);

-- Seed Users
INSERT INTO USER (user_id, username, full_name, email, role, client_id_assigned, is_active) VALUES
('USR-001', 'admin', 'System Administrator', 'admin@manufacturing.com', 'ADMIN', NULL, TRUE),
('USR-002', 'operator1', 'John Doe', 'john.doe@manufacturing.com', 'OPERATOR_DATAENTRY', 'BOOT-LINE-A', TRUE),
('USR-003', 'leader1', 'Jane Smith', 'jane.smith@manufacturing.com', 'LEADER_DATACONFIG', 'BOOT-LINE-A', TRUE);

-- Seed Employees
INSERT INTO EMPLOYEE (employee_id, employee_name, department, is_floating_pool, client_id_assigned, is_active) VALUES
('EMP-001', 'Maria Garcia', 'SEWING', FALSE, 'BOOT-LINE-A', TRUE),
('EMP-002', 'Carlos Rodriguez', 'CUTTING', FALSE, 'BOOT-LINE-A', TRUE),
('EMP-015', 'Float Worker 1', 'GENERAL', TRUE, NULL, TRUE);

-- Seed Work Order
INSERT INTO WORK_ORDER (work_order_id, client_id_fk, style_model, planned_quantity, planned_start_date,
                        planned_ship_date, ideal_cycle_time, status, created_by) VALUES
('2025-12-15-BOOT-ABC123', 'BOOT-LINE-A', 'ROPER-BOOT', 1000, '2025-12-15', '2025-12-20', 0.25, 'ACTIVE', 'USR-001');

-- Seed Job
INSERT INTO JOB (job_id, work_order_id_fk, part_number, quantity_ordered) VALUES
('2025-12-15-BOOT-ABC123-L1', '2025-12-15-BOOT-ABC123', 'BOOT-ABC123', 1000);

-- Seed Part Opportunities
INSERT INTO PART_OPPORTUNITIES (part_number, opportunities_per_unit, description, updated_by) VALUES
('BOOT-ABC123', 47, 'Western Boot - toe box seam, heel seam, sole adhesion, stitching integrity, fit, color, material defects, etc.', 'USR-001');

-- Seed Production Entry (test inference)
INSERT INTO PRODUCTION_ENTRY (production_entry_id, work_order_id_fk, job_id_fk, client_id_fk,
                               shift_date, shift_type, units_produced, units_defective,
                               run_time_hours, employees_assigned, data_collector_id,
                               entry_method, created_by) VALUES
('PROD-TEST-001', '2025-12-15-BOOT-ABC123', '2025-12-15-BOOT-ABC123-L1', 'BOOT-LINE-A',
 '2025-12-15', 'SHIFT_1ST', 100, 2, 8.5, 10, 'USR-002', 'MANUAL_ENTRY', 'USR-002');

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
