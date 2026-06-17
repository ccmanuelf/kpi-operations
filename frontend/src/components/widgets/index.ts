/**
 * Dashboard Widgets - Export Index
 *
 * Provides centralized export for all dashboard widget components
 */
import i18n from '@/i18n'

// Widgets
export { default as DowntimeImpactWidget } from './DowntimeImpactWidget.vue'
export { default as BradfordFactorWidget } from './BradfordFactorWidget.vue'
export { default as QualityByOperatorWidget } from './QualityByOperatorWidget.vue'
export { default as ReworkByOperationWidget } from './ReworkByOperationWidget.vue'

// Widget list for dynamic loading.
// name/description use getters so locale changes are reflected reactively
// (i18n.global.t is reactive inside getters — validated in reactive-resolution.spec.ts).
export const widgetRegistry = {
  'downtime-impact': {
    component: 'DowntimeImpactWidget',
    get name() { return i18n.global.t('widgets.registry.downtimeImpact') },
    category: 'downtime',
    priority: 'P2-002',
    get description() { return i18n.global.t('widgets.registry.downtimeImpactDesc') },
  },
  'bradford-factor': {
    component: 'BradfordFactorWidget',
    get name() { return i18n.global.t('widgets.registry.bradfordFactor') },
    category: 'attendance',
    priority: 'P3-003',
    get description() { return i18n.global.t('widgets.registry.bradfordFactorDesc') },
  },
  'quality-by-operator': {
    component: 'QualityByOperatorWidget',
    get name() { return i18n.global.t('widgets.registry.qualityByOperator') },
    category: 'quality',
    priority: 'P4-001',
    get description() { return i18n.global.t('widgets.registry.qualityByOperatorDesc') },
  },
  'rework-by-operation': {
    component: 'ReworkByOperationWidget',
    get name() { return i18n.global.t('widgets.registry.reworkByOperation') },
    category: 'quality',
    priority: 'P4-002',
    get description() { return i18n.global.t('widgets.registry.reworkByOperationDesc') },
  },
}

// Default export
export default {
  DowntimeImpactWidget: () => import('./DowntimeImpactWidget.vue'),
  BradfordFactorWidget: () => import('./BradfordFactorWidget.vue'),
  QualityByOperatorWidget: () => import('./QualityByOperatorWidget.vue'),
  ReworkByOperationWidget: () => import('./ReworkByOperationWidget.vue'),
}
