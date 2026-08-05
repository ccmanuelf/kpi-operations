/**
 * Composable for AttendanceEntryGrid script logic — reactive
 * state, column definitions, CRUD, paste handling, employee
 * loading, bulk status, status counts, read-back confirmation.
 *
 * Backend alignment: payload matches backend/schemas/attendance.py
 * AttendanceRecordCreate. shift_date and shift_id come from the
 * composable-level selectedDate/selectedShift. UI status string
 * (Present/Absent/Late/Half Day/Leave/Vacation/Medical) is translated
 * to is_absent + absence_type + is_late on save. clock_in/clock_out
 * (HH:MM strings) are combined with shift_date to produce ISO
 * arrival_time/departure_time datetimes.
 *
 * Labor-hours capture (Cycle 3 PR-A, Task 7): normal_hours/double_hours/
 * triple_hours (OT split, all-null = unsplit), labor_class_override
 * (direct/indirect/null), and allocations (intra-day hour ledger, edited
 * via AllocationEditorDialog.vue) ride the same create/update payload —
 * see backend/schemas/attendance.py AttendanceRecordCreate/Update.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'
import { format } from 'date-fns'
import { LABOR_CLASS_CODES, laborClassLabelKey } from '@/constants/laborTaxonomy'
import { allocatedTotal, type AllocationItemPayload } from '@/composables/useAllocationEditor'

export interface AttendanceRow {
  attendance_entry_id?: string | number
  employee_id?: string | number
  employee_name?: string
  department?: string
  shift_date?: string
  shift_id?: string | number | null
  status?: string
  clock_in?: string
  clock_out?: string
  scheduled_hours?: number
  actual_hours?: number
  absence_reason?: string
  notes?: string
  normal_hours?: number | null
  double_hours?: number | null
  triple_hours?: number | null
  labor_class_override?: string | null
  allocations?: AllocationItemPayload[]
  billed_hours?: number
  available_for_efficiency_hours?: number | null
  effective_labor_class?: string | null
  _hasChanges?: boolean
  _isNew?: boolean
  _isExisting?: boolean
  [key: string]: unknown
}

export interface ShiftRef {
  shift_id: string | number
  shift_name?: string
  [key: string]: unknown
}

interface AGGridApi {
  sizeColumnsToFit: () => void
  refreshCells: () => void
  applyTransaction: (_params: { add?: AttendanceRow[]; addIndex?: number }) => void
  forEachNode: (_cb: (_node: { data: AttendanceRow }) => void) => void
}

interface AGGridRef {
  gridApi?: AGGridApi
  refreshCells?: () => void
}

interface SnackbarState {
  show: boolean
  message: string
  color: string
}

export interface ConfirmationField {
  key: string
  label: string
  type: 'text' | 'date' | 'number' | 'boolean'
  displayValue?: string | number
}

interface PasteData {
  parsedData: unknown
  convertedRows: AttendanceRow[]
  validationResult: unknown
  columnMapping: unknown
  [key: string]: unknown
}

interface UseAttendanceGridDataOptions {
  TimePickerCellEditor?: unknown
}

const DEFAULT_SCHEDULED_HOURS = 8

// Mirrors backend/schemas/attendance.py from_legacy_csv mapping.
// Half Day is not a backend concept — represented as Present with
// reduced actual_hours = scheduled / 2 (operator can adjust).
export interface StatusTranslation {
  is_absent: 0 | 1
  absence_type: string | null
  is_late: 0 | 1
  actualHoursFactor: number
}

export const translateStatus = (status: string | undefined): StatusTranslation => {
  switch ((status || 'Present').toLowerCase()) {
    case 'absent':
      return { is_absent: 1, absence_type: 'UNSCHEDULED_ABSENCE', is_late: 0, actualHoursFactor: 0 }
    case 'late':
      return { is_absent: 0, absence_type: null, is_late: 1, actualHoursFactor: 1 }
    case 'half day':
      return { is_absent: 0, absence_type: null, is_late: 0, actualHoursFactor: 0.5 }
    case 'leave':
      return { is_absent: 1, absence_type: 'PERSONAL_LEAVE', is_late: 0, actualHoursFactor: 0 }
    case 'vacation':
      return { is_absent: 1, absence_type: 'VACATION', is_late: 0, actualHoursFactor: 0 }
    case 'medical':
      return { is_absent: 1, absence_type: 'MEDICAL_LEAVE', is_late: 0, actualHoursFactor: 0 }
    case 'present':
    default:
      return { is_absent: 0, absence_type: null, is_late: 0, actualHoursFactor: 1 }
  }
}

export const combineDateTime = (
  date: string | undefined,
  time: string | undefined,
): string | undefined => {
  if (!date || !time) return undefined
  const trimmed = time.trim()
  if (!/^\d{1,2}:\d{2}$/.test(trimmed)) return undefined
  const [h, m] = trimmed.split(':')
  return `${date}T${h.padStart(2, '0')}:${m}:00`
}

// Allocations button-cell (module scope — no per-instance closures needed
// beyond the params passed in). Empty cell (no button label text) when
// nothing's allocated yet, per the no-low-contrast-placeholder rule; the
// button itself always renders so a row can still open the dialog to make
// its first allocation.
const renderAllocationsCell = (
  params: { data: AttendanceRow },
  ctx: {
    t: (_key: string, _named?: Record<string, unknown>) => string
    openAllocationDialog: (_row: AttendanceRow) => void
  },
): HTMLElement => {
  const btn = document.createElement('button')
  btn.className = 'ag-grid-allocations-btn'
  btn.type = 'button'
  btn.setAttribute('data-testid', 'attendance-allocations-btn')
  btn.title = ctx.t('labor.allocationsTitle')
  btn.style.cssText =
    'background: transparent; border: 1px solid currentColor; border-radius: 4px; ' +
    'padding: 2px 8px; cursor: pointer; font-size: 11px; font-weight: 600; color: inherit;'

  const total = allocatedTotal(params.data.allocations || [])
  // "+" is an action affordance ("add an allocation"), not a data value —
  // distinct from a placeholder like "0/8 h" that could be misread as an
  // actual (zero) allocation.
  btn.textContent =
    total > 0
      ? ctx.t('labor.allocatedSummary', {
          allocated: total,
          actual: params.data.actual_hours ?? 0,
        })
      : '+'

  btn.addEventListener('click', () => ctx.openAllocationDialog(params.data))
  return btn
}

export default function useAttendanceGridData(
  { TimePickerCellEditor }: UseAttendanceGridDataOptions = {},
) {
  const { t } = useI18n()
  const authStore = useAuthStore()
  const kpiSelectionStore = useKPIStore()

  const gridRef = ref<AGGridRef | null>(null)
  const selectedDate = ref(format(new Date(), 'yyyy-MM-dd'))
  const selectedShift = ref<string | number | null>(null)
  const selectedLine = ref<string | number | null>(null)
  const shifts = ref<ShiftRef[]>([])
  const attendanceData = ref<AttendanceRow[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const showConfirmDialog = ref(false)
  const pendingData = ref<AttendanceRow>({})
  const pendingRows = ref<AttendanceRow[]>([])

  // AG Grid's cellValueChanged event.data (and the row handed into the
  // allocations dialog) is not reliably the same object instance Vue
  // tracks inside attendanceData.value — verified empirically in a real
  // browser session: mutating event.data in place left attendanceData.value's
  // own copy of that row untouched. markRowAsChanged/onAllocationsSaved
  // now re-resolve to the actual tracked row by identity before mutating
  // (see findTrackedRow below), which is the real fix. editTick is a
  // belt-and-suspenders dirty-signal on top of that: every mutation site
  // bumps it, and every computed that needs to see the mutation reads it
  // (a no-op read, purely to register the dependency) before deriving
  // from attendanceData.value — covers the defensive fallback path where
  // no tracked row is found and a not-necessarily-identical row object
  // gets mutated directly instead.
  const editTick = ref(0)

  const showPasteDialog = ref(false)
  const parsedPasteData = ref<unknown | null>(null)
  const convertedPasteRows = ref<AttendanceRow[]>([])
  const pasteValidationResult = ref<unknown | null>(null)
  const pasteColumnMapping = ref<unknown | null>(null)

  const pendingRowsCount = computed(() => pendingRows.value.length)

  // Operators inherit client_id from auth; admin users fall back to KPI store selection.
  const activeClientId = (): string | number | null => {
    return authStore.user?.client_id_assigned ?? kpiSelectionStore.selectedClient ?? null
  }

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const shiftName =
      shifts.value.find((s) => s.shift_id === selectedShift.value)?.shift_name || 'N/A'

    return [
      { key: 'employee_id', label: t('grids.columns.employeeId'), type: 'text' },
      { key: 'employee_name', label: t('grids.columns.employeeName'), type: 'text' },
      { key: 'department', label: t('grids.columns.department'), type: 'text' },
      {
        key: 'shift_date',
        label: t('grids.columns.shiftDate'),
        type: 'date',
        displayValue: selectedDate.value,
      },
      { key: 'shift_id', label: t('filters.shift'), type: 'text', displayValue: shiftName },
      { key: 'status', label: t('grids.columns.status'), type: 'text' },
      { key: 'clock_in', label: t('grids.columns.clockIn'), type: 'text' },
      { key: 'clock_out', label: t('grids.columns.clockOut'), type: 'text' },
      { key: 'scheduled_hours', label: t('grids.columns.scheduledHours'), type: 'number' },
      { key: 'actual_hours', label: t('grids.columns.actualHours'), type: 'number' },
      { key: 'absence_reason', label: t('grids.columns.absenceReason'), type: 'text' },
    ]
  })

  const hasChanges = computed(() => {
    void editTick.value
    return attendanceData.value.some((row) => row._hasChanges)
  })

  const changedRowsCount = computed(() => {
    void editTick.value
    return attendanceData.value.filter((row) => row._hasChanges).length
  })

  // AG Grid's cellValueChanged event.data (and the row handed to the
  // allocations dialog) is NOT reliably the same object instance tracked
  // in attendanceData.value — verified in the browser: mutating it
  // in-place does not affect what attendanceData.value holds, even
  // though editTick forces a re-derive (there's nothing new to derive,
  // because the tracked row was never touched). Re-resolve to the
  // actual reactive row by employee_id (unique per grid load — the
  // same key existingMap merges on) before mutating, so the mutation
  // lands on the object hasChanges/changedRowsCount/noSplitCount/
  // unallocatedCount/statusCounts actually iterate. Falls back to the
  // given row when no match is found (defensive — shouldn't happen for
  // a row that came from the grid's own rowData).
  const findTrackedRow = (row: AttendanceRow): AttendanceRow | undefined =>
    attendanceData.value.find((r) => r.employee_id === row.employee_id)

  // Allocation dialog (AllocationEditorDialog.vue) — opened from the grid's
  // allocations button-cell (see columnDefs below).
  const showAllocationDialog = ref(false)
  const allocationDialogRow = ref<AttendanceRow | null>(null)

  const openAllocationDialog = (row: AttendanceRow): void => {
    allocationDialogRow.value = findTrackedRow(row) ?? row
    showAllocationDialog.value = true
  }

  const onAllocationsSaved = (payload: {
    row: AttendanceRow
    items: AllocationItemPayload[]
  }): void => {
    const target = findTrackedRow(payload.row) ?? payload.row
    target.allocations = payload.items
    target._hasChanges = true
    editTick.value++
    gridRef.value?.refreshCells?.()
  }

  // Completeness chips (host renders both `v-if > 0`): entries with actual
  // hours recorded but no OT split captured yet, and entries with no hour
  // allocations recorded yet.
  const noSplitCount = computed(() => {
    void editTick.value
    return attendanceData.value.filter(
      (row) =>
        row.actual_hours !== undefined &&
        row.actual_hours !== null &&
        row.normal_hours == null &&
        row.double_hours == null &&
        row.triple_hours == null,
    ).length
  })

  const unallocatedCount = computed(() => {
    void editTick.value
    return attendanceData.value.filter((row) => !row.allocations || row.allocations.length === 0)
      .length
  })

  const statusCounts = computed(() => {
    void editTick.value
    const counts = { present: 0, absent: 0, late: 0, leave: 0, halfDay: 0 }

    attendanceData.value.forEach((row) => {
      const status = row.status?.toLowerCase()
      if (status === 'present') counts.present++
      else if (status === 'absent') counts.absent++
      else if (status === 'late') counts.late++
      else if (status === 'leave' || status === 'vacation' || status === 'medical')
        counts.leave++
      else if (status === 'half day') counts.halfDay++
    })

    return counts
  })

  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.employeeId'),
      field: 'employee_id',
      editable: false,
      pinned: 'left' as const,
      width: 130,
      cellClass: 'font-weight-bold',
    },
    {
      headerName: t('grids.columns.employeeName'),
      field: 'employee_name',
      editable: false,
      pinned: 'left' as const,
      width: 200,
      cellClass: 'font-weight-bold',
    },
    {
      headerName: t('grids.columns.department'),
      field: 'department',
      editable: false,
      width: 150,
    },
    {
      headerName: t('grids.columns.status'),
      field: 'status',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['Present', 'Absent', 'Late', 'Half Day', 'Leave', 'Vacation', 'Medical'],
      },
      cellClass: (params: { value?: string }) => {
        const classes: Record<string, string> = {
          Present: 'ag-cell-success ag-cell-bold',
          Absent: 'ag-cell-error ag-cell-bold',
          Late: 'ag-cell-warning ag-cell-bold',
          'Half Day': 'ag-cell-warning-light ag-cell-bold',
          Leave: 'ag-cell-purple ag-cell-bold',
          Vacation: 'ag-cell-purple ag-cell-bold',
          Medical: 'ag-cell-purple ag-cell-bold',
        }
        return classes[params.value || ''] || ''
      },
      width: 130,
    },
    {
      headerName: t('grids.columns.clockIn'),
      field: 'clock_in',
      editable: true,
      cellEditor: TimePickerCellEditor || undefined,
      cellEditorPopup: false,
      width: 120,
      valueFormatter: (params: { value?: string }) => params.value || '--:--',
    },
    {
      headerName: t('grids.columns.clockOut'),
      field: 'clock_out',
      editable: true,
      cellEditor: TimePickerCellEditor || undefined,
      cellEditorPopup: false,
      width: 120,
      valueFormatter: (params: { value?: string }) => params.value || '--:--',
    },
    {
      headerName: t('grids.columns.scheduledHours'),
      field: 'scheduled_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      width: 130,
    },
    {
      headerName: t('grids.columns.actualHours'),
      field: 'actual_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      width: 130,
    },
    {
      headerName: t('labor.otNormal'),
      field: 'normal_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      // No placeholder text for a null/unsplit tier — a genuinely empty
      // cell (not "0.00", which would misrepresent an unsplit entry as
      // explicitly zero straight-time hours).
      valueFormatter: (params: { value?: number | null }) =>
        params.value === null || params.value === undefined ? '' : String(params.value),
      width: 110,
    },
    {
      headerName: t('labor.otDouble'),
      field: 'double_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      valueFormatter: (params: { value?: number | null }) =>
        params.value === null || params.value === undefined ? '' : String(params.value),
      width: 110,
    },
    {
      headerName: t('labor.otTriple'),
      field: 'triple_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      valueFormatter: (params: { value?: number | null }) =>
        params.value === null || params.value === undefined ? '' : String(params.value),
      width: 110,
    },
    {
      headerName: t('labor.laborClassOverride'),
      field: 'labor_class_override',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: [null, ...LABOR_CLASS_CODES],
        formatValue: (v: unknown) =>
          v ? t(laborClassLabelKey(String(v))) : t('labor.unclassified'),
      },
      // Resting-value display: EMPTY for null (most rows — override
      // absent, effective class falls back to the employee default) per
      // the no-low-contrast-placeholder rule; only a set override renders
      // text (mirrors useWorkOrderGridData's delay-badge empty-cell
      // pattern for the non-applicable case).
      valueFormatter: (params: { value?: string | null }) =>
        params.value ? t(laborClassLabelKey(params.value)) : '',
      width: 140,
    },
    {
      headerName: t('labor.allocationsTitle'),
      field: 'allocations',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params: { data: AttendanceRow }) =>
        renderAllocationsCell(params, { t, openAllocationDialog }),
      width: 150,
    },
    {
      headerName: t('grids.columns.absenceReason'),
      field: 'absence_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: [
          'Sick Leave',
          'Personal Leave',
          'Family Emergency',
          'Medical Appointment',
          'No Show',
          'Unauthorized',
          'Vacation',
          'Other',
        ],
      },
      width: 180,
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 250,
    },
  ])

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const onGridReady = (params: { api: AGGridApi }): void => {
    setTimeout(() => params.api.sizeColumnsToFit(), 100)
  }

  const loadEmployees = async (): Promise<void> => {
    if (!selectedDate.value || !selectedShift.value) {
      showSnackbar(t('grids.attendance.errors.dateAndShift'), 'warning')
      return
    }

    loading.value = true
    try {
      const response = await api.get('/employees', {
        params: { shift_id: selectedShift.value, active: true },
      })

      const existingAttendance = await api.getAttendanceEntries({
        shift_date: selectedDate.value,
        shift_id: selectedShift.value,
      })

      const existingMap = new Map(
        (existingAttendance.data as AttendanceRow[]).map((a) => [a.employee_id, a]),
      )

      attendanceData.value = (response.data as AttendanceRow[]).map((emp) => {
        const existing = existingMap.get(emp.employee_id)

        if (existing) {
          // Backend returns shift_date as ISO datetime; normalise to YYYY-MM-DD.
          const shiftDate =
            typeof existing.shift_date === 'string'
              ? existing.shift_date.slice(0, 10)
              : existing.shift_date
          // arrival_time/departure_time are ISO datetimes on response; extract HH:MM.
          const arrival = typeof existing.arrival_time === 'string'
            ? (existing.arrival_time as string).slice(11, 16)
            : ''
          const departure = typeof existing.departure_time === 'string'
            ? (existing.departure_time as string).slice(11, 16)
            : ''
          return {
            ...existing,
            shift_date: shiftDate,
            clock_in: arrival,
            clock_out: departure,
            employee_name: emp.employee_name || (emp as { name?: string }).name,
            department: emp.department,
            _isExisting: true,
          }
        }

        return {
          employee_id: emp.employee_id,
          employee_name: emp.employee_name || (emp as { name?: string }).name,
          department: emp.department,
          shift_date: selectedDate.value,
          shift_id: selectedShift.value,
          status: 'Present',
          clock_in: '',
          clock_out: '',
          scheduled_hours: DEFAULT_SCHEDULED_HOURS,
          actual_hours: DEFAULT_SCHEDULED_HOURS,
          absence_reason: '',
          notes: '',
          normal_hours: null,
          double_hours: null,
          triple_hours: null,
          labor_class_override: null,
          allocations: [],
          _hasChanges: false,
          _isNew: true,
        }
      })

      showSnackbar(
        t('grids.attendance.loadedEmployees', { count: attendanceData.value.length }),
        'success',
      )
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading employees:', error)
      const ax = error as { message?: string }
      showSnackbar('Error loading employees: ' + (ax?.message || ''), 'error')
    } finally {
      loading.value = false
    }
  }

  const markRowAsChanged = (event: {
    data: AttendanceRow
    colDef: { field: string }
  }): void => {
    // event.data is not reliably the same object attendanceData.value
    // tracks (see findTrackedRow's declaration comment) — merge AG
    // Grid's current field values onto the actual tracked row so the
    // mutation is visible to attendanceData.value's dependents. Object.assign
    // (not replacing the array element) preserves the tracked row's
    // identity for anything else already holding a reference to it
    // (e.g. an open allocation dialog).
    const target = findTrackedRow(event.data) ?? event.data
    Object.assign(target, event.data)
    target._hasChanges = true

    if (event.colDef.field === 'clock_in' && target.clock_in) {
      target.status = 'Late'
    }

    // Dirty-signal read by hasChanges/changedRowsCount/noSplitCount/
    // unallocatedCount/statusCounts — belt-and-suspenders alongside the
    // identity-resolved mutation above (also covers the fallback path
    // where no tracked row was found).
    editTick.value++

    gridRef.value?.refreshCells?.()
  }

  const bulkSetStatus = (): void => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    gridApi.forEachNode((node) => {
      node.data.status = 'Present'
      node.data._hasChanges = true
    })

    gridApi.refreshCells()
    showSnackbar(t('grids.attendance.markedPresent'), 'success')
  }

  const buildPayload = (
    row: AttendanceRow,
    clientId: string | number,
  ): Record<string, unknown> => {
    const translated = translateStatus(row.status)
    const scheduledHours = row.scheduled_hours ?? DEFAULT_SCHEDULED_HOURS
    const actualHours =
      row.actual_hours !== undefined && row.actual_hours !== null
        ? row.actual_hours
        : scheduledHours * translated.actualHoursFactor
    const absenceHours = translated.is_absent ? Math.max(0, scheduledHours - actualHours) : 0

    return {
      client_id: String(clientId),
      employee_id: Number(row.employee_id),
      shift_date: row.shift_date || selectedDate.value,
      shift_id: row.shift_id ? Number(row.shift_id) : undefined,
      scheduled_hours: scheduledHours,
      actual_hours: actualHours,
      absence_hours: absenceHours,
      is_absent: translated.is_absent,
      absence_type: translated.absence_type || undefined,
      arrival_time: combineDateTime(row.shift_date || selectedDate.value, row.clock_in),
      departure_time: combineDateTime(row.shift_date || selectedDate.value, row.clock_out),
      is_late: translated.is_late,
      absence_reason: row.absence_reason || undefined,
      notes: row.notes || undefined,
      // Labor-hours capture (Cycle 3 PR-A, Task 7) — all-null tiers = unsplit
      // (backend no-ops); explicit null override = use employee default;
      // allocations always carries the row's current ledger so a save that
      // doesn't touch allocations resends (not clears) what's already there.
      normal_hours: row.normal_hours ?? null,
      double_hours: row.double_hours ?? null,
      triple_hours: row.triple_hours ?? null,
      labor_class_override: row.labor_class_override ?? null,
      allocations: (row.allocations || []).map((a) => ({ category: a.category, hours: a.hours })),
    }
  }

  const saveAttendance = async (): Promise<void> => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const changedRows: AttendanceRow[] = []
    gridApi.forEachNode((node) => {
      if (node.data._hasChanges) changedRows.push(node.data)
    })

    if (changedRows.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    if (!activeClientId()) {
      showSnackbar(t('grids.attendance.errors.noClient'), 'error')
      return
    }

    pendingRows.value = changedRows
    pendingData.value = changedRows[0]
    showConfirmDialog.value = true
  }

  const onConfirmSave = async (): Promise<void> => {
    showConfirmDialog.value = false
    saving.value = true

    let successCount = 0
    let errorCount = 0

    const clientId = activeClientId()
    if (!clientId) {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
      showSnackbar(t('grids.attendance.errors.noClient'), 'error')
      return
    }

    try {
      for (const row of pendingRows.value) {
        const data = buildPayload(row, clientId)

        try {
          if (row._isNew && !row._isExisting) {
            await api.createAttendanceEntry(data)
            successCount++
          } else if (row.attendance_entry_id) {
            await api.updateAttendanceEntry(row.attendance_entry_id, data)
            successCount++
          } else {
            await api.createAttendanceEntry(data)
            successCount++
          }

          row._hasChanges = false
          row._isNew = false
        } catch (err) {
          errorCount++
          // eslint-disable-next-line no-console
          console.error('Error saving attendance for employee:', row.employee_id, err)
        }
      }

      if (errorCount === 0) {
        showSnackbar(
          t('grids.attendance.savedRecords', { success: successCount }),
          'success',
        )
        attendanceData.value = []
      } else {
        showSnackbar(
          t('grids.attendance.savedWithErrors', {
            success: successCount,
            failed: errorCount,
          }),
          'warning',
        )
      }
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar('Error saving attendance: ' + (ax?.message || ''), 'error')
    } finally {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
    }
  }

  const onCancelSave = (): void => {
    showConfirmDialog.value = false
    pendingRows.value = []
    pendingData.value = {}
    showSnackbar(t('grids.saveCancelled'), 'info')
  }

  const onRowsPasted = (pasteData: PasteData): void => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd: Partial<AttendanceRow>[]): void => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const preparedRows: AttendanceRow[] = rowsToAdd.map((row) => ({
      attendance_entry_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      employee_id: row.employee_id || '',
      employee_name: row.employee_name || '',
      department: row.department || '',
      shift_date: row.shift_date || selectedDate.value,
      shift_id: row.shift_id || selectedShift.value,
      status: row.status || 'Present',
      clock_in: row.clock_in || '',
      clock_out: row.clock_out || '',
      scheduled_hours: row.scheduled_hours ?? DEFAULT_SCHEDULED_HOURS,
      actual_hours: row.actual_hours ?? DEFAULT_SCHEDULED_HOURS,
      absence_reason: row.absence_reason || '',
      notes: row.notes || '',
      // Labor-hours capture (Cycle 3 PR-A, Task 7 fix round 1) — carry
      // the OT split + override through from the pasted row instead of
      // dropping them. No client-side split-sum validation here (matches
      // this whitelist's existing pattern of not cross-validating other
      // fields on paste); an invalid split surfaces as a 422 on save,
      // same per-row idiom as every other paste-then-save path.
      normal_hours: row.normal_hours ?? null,
      double_hours: row.double_hours ?? null,
      triple_hours: row.triple_hours ?? null,
      labor_class_override: row.labor_class_override ?? null,
      _hasChanges: true,
      _isNew: true,
    }))

    gridApi.applyTransaction({ add: preparedRows, addIndex: 0 })
    showPasteDialog.value = false
    showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
  }

  const onPasteCancel = (): void => {
    showPasteDialog.value = false
    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  onMounted(async () => {
    try {
      const response = await api.getShifts()
      shifts.value = response.data
      if (shifts.value.length > 0) {
        selectedShift.value = shifts.value[0].shift_id
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading shifts:', error)
      showSnackbar(t('grids.attendance.errors.loadShifts'), 'error')
    }
  })

  return {
    gridRef,
    selectedDate,
    selectedShift,
    selectedLine,
    shifts,
    attendanceData,
    loading,
    saving,
    snackbar,
    showConfirmDialog,
    pendingData,
    pendingRowsCount,
    confirmationFieldConfig,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    hasChanges,
    changedRowsCount,
    statusCounts,
    showAllocationDialog,
    allocationDialogRow,
    openAllocationDialog,
    onAllocationsSaved,
    noSplitCount,
    unallocatedCount,
    columnDefs,
    onGridReady,
    loadEmployees,
    markRowAsChanged,
    bulkSetStatus,
    saveAttendance,
    onConfirmSave,
    onCancelSave,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel,
  }
}
