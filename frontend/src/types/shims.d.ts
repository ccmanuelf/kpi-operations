/**
 * Ambient declarations for the JS-mostly codebase.
 *
 * Most stores, services, and composables are still .js, so importing
 * them from a .ts file (or .vue with `<script setup lang="ts">`)
 * triggers TS7016 ("Could not find a declaration file"). Instead of
 * flipping `allowJs: true` (which pulls 160+ JS files into the type-
 * check graph and exposes hundreds of follow-on errors), we declare
 * the JS-side public surface here as `any`.
 *
 * This is an intentional escape hatch — when a JS module gets ported
 * to .ts, drop its line here.
 */

// Catch-all for the JS API surface. Each .js module imported from a
// .ts file gets an `any`-typed declaration so TS doesn't trip on
// TS7016. Drop a line here when the underlying module is ported to
// .ts and starts emitting real types.
declare module '@/services/api' {
  const value: any
  export default value
  export const getSavedFilters: any
  export const createSavedFilter: any
  export const updateSavedFilter: any
  export const deleteSavedFilter: any
  export const applyFilter: any
  export const setDefaultFilter: any
  export const clearFilterHistory: any
  export const duplicateFilter: any
  export const getDashboardPreferences: any
  export const saveDashboardPreferences: any
  export const resetDashboardPreferences: any
  export const getWorkOrders: any
  export const updateWorkOrder: any
  export const createWorkOrder: any
  export const deleteWorkOrder: any
  export const getDataCompleteness: any
}

declare module '@/services/api/simulationV2' {
  const value: any
  export default value
  export const validateSimulationConfig: any
  export const runSimulation: any
  export const markAsVisited: any
}

declare module '@/composables/useDashboardOverviewData' {
  export const useDashboardOverviewData: any
  const value: any
  export default value
}

// `simulationV2Store` is covered by the colocated
// src/stores/simulationV2Store.d.ts declaration file (resolves both
// `@/stores/simulationV2Store` and relative `../simulationV2Store`
// import forms uniformly).

// Vue SFCs without a colocated .d.ts — the Volar plugin handles
// `<script setup>`-defined components, but plain `<script>` SFCs that
// use the Options API need this catch-all.
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, any>
  export default component
}
