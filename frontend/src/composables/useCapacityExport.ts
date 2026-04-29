/**
 * Composable for Capacity Planning import/export. JSON/CSV export
 * for the active worksheet, JSON import that goes through the
 * worksheet ops sub-store.
 */
import { ref, type Ref } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface WorksheetOption {
  title: string
  value: string
}

const worksheetOptions: WorksheetOption[] = [
  { title: 'Orders', value: 'orders' },
  { title: 'Calendar', value: 'masterCalendar' },
  { title: 'Production Lines', value: 'productionLines' },
  { title: 'Standards', value: 'productionStandards' },
  { title: 'BOM', value: 'bom' },
  { title: 'Stock', value: 'stockSnapshot' },
]

type ExportFormat = 'JSON' | 'CSV'

export function useCapacityExport(activeTab: Ref<string>) {
  const store = useCapacityPlanningStore()

  const showExportDialog = ref(false)
  const showImportDialog = ref(false)

  const exportFormat = ref<ExportFormat>('JSON')
  const importFile = ref<File | null>(null)
  const importTarget = ref('orders')

  const arrayToCSV = (data: Record<string, unknown>[]): string => {
    if (!Array.isArray(data) || data.length === 0) return ''
    const headers = Object.keys(data[0]).filter((k) => !k.startsWith('_'))
    const escapeField = (val: unknown): string => {
      const str = val == null ? '' : String(val)
      return str.includes(',') || str.includes('"') || str.includes('\n')
        ? `"${str.replace(/"/g, '""')}"`
        : str
    }
    const rows = data.map((row) => headers.map((h) => escapeField(row[h])).join(','))
    return [headers.join(','), ...rows].join('\n')
  }

  const downloadBlob = (blob: Blob, filename: string): void => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const exportWorkbook = (): void => {
    showExportDialog.value = false
    const dateStr = new Date().toISOString().slice(0, 10)

    if (exportFormat.value === 'CSV') {
      const wsKey = activeTab.value
      const worksheet = store.worksheets[wsKey]
      if (!worksheet || !Array.isArray(worksheet.data)) return
      const csv = arrayToCSV(worksheet.data as Record<string, unknown>[])
      downloadBlob(
        new Blob([csv], { type: 'text/csv;charset=utf-8' }),
        `capacity-${wsKey}-${dateStr}.csv`,
      )
    } else {
      const json = store.exportWorkbookJSON()
      downloadBlob(
        new Blob([json], { type: 'application/json' }),
        `capacity-workbook-${dateStr}.json`,
      )
    }
  }

  const importData = async (): Promise<void> => {
    showImportDialog.value = false
    if (!importFile.value) return

    try {
      const text = await importFile.value.text()
      const data = JSON.parse(text)
      store.importData(importTarget.value, Array.isArray(data) ? data : [data])
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Import failed:', error)
    }
  }

  return {
    showExportDialog,
    showImportDialog,
    exportFormat,
    importFile,
    importTarget,
    worksheetOptions,
    exportWorkbook,
    importData,
  }
}
