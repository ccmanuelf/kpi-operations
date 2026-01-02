# Manufacturing KPI Platform - Keyboard Shortcuts Reference

**Version**: 2.0 (Excel-Like Data Entry with AG Grid)
**Last Updated**: January 1, 2026

---

## Quick Start Guide

### What's New in Version 2.0?

✅ **Excel-Like Editing**: Copy/paste directly from Excel or Google Sheets
✅ **Keyboard Navigation**: Use Tab, Enter, and Arrow keys to navigate cells
✅ **Bulk Editing**: Select and edit multiple cells at once
✅ **Auto-Fill**: Drag cell handles to fill down data
✅ **Undo/Redo**: Press Ctrl+Z to undo mistakes

**Goal**: Enter 50-200 records per shift in 5-10 minutes (vs. 30-45 minutes previously)

---

## Keyboard Shortcuts

### Navigation

| Shortcut | Action | Example Use Case |
|----------|--------|------------------|
| **Tab** | Move to next cell (right) | Quickly jump through production data columns |
| **Shift + Tab** | Move to previous cell (left) | Go back to fix a mistake |
| **Enter** | Move down to cell below | Enter data in a column, press Enter to move down |
| **Shift + Enter** | Move up to cell above | Move up to previous row |
| **Arrow Keys** | Navigate in any direction | Fine-tune cell selection |
| **Home** | Move to first cell in row | Jump to beginning of row |
| **End** | Move to last cell in row | Jump to end of row |
| **Ctrl + Home** | Move to first cell in grid | Jump to top-left corner |
| **Ctrl + End** | Move to last cell in grid | Jump to bottom-right corner |
| **Page Down** | Scroll down one page | Quickly navigate large datasets |
| **Page Up** | Scroll up one page | Scroll back up |

---

### Editing

| Shortcut | Action | Example Use Case |
|----------|--------|------------------|
| **F2** or **Double Click** | Enter edit mode | Start editing a cell |
| **Escape** | Cancel editing | Discard changes to current cell |
| **Enter** (in edit mode) | Save and move down | Save cell and move to next row |
| **Tab** (in edit mode) | Save and move right | Save cell and move to next column |
| **Delete** | Clear cell contents | Quickly delete cell value |
| **Backspace** | Clear cell and enter edit mode | Start typing new value |
| **Type** (when cell selected) | Overwrite cell contents | Start typing to replace value |

---

### Copy/Paste

| Shortcut | Action | Example Use Case |
|----------|--------|------------------|
| **Ctrl + C** | Copy selected cells | Copy production data from Excel |
| **Ctrl + X** | Cut selected cells | Move data to another location |
| **Ctrl + V** | Paste copied cells | Paste data from Excel/clipboard |
| **Ctrl + D** | Fill down (repeat value) | Copy first cell value to selected cells below |
| **Ctrl + R** | Fill right (repeat value) | Copy first cell value to selected cells on right |

**Pro Tip**: Copy a range of cells from Excel (e.g., 50 rows × 8 columns) and paste directly into the grid. AG Grid will automatically match columns and validate data.

---

### Selection

| Shortcut | Action | Example Use Case |
|----------|--------|------------------|
| **Click** | Select single cell | Focus on one cell |
| **Shift + Click** | Select cell range | Select from current cell to clicked cell |
| **Ctrl + Click** | Add cell to selection | Select multiple non-adjacent cells |
| **Ctrl + A** | Select all cells | Select entire grid |
| **Click + Drag** | Select multiple cells | Drag mouse to select range |
| **Shift + Arrow Keys** | Extend selection | Grow selection in any direction |

---

### Undo/Redo

| Shortcut | Action | Example Use Case |
|----------|--------|------------------|
| **Ctrl + Z** | Undo last change | Revert accidental edits |
| **Ctrl + Y** or **Ctrl + Shift + Z** | Redo change | Re-apply undone change |

**Note**: Undo/redo works for cell edits, but not for adding/deleting rows (use Cancel button instead).

---

### Other Shortcuts

| Shortcut | Action | Example Use Case |
|----------|--------|------------------|
| **Ctrl + F** | Search/filter (if enabled) | Find specific work order or product |
| **F1** | Show help dialog | Display this keyboard shortcuts reference |

---

## Data Entry Workflows

### Production Entry (50 records in 5 minutes)

**Scenario**: Enter production data for 50 work orders from an Excel spreadsheet

**Steps**:

1. **Open Excel file** with production data (columns: Date, Product, Shift, Work Order, Units, Runtime, Employees)
2. **Select all data rows** in Excel (Ctrl + Shift + End)
3. **Copy** (Ctrl + C)
4. **Go to Manufacturing KPI Platform** → Production Entry
5. **Click "Add Entry" button** to create first blank row
6. **Click on first cell** (Date column)
7. **Paste** (Ctrl + V) - all 50 rows paste automatically
8. **Review data** - cells with errors highlighted in red
9. **Fix any validation errors** (Tab to navigate)
10. **Click "Save All"** - done!

**Time Saved**: 25 minutes (30 min → 5 min)

---

### Attendance Entry (150 employees in 8 minutes)

**Scenario**: Enter daily attendance for 150 employees

**Steps**:

1. **Go to Attendance Entry** page
2. **Select Date and Shift** → Click "Load Employees"
3. Grid auto-populates with 150 employees (all marked "Present" by default)
4. **Use keyboard to update statuses**:
   - Press **Tab** to move through each employee
   - Type **"A"** for Absent, **"L"** for Late (dropdown auto-filters)
   - Press **Enter** to move down
5. **For absent employees**, Tab to "Absence Reason" column and select reason
6. **For late employees**, Tab to "Late Minutes" and enter value
7. **Click "Save Attendance Records"** - done!

**Time Saved**: 37 minutes (45 min → 8 min)

---

### Quality Inspection (20 lots in 3 minutes)

**Scenario**: Enter quality inspection results for 20 production lots

**Steps**:

1. **Copy inspection data from lab sheet** (Excel or paper → manually type)
2. **Go to Quality Entry** page
3. **Click "Add Inspection"** 20 times (or copy/paste from Excel)
4. **Enter data** using Tab to navigate:
   - Work Order → Tab
   - Product → Tab (dropdown)
   - Inspected Qty → Tab
   - Defect Qty → Tab (FPY% auto-calculates!)
   - Disposition → Tab (dropdown)
5. **Review calculated metrics** (FPY%, PPM) - cells turn red if below threshold
6. **Click "Save All"** - done!

**Time Saved**: AG Grid auto-calculates FPY and PPM (no manual math needed)

---

## Tips & Tricks

### 1. Copy from Excel Without Formatting

If pasting from Excel brings unwanted formatting:
- **Paste as plain text**: Use **Ctrl + Shift + V** (in some browsers)
- Or: Copy from Excel → Paste to Notepad → Copy from Notepad → Paste to AG Grid

### 2. Fill Down Repetitive Data

For columns with repeated values (e.g., same shift for all rows):
- **Enter value in first cell**
- **Select first cell + all cells below** (Shift + Click on last cell)
- **Press Ctrl + D** (fill down) - value copies to all selected cells

### 3. Quickly Fix Errors

Cells with validation errors are highlighted in red:
- **Navigate to red cell** (Tab or Arrow keys)
- **Fix error** (edit cell)
- **Press Enter** to move to next error
- Repeat until all red cells are fixed

### 4. Use Dropdowns for Fast Entry

For columns with dropdowns (Product, Shift, Status):
- **Start typing** the first letter (e.g., "S" for "Shift 1")
- Dropdown auto-filters matching options
- **Press Enter** to select

### 5. Select Entire Column

To select all cells in a column:
- **Click column header** (e.g., "Units Produced")
- **Press Ctrl + C** to copy entire column
- **Paste** into Excel for analysis

---

## Comparison: Old vs. New

### Old Method (v-data-table)

| Task | Method | Time |
|------|--------|------|
| Enter 50 production records | Click Edit → Type → Click Save (one by one) | 30 min |
| Enter 150 attendance records | Click form → Fill dropdowns → Click Submit (one by one) | 45 min |
| Copy from Excel | Not possible - manual re-typing | N/A |
| Keyboard navigation | Limited (mostly mouse clicks) | Slow |
| Bulk editing | Not supported | N/A |

### New Method (AG Grid)

| Task | Method | Time |
|------|--------|------|
| Enter 50 production records | Copy/paste from Excel → Fix errors → Save All | **5 min** ⚡ |
| Enter 150 attendance records | Load employees → Tab through → Save | **8 min** ⚡ |
| Copy from Excel | **Ctrl + C → Ctrl + V** | Instant |
| Keyboard navigation | **Tab, Enter, Arrow keys** | Fast |
| Bulk editing | **Select range → Fill down (Ctrl + D)** | Seconds |

**Overall Time Savings**: **80% reduction** in data entry time

---

## Troubleshooting

### Problem: Paste doesn't work

**Solution**:
- Make sure you've **selected a cell** before pasting (click on a cell first)
- Ensure clipboard has **text data** (not images or formatting)
- Try **Ctrl + Shift + V** (paste as plain text)

### Problem: Validation errors after pasting

**Solution**:
- **Red cells** indicate validation errors (e.g., negative numbers, invalid dates)
- Navigate to red cell (Tab key) and fix manually
- Common errors:
  - Date format (use YYYY-MM-DD, e.g., 2026-01-15)
  - Product/Shift IDs must match dropdown values

### Problem: Can't edit cell

**Solution**:
- **Double-click** cell or press **F2** to enter edit mode
- Some columns are **read-only** (e.g., calculated fields like FPY%)
- Ensure you have **edit permissions** (OPERATOR, LEADER, or ADMIN role)

### Problem: Undo not working

**Solution**:
- Undo (**Ctrl + Z**) only works for cell edits, not row additions/deletions
- If you added a row by mistake, click the **Delete button** (trash icon)

---

## Training Resources

### Video Tutorials (Coming Soon)

1. **Production Entry with AG Grid** (5 min)
2. **Attendance Entry Bulk Upload** (4 min)
3. **Copy/Paste from Excel** (2 min)
4. **Keyboard Navigation Masterclass** (10 min)

### Practice Exercises

1. **Exercise 1**: Enter 10 production records using only keyboard (no mouse)
2. **Exercise 2**: Copy/paste 50 rows from Excel sample file
3. **Exercise 3**: Use fill-down (Ctrl + D) to populate shift IDs

### Support

**Questions?** Contact IT Support:
- Email: support@example.com
- Phone: ext. 1234
- Help Desk: Open 8am-5pm Monday-Friday

---

## Quick Reference Card (Print This!)

```
┌─────────────────────────────────────────────────────────┐
│   MANUFACTURING KPI PLATFORM - KEYBOARD SHORTCUTS       │
├─────────────────────────────────────────────────────────┤
│ NAVIGATION                                              │
│  Tab              → Next cell (right)                   │
│  Shift + Tab      → Previous cell (left)                │
│  Enter            → Move down                           │
│  Arrow Keys       → Navigate in any direction           │
│                                                          │
│ EDITING                                                 │
│  F2 / Double Click → Enter edit mode                    │
│  Escape           → Cancel editing                      │
│  Delete           → Clear cell                          │
│                                                          │
│ COPY/PASTE                                              │
│  Ctrl + C         → Copy                                │
│  Ctrl + V         → Paste                               │
│  Ctrl + D         → Fill down                           │
│                                                          │
│ UNDO/REDO                                               │
│  Ctrl + Z         → Undo                                │
│  Ctrl + Y         → Redo                                │
│                                                          │
│ HELP                                                    │
│  F1               → Show keyboard shortcuts             │
└─────────────────────────────────────────────────────────┘
```

---

**Pro Tip**: Print this reference card and keep it at your workstation for quick access!
