/**
 * @deprecated Use productionDataStore.js instead.
 * This file is a backward-compatibility re-export.
 * The store was renamed from kpiStore → productionDataStore to resolve
 * the naming collision where both kpi.js and kpiStore.js exported useKPIStore.
 */
export { useProductionDataStore as useKPIStore } from './productionDataStore'
