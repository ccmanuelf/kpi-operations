/**
 * Dashboard Widgets - Export Index
 *
 * Provides centralized export for all dashboard widget components
 */

// Widgets
export { default as DowntimeImpactWidget } from './DowntimeImpactWidget.vue'
export { default as BradfordFactorWidget } from './BradfordFactorWidget.vue'
export { default as QualityByOperatorWidget } from './QualityByOperatorWidget.vue'
export { default as ReworkByOperationWidget } from './ReworkByOperationWidget.vue'

// Widget list for dynamic loading
export const widgetRegistry = {
  'downtime-impact': {
    component: 'DowntimeImpactWidget',
    name: 'Downtime Impact on OEE',
    category: 'downtime',
    priority: 'P2-002',
    description: 'Shows downtime categories ranked by their impact on Overall Equipment Effectiveness'
  },
  'bradford-factor': {
    component: 'BradfordFactorWidget',
    name: 'Bradford Factor Score',
    category: 'attendance',
    priority: 'P3-003',
    description: 'Displays Bradford Factor attendance scoring with risk thresholds'
  },
  'quality-by-operator': {
    component: 'QualityByOperatorWidget',
    name: 'Quality by Operator',
    category: 'quality',
    priority: 'P4-001',
    description: 'Operator-level quality metrics with First Pass Yield tracking'
  },
  'rework-by-operation': {
    component: 'ReworkByOperationWidget',
    name: 'Rework by Operation',
    category: 'quality',
    priority: 'P4-002',
    description: 'Rework analysis by operation with Pareto breakdown and cost estimation'
  }
}

// Default export
export default {
  DowntimeImpactWidget: () => import('./DowntimeImpactWidget.vue'),
  BradfordFactorWidget: () => import('./BradfordFactorWidget.vue'),
  QualityByOperatorWidget: () => import('./QualityByOperatorWidget.vue'),
  ReworkByOperationWidget: () => import('./ReworkByOperationWidget.vue')
}
