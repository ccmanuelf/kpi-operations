/**
 * Alert Components - Export Index
 *
 * Provides centralized export for all alert components
 */
import i18n from '@/i18n'

// Alerts
export { default as AbsenteeismAlert } from './AbsenteeismAlert.vue'

// Alert registry for dynamic loading.
// name/description use getters so locale changes are reflected reactively.
export const alertRegistry = {
  'absenteeism-alert': {
    component: 'AbsenteeismAlert',
    get name() { return i18n.global.t('alerts.registry.absenteeismAlert') },
    category: 'attendance',
    priority: 'P3-004',
    get description() { return i18n.global.t('alerts.registry.absenteeismAlertDesc') },
  },
}

// Default export
export default {
  AbsenteeismAlert: () => import('./AbsenteeismAlert.vue'),
}
