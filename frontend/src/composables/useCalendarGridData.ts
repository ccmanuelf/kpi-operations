/**
 * Composable for CalendarGrid script logic — column definitions,
 * monthly auto-generation, and store-bound CRUD wrappers.
 *
 * Backend alignment: column field names match
 * backend/routes/capacity/_models.py CalendarEntryCreate
 * (calendar_date, is_working_day, shifts_available, shift1_hours,
 * shift2_hours, shift3_hours, holiday_name, notes). Persistence is
 * centralised via `useCapacityPlanningStore.saveWorksheet('masterCalendar')`.
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface CalendarRow {
  _id?: number | string
  _isNew?: boolean
  calendar_date?: string
  is_working_day?: boolean
  shifts_available?: number
  shift1_hours?: number
  shift2_hours?: number
  shift3_hours?: number
  holiday_name?: string | null
  notes?: string | null
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean | ((params: { data: CalendarRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: number[]; min?: number; max?: number; precision?: number }
  cellRenderer?: (params: { data: CalendarRow; rowIndex: number }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

interface UseCalendarGridDataReturn {
  calendar: ComputedRef<CalendarRow[]>
  hasChanges: ComputedRef<boolean>
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeRow: (index: number) => void
  onCellValueChanged: () => void
  generateMonth: (year: number, month: number) => CalendarRow[]
  importGeneratedMonth: (year: number, month: number) => void
}

export default function useCalendarGridData(): UseCalendarGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const calendar = computed<CalendarRow[]>(
    () => (store.worksheets.masterCalendar.data as CalendarRow[]) || [],
  )

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.masterCalendar.dirty),
  )

  const addRow = (): void => {
    store.addRow('masterCalendar')
  }

  const removeRow = (index: number): void => {
    store.removeRow('masterCalendar', index)
  }

  const onCellValueChanged = (): void => {
    store.worksheets.masterCalendar.dirty = true
  }

  // Generate calendar entries for a given (year, month). Weekends are
  // marked as non-working days with 0 shift hours; weekdays default to a
  // single 8-hour shift. Returns the generated rows; does NOT mutate the store.
  const generateMonth = (year: number, month: number): CalendarRow[] => {
    const daysInMonth = new Date(year, month, 0).getDate()
    const entries: CalendarRow[] = []
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month - 1, day)
      const dayOfWeek = date.getDay()
      const isWeekend = dayOfWeek === 0 || dayOfWeek === 6
      entries.push({
        calendar_date: date.toISOString().slice(0, 10),
        is_working_day: !isWeekend,
        shifts_available: 1,
        shift1_hours: isWeekend ? 0 : 8.0,
        shift2_hours: 0,
        shift3_hours: 0,
        holiday_name: null,
        notes: null,
      })
    }
    return entries
  }

  const importGeneratedMonth = (year: number, month: number): void => {
    const entries = generateMonth(year, month)
    store.importData('masterCalendar', entries)
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanning.calendar.headers.date'),
      field: 'calendar_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      pinned: 'left',
      width: 140,
    },
    {
      headerName: t('capacityPlanning.calendar.headers.workingDay'),
      field: 'is_working_day',
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: (params) =>
        renderCheckmark(Boolean((params.data as CalendarRow).is_working_day)),
      width: 110,
    },
    {
      headerName: t('capacityPlanning.calendar.headers.shifts'),
      field: 'shifts_available',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: [1, 2, 3] },
      width: 90,
    },
    {
      headerName: t('capacityPlanning.calendar.headers.shift1Hours'),
      field: 'shift1_hours',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.calendar.headers.shift2Hours'),
      field: 'shift2_hours',
      // shift2 only editable when shifts_available >= 2 (matches the
      // legacy v-data-table's :disabled binding).
      editable: (params) =>
        Number((params.data as CalendarRow).shifts_available || 0) >= 2,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.calendar.headers.holiday'),
      field: 'holiday_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 160,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) => renderDeleteAction(params, removeRow),
      width: 90,
      pinned: 'right',
    },
  ])

  return {
    calendar,
    hasChanges,
    columnDefs,
    addRow,
    removeRow,
    onCellValueChanged,
    generateMonth,
    importGeneratedMonth,
  }
}

const renderCheckmark = (value: boolean): HTMLElement => {
  const span = document.createElement('span')
  span.textContent = value ? '\u2713' : ''
  span.style.color = value ? 'var(--cds-support-success, #198038)' : 'inherit'
  return span
}

const renderDeleteAction = (
  params: { data: CalendarRow; rowIndex: number },
  remove: (i: number) => void,
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  div.innerHTML = `
    <button class="ag-grid-delete-btn" title="Delete" style="
      background: #c62828;
      color: white;
      border: none;
      padding: 2px 6px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    ">✕</button>
  `
  div
    .querySelector('.ag-grid-delete-btn')
    ?.addEventListener('click', () => remove(params.rowIndex))
  return div
}
