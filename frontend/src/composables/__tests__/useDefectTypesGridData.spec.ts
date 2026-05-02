/**
 * Unit tests for useDefectTypesGridData composable —
 * Group E Surface #14 (Defect Types catalog admin migration).
 *
 * Verifies inline-editing behaviour: existing rows autosave PUT on
 * cell-value change; new rows accumulate locally; defect_code is
 * read-only after creation; required fields gate the save action.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    createDefectType: vi.fn(),
    updateDefectType: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

import useDefectTypesGridData, {
  SEVERITY_OPTIONS,
  CATEGORY_OPTIONS,
  type DefectTypeGridRow,
} from '../useDefectTypesGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((params: { data: DefectTypeGridRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; precision?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const buildHarness = () => {
  const selectedClient = ref<string | number | null>('CLIENT1')
  const defectTypes = ref<DefectTypeGridRow[]>([])
  const loadDefectTypes = vi.fn().mockResolvedValue(undefined)
  const notify = {
    showSuccess: vi.fn(),
    showError: vi.fn(),
  }
  const onConfirmDelete = vi.fn()

  const grid = useDefectTypesGridData({
    selectedClient,
    defectTypes,
    loadDefectTypes,
    notify,
    onConfirmDelete,
  })

  return { ...grid, selectedClient, defectTypes, loadDefectTypes, notify, onConfirmDelete }
}

describe('useDefectTypesGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockApi.createDefectType.mockResolvedValue({ data: {} })
    mockApi.updateDefectType.mockResolvedValue({ data: {} })
  })

  describe('catalog options', () => {
    it('SEVERITY_OPTIONS lists the three canonical severities', () => {
      expect(SEVERITY_OPTIONS).toEqual(['CRITICAL', 'MAJOR', 'MINOR'])
    })

    it('CATEGORY_OPTIONS contains 15 manufacturing categories', () => {
      expect(CATEGORY_OPTIONS).toHaveLength(15)
      expect(CATEGORY_OPTIONS).toContain('Assembly')
      expect(CATEGORY_OPTIONS).toContain('Material')
      expect(CATEGORY_OPTIONS).toContain('Process')
    })
  })

  describe('column definitions', () => {
    it('defect_code editable only on new rows', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'defect_code')!
      const editable = col.editable as (params: { data: DefectTypeGridRow }) => boolean
      expect(editable({ data: { _isNew: true } })).toBe(true)
      expect(editable({ data: { _isNew: false, defect_type_id: 1 } })).toBe(false)
    })

    it('defect_code pinned left', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'defect_code')!
      expect(col.pinned).toBe('left')
    })

    it('defect_name uses text editor and is always editable', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'defect_name')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.editable).toBe(true)
    })

    it('description uses large-text editor', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'description')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
    })

    it('category uses select editor over CATEGORY_OPTIONS', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'category')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(CATEGORY_OPTIONS)
    })

    it('severity_default uses select editor over SEVERITY_OPTIONS', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'severity_default')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(SEVERITY_OPTIONS)
    })

    it('sort_order uses numeric integer editor', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'sort_order')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 0 })
    })

    it('is_active uses checkbox editor', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'is_active')!
      expect(col.cellEditor).toBe('agCheckboxCellEditor')
    })

    it('_actions column pinned right', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('addRow', () => {
    it('refuses to add a new row when no client is selected', () => {
      const { addRow, defectTypes, selectedClient, notify } = buildHarness()
      selectedClient.value = null
      addRow()
      expect(defectTypes.value).toHaveLength(0)
      expect(notify.showError).toHaveBeenCalled()
    })

    it('prepends a placeholder row marked _isNew with sensible defaults', () => {
      const { addRow, defectTypes } = buildHarness()
      addRow()
      expect(defectTypes.value).toHaveLength(1)
      const row = defectTypes.value[0]
      expect(row._isNew).toBe(true)
      expect(row.severity_default).toBe('MAJOR')
      expect(row.is_active).toBe(true)
    })

    it('sets sort_order to existing length + 1', () => {
      const { addRow, defectTypes } = buildHarness()
      defectTypes.value = [
        { defect_type_id: 1 } as DefectTypeGridRow,
        { defect_type_id: 2 } as DefectTypeGridRow,
      ]
      addRow()
      expect(defectTypes.value[0].sort_order).toBe(3)
    })
  })

  describe('saveNewRow', () => {
    it('POSTs with client_id and required fields', async () => {
      const { saveNewRow, selectedClient } = buildHarness()
      selectedClient.value = 'CLIENT1'
      await saveNewRow({
        _isNew: true,
        defect_code: 'D001',
        defect_name: 'Scratch',
        severity_default: 'MAJOR',
        is_active: true,
      } as DefectTypeGridRow)
      expect(mockApi.createDefectType).toHaveBeenCalledWith(
        expect.objectContaining({
          defect_code: 'D001',
          defect_name: 'Scratch',
          severity_default: 'MAJOR',
          client_id: 'CLIENT1',
        }),
      )
    })

    it('refuses to POST when required fields are missing', async () => {
      const { saveNewRow, notify } = buildHarness()
      await saveNewRow({
        _isNew: true,
        defect_code: '',
        defect_name: 'Scratch',
        severity_default: 'MAJOR',
      } as DefectTypeGridRow)
      expect(mockApi.createDefectType).not.toHaveBeenCalled()
      expect(notify.showError).toHaveBeenCalled()
    })

    it('refuses to POST when severity_default is missing', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        defect_code: 'D001',
        defect_name: 'Scratch',
      } as DefectTypeGridRow)
      expect(mockApi.createDefectType).not.toHaveBeenCalled()
    })

    it('reloads on success', async () => {
      const { saveNewRow, loadDefectTypes } = buildHarness()
      await saveNewRow({
        _isNew: true,
        defect_code: 'D001',
        defect_name: 'Scratch',
        severity_default: 'MAJOR',
      } as DefectTypeGridRow)
      expect(loadDefectTypes).toHaveBeenCalled()
    })
  })

  describe('removeNewRow', () => {
    it('removes the matching row from defectTypes', () => {
      const { removeNewRow, defectTypes } = buildHarness()
      defectTypes.value = [
        { _isNew: true, defect_code: 'X' },
        { defect_type_id: 2 },
      ]
      // Pass the *reactive proxy* reference (matches what AG Grid hands
      // the cellRenderer in production).
      removeNewRow(defectTypes.value[0])
      expect(defectTypes.value).toHaveLength(1)
      expect(defectTypes.value[0]).toMatchObject({ defect_type_id: 2 })
    })
  })

  describe('onCellValueChanged', () => {
    it('PUTs the row when an existing row changes', async () => {
      const { onCellValueChanged } = buildHarness()
      const row: DefectTypeGridRow = {
        defect_type_id: 5,
        defect_code: 'D001',
        defect_name: 'Updated',
        severity_default: 'MINOR',
        is_active: true,
      }
      await onCellValueChanged({ data: row, column: { colId: 'defect_name' } })
      expect(mockApi.updateDefectType).toHaveBeenCalledWith(
        5,
        expect.objectContaining({ defect_name: 'Updated' }),
      )
    })

    it('does NOT PUT for new rows (saves explicitly via saveNewRow)', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: { _isNew: true, defect_code: 'D001' } as DefectTypeGridRow,
        column: { colId: 'defect_name' },
      })
      expect(mockApi.updateDefectType).not.toHaveBeenCalled()
    })

    it('does NOT PUT when defect_type_id is missing', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: { defect_code: 'D001' } as DefectTypeGridRow,
        column: { colId: 'defect_name' },
      })
      expect(mockApi.updateDefectType).not.toHaveBeenCalled()
    })

    it('reloads on PUT failure to roll back the cell', async () => {
      mockApi.updateDefectType.mockRejectedValue(new Error('boom'))
      const { onCellValueChanged, loadDefectTypes } = buildHarness()
      await onCellValueChanged({
        data: {
          defect_type_id: 5,
          defect_code: 'D001',
          defect_name: 'X',
          severity_default: 'MAJOR',
        } as DefectTypeGridRow,
        column: { colId: 'defect_name' },
      })
      expect(loadDefectTypes).toHaveBeenCalled()
    })
  })
})
