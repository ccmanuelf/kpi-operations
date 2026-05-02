/**
 * @vitest-environment happy-dom
 *
 * Unit tests for useScenariosGridData composable —
 * Group H Surface #20 (ScenariosPanel).
 *
 * Verifies column shape, scenario_type catalogue alignment with backend,
 * default-parameters per type, addRow defaults, type-switch resets
 * parameters to type defaults, parameters JSON valueSetter parses input,
 * existing rows are non-editable (no backend PUT), saveRow calls the
 * provided onSaveNewRow handler, runRow only fires for DRAFT rows, and
 * delete triggers onConfirmDelete.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

import useScenariosGridData, {
  SCENARIO_TYPE_OPTIONS,
  DEFAULT_PARAMETERS,
  type ScenarioRow,
} from '../useScenariosGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((params: { data: ScenarioRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: unknown[] }
  valueGetter?: (params: { data: ScenarioRow }) => unknown
  valueFormatter?: (params: { value?: unknown; data?: ScenarioRow }) => string
  valueSetter?: (params: { data: ScenarioRow; newValue: unknown }) => boolean
  pinned?: 'left' | 'right'
  width?: number
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const buildHarness = () => {
  const scenarios = ref<ScenarioRow[]>([])
  const notify = { showSuccess: vi.fn(), showError: vi.fn() }
  const onSaveNewRow = vi.fn().mockResolvedValue(undefined)
  const onRunRow = vi.fn().mockResolvedValue(undefined)
  const onConfirmDelete = vi.fn()

  const grid = useScenariosGridData({
    scenarios,
    notify,
    onSaveNewRow,
    onRunRow,
    onConfirmDelete,
  })

  return { ...grid, scenarios, notify, onSaveNewRow, onRunRow, onConfirmDelete }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('catalogs', () => {
  it('SCENARIO_TYPE_OPTIONS mirrors backend ScenarioCreate.scenario_type catalogue', () => {
    expect(SCENARIO_TYPE_OPTIONS).toEqual([
      'OVERTIME',
      'SETUP_REDUCTION',
      'SUBCONTRACT',
      'NEW_LINE',
      'THREE_SHIFT',
      'LEAD_TIME_DELAY',
      'ABSENTEEISM_SPIKE',
      'MULTI_CONSTRAINT',
    ])
  })

  it('DEFAULT_PARAMETERS covers every scenario type', () => {
    SCENARIO_TYPE_OPTIONS.forEach((type) => {
      expect(DEFAULT_PARAMETERS[type]).toBeDefined()
      expect(typeof DEFAULT_PARAMETERS[type]).toBe('object')
    })
  })

  it('OVERTIME default is overtime_percent: 20 (matches legacy hint)', () => {
    expect(DEFAULT_PARAMETERS.OVERTIME).toEqual({ overtime_percent: 20 })
  })

  it('SUBCONTRACT default includes department: CUTTING', () => {
    expect(DEFAULT_PARAMETERS.SUBCONTRACT).toEqual({
      subcontract_percent: 40,
      department: 'CUTTING',
    })
  })
})

describe('column definitions', () => {
  it('checkbox selection column is hidden for new rows', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, '_select') as
      | { checkboxSelection?: (p: { data: ScenarioRow }) => boolean }
      | undefined
    expect(col).toBeDefined()
    expect(col!.checkboxSelection!({ data: { _isNew: true } })).toBe(false)
    expect(col!.checkboxSelection!({ data: { _isNew: false } })).toBe(true)
  })

  it('scenario_name is editable only on new rows', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'scenario_name')
    expect(col).toBeDefined()
    expect(typeof col!.editable).toBe('function')
    expect((col!.editable as (p: { data: ScenarioRow }) => boolean)({ data: { _isNew: true } })).toBe(true)
    expect((col!.editable as (p: { data: ScenarioRow }) => boolean)({ data: { _isNew: false } })).toBe(false)
  })

  it('scenario_type uses agSelectCellEditor with backend catalogue', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'scenario_type')
    expect(col!.cellEditor).toBe('agSelectCellEditor')
    expect(col!.cellEditorParams!.values).toEqual(SCENARIO_TYPE_OPTIONS)
  })

  it('scenario_type valueSetter rejects unknown types', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'scenario_type')!
    const row: ScenarioRow = { _isNew: true, scenario_type: 'OVERTIME' }
    expect(col.valueSetter!({ data: row, newValue: 'BOGUS' })).toBe(false)
    expect(row.scenario_type).toBe('OVERTIME')
  })

  it('scenario_type valueSetter resets parameters to the new type defaults', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'scenario_type')!
    const row: ScenarioRow = {
      _isNew: true,
      scenario_type: 'OVERTIME',
      parameters: { overtime_percent: 50 },
    }
    expect(col.valueSetter!({ data: row, newValue: 'SUBCONTRACT' })).toBe(true)
    expect(row.scenario_type).toBe('SUBCONTRACT')
    expect(row.parameters).toEqual(DEFAULT_PARAMETERS.SUBCONTRACT)
  })

  it('scenario_type valueSetter refuses to mutate existing rows', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'scenario_type')!
    const row: ScenarioRow = {
      _isNew: false,
      scenario_type: 'OVERTIME',
      parameters: { overtime_percent: 20 },
    }
    expect(col.valueSetter!({ data: row, newValue: 'NEW_LINE' })).toBe(false)
    expect(row.scenario_type).toBe('OVERTIME')
    expect(row.parameters).toEqual({ overtime_percent: 20 })
  })

  it('parameters cell uses popup large-text editor', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters') as
      | { cellEditor?: string; cellEditorPopup?: boolean }
      | undefined
    expect(col!.cellEditor).toBe('agLargeTextCellEditor')
    expect(col!.cellEditorPopup).toBe(true)
  })

  it('parameters valueGetter returns JSON string', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    expect(
      col.valueGetter!({ data: { parameters: { overtime_percent: 25 } } as ScenarioRow }),
    ).toBe('{"overtime_percent":25}')
  })

  it('parameters valueFormatter renders compact key=value pairs', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    const formatted = col.valueFormatter!({
      value: '{"overtime_percent":25,"shift":"A"}',
      data: { parameters: { overtime_percent: 25, shift: 'A' } } as ScenarioRow,
    })
    expect(formatted).toBe('overtime_percent=25, shift=A')
  })

  it('parameters valueFormatter renders -- when empty', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    expect(
      col.valueFormatter!({ value: '{}', data: { parameters: {} } as ScenarioRow }),
    ).toBe('--')
  })

  it('parameters valueSetter parses valid JSON for new rows', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    const row: ScenarioRow = { _isNew: true, parameters: {} }
    expect(
      col.valueSetter!({
        data: row,
        newValue: '{"overtime_percent": 30}',
      }),
    ).toBe(true)
    expect(row.parameters).toEqual({ overtime_percent: 30 })
  })

  it('parameters valueSetter rejects malformed JSON', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    const row: ScenarioRow = { _isNew: true, parameters: { overtime_percent: 20 } }
    expect(
      col.valueSetter!({ data: row, newValue: '{not json' }),
    ).toBe(false)
    expect(row.parameters).toEqual({ overtime_percent: 20 })
  })

  it('parameters valueSetter rejects arrays (must be object)', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    const row: ScenarioRow = { _isNew: true, parameters: {} }
    expect(col.valueSetter!({ data: row, newValue: '[1,2,3]' })).toBe(false)
  })

  it('parameters valueSetter accepts empty input as empty object', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    const row: ScenarioRow = { _isNew: true, parameters: { x: 1 } }
    expect(col.valueSetter!({ data: row, newValue: '   ' })).toBe(true)
    expect(row.parameters).toEqual({})
  })

  it('parameters valueSetter refuses to mutate existing rows', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'parameters')!
    const row: ScenarioRow = { _isNew: false, parameters: { a: 1 } }
    expect(col.valueSetter!({ data: row, newValue: '{"b":2}' })).toBe(false)
    expect(row.parameters).toEqual({ a: 1 })
  })

  it('status column is read-only', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'status')
    expect(col!.editable).toBe(false)
  })

  it('result columns (total_output, avg_utilization, on_time_rate) are read-only with formatters', () => {
    const { columnDefs } = buildHarness()
    const total = findCol(columnDefs.value, '_total_output')!
    const util = findCol(columnDefs.value, '_avg_utilization')!
    const otr = findCol(columnDefs.value, '_on_time_rate')!

    expect(total.editable).toBe(false)
    expect(util.editable).toBe(false)
    expect(otr.editable).toBe(false)

    const sample: ScenarioRow = {
      results: { total_output: 12345, avg_utilization: 87.6, on_time_rate: 94.2 },
    }
    expect(total.valueGetter!({ data: sample })).toBe(12345)
    expect(total.valueFormatter!({ value: 12345 })).toBe('12,345')
    expect(util.valueFormatter!({ value: 87.6 })).toBe('87.6%')
    expect(otr.valueFormatter!({ value: 94.2 })).toBe('94.2%')
  })

  it('result columns fall back to results_json when results is absent', () => {
    const { columnDefs } = buildHarness()
    const total = findCol(columnDefs.value, '_total_output')!
    const sample: ScenarioRow = {
      results_json: { total_output: 999 } as Record<string, unknown>,
    }
    expect(total.valueGetter!({ data: sample })).toBe(999)
  })

  it('result columns render -- for missing values', () => {
    const { columnDefs } = buildHarness()
    const total = findCol(columnDefs.value, '_total_output')!
    expect(total.valueFormatter!({ value: undefined })).toBe('--')
    expect(total.valueFormatter!({ value: null })).toBe('--')
  })

  it('actions column is pinned right and non-editable', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, '_actions')!
    expect(col.pinned).toBe('right')
    expect(col.editable).toBe(false)
  })
})

describe('addRow', () => {
  it('prepends a draft row with OVERTIME defaults', () => {
    const { addRow, scenarios } = buildHarness()
    addRow()
    expect(scenarios.value.length).toBe(1)
    const row = scenarios.value[0]
    expect(row._isNew).toBe(true)
    expect(row.scenario_type).toBe('OVERTIME')
    expect(row.scenario_name).toBe('')
    expect(row.parameters).toEqual({ overtime_percent: 20 })
    expect(row.status).toBe('DRAFT')
  })

  it('keeps existing rows in place when adding', () => {
    const { addRow, scenarios } = buildHarness()
    scenarios.value = [{ id: 1, scenario_name: 'old', status: 'EVALUATED' } as ScenarioRow]
    addRow()
    expect(scenarios.value.length).toBe(2)
    expect((scenarios.value[1] as { id?: number }).id).toBe(1)
  })
})

describe('removeNewRow', () => {
  it('removes only the matching draft row', () => {
    const { addRow, removeNewRow, scenarios } = buildHarness()
    addRow()
    addRow()
    const target = scenarios.value[0]
    removeNewRow(target)
    expect(scenarios.value.length).toBe(1)
    expect(scenarios.value).not.toContain(target)
  })
})

describe('row actions (via cell renderer)', () => {
  // The action buttons live inside the cell renderer; we verify the
  // renderer wires up the right callbacks by simulating button clicks
  // on the rendered HTMLElement.
  const renderActions = (row: ScenarioRow, harness: ReturnType<typeof buildHarness>) => {
    const col = findCol(harness.columnDefs.value, '_actions') as
      | { cellRenderer?: (p: { data: ScenarioRow; rowIndex: number }) => HTMLElement }
      | undefined
    return col!.cellRenderer!({ data: row, rowIndex: 0 })
  }

  it('new-row cancel button discards via removeNewRow', () => {
    const harness = buildHarness()
    harness.addRow()
    const row = harness.scenarios.value[0]
    const el = renderActions(row, harness)
    ;(el.querySelector('.ag-grid-cancel-btn') as HTMLButtonElement)?.click()
    expect(harness.scenarios.value).not.toContain(row)
  })

  it('new-row save button calls onSaveNewRow when required fields present', async () => {
    const harness = buildHarness()
    harness.addRow()
    const row = harness.scenarios.value[0]
    row.scenario_name = 'OT Test'
    const el = renderActions(row, harness)
    ;(el.querySelector('.ag-grid-save-btn') as HTMLButtonElement)?.click()
    await Promise.resolve()
    await Promise.resolve()
    expect(harness.onSaveNewRow).toHaveBeenCalledWith(row)
  })

  it('new-row save button blocks when scenario_name is empty', async () => {
    const harness = buildHarness()
    harness.addRow()
    const row = harness.scenarios.value[0]
    const el = renderActions(row, harness)
    ;(el.querySelector('.ag-grid-save-btn') as HTMLButtonElement)?.click()
    await Promise.resolve()
    expect(harness.onSaveNewRow).not.toHaveBeenCalled()
    expect(harness.notify.showError).toHaveBeenCalled()
  })

  it('existing-row Run button is enabled only for DRAFT', () => {
    const harness = buildHarness()
    const row: ScenarioRow = {
      id: 1,
      scenario_name: 'A',
      scenario_type: 'OVERTIME',
      status: 'EVALUATED',
    }
    const el = renderActions(row, harness)
    const btn = el.querySelector('.ag-grid-run-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('existing-row Run button calls onRunRow when DRAFT', async () => {
    const harness = buildHarness()
    const row: ScenarioRow = {
      id: 1,
      scenario_name: 'A',
      scenario_type: 'OVERTIME',
      status: 'DRAFT',
    }
    const el = renderActions(row, harness)
    ;(el.querySelector('.ag-grid-run-btn') as HTMLButtonElement)?.click()
    await Promise.resolve()
    await Promise.resolve()
    expect(harness.onRunRow).toHaveBeenCalledWith(row)
  })

  it('existing-row Delete button calls onConfirmDelete', () => {
    const harness = buildHarness()
    const row: ScenarioRow = {
      id: 1,
      scenario_name: 'A',
      scenario_type: 'OVERTIME',
      status: 'EVALUATED',
    }
    const el = renderActions(row, harness)
    ;(el.querySelector('.ag-grid-delete-btn') as HTMLButtonElement)?.click()
    expect(harness.onConfirmDelete).toHaveBeenCalledWith(row)
  })
})
