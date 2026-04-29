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

declare module '@/composables/useDashboardOverviewData' {
  export const useDashboardOverviewData: any
  const value: any
  export default value
}

declare module '@/utils/performance' {
  export const referenceDataCache: any
  export const performanceMonitor: any
  export const debounce: any
  export const throttle: any
  const value: any
  export default value
}

declare module '@/utils/workflow/mermaidConverter' {
  export const configToVueFlow: any
  export const vueFlowToConfig: any
  export const configToMermaid: any
  export const mermaidToConfig: any
}

declare module '@/utils/workflow/workflowValidator' {
  export const validateWorkflow: any
}

// Capacity Planning sub-stores (still JS). Each defineStore call
// returns a Pinia store proxy that exposes refs and actions; typing
// them as `any` is acceptable for the delegating wrapper above them
// because the wrapper preserves backward-compat string keys.
declare module '@/stores/capacity/useWorksheetOps' {
  export const useWorksheetOpsStore: any
}

declare module '@/stores/capacity/useWorkbookStore' {
  export const useWorkbookStore: any
}

declare module '@/stores/capacity/useAnalysisStore' {
  export const useAnalysisStore: any
}

declare module '@/stores/capacity/defaults' {
  export const getDefaultCalendarEntry: any
  export const getDefaultProductionLine: any
  export const getDefaultOrder: any
  export const getDefaultStandard: any
  export const getDefaultBOMHeader: any
  export const getDefaultBOMDetail: any
  export const getDefaultStockSnapshot: any
  export const getDefaultComponentCheckRow: any
  export const getDefaultCapacityAnalysisRow: any
  export const getDefaultScheduleRow: any
  export const getDefaultScenario: any
  export const getDefaultKPITrackingRow: any
  export const getDefaultDashboardInputs: any
}

// Relative imports (`./capacity/...` from capacityPlanningStore.ts)
// can't use ambient module declarations — they need colocated .d.ts
// shims, see src/stores/capacity/*.d.ts.

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
