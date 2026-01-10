/**
 * Alert Components - Export Index
 *
 * Provides centralized export for all alert components
 */

// Alerts
export { default as AbsenteeismAlert } from './AbsenteeismAlert.vue'

// Alert registry for dynamic loading
export const alertRegistry = {
  'absenteeism-alert': {
    component: 'AbsenteeismAlert',
    name: 'Absenteeism Threshold Alert',
    category: 'attendance',
    priority: 'P3-004',
    description: 'Alerts when absenteeism rate exceeds configurable threshold'
  }
}

// Default export
export default {
  AbsenteeismAlert: () => import('./AbsenteeismAlert.vue')
}
