/**
 * Composable for Capacity Planning import/export functionality.
 * Handles: export to JSON/CSV, import from file, format selection.
 */
import { ref } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const worksheetOptions = [
  { title: 'Orders', value: 'orders' },
  { title: 'Calendar', value: 'masterCalendar' },
  { title: 'Production Lines', value: 'productionLines' },
  { title: 'Standards', value: 'productionStandards' },
  { title: 'BOM', value: 'bom' },
  { title: 'Stock', value: 'stockSnapshot' },
]

export function useCapacityExport(activeTab) {
  const store = useCapacityPlanningStore()

  // Dialog visibility
  const showExportDialog = ref(false)
  const showImportDialog = ref(false)

  // Export/Import state
  const exportFormat = ref('JSON')
  const importFile = ref(null)
  const importTarget = ref('orders')

  /**
   * Convert an array of objects to a CSV string.
   * Properly escapes fields containing commas, quotes, or newlines.
   */
  const arrayToCSV = (data) => {
    if (!Array.isArray(data) || data.length === 0) return ''
    const headers = Object.keys(data[0]).filter(k => !k.startsWith('_'))
    const escapeField = (val) => {
      const str = val == null ? '' : String(val)
      return str.includes(',') || str.includes('"') || str.includes('\n')
        ? `"${str.replace(/"/g, '""')}"`
        : str
    }
    const rows = data.map(row => headers.map(h => escapeField(row[h])).join(','))
    return [headers.join(','), ...rows].join('\n')
  }

  /**
   * Trigger a file download from a Blob.
   */
  const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const exportWorkbook = () => {
    showExportDialog.value = false
    const dateStr = new Date().toISOString().slice(0, 10)

    if (exportFormat.value === 'CSV') {
      const wsKey = activeTab.value
      const worksheet = store.worksheets[wsKey]
      if (!worksheet || !Array.isArray(worksheet.data)) return
      const csv = arrayToCSV(worksheet.data)
      downloadBlob(
        new Blob([csv], { type: 'text/csv;charset=utf-8' }),
        `capacity-${wsKey}-${dateStr}.csv`
      )
    } else {
      const json = store.exportWorkbookJSON()
      downloadBlob(
        new Blob([json], { type: 'application/json' }),
        `capacity-workbook-${dateStr}.json`
      )
    }
  }

  const importData = async () => {
    showImportDialog.value = false
    if (!importFile.value) return

    try {
      const text = await importFile.value.text()
      const data = JSON.parse(text)
      store.importData(importTarget.value, Array.isArray(data) ? data : [data])
    } catch (error) {
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
