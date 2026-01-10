# Data Field Inventory - Instructions & Guide

## Overview

This data inventory consists of **5 CSV files** organized by module/phase. Each file contains all data fields required for that phase, with columns for you and the Operations team to assess current data status.

---

## How to Use These Files

### **Step 1: Review and Validate Each CSV File**

Start with `01-Core_DataEntities_Inventory.csv` (foundational), then proceed through phases 1-4.

### **Step 2: Fill In ALL Columns**

For EACH row (data field), provide an assessment of:

| Column | What to Fill In | Example |
|--------|-----------------|---------|
| **Current_Format** | How is this CURRENTLY collected, if at all? | "Excel column 'WO#'" / "Paper logbook" / "Not collected" / "Time clock system" |
| **Quality_Level** | Assess data completeness/consistency | "Complete & Consistent" / "Partial (80%)" / "Inconsistent formats" / "Missing" |
| **Action_Needed** | What Operations needs to do | "Standardize date format" / "Start collecting" / "Merge from 3 different sources" / "No action needed" |
| **Notes** | Any concerns, blockers, or context | "Finance uses MM/DD/YYYY, we use YYYY-MM-DD" / "Only Client A has this" / "Engineering updates quarterly" |

### **Step 3: Identify Data Gaps**

- Mark fields as "Missing" if not currently collected
- For Missing fields, your team should plan:
  - **Who** will collect it?
  - **When** (real-time, hourly, end-of-shift)?
  - **How** (system, manual, sensor)?
  - **Training** required for data collectors?

### **Step 4: Prioritize Actions**

Before returning to us, prioritize:
- **Red (Critical)**: Required fields still missing - must collect before development
- **Yellow (Important)**: Optional fields that would improve accuracy
- **Green (Nice-to-have)**: Complementary fields for future phases

### **Step 5: Return Completed Files**

Send back all 5 CSVs with your assessments. Include a summary:
- % of fields already collected
- % of fields needing standardization
- % of fields needing new collection process
- Any blockers to implementation

---

## File Descriptions

### **01-Core_DataEntities_Inventory.csv**
**Foundational tables used by ALL modules**

Contains fields for:
- WORK_ORDER (Job tracking, dates, quantities)
- JOB (Individual line items within work orders)
- CLIENT (Business unit configuration)
- EMPLOYEE (Staff directory)
- FLOATING_POOL (Shared resource tracking)
- USER (System accounts & authentication)

*Start here - these are the foundation for everything else*

---

### **02-Phase1_Production_Inventory.csv**
**Feeds KPI #3 (Efficiency) & KPI #9 (Performance)**

Contains fields for:
- PRODUCTION_ENTRY (Units produced, defects, run time)
- Shift information
- Operation/stage tracking
- Data collector identification

*Phase 1 MVP deliverable - data grid entry & calculations*

---

### **03-Phase2_Downtime_WIP_Inventory.csv**
**Feeds KPI #7 (OEE) & KPI #8 (Availability) & KPI #1 (WIP Aging)**

Contains fields for:
- DOWNTIME_ENTRY (Equipment failure, material shortage, setup, etc.)
- HOLD_ENTRY (Job on hold tracking & resume)
- Downtime reasons & duration
- Hold approval & release tracking

*Phase 2 deliverable - downtime logging & WIP hold logic*

---

### **04-Phase3_Attendance_Inventory.csv**
**Feeds KPI #2 (On-Time Delivery) & KPI #10 (Absenteeism)**

Contains fields for:
- ATTENDANCE_ENTRY (Scheduled vs actual hours)
- COVERAGE_ENTRY (Floating staff assignments)
- Absence types (unscheduled, vacation, medical, etc.)
- Absence coverage tracking

*Phase 3 deliverable - attendance & floating staff logic*

---

### **05-Phase4_Quality_Inventory.csv**
**Feeds KPI #4 (PPM), #5 (DPMO), #6 (FPY), #7 (RTY)**

Contains fields for:
- QUALITY_ENTRY (Defects, repair/rework tracking)
- PART_OPPORTUNITIES (Opportunities per unit master data)
- Defect categorization
- Repair vs Rework vs Scrap tracking

*Phase 4 deliverable - quality metrics & defect tracking*

---

## Column Definitions

### **Standard Columns in All Files**

| Column | Description |
|--------|-------------|
| **Field_Name** | Database field name (snake_case, e.g., `work_order_id`) |
| **Table_Name** | Which database table this belongs to (e.g., `WORK_ORDER`) |
| **Data_Type** | SQL data type (VARCHAR, INT, DATE, DECIMAL, ENUM, BOOLEAN) |
| **Required** | YES = mandatory for system to function |
| **Optional** | YES = nice-to-have, improves KPI accuracy |
| **Complementary** | YES = enhances other metrics, useful for audit trails |
| **Current_Format** | **[YOU FILL IN]** How you currently collect this (or "Not collected") |
| **Suggested_Format** | Our recommendation for standardization (examples, validation rules) |
| **Format_Notes** | Examples, constraints, validation patterns |
| **Quality_Level** | **[YOU FILL IN]** Complete / Partial(XX%) / Inconsistent / Missing / Unknown |
| **Action_Needed** | **[YOU FILL IN]** What your team needs to do about this field |
| **Notes** | **[YOU FILL IN]** Concerns, blockers, context, observations |

---

## Key Principles

### **1. Standardization Over Perfection**

Don't delay for perfect data. Standardize formats NOW:
- **Dates**: Always ISO 8601 (YYYY-MM-DD)
- **Times**: Always 24-hour format (HH:MM)
- **Decimals**: Use period (.) not comma (,)
- **Booleans**: YES/NO or TRUE/FALSE (pick one, stick to it)

### **2. Start Collecting Missing Fields Now**

Fields marked "Missing" need collection plans. Start BEFORE development:
- Example: If `ideal_cycle_time` not available, contact Engineering NOW
- Example: If `downtime_reason` not logged, create standardized list NOW
- Don't let development block on data collection

### **3. Don't Over-Collect**

Some fields are Optional or Complementary. You can defer these:
- **Phase 1**: Only collect Required fields
- **Phase 2+**: Add Optional fields as system proves value
- **Future**: Add Complementary fields for advanced analytics

### **4. Data Validation Rules Are Built-In**

Each field includes Format_Notes with:
- Min/max values
- Allowed characters
- Regex patterns
- Example valid entries

Use these to train data collectors.

---

## Quality Assessment Guide

When filling "Quality_Level":

| Level | Description | Example | Action |
|-------|-------------|---------|--------|
| **Complete & Consistent** | 100% of data available in standard format | All work orders have ISO dates | No action needed |
| **Partial (XX%)** | 80-99% available, mostly consistent | 95% have planned_ship_date, 5% missing | Identify missing 5%, pursue them |
| **Inconsistent** | 100% available but multiple formats mixed | Some dates are MM/DD/YYYY, others YYYY-MM-DD | Create format standardization plan |
| **Missing** | 0-50% available or not collected | `ideal_cycle_time` only in 20% of WOs | Create collection process |
| **Unknown** | Never assessed or unclear | "Not sure if downtime is tracked" | Assign someone to investigate |

---

## Task Expectations

**Recommended:** Complete this inventory obtaining feedback or evaluating for data integrity

1. **Steps 1-2**: Each team lead reviews their section
2. **Steps 3-5**: Dig through existing data (spreadsheets, logbooks, systems)
3. **Steps 6-7**: Team discussion - align on standards, identify blockers
4. **Steps 8-14**: Create action plans for missing/inconsistent data

**Do NOT:**
- ❌ Leave fields as "Unknown" - investigate
- ❌ Rush through - accuracy matters for development
- ❌ Mark everything as "Inconsistent" without specifics - be detailed
- ❌ Plan to collect during development - collect NOW

**DO:**
- ✅ Be honest about data quality
- ✅ Flag blockers early (Engineering slow to provide specs?)
- ✅ Assign owners for each action item
- ✅ Plan training for data collectors on new standardized formats

---

## Example Completed Row

**Current state (blank):**
```
ideal_cycle_time,WORK_ORDER,DECIMAL(10.4),CONDITIONAL,NO,NO,"","Decimal hours (0.25 hrs = 15 min, 2.5 hrs = 2h 30m)","Stored in hours, converted for UI display if needed","","",""
```

**Completed by your team:**
```
ideal_cycle_time,WORK_ORDER,DECIMAL(10.4),CONDITIONAL,NO,NO,"Excel 'StdTime' column, hours or minutes mixed","Decimal hours (0.25 hrs = 15 min, 2.5 hrs = 2h 30m)","Stored in hours, converted for UI display if needed","Partial (80% - some styles missing)","1. Contact Engineering for missing styles 2. Standardize all to decimal hours 3. Verify values with Production","Engineering updates quarterly - need process to sync. Client A uses minutes, Client B uses hours - standardize to hours"
```

---

## Questions to Ask Your Team

As you review each field:

1. **Do we have it?** If not, where can we get it?
2. **In what format?** Is it consistent across all Clients?
3. **Who collects it?** Is their process documented?
4. **How often?** Real-time, hourly, daily, weekly?
5. **Quality?** Complete? Accurate? Reliable?
6. **Issues?** Any known gaps, errors, or inconsistencies?
7. **Can we standardize?** What format makes sense for everyone?

---

## Next Steps After Completion

1. **Return all 5 CSVs** with your team's assessments
2. **Include a 1-2 page summary**:
   - Overall data readiness % (what % of fields are ready to go)
   - Critical gaps (fields absolutely needed before development)
   - Blockers (external dependencies, slow teams, etc.)
   - Timeline (when can we have all critical fields ready?)
3. **Provide sample data** (optional, but helpful):
   - 2-3 rows of actual production data (anonymized)
   - Shows real format, quality, and edge cases
4. **Evaluate the expected calculations** (CRITICAL):
   - See file: `Metrics_Sheet1.csv`
---

## Contact

If you have questions while filling these out:
- **Data format questions**: Reference the "Format_Notes" column
- **Field purpose questions**: Check the KPI it feeds (linked in each row)
- **Standardization questions**: Reference the "Suggested_Format" column
- **Strategic questions**: Document in "Notes" column, we'll clarify after

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-02 | Initial creation |

---

**Ready to start? Open the first file: `01-Core_DataEntities_Inventory.csv`**
