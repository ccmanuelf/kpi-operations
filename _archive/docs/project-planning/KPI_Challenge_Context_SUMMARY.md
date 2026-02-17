# KPI Challenge Context - Executive Summary

**Source**: Comprehensive conversation distilled from 124KB original file  
**Purpose**: Provide hive-mind agents with essential context for building Manufacturing KPI Platform

---

## 🎯 **Core Business Problem**

**Current State (Pain Points)**:
- 100% manual KPI calculations (guesstimates, not actual calculations)
- Data scattered across non-standardized Excel files and paper logs
- No centralized tracking, validation, or audit trails
- Multiple data collectors per client creating inconsistencies
- KPIs only reported on whiteboards/dry-erase boards
- Missing critical data (dates, priorities often absent from work orders)

**Target State (Solution)**:
- Automated KPI calculations with validated data inputs
- Centralized platform with standardized data collection
- Web-based tablet interface (minimize manual entry, future QR scanning)
- Real-time data validation and audit trails
- Modular architecture to avoid data duplication

---

## 📊 **Scale Requirements**

| Metric | Current | Peak | 2026 Target |
|--------|---------|------|-------------|
| **Clients/Business Units** | 15 | 35 | 50+ |
| **Employees** | 800 | 2,500 | 3,000+ |
| **Data Collectors** | 1-5 per client | Varies | Multiple per client |

---

## ⏰ **Shift System**

- **1st Shift**: 7am-5pm Mon-Fri (10 hrs/day = 50 hrs/week)
- **2nd Shift**: 9pm-6am Mon-Fri (9 hrs/day = 45 hrs/week)
- **Sat OT**: 7am-3pm (8 hrs)
- **Sun OT**: 7am-3pm (8 hrs)
- **Special OT**: Any hours outside standard shifts

---

## 🏭 **Production Flow**

**Typical Stages** (with slight variations per client):
Cutting → Sewing → Assembly → QC → Packing

---

## 📋 **10 KPI Modules to Build**

1. **WIP Aging** - Days in WIP (filter: style-model, part number, work order)
2. **On-Time Delivery** - Orders delivered by promised date
3. **Production Efficiency** - (Hours Produced / Hours Available) × 100
4. **Quality PPM** - Parts Per Million defects
5. **Quality DPMO** - Defects Per Million Opportunities
6. **Quality FPY & RTY** - First Pass Yield & Rolled Throughput Yield
7. **Availability** - Uptime vs Downtime percentage
8. **Performance** - Actual cycle time vs ideal cycle time
9. **Production Hours** - By Operation or Stage (daily/weekly/monthly)
10. **Absenteeism Rate** - (Total absence hours / Total scheduled hours) × 100

---

## 🔑 **Critical Design Principles**

### **1. Multi-Tenant Architecture**
- Data must be isolated per client/business unit
- UI must support filtering/switching between clients
- Database indexing for 50+ clients, 3000+ employees

### **2. Zero Data Duplication**
- Single source of truth for shared data
- Production Hours feeds: Efficiency, Availability, Performance, Hours by Operation
- Downtime data feeds: Availability, Performance
- Quality data feeds: PPM, DPMO, FPY, RTY
- Attendance data feeds: Absenteeism

### **3. Data Validation & Integrity**
- Mandatory fields enforcement (work order numbers, dates, quantities)
- Real-time validation rules
- Audit trails (who changed what, when)
- Reject invalid data or flag for manual review

### **4. Flexible Data Capture**
- **Manual Entry**: Web-based tablet interface
- **File Upload**: Support CSV/Excel for bulk imports
- **Future**: QR code scanning to minimize typing

### **5. Data Granularity**
- **Ideal**: Individual transaction per piece with timestamp
- **Minimum Viable**: Per work order, date/shift level
- **Reporting**: Daily/shift captured, displayed weekly/monthly

---

## 🏗️ **Shared Data Foundation**

### **Core Entities** (from CSV inventories):
- **WORK_ORDER** - Job tracking, dates, quantities, style-model, part number
- **JOB** - Individual line items within work orders
- **CLIENT** - Business unit configuration (50+ clients)
- **EMPLOYEE** - Staff directory (3000+ employees)
- **USER** - System accounts & authentication

### **Transaction Entities**:
- **PRODUCTION_ENTRY** - Units produced, defects, run time, operation/stage
- **DOWNTIME_ENTRY** - Equipment failure, material shortage, setup time
- **HOLD_ENTRY** - WIP on hold tracking & resume
- **ATTENDANCE_ENTRY** - Scheduled vs actual hours, absence types
- **QUALITY_ENTRY** - Defects, repair/rework tracking
- **PART_OPPORTUNITIES** - Opportunities per unit for DPMO calculation

---

## 📐 **Metric Definitions**

### **WIP Aging (#1)**
- **Calculation**: Today's Date - Date Entered WIP
- **Filters**: Style-model, Part number, Work order
- **Granularity**: By work order

### **On-Time Delivery (#2)**
- **Definition**: Orders delivered to warehouse by planned date
- **Criteria**: Must be 100% complete (no partial shipments)
- **Calculation**: (Orders delivered on/before due date / Total orders) × 100

### **Production Efficiency (#3)**
- **Formula**: (Standard Hours Produced / Hours Available) × 100
- **Standard Hours Produced**: Pieces × Standard Time per piece
- **Hours Available**: Scheduled production time (excludes breaks, lunch)
- **Note**: Downtime reduces available hours

### **Quality PPM (#4)**
- **Formula**: (Total defects / Total units inspected) × 1,000,000
- **Scope**: Defects found at final inspection

### **Quality DPMO (#5)**
- **Formula**: (Total defects / Total opportunities) × 1,000,000
- **Opportunities**: Defined per unit (e.g., seams, stitches, fits)
- **Source**: PART_OPPORTUNITIES table

### **Quality FPY & RTY (#6)**
- **FPY (First Pass Yield)**: (Units passed first time / Total units) × 100
- **RTY (Rolled Throughput Yield)**: FPY₁ × FPY₂ × ... × FPYₙ
- **Scope**: Across all production stages

### **Availability (#7)**
- **Formula**: (Uptime / (Uptime + Downtime)) × 100
- **Downtime includes**: Equipment failure, material shortage, setup time
- **Excludes**: Scheduled breaks, lunch (not counted as downtime)

### **Performance (#8)**
- **Formula**: (Ideal Cycle Time / Actual Cycle Time) × 100
- **Ideal Cycle Time**: Predetermined standard or historical average
- **Actual Cycle Time**: Measured per piece or per batch
- **Varies by**: Style-model and operation

### **Production Hours (#9)**
- **Tracked by**: Operation or Stage (Cutting, Sewing, Assembly, QC, Packing)
- **Reported**: Daily, Weekly, Monthly aggregates
- **Granularity**: Shift level with timestamps preferred

### **Absenteeism Rate (#10)**
- **Formula**: (Total absence hours / Total scheduled hours) × 100
- **Absence types**: Unscheduled absences (sick, no-show)
- **Excludes**: Planned time off (vacation, medical leave)
- **Scheduled hours**: Contracted hours per employee

---

## 🎯 **Implementation Priorities**

### **Phase 1 MVP** (Start here):
- **Production Efficiency (#3)** - Core metric, feeds multiple others
- **Performance (#8)** - Directly linked to production data
- Establish: WORK_ORDER, EMPLOYEE, PRODUCTION_ENTRY tables

### **Phase 2**:
- **WIP Aging (#1)** - Add HOLD_ENTRY tracking
- **Availability (#7)** - Add DOWNTIME_ENTRY tracking
- **OEE calculation** - Combines Availability, Performance, Quality

### **Phase 3**:
- **On-Time Delivery (#2)** - Add ATTENDANCE_ENTRY for workforce tracking
- **Absenteeism (#10)** - Leverage ATTENDANCE_ENTRY

### **Phase 4**:
- **Quality Metrics (#4, #5, #6)** - Add QUALITY_ENTRY, PART_OPPORTUNITIES
- **Production Hours by Operation (#9)** - Aggregate from PRODUCTION_ENTRY

---

## 🔒 **Critical Constraints**

1. **NO DATA DUPLICATION** - Single source of truth for all shared data
2. **MULTI-TENANT SECURITY** - Data isolation per client/business unit
3. **SCALABILITY** - Must handle 50+ clients, 3000+ employees, thousands of daily transactions
4. **DATA VALIDATION** - Enforce mandatory fields, reject invalid entries
5. **AUDIT TRAILS** - Track who changed what data and when
6. **RESPONSIVE UI** - Tablet-optimized for production floor use
7. **TIMESTAMP EVERYTHING** - Enable precise analysis and troubleshooting

---

## 💡 **Key Insights from Original Conversation**

- Current calculations are "guesstimates" - automation will reveal true performance
- Data collectors vary in technical skills - UI must be simple
- Missing dates/priorities in work orders is common - system must handle gracefully
- Paper logs updated daily at shift end - target real-time tablet entry instead
- Whiteboards are current "dashboard" - replace with real-time web dashboards
- QR code scanning is future goal - design for it but don't block on it

---

## 🚀 **Technology Requirements**

**Frontend**: Vue 3 + Vuetify 3 + Tailwind CSS (responsive, tablet-optimized)  
**Backend**: FastAPI (Python) - data validation, business logic, KPI calculations  
**Database**: SQLite for Local Development, later migrate to MariaDB (InMotion hosting) - multi-tenant schema, proper indexing  
**Deployment**: Local development environment initially

---

**This summary distills 124KB of detailed requirements into actionable specifications for the development team.**
