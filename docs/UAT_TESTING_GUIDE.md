# 🧪 KPI Operations Dashboard - User Acceptance Testing (UAT) Guide

**Version:** 1.0.0
**Last Updated:** January 15, 2026
**Status:** ✅ UAT Ready
**Design System:** IBM Carbon Design v11

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Test Environment Setup](#test-environment-setup)
4. [Test Credentials](#test-credentials)
5. [Test Scenarios](#test-scenarios)
6. [Acceptance Criteria](#acceptance-criteria)
7. [Known Issues](#known-issues)
8. [Reporting Issues](#reporting-issues)

---

## Overview

This document provides comprehensive User Acceptance Testing (UAT) instructions for the KPI Operations Dashboard Platform. The system is designed for factory supervisors to track manufacturing KPIs including production efficiency, quality metrics, attendance, and downtime.

### Application Summary
- **Frontend:** Vue.js 3.4 + Vuetify 3.5 (IBM Carbon Design v11)
- **Backend:** Python FastAPI
- **Database:** SQLite (5,000+ sample records pre-populated)
- **Test Coverage:** 1,161 backend tests | 120 E2E scenarios

---

## Prerequisites

### System Requirements
- Modern web browser (Chrome 90+, Firefox 90+, Safari 15+, Edge 90+)
- Screen resolution: 1280x720 minimum (1920x1080 recommended)
- Network access to application servers

### Test Data Available
| Entity | Count | Description |
|--------|-------|-------------|
| Clients | 5 | Manufacturing clients |
| Employees | 100 | Factory workers |
| Products | 10 | Products per client |
| Production Entries | 75 | Daily production records |
| Quality Entries | 25 | Quality inspections |
| Attendance Records | 4,800 | Employee attendance |
| Downtime Events | 63 | Equipment downtime |
| Hold Entries | 80 | WIP hold/resume events |
| Shifts | 3 | Morning, Afternoon, Night |

---

## Test Environment Setup

### Option 1: Local Development
```bash
# Backend (Terminal 1)
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Frontend (Terminal 2)
cd frontend
npm run dev
```

### Option 2: Docker Deployment
```bash
docker-compose up -d
```

### Access URLs
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## Test Credentials

### Admin User (Full Access)
```
Username: admin
Password: admin123
Role: ADMIN
```

### Power User (Supervisor)
```
Username: supervisor
Password: super123
Role: POWERUSER
```

### Regular User (Operator)
```
Username: operator
Password: oper123
Role: USER
```

---

## Test Scenarios

### 1. Authentication & Authorization

#### 1.1 Login Flow
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to application URL | Login page displays with IBM Carbon styling |
| 2 | Enter invalid credentials | Error message "Invalid credentials" appears |
| 3 | Enter valid credentials (admin/admin123) | Dashboard loads with navigation menu |
| 4 | Click user avatar → Logout | Returns to login page |

#### 1.2 Role-Based Access
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Login as admin | All menu items visible (including Admin section) |
| 2 | Login as operator | Admin menu items hidden |
| 3 | Try to access /admin URL as operator | Redirected to dashboard |

### 2. Dashboard & Navigation

#### 2.1 Main Dashboard
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Dashboard | KPI summary cards display with real-time metrics |
| 2 | Verify sidebar navigation | Clean IBM Carbon Shell-style navigation |
| 3 | Check responsive layout | Sidebar collapses on mobile/tablet |
| 4 | Verify KPI cards | Show: Efficiency, Quality, Availability, OTD metrics |

#### 2.2 Navigation Menu
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Production" | Production entry page loads |
| 2 | Click "Quality" | Quality inspection page loads |
| 3 | Click "Attendance" | Attendance tracking page loads |
| 4 | Click "Downtime" | Downtime analysis page loads |
| 5 | Click "Holds" | WIP Hold/Resume page loads |
| 6 | Click "Reports" | Reports generation page loads |

### 3. Production Entry Module

#### 3.1 View Production Data
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Production page | AG Grid displays production entries |
| 2 | Filter by date range | Grid updates with filtered data |
| 3 | Sort by column (click header) | Data sorts ascending/descending |
| 4 | Search in grid | Results filter in real-time |

#### 3.2 Add Production Entry
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Add Entry" button | Entry dialog opens |
| 2 | Fill required fields | Validation passes |
| 3 | Click "Save" | Entry saved, grid refreshes |
| 4 | Verify KPIs update | Efficiency/Performance recalculate |

#### 3.3 CSV Import - Production
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Import CSV" button | Upload dialog opens |
| 2 | Upload valid CSV file | Preview shows parsed data |
| 3 | Click "Import" | Records created with success count |
| 4 | Upload invalid CSV | Error messages show for failed rows |

### 4. Quality Module

#### 4.1 View Quality Inspections
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Quality page | Quality grid displays inspections |
| 2 | Verify PPM metric card | Shows Parts Per Million defects |
| 3 | Verify FPY metric card | Shows First Pass Yield percentage |
| 4 | Filter by inspection stage | Grid filters correctly |

#### 4.2 Add Quality Inspection
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Add Inspection" | Dialog opens |
| 2 | Enter units inspected | Field accepts numeric input |
| 3 | Enter defects found | Validates defects ≤ inspected |
| 4 | Select inspection stage | Dropdown shows: Incoming, In-Process, Final |
| 5 | Save inspection | Record created, metrics update |

#### 4.3 CSV Import - Quality
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Import CSV" | Upload dialog opens |
| 2 | Upload quality data CSV | Preview shows inspection records |
| 3 | Import successfully | Quality metrics recalculate |

### 5. Attendance Module

#### 5.1 View Attendance Records
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Attendance page | Attendance grid loads |
| 2 | Verify absenteeism metric | Shows current absenteeism rate |
| 3 | Filter by employee | Grid shows selected employee records |
| 4 | Filter by date | Shows attendance for date range |

#### 5.2 Record Attendance
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Add Record" | Dialog opens |
| 2 | Select employee from dropdown | Employee list loads |
| 3 | Select status (Present/Absent/Late) | Status dropdown works |
| 4 | Enter hours | Validates 0-24 range |
| 5 | Save record | Absenteeism KPI updates |

#### 5.3 CSV Import - Attendance
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Import CSV" | Upload dialog opens |
| 2 | Upload attendance CSV | Preview shows records |
| 3 | Import successfully | Bulk records created |

### 6. Downtime Module

#### 6.1 View Downtime Events
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Downtime page | Downtime grid loads |
| 2 | Verify availability metric | Shows equipment availability % |
| 3 | Sort by duration | Sorts downtime events |
| 4 | Filter by category | Filters by downtime type |

#### 6.2 Log Downtime Event
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Log Downtime" | Dialog opens |
| 2 | Select product/machine | Dropdowns populate correctly |
| 3 | Enter duration (hours) | Validates 0-24 range |
| 4 | Select category | Shows: Maintenance, Setup, Breakdown, etc. |
| 5 | Save event | Availability KPI updates |

#### 6.3 CSV Import - Downtime
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Import CSV" | Upload dialog opens |
| 2 | Upload downtime CSV | Preview shows events |
| 3 | Import successfully | Downtime records created |

### 7. Hold/Resume Module

#### 7.1 View WIP Holds
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Holds page | Hold grid loads |
| 2 | View active holds | Grid shows open holds |
| 3 | View resolved holds | Filter shows resolved holds |
| 4 | Sort by age | Sorts by hold duration |

#### 7.2 Create Hold
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Create Hold" | Dialog opens |
| 2 | Enter work order number | Field validates format |
| 3 | Enter quantity held | Positive integer required |
| 4 | Select hold category | Dropdown shows categories |
| 5 | Save hold | WIP Aging metrics update |

#### 7.3 Resume Hold
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Select existing hold | Hold details load |
| 2 | Click "Resume" button | Resume dialog opens |
| 3 | Enter resolution notes | Text field accepts input |
| 4 | Confirm resume | Hold marked as resolved |

### 8. Reports Module

#### 8.1 Generate Reports
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Reports page | Report options display |
| 2 | Select date range | Date picker works correctly |
| 3 | Select report type | Options available for each KPI |
| 4 | Click "Generate" | Report generates/downloads |

### 9. Admin Functions (Admin Role Only)

#### 9.1 Client Management
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Admin > Clients | Client list displays |
| 2 | Click "Add Client" | Client form opens |
| 3 | Fill client details | Validation works |
| 4 | Save client | New client created |

#### 9.2 User Management
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Admin > Users | User list displays |
| 2 | Click "Add User" | User form opens |
| 3 | Assign role | Role dropdown works |
| 4 | Assign to client | Client assignment works |

### 10. UI/UX Verification (IBM Carbon Design)

#### 10.1 Visual Design
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Verify primary color | IBM Blue (#0f62fe) used for primary actions |
| 2 | Verify success states | Green (#198038) for success indicators |
| 3 | Verify error states | Red (#da1e28) for errors |
| 4 | Verify warning states | Yellow (#f1c21b) for warnings |

#### 10.2 Typography
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Verify headings | IBM Plex Sans or Roboto font |
| 2 | Check text hierarchy | Clear visual hierarchy |
| 3 | Verify data grid text | Readable at 14px+ |

#### 10.3 Accessibility
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Tab through page | Focus visible on all interactive elements |
| 2 | Test keyboard navigation | All actions accessible via keyboard |
| 3 | Check color contrast | WCAG 2.1 AA compliant |

#### 10.4 Responsive Design
| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Resize to 768px width | Layout adapts for tablet |
| 2 | Resize to 375px width | Mobile layout renders correctly |
| 3 | Test sidebar behavior | Collapses appropriately |

---

## Acceptance Criteria

### Mandatory for UAT Approval
- [ ] All login/logout flows work correctly
- [ ] All data entry screens functional
- [ ] All CSV import features work
- [ ] KPI calculations accurate
- [ ] Data persists after refresh
- [ ] No JavaScript console errors
- [ ] Role-based access enforced

### Recommended
- [ ] Response time < 2 seconds for page loads
- [ ] No visual glitches in UI
- [ ] Consistent IBM Carbon styling
- [ ] Keyboard navigation works

---

## Known Issues

| ID | Description | Severity | Workaround |
|----|-------------|----------|------------|
| KI-001 | JOB table is empty | Low | Use CSV import to populate jobs |
| KI-002 | Some CRUD functions pending implementation | Low | Tests skip these scenarios |

---

## Reporting Issues

### Issue Template
```markdown
**Issue Type:** [Bug/Enhancement/Question]
**Severity:** [Critical/High/Medium/Low]
**Module:** [Production/Quality/Attendance/Downtime/Hold/Reports/Admin]

**Steps to Reproduce:**
1.
2.
3.

**Expected Result:**

**Actual Result:**

**Screenshots:** (if applicable)

**Browser/OS:**
```

### Contact
- Create GitHub issue in repository
- Tag with `uat-feedback` label

---

## UAT Sign-Off

| Tester | Role | Date | Status |
|--------|------|------|--------|
| | | | Pending |
| | | | Pending |
| | | | Pending |

---

**Document Version:** 1.0.0
**Prepared By:** Claude Code
**Review Date:** January 15, 2026
