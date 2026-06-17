/**
 * Shared factory for capacity-planning export/import sheet options.
 * Returns a computed array of { title, value } pairs so the labels
 * stay reactive to locale changes.
 *
 * Consumers: useCapacityExport (and transitively CapacityPlanningView /
 * WorkbookActionDialogs which receive the value via prop).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export interface WorksheetOption {
  title: string
  value: string
}

export function useExportSheetOptions() {
  const { t } = useI18n()
  return computed<WorksheetOption[]>(() => [
    { title: t('capacityExport.sheets.orders'), value: 'orders' },
    { title: t('capacityExport.sheets.masterCalendar'), value: 'masterCalendar' },
    { title: t('capacityExport.sheets.productionLines'), value: 'productionLines' },
    { title: t('capacityExport.sheets.productionStandards'), value: 'productionStandards' },
    { title: t('capacityExport.sheets.bom'), value: 'bom' },
    { title: t('capacityExport.sheets.stockSnapshot'), value: 'stockSnapshot' },
  ])
}
