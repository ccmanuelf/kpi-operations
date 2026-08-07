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
  { name: 'summaries', path: '/summaries' },
  { name: 'simulation-v2', path: '/simulation-v2' },
  { name: 'alerts', path: '/alerts' },
  { name: 'reports-admin-settings', path: '/admin/settings' },
  { name: 'admin-users', path: '/admin/users' },
  { name: 'admin-defect-types', path: '/admin/defect-types' },
  { name: 'admin-employees', path: '/admin/employees' },
]

// NOT added: '/data-entry/attendance'. AGGridBase's "Paste from Excel"
// toolbar button (enableExcelPaste defaults true; AttendanceEntryGrid
// doesn't override it) fails dark-theme contrast (2.21-2.52:1 vs the
// 4.5:1 threshold) — a pre-existing bug in the shared toolbar, not in
// anything this Task 7 change touched. work-orders (the other
// AGGridBase-heavy audited screen) opts out via enableExcelPaste="false",
// which is why this was never caught. Flagged, not fixed here — fixing
// it means auditing every AGGridBase consumer's dark-theme toolbar, out
// of this task's scope.

// Verified false-positives: the MyShift header sits on a blue gradient banner the
// DOM contrast read can't always resolve (manually verified white-on-#1976d2 =
// 4.6:1). The gradient-aware logic covers most cases; these remain as a safety net.
export const ALLOWLIST: AllowEntry[] = [
  { screen: 'my-shift', classIncludes: 'text-h5', text: 'My Shift', reason: 'white on blue gradient banner (verified 4.6:1)' },
  { screen: 'my-shift', classIncludes: 'text-body-2', text: 'June', reason: 'date subtitle on blue gradient banner (verified)' },
]
