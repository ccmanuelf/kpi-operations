import type { AllowEntry } from '../../src/utils/contrastAudit'

export const SCREENS: { name: string; path: string }[] = [
  { name: 'dashboard', path: '/kpi-dashboard' },
  { name: 'my-shift', path: '/my-shift' },
  { name: 'kpi-efficiency', path: '/kpi/efficiency' },
  { name: 'kpi-quality', path: '/kpi/quality' },
  { name: 'kpi-oee', path: '/kpi/oee' },
  { name: 'plan-vs-actual', path: '/plan-vs-actual' },
  { name: 'work-orders', path: '/work-orders' },
  { name: 'capacity-planning', path: '/capacity-planning' },
  { name: 'simulation-v2', path: '/simulation-v2' },
  { name: 'alerts', path: '/alerts' },
  { name: 'reports-admin-settings', path: '/admin/settings' },
  { name: 'admin-users', path: '/admin/users' },
  { name: 'admin-defect-types', path: '/admin/defect-types' },
]

// Verified false-positives: the MyShift header sits on a blue gradient banner the
// DOM contrast read can't always resolve (manually verified white-on-#1976d2 =
// 4.6:1). The gradient-aware logic covers most cases; these remain as a safety net.
export const ALLOWLIST: AllowEntry[] = [
  { screen: 'my-shift', classIncludes: 'text-h5', text: 'My Shift', reason: 'white on blue gradient banner (verified 4.6:1)' },
  { screen: 'my-shift', classIncludes: 'text-body-2', text: 'June', reason: 'date subtitle on blue gradient banner (verified)' },
]
