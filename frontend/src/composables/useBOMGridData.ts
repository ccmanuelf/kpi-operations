/**
 * Composable for BOMGrid script logic — master-detail column
 * definitions, selection state, and store-bound CRUD wrappers.
 *
 * Design: AG Grid Community Edition has no native master-detail
 * (Enterprise-only), so this composable exposes two parallel grids:
 *   - Parent grid: BOM headers (one row per parent_item_code).
 *   - Child grid: Components for whichever BOM the operator selects.
 *
 * Persistence is centralised via
 * `useCapacityPlanningStore.saveWorksheet('bom')`. The store action
 * persists both header rows (POST /capacity/bom + PUT /capacity/bom/{id})
 * and component rows (POST /capacity/bom/{id}/components + PUT
 * /capacity/bom/{id}/components/{cid}); per the Phase 0 audit those
 * component-level endpoints exist on the backend but were not wired
 * into any UI before this migration.
 */
import { ref, computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface BOMComponentRow {
  _id?: number | string
  _isNew?: boolean
  component_item_code?: string
  component_description?: string
  quantity_per?: number
  unit_of_measure?: string
  waste_percentage?: number
  [key: string]: unknown
}

export interface BOMHeaderRow {
  _id?: number | string
  _isNew?: boolean
  parent_item_code?: string
  parent_item_description?: string
  style_model?: string
  revision?: string
  is_active?: boolean
  components?: BOMComponentRow[]
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; max?: number; precision?: number }
  cellRenderer?: (params: {
    data: BOMHeaderRow | BOMComponentRow
    rowIndex: number
  }) => HTMLElement
  valueGetter?: (params: { data: BOMHeaderRow }) => unknown
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

export const BOM_UOM_OPTIONS: string[] = ['EA', 'M', 'YD', 'KG', 'LB', 'PC', 'SET']

interface UseBOMGridDataReturn {
  boms: ComputedRef<BOMHeaderRow[]>
  hasChanges: ComputedRef<boolean>
  selectedBOMIndex: Ref<number | null>
  selectedBOM: ComputedRef<BOMHeaderRow | null>
  selectedComponents: ComputedRef<BOMComponentRow[]>
  bomColumnDefs: ComputedRef<ColumnDef[]>
  componentColumnDefs: ComputedRef<ColumnDef[]>
  addBOM: () => void
  removeBOM: (index: number) => void
  addComponent: () => void
  removeComponent: (componentIndex: number) => void
  onBOMRowClicked: (event: { data: BOMHeaderRow; rowIndex: number }) => void
  onBOMCellValueChanged: () => void
  onComponentCellValueChanged: () => void
}

export default function useBOMGridData(): UseBOMGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const boms = computed<BOMHeaderRow[]>(
    () => (store.worksheets.bom.data as BOMHeaderRow[]) || [],
  )

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.bom.dirty),
  )

  const selectedBOMIndex = ref<number | null>(null)

  const selectedBOM = computed<BOMHeaderRow | null>(() => {
    const i = selectedBOMIndex.value
    if (i === null || i < 0 || i >= boms.value.length) return null
    return boms.value[i] ?? null
  })

  const selectedComponents = computed<BOMComponentRow[]>(() => {
    return selectedBOM.value?.components || []
  })

  const addBOM = (): void => {
    store.addRow('bom')
    // Auto-select the newly-added row (which is appended at the end by
    // the store's addRow action).
    selectedBOMIndex.value = boms.value.length - 1
  }

  const removeBOM = (index: number): void => {
    store.removeRow('bom', index)
    if (selectedBOMIndex.value === index) {
      selectedBOMIndex.value = null
    } else if (selectedBOMIndex.value !== null && selectedBOMIndex.value > index) {
      // Shift the selection down to compensate for the removed row.
      selectedBOMIndex.value = selectedBOMIndex.value - 1
    }
  }

  const addComponent = (): void => {
    if (selectedBOMIndex.value === null) return
    store.addBOMComponent(selectedBOMIndex.value)
  }

  const removeComponent = (componentIndex: number): void => {
    if (selectedBOMIndex.value === null) return
    store.removeBOMComponent(selectedBOMIndex.value, componentIndex)
  }

  const onBOMRowClicked = (event: { data: BOMHeaderRow; rowIndex: number }): void => {
    selectedBOMIndex.value = event.rowIndex
  }

  const onBOMCellValueChanged = (): void => {
    store.worksheets.bom.dirty = true
  }

  const onComponentCellValueChanged = (): void => {
    store.worksheets.bom.dirty = true
  }

  const bomColumnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanning.bom.parentItemCode'),
      field: 'parent_item_code',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 150,
    },
    {
      headerName: t('common.description'),
      field: 'parent_item_description',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 220,
    },
    {
      headerName: t('capacityPlanning.bom.styleCode'),
      field: 'style_model',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 130,
    },
    {
      headerName: t('capacityPlanning.bom.revision'),
      field: 'revision',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 100,
    },
    {
      headerName: t('capacityPlanning.bom.componentsCount'),
      field: '_components_count',
      editable: false,
      sortable: false,
      filter: false,
      valueGetter: (params) =>
        Array.isArray((params.data as BOMHeaderRow).components)
          ? (params.data as BOMHeaderRow).components!.length
          : 0,
      width: 130,
    },
    {
      headerName: t('common.active'),
      field: 'is_active',
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: (params) =>
        renderCheckmark((params.data as BOMHeaderRow).is_active !== false),
      width: 100,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) => renderBOMActions(params, removeBOM),
      width: 90,
      pinned: 'right',
    },
  ])

  const componentColumnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanning.bom.headers.componentCode'),
      field: 'component_item_code',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 150,
    },
    {
      headerName: t('capacityPlanning.bom.headers.description'),
      field: 'component_description',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 220,
    },
    {
      headerName: t('capacityPlanning.bom.headers.qtyPer'),
      field: 'quantity_per',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 4 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.bom.headers.uom'),
      field: 'unit_of_measure',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: BOM_UOM_OPTIONS },
      width: 90,
    },
    {
      headerName: t('capacityPlanning.bom.headers.wastePercent'),
      field: 'waste_percentage',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 100, precision: 2 },
      width: 130,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) => renderComponentActions(params, removeComponent),
      width: 90,
      pinned: 'right',
    },
  ])

  return {
    boms,
    hasChanges,
    selectedBOMIndex,
    selectedBOM,
    selectedComponents,
    bomColumnDefs,
    componentColumnDefs,
    addBOM,
    removeBOM,
    addComponent,
    removeComponent,
    onBOMRowClicked,
    onBOMCellValueChanged,
    onComponentCellValueChanged,
  }
}

const renderCheckmark = (value: boolean): HTMLElement => {
  const span = document.createElement('span')
  span.textContent = value ? '\u2713' : ''
  span.style.color = value ? 'var(--cds-support-success, #198038)' : 'inherit'
  return span
}

const renderBOMActions = (
  params: { data: BOMHeaderRow | BOMComponentRow; rowIndex: number },
  removeBOM: (i: number) => void,
): HTMLElement => {
  const div = document.createElement('div')
  div.innerHTML = `
    <button class="ag-grid-delete-btn" title="Delete BOM" style="
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
    ?.addEventListener('click', (event) => {
      event.stopPropagation()
      removeBOM(params.rowIndex)
    })
  return div
}

const renderComponentActions = (
  params: { data: BOMHeaderRow | BOMComponentRow; rowIndex: number },
  removeComponent: (i: number) => void,
): HTMLElement => {
  const div = document.createElement('div')
  div.innerHTML = `
    <button class="ag-grid-delete-btn" title="Delete component" style="
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
    ?.addEventListener('click', () => removeComponent(params.rowIndex))
  return div
}
