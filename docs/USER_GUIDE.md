# User Guide - Manufacturing KPI Platform v1.0.0

Welcome to the Manufacturing KPI Platform. This guide will help you navigate and use the platform effectively.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Data Entry Workflows](#data-entry-workflows)
4. [KPI Reports Guide](#kpi-reports-guide)
5. [Keyboard Shortcuts](#keyboard-shortcuts)
6. [Mobile Usage Tips](#mobile-usage-tips)
7. [Frequently Asked Questions](#frequently-asked-questions)

---

## Getting Started

### Logging In

1. Open your web browser and navigate to the platform URL
2. Enter your **username** and **password**
3. Click **Sign In**

**Default Credentials (Demo):**
| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Supervisor | supervisor1 | password123 |
| Operator | operator1 | password123 |

**Important:** Change your password after first login for security.

### User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access to all clients and settings |
| **PowerUser** | Full access within assigned client |
| **Leader** | Read/write access, can approve entries |
| **Operator** | Basic data entry, view own entries |

### Navigation

The main navigation is located on the left sidebar:

- **Dashboard** - Overview of all KPIs
- **Production Entry** - Record production data
- **My Shift** - Personalized shift view (Operators)
- **Work Orders** - Manage work orders and jobs
- **Downtime** - Record machine downtime
- **Quality** - Record quality inspections
- **Attendance** - Track employee attendance
- **Reports** - Generate and download reports
- **Settings** - User preferences (varies by role)

---

## Dashboard Overview

### Main Dashboard

The dashboard provides a real-time overview of your manufacturing KPIs.

#### KPI Cards

Each KPI is displayed in a card showing:
- **Current Value** - Today's or current period value
- **Trend Arrow** - Up (improving), down (declining), or stable
- **Change Percentage** - Compared to previous period
- **Sparkline** - Mini chart showing recent trend

**Color Coding:**
- **Green** - Meeting or exceeding target
- **Yellow** - Below target but acceptable
- **Red** - Needs immediate attention

#### Available KPIs

| KPI | Description | Target |
|-----|-------------|--------|
| **Efficiency** | Hours produced vs. available | >85% |
| **Performance** | Actual vs. ideal cycle time | >90% |
| **Availability** | Uptime percentage | >95% |
| **OTD** | On-Time Delivery rate | >95% |
| **PPM** | Parts per million defects | <1000 |
| **DPMO** | Defects per million opportunities | <3400 |
| **FPY** | First Pass Yield | >98% |
| **RTY** | Rolled Throughput Yield | >95% |
| **Absenteeism** | Absence rate | <3% |
| **WIP Aging** | Average work-in-progress age | <5 days |

### Customizing Your Dashboard

1. Click the **Customize** button (gear icon) in the top right
2. Drag and drop widgets to rearrange
3. Click the **X** on widgets to remove them
4. Click **Add Widget** to add new widgets
5. Click **Save Layout** to preserve changes

**Available Widgets:**
- KPI Summary Cards
- Trend Charts
- Bradford Factor Analysis
- Data Completeness Indicator
- QR Scanner
- Quick Actions

### Using Saved Filters

Save frequently used filter combinations:

1. Set your desired filters (date range, shift, product)
2. Click the **Saved Filters** dropdown
3. Click **Save Current Filter**
4. Enter a name (e.g., "Morning Shift - January")
5. Click **Save**

To load a saved filter, simply select it from the dropdown.

### Predictive Analytics

View KPI forecasts:

1. Click on any KPI card to open the detail view
2. Toggle **Show Forecast** in the chart header
3. The chart will display predicted values for the next 7-30 days
4. Confidence intervals are shown as shaded areas

---

## Data Entry Workflows

### Production Entry

Record daily production metrics:

1. Navigate to **Production Entry** from the sidebar
2. Click **New Entry** or use the data grid
3. Fill in required fields:
   - **Work Order** - Select from dropdown or scan QR
   - **Job** - Select the specific job
   - **Shift** - Morning, Afternoon, or Night
   - **Units Produced** - Total good units
   - **Run Time** - Hours the machine was running
   - **Employees** - Number of operators assigned
   - **Defects** - Count of defective units
   - **Scrap** - Count of scrapped units
4. Click **Save** or press `Ctrl+S`

**Tips:**
- The system automatically calculates Efficiency and Performance
- Missing cycle times are inferred from historical data
- Entries are flagged if values seem unusual

### Using the Data Grid (Excel-Like)

The data grid provides spreadsheet-like functionality:

| Action | How To |
|--------|--------|
| Edit cell | Single-click on cell |
| Navigate | Arrow keys, Tab, Enter |
| Copy | `Ctrl+C` (selection) |
| Paste | `Ctrl+V` |
| Undo | `Ctrl+Z` (up to 20 actions) |
| Redo | `Ctrl+Y` |
| Delete | Select cells, press `Delete` |
| Fill down | Drag the fill handle (bottom-right corner) |
| Multi-select | `Shift+Click` or `Ctrl+Click` |

### CSV Bulk Upload

Upload multiple records at once:

1. Click **Upload CSV** button
2. Download the template if needed
3. **Step 1**: Select your CSV file
4. **Step 2**: Preview and validate data
   - Review any errors highlighted in red
   - Fix errors in your CSV and re-upload if needed
5. **Step 3**: Confirm import
   - Review the read-back summary
   - Verify record counts match expected
6. Click **Import** to complete

**CSV Format Requirements:**
- UTF-8 encoding
- Comma-separated values
- First row must be headers
- Date format: YYYY-MM-DD
- Numbers without formatting (no commas)

### Quality Inspection Entry

Record quality inspection results:

1. Navigate to **Quality** from sidebar
2. Click **New Inspection**
3. Enter:
   - **Work Order / Job**
   - **Units Inspected**
   - **Units Passed**
   - **Defect Details** (type and count for each)
4. Save the inspection

### Downtime Recording

Log machine downtime events:

1. Navigate to **Downtime** from sidebar
2. Click **New Downtime Event**
3. Enter:
   - **Machine/Line**
   - **Start Time**
   - **End Time** (or leave open if ongoing)
   - **Reason Code** (from dropdown)
   - **Description**
   - **Planned/Unplanned** checkbox
4. Save the event

### Attendance Entry

Record employee attendance:

1. Navigate to **Attendance** from sidebar
2. Use the shift grid to mark attendance:
   - Click cell to toggle Present/Absent
   - Right-click for more options (Late, Left Early, etc.)
3. Changes save automatically

### Using QR Codes

Quickly look up work orders:

1. Click the **QR Scanner** button in the header (or add widget)
2. Allow camera access when prompted
3. Point camera at work order QR code
4. Work order details auto-populate

---

## KPI Reports Guide

### Generating Reports

1. Navigate to **Reports** from sidebar
2. Select report type:
   - **Daily Summary** - Single day overview
   - **Weekly Report** - Week-over-week analysis
   - **Monthly Report** - Full month with trends
   - **Custom Range** - Select specific dates
3. Choose KPIs to include (all by default)
4. Click **Generate PDF** or **Generate Excel**

### Report Contents

**PDF Reports include:**
- Executive summary with key metrics
- KPI trend charts
- Data tables with details
- Comparison to targets
- Recommendations (if enabled)

**Excel Reports include:**
- Summary sheet with KPIs
- Raw data sheets (production, quality, etc.)
- Pivot-ready data format
- Charts on separate sheets

### Email Reports

Schedule automatic report delivery:

1. Navigate to **Reports > Email Settings**
2. Click **Configure Email Delivery**
3. Set:
   - **Recipients** - Email addresses
   - **Frequency** - Daily, Weekly, or Monthly
   - **Time** - When to send (default 6:00 AM)
   - **Include** - PDF, Excel, or both
4. Click **Save Configuration**

---

## Keyboard Shortcuts

Press `Ctrl+/` (or `Cmd+/` on Mac) to view all shortcuts.

### Global Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+/` | Show keyboard shortcuts help |
| `Ctrl+D` | Go to Dashboard |
| `Ctrl+E` | Go to Data Entry |
| `Ctrl+K` | Go to KPI Overview |
| `Ctrl+S` | Save current form/entry |
| `Escape` | Close dialog/modal |

### Data Grid Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Move to next cell |
| `Shift+Tab` | Move to previous cell |
| `Enter` | Confirm edit, move down |
| `Ctrl+C` | Copy selected cells |
| `Ctrl+V` | Paste |
| `Ctrl+Z` | Undo last change |
| `Ctrl+Y` | Redo |
| `Delete` | Clear selected cells |
| `Ctrl+A` | Select all cells |
| `Home` | Go to first cell in row |
| `End` | Go to last cell in row |
| `Ctrl+Home` | Go to first cell |
| `Ctrl+End` | Go to last cell |

### Form Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Next field |
| `Shift+Tab` | Previous field |
| `Enter` | Submit form |
| `Escape` | Cancel/close |

---

## Mobile Usage Tips

The platform is optimized for tablets and phones.

### Tablet Tips (Recommended for Shop Floor)

- **Landscape orientation** works best for data grids
- Tap and hold for context menu options
- Swipe left/right to navigate between sections
- Use the bottom navigation bar for quick access

### Phone Tips

- **Portrait orientation** recommended for forms
- Grids automatically adjust to single-column view
- Use the hamburger menu (top-left) for navigation
- QR scanner works best with good lighting

### Offline Mode (Limited)

Basic form data is cached locally:
- Entries are saved when connection returns
- A yellow banner indicates offline status
- Avoid closing the browser while offline

### Touch-Friendly Features

- All buttons meet 44px minimum touch target
- Swipe gestures for common actions
- Long-press for secondary actions
- Pull-to-refresh on lists

---

## Frequently Asked Questions

### Account & Access

**Q: How do I change my password?**
A: Go to Settings > Profile > Change Password. Enter your current password, then your new password twice.

**Q: I forgot my password. What do I do?**
A: Contact your administrator to reset your password. Self-service reset is not currently available.

**Q: Why can't I see certain menu items?**
A: Menu visibility is based on your role. Contact your administrator if you need additional access.

### Data Entry

**Q: Can I edit a submitted entry?**
A: Yes, you can edit entries you created. Leaders and above can edit any entry. Entries confirmed by supervisors cannot be modified without supervisor approval.

**Q: What does "Estimated" mean on a KPI?**
A: When actual data is missing (like cycle time), the system estimates values using historical averages. Estimated values are flagged with an indicator and have a confidence score.

**Q: My CSV upload failed. What should I check?**
A: Common issues:
- Wrong date format (use YYYY-MM-DD)
- Missing required columns
- Invalid product/job IDs
- Numbers with commas or currency symbols

**Q: How far back can I enter data?**
A: By default, entries can be backdated up to 7 days. Contact your administrator for older entries.

### Reports & KPIs

**Q: Why is my efficiency over 100%?**
A: This can happen if actual cycle times are faster than the ideal cycle time in the system. Contact your administrator to verify cycle time settings.

**Q: KPIs don't match my manual calculations. Why?**
A: Ensure you're comparing the same:
- Date range
- Shifts included
- Products/work orders filtered
Check the filter settings on the dashboard.

**Q: Can I export raw data?**
A: Yes, use the Excel report option which includes raw data sheets, or use the Export button on any data grid.

### Technical Issues

**Q: The page is loading slowly. What can I do?**
A: Try:
- Refresh the page
- Clear browser cache
- Reduce the date range filter
- Use Chrome or Edge for best performance

**Q: Charts aren't displaying correctly.**
A: Ensure JavaScript is enabled. Try:
- Refreshing the page
- Using a different browser
- Clearing browser cache

**Q: I'm getting "Session Expired" messages.**
A: Your session expires after 8 hours of inactivity. Simply log in again. Your unsaved data may be lost.

---

## Support

For additional help:

1. Click the **Help** icon (?) in the top right
2. Check the in-app tooltips (hover over ? icons)
3. Contact your system administrator
4. Submit a support ticket through your IT helpdesk

---

**Last Updated**: 2026-01-25
**Version**: 1.0.0
