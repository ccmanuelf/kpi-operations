/**
 * Unit tests for usePartOpportunitiesGridData composable —
 * Group E Surface #15 (Part Opportunities admin migration).
 *
 * Mirrors the Defect Types spec (Surface #14): inline-editing pattern
 * verified — existing rows autosave PUT, new rows accumulate with
 * explicit Save, part_number + client_id are read-only after creation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    post: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

import usePartOpportunitiesGridData, {
  COMPLEXITY_OPTIONS,
  type PartOpportunityGridRow,
  type ClientOption,
} from '../usePartOpportunitiesGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((params: { data: PartOpportunityGridRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; precision?: number } | (() => { values?: unknown[] })
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const buildHarness = () => {
  const selectedClient = ref<string | number | null>('CLIENT1')
  const partOpportunities = ref<PartOpportunityGridRow[]>([])
  const clientOptions = ref<ClientOption[]>([
    { client_id: 'CLIENT1', client_name: 'Acme Co' },
    { client_id: 'CLIENT2', client_name: 'Beta Inc' },
  ])
  const loadPartOpportunities = vi.fn().mockResolvedValue(undefined)
  const notify = { showSuccess: vi.fn(), showError: vi.fn() }
  const onConfirmDelete = vi.fn()

  const grid = usePartOpportunitiesGridData({
    selectedClient,
    partOpportunities,
    clientOptions,
    loadPartOpportunities,
    notify,
    onConfirmDelete,
  })

  return {
    ...grid,
    selectedClient,
    partOpportunities,
    clientOptions,
    loadPartOpportunities,
    notify,
    onConfirmDelete,
  }
}

describe('usePartOpportunitiesGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockApi.post.mockResolvedValue({ data: {} })
    mockApi.put.mockResolvedValue({ data: {} })
  })

  describe('catalog options', () => {
    it('COMPLEXITY_OPTIONS lists the four canonical complexity levels', () => {
      expect(COMPLEXITY_OPTIONS).toEqual(['Simple', 'Standard', 'Complex', 'Very Complex'])
    })
  })

  describe('column definitions', () => {
    it('part_number editable only on new rows (pinned left)', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'part_number')!
      const editable = col.editable as (p: { data: PartOpportunityGridRow }) => boolean
      expect(editable({ data: { _isNew: true } })).toBe(true)
      expect(editable({ data: { _isNew: false, part_opportunities_id: 1 } })).toBe(false)
      expect(col.pinned).toBe('left')
    })

    it('opportunities_per_unit uses numeric editor (min:1, precision:0)', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'opportunities_per_unit')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      const params = col.cellEditorParams as { min?: number; precision?: number }
      expect(params.min).toBe(1)
      expect(params.precision).toBe(0)
    })

    it('part_description uses text editor', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'part_description')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('complexity uses select editor over COMPLEXITY_OPTIONS', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'complexity')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      const params = col.cellEditorParams as { values?: unknown[] }
      expect(params.values).toEqual(COMPLEXITY_OPTIONS)
    })

    it('client_id uses select editor over clientOptions and editable only on new rows', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'client_id')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      const editable = col.editable as (p: { data: PartOpportunityGridRow }) => boolean
      expect(editable({ data: { _isNew: true } })).toBe(true)
      expect(editable({ data: { _isNew: false } })).toBe(false)
    })

    it('notes uses large-text editor (popup)', () => {
      const { columnDefs } = buildHarness()
      const col = findCol(columnDefs.value, 'notes')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
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
    it('prepends a placeholder row marked _isNew with sensible defaults', () => {
      const { addRow, partOpportunities } = buildHarness()
      addRow()
      expect(partOpportunities.value).toHaveLength(1)
      const row = partOpportunities.value[0]
      expect(row._isNew).toBe(true)
      expect(row.complexity).toBe('Standard')
      expect(row.opportunities_per_unit).toBe(10)
      expect(row.is_active).toBe(true)
    })

    it('uses selectedClient for the new row client_id', () => {
      const { addRow, partOpportunities, selectedClient } = buildHarness()
      selectedClient.value = 'CLIENT2'
      addRow()
      expect(partOpportunities.value[0].client_id).toBe('CLIENT2')
    })
  })

  describe('saveNewRow', () => {
    it('POSTs payload when required fields are present', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        part_number: 'P001',
        opportunities_per_unit: 5,
        client_id: 'CLIENT1',
      } as PartOpportunityGridRow)
      expect(mockApi.post).toHaveBeenCalledWith(
        '/part-opportunities',
        expect.objectContaining({
          part_number: 'P001',
          opportunities_per_unit: 5,
          client_id: 'CLIENT1',
        }),
      )
    })

    it('refuses to POST when part_number missing', async () => {
      const { saveNewRow, notify } = buildHarness()
      await saveNewRow({
        _isNew: true,
        opportunities_per_unit: 5,
        client_id: 'CLIENT1',
      } as PartOpportunityGridRow)
      expect(mockApi.post).not.toHaveBeenCalled()
      expect(notify.showError).toHaveBeenCalled()
    })

    it('refuses to POST when client_id missing', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        part_number: 'P001',
        opportunities_per_unit: 5,
      } as PartOpportunityGridRow)
      expect(mockApi.post).not.toHaveBeenCalled()
    })

    it('refuses to POST when opportunities_per_unit is 0 or negative', async () => {
      const { saveNewRow } = buildHarness()
      await saveNewRow({
        _isNew: true,
        part_number: 'P001',
        opportunities_per_unit: 0,
        client_id: 'CLIENT1',
      } as PartOpportunityGridRow)
      expect(mockApi.post).not.toHaveBeenCalled()
    })

    it('reloads on success', async () => {
      const { saveNewRow, loadPartOpportunities } = buildHarness()
      await saveNewRow({
        _isNew: true,
        part_number: 'P001',
        opportunities_per_unit: 5,
        client_id: 'CLIENT1',
      } as PartOpportunityGridRow)
      expect(loadPartOpportunities).toHaveBeenCalled()
    })
  })

  describe('removeNewRow', () => {
    it('removes the matching row from partOpportunities', () => {
      const { removeNewRow, partOpportunities } = buildHarness()
      partOpportunities.value = [
        { _isNew: true, part_number: 'X' },
        { part_opportunities_id: 2 },
      ]
      removeNewRow(partOpportunities.value[0])
      expect(partOpportunities.value).toHaveLength(1)
      expect(partOpportunities.value[0]).toMatchObject({ part_opportunities_id: 2 })
    })
  })

  describe('onCellValueChanged', () => {
    it('PUTs the row when an existing row changes', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: {
          part_opportunities_id: 7,
          part_number: 'P001',
          opportunities_per_unit: 8,
          client_id: 'CLIENT1',
          is_active: true,
        } as PartOpportunityGridRow,
        column: { colId: 'opportunities_per_unit' },
      })
      expect(mockApi.put).toHaveBeenCalledWith(
        '/part-opportunities/7',
        expect.objectContaining({ opportunities_per_unit: 8 }),
      )
    })

    it('does NOT PUT for new rows', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: { _isNew: true, part_number: 'X' } as PartOpportunityGridRow,
        column: { colId: 'opportunities_per_unit' },
      })
      expect(mockApi.put).not.toHaveBeenCalled()
    })

    it('does NOT PUT when part_opportunities_id missing', async () => {
      const { onCellValueChanged } = buildHarness()
      await onCellValueChanged({
        data: { part_number: 'X' } as PartOpportunityGridRow,
        column: { colId: 'opportunities_per_unit' },
      })
      expect(mockApi.put).not.toHaveBeenCalled()
    })

    it('reloads on PUT failure to roll back', async () => {
      mockApi.put.mockRejectedValue(new Error('boom'))
      const { onCellValueChanged, loadPartOpportunities } = buildHarness()
      await onCellValueChanged({
        data: {
          part_opportunities_id: 7,
          part_number: 'P001',
          opportunities_per_unit: 8,
          client_id: 'CLIENT1',
        } as PartOpportunityGridRow,
        column: { colId: 'opportunities_per_unit' },
      })
      expect(loadPartOpportunities).toHaveBeenCalled()
    })
  })
})
