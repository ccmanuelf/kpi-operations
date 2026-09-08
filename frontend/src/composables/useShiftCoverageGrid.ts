/**
 * Shift-coverage data entry: required versus actual headcount per shift-day.
 *
 * The write paths this drives were reachable only by API until now. Two things
 * about them shape this file:
 *
 * 1. **The write tier SPLITS.** POST and PUT sit on `get_current_contributor`
 *    (everyone but viewer); DELETE sits on `get_current_active_supervisor`
 *    (everyone but viewer AND operator). Gating both on one flag either hides
 *    an edit an operator may legitimately make or offers them a delete the
 *    server answers with 403. Pinned server-side by
 *    test_coverage_edit_is_contributor_but_delete_is_supervisory.
 * 2. **`coverage_percentage` is DERIVED.** The server recomputes it from
 *    required and actual on every write and clamps it to the column ceiling,
 *    so an editable percentage column would accept a number the next read
 *    silently replaces. It is read-only here for that reason, not for tidiness.
 */
import { computed, ref, type ComputedRef } from 'vue'

import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'

export interface CoverageRow {
  coverage_id: number
  client_id: string
  shift_id: number
  coverage_date: string
  required_employees: number
  actual_employees: number
  coverage_percentage: number
  notes?: string | null
  entered_by?: string
}

export interface CoverageColumnSpec {
  field: string
  /** i18n key; the component resolves it. */
  headerKey: string
  editable: boolean
  width?: number
  minWidth?: number
  flex?: number
  pinned?: 'left' | 'right'
  editor?: 'number' | 'text'
  editorParams?: Record<string, number>
  format?: 'shift' | 'percent'
  shortfallBelow?: number
}

export interface ClientOption {
  client_id: string | number
  client_name: string
}

export interface ShiftOption {
  shift_id: number
  client_id: string
  shift_name: string
}

/** Presets rather than a bare pair of date pickers.
 *
 * A shift-coverage story plays out over months -- the seeded labour disruption
 * runs about sixty days -- and a reader who has to discover that by widening
 * two date fields by hand will not discover it at all. 90 days is the default
 * because it is long enough to show a trend and short enough to stay a
 * data-entry screen; 180 reaches a full episode.
 */
export const RANGE_PRESETS = [30, 90, 180] as const
export const DEFAULT_RANGE_DAYS = 90

/** Below this, a shift ran short-handed. Matches the OOC treatment the KPI
 * cards use, so "red" means the same thing on both screens. */
export const SHORTFALL_THRESHOLD = 90

/**
 * The LOCAL calendar date, not the UTC one.
 *
 * `toISOString()` converts to UTC first, so west of Greenwich a late-evening
 * "today" becomes tomorrow's date and east of it an early-morning "today"
 * becomes yesterday's. A shift-coverage screen whose default range is off by a
 * day either hides the most recent shift or asks for one that has not happened.
 */
const localISO = (d: Date): string => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const isoDaysAgo = (days: number, from: Date): string => {
  const d = new Date(from)
  d.setDate(d.getDate() - days)
  return localISO(d)
}

/**
 * Deliberately free of `useI18n`, like useAssumptionRegistry: a composable that
 * resolves translations needs a Vue app context to be exercised at all, which
 * puts the logic worth testing behind component setup. Column headers are
 * emitted as KEYS and errors as a key plus the server's own detail; the
 * component does the translating.
 */
export interface CoverageError {
  /** i18n key for the fallback wording. */
  key: string
  /** The server's own message, which names WHICH record collided. Preferred
   * over the key whenever present -- it is more specific than anything the
   * client can compose. */
  detail?: string
}

export function useShiftCoverageGrid() {
  const auth = useAuthStore()

  const clients = ref<ClientOption[]>([])
  const shifts = ref<ShiftOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const rows = ref<CoverageRow[]>([])

  const today = new Date()
  const endDate = ref<string>(localISO(today))
  const startDate = ref<string>(isoDaysAgo(DEFAULT_RANGE_DAYS, today))

  const loading = ref(false)
  const loaded = ref(false)
  const saving = ref(false)
  /** Set when a write committed but the follow-up read failed: the row is in
   * the database and NOT on screen, which is not the same as the write
   * failing and must not be reported as if it were. */
  const staleAfterWrite = ref(false)
  const error = ref<CoverageError | null>(null)

  /**
   * POST/PUT are contributor-tier; DELETE is supervisory. These are two
   * different questions and are deliberately two different flags.
   */
  const canEdit = computed<boolean>(() => auth.isContributorTier)
  const canDelete = computed<boolean>(() => auth.isSupervisoryTier)

  const shiftName = (shiftId: number): string =>
    shifts.value.find((s) => s.shift_id === shiftId)?.shift_name ?? String(shiftId)

  /** Shift-days that ran below the threshold — the screen's call to action. */
  /**
   * Only the selected client's shifts may be offered.
   *
   * `getShifts()` returns every shift the caller can see, which for an admin
   * is all four demo clients. Offering another tenant's shift produces a row
   * the server refuses with 400 ("belongs to a different client") -- the
   * cross-tenant guard added in #287 catches it, but a dropdown whose options
   * are known-invalid is the same "offers an action that fails" defect this
   * screen exists to remove, just moved one layer up.
   */
  const shiftsForClient = computed<ShiftOption[]>(() =>
    selectedClient.value == null
      ? []
      : shifts.value.filter((s) => String(s.client_id) === String(selectedClient.value)),
  )

  const shortfalls = computed<CoverageRow[]>(() =>
    rows.value.filter((r) => Number(r.coverage_percentage) < SHORTFALL_THRESHOLD),
  )

  const averageCoverage = computed<number | null>(() => {
    if (!rows.value.length) return null
    const total = rows.value.reduce((sum, r) => sum + Number(r.coverage_percentage || 0), 0)
    return Math.round((total / rows.value.length) * 10) / 10
  })

  const applyRange = (days: number): void => {
    const now = new Date()
    endDate.value = localISO(now)
    startDate.value = isoDaysAgo(days, now)
  }

  const loadClients = async (): Promise<void> => {
    const res = await api.getClients()
    clients.value = (res.data as ClientOption[]) || []
  }

  const loadShifts = async (): Promise<void> => {
    const res = await api.getShifts()
    shifts.value = (res.data as ShiftOption[]) || []
  }

  //: Identifies the most recent read. Comparing the CLIENT is not enough:
  //: switching A -> B -> A lets the first request match again on arrival and
  //: overwrite the third request's newer rows with its own older ones.
  let readToken = 0

  /**
   * Returns TRUE only when this read applied its data. A superseded read
   * returns false rather than throwing, and a read with no client selected
   * never runs -- so a caller cannot infer "the screen reflects my write"
   * from the mere absence of an exception.
   */
  const load = async (): Promise<boolean> => {
    if (!selectedClient.value) {
      // Bump the token here too, or clearing the selection fails to supersede
      // a read already in flight and it repopulates the table for a client
      // that is no longer selected.
      readToken += 1
      rows.value = []
      loaded.value = false
      loading.value = false
      return false
    }
    const token = ++readToken
    const requestedFor = String(selectedClient.value)
    loading.value = true
    error.value = null
    try {
      const { data } = await api.getShiftCoverage({
        client_id: requestedFor,
        start_date: startDate.value,
        end_date: endDate.value,
      })
      if (token !== readToken) return false
      rows.value = (data as CoverageRow[]) ?? []
      loaded.value = true
      // A successful read is the freshest state there is, so an earlier
      // "could not refresh" warning no longer describes what is on screen.
      staleAfterWrite.value = false
      return true
    } catch (err) {
      // A superseded failure must not clear the newer rows either, and must
      // not be reported to this read's caller as ITS failure.
      if (token !== readToken) return false
      rows.value = []
      loaded.value = false
      error.value = errorFor(err)
      throw err
    } finally {
      if (token === readToken) loading.value = false
    }
  }

  /**
   * Re-read after a committed write.
   *
   * A write that succeeded followed by a read that did not is NOT a failed
   * write, and saying so sends the operator back to re-enter a record that
   * already exists — which the server then refuses as a duplicate. The banner
   * says the list is stale instead.
   */
  const refreshAfterWrite = async (): Promise<void> => {
    try {
      const applied = await load()
      staleAfterWrite.value = !applied
    } catch {
      staleAfterWrite.value = true
    }
  }

  const errorFor = (err: unknown): CoverageError => {
    const res = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response
    const detail = res?.data?.detail
    const key =
      res?.status === 409
        ? 'coverage.errors.duplicate'
        : res?.status === 403
          ? 'coverage.errors.forbidden'
          : 'coverage.errors.generic'
    return typeof detail === 'string' && detail ? { key, detail } : { key }
  }

  /**
   * `forClient` is passed in rather than read from `selectedClient` here: the
   * dialog captures it when it opens, so a selection that changes while the
   * form is filled in or while the POST is in flight cannot file the row under
   * a tenant the operator was not looking at.
   */
  const create = async (payload: Partial<CoverageRow>, forClient?: string): Promise<boolean> => {
    const clientId = forClient ?? String(selectedClient.value)
    saving.value = true
    error.value = null
    try {
      await api.createShiftCoverage({
        client_id: clientId,
        shift_id: payload.shift_id,
        coverage_date: payload.coverage_date,
        required_employees: payload.required_employees,
        actual_employees: payload.actual_employees,
        notes: payload.notes ?? null,
      })
    } catch (err) {
      error.value = errorFor(err)
      return false
    } finally {
      saving.value = false
    }
    await refreshAfterWrite()
    return true
  }

  /**
   * Only the three fields the API accepts on update. `ShiftCoverageUpdate`
   * exposes required_employees, actual_employees and notes and nothing else --
   * a row cannot be moved to another client, shift or date, which is what
   * keeps the create-time ownership check from being routed around.
   */
  const update = async (row: CoverageRow, changes: Partial<CoverageRow>): Promise<boolean> => {
    saving.value = true
    error.value = null
    try {
      await api.updateShiftCoverage(row.coverage_id, {
        required_employees: changes.required_employees ?? row.required_employees,
        actual_employees: changes.actual_employees ?? row.actual_employees,
        notes: changes.notes ?? row.notes ?? null,
      })
    } catch (err) {
      error.value = errorFor(err)
      // Re-read on FAILURE too. This is called from an inline grid edit, and
      // AG Grid has already written the new value into its own row model by
      // the time the request goes out -- so a rejected edit otherwise leaves
      // the cell showing a number the server refused, beside an error message
      // saying it was refused. The grid must end up showing what was stored.
      await refreshAfterWrite()
      return false
    } finally {
      saving.value = false
    }
    await refreshAfterWrite()
    return true
  }

  const remove = async (row: CoverageRow): Promise<boolean> => {
    saving.value = true
    error.value = null
    try {
      await api.deleteShiftCoverage(row.coverage_id)
    } catch (err) {
      error.value = errorFor(err)
      return false
    } finally {
      saving.value = false
    }
    await refreshAfterWrite()
    return true
  }

  /**
   * Column SPECS, not finished AG Grid defs: `headerKey` is an i18n key the
   * component resolves. What matters here and is therefore tested here is
   * which columns are editable and for whom.
   */
  const columnSpecs: ComputedRef<CoverageColumnSpec[]> = computed(() => [
    { field: 'coverage_date', headerKey: 'coverage.headers.date', width: 130, pinned: 'left', editable: false },
    { field: 'shift_id', headerKey: 'coverage.headers.shift', width: 130, editable: false, format: 'shift' },
    {
      field: 'required_employees',
      headerKey: 'coverage.headers.required',
      width: 120,
      editable: canEdit.value,
      editor: 'number',
      editorParams: { min: 1, precision: 0 },
    },
    {
      field: 'actual_employees',
      headerKey: 'coverage.headers.actual',
      width: 120,
      editable: canEdit.value,
      editor: 'number',
      editorParams: { min: 0, precision: 0 },
    },
    {
      // Derived server-side and clamped there. An editable column would take a
      // number the very next read replaces, which reads as the app losing the
      // operator's input.
      field: 'coverage_percentage',
      headerKey: 'coverage.headers.coverage',
      width: 130,
      editable: false,
      format: 'percent',
      shortfallBelow: SHORTFALL_THRESHOLD,
    },
    {
      field: 'notes',
      headerKey: 'coverage.headers.notes',
      flex: 1,
      minWidth: 160,
      editable: canEdit.value,
      editor: 'text',
    },
  ])

  return {
    clients,
    shifts,
    shiftsForClient,
    selectedClient,
    rows,
    startDate,
    endDate,
    loading,
    loaded,
    saving,
    staleAfterWrite,
    error,
    canEdit,
    canDelete,
    shortfalls,
    averageCoverage,
    columnSpecs,
    shiftName,
    applyRange,
    loadClients,
    loadShifts,
    load,
    create,
    update,
    remove,
  }
}

export default useShiftCoverageGrid
