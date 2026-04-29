import axiosClient from './client'

export { default as api, api as axiosInstance } from './client'

export * from './auth'
export * from './production'
export * from './kpi'
export * from './dataEntry'
export * from './reports'
// `reference` and `admin` both expose `getClients` and `getDefectTypes`
// (admin: direct endpoints, reference: cached wrappers). Re-export the
// non-conflicting names from reference so TS doesn't reject the
// duplicate; the cached versions remain reachable via direct module
// imports (`@/services/api/reference`) and the default-export below
// where `...reference` overrides `...admin`, preserving JS behavior.
export {
  getProducts,
  getShifts,
  getDowntimeReasons,
  invalidateReferenceCache,
  invalidateReferenceType,
  prefetchReferenceData,
  getReferenceDataCacheStats,
} from './reference'
export * from './admin'
export * from './preferences'
export * from './qr'
export * from './predictions'
export * from './workOrders'
export * from './myShift'
export * from './workflow'
export * from './simulation'
export * from './productionLines'
export * from './planVsActual'
export * from './csvExport'
export * from './onboarding'
export * as capacityPlanning from './capacityPlanning'

import * as auth from './auth'
import * as production from './production'
import * as kpi from './kpi'
import * as dataEntry from './dataEntry'
import * as reports from './reports'
import * as reference from './reference'
import * as admin from './admin'
import * as preferences from './preferences'
import * as qr from './qr'
import * as predictions from './predictions'
import * as workOrders from './workOrders'
import * as myShift from './myShift'
import * as workflow from './workflow'
import * as simulation from './simulation'
import * as productionLines from './productionLines'
import * as planVsActual from './planVsActual'
import * as csvExport from './csvExport'
import * as onboarding from './onboarding'
import * as capacityPlanning from './capacityPlanning'

// Default export object — backwards-compatible single namespace for
// `import api from '@/services/api'` callers that do `api.login(...)`.
// Also exposes the axios verbs for direct calls.
export default {
  get: axiosClient.get.bind(axiosClient),
  post: axiosClient.post.bind(axiosClient),
  put: axiosClient.put.bind(axiosClient),
  delete: axiosClient.delete.bind(axiosClient),
  patch: axiosClient.patch.bind(axiosClient),
  ...auth,
  ...production,
  ...kpi,
  ...dataEntry,
  ...reports,
  ...reference,
  ...admin,
  ...preferences,
  ...qr,
  ...predictions,
  ...workOrders,
  ...myShift,
  ...workflow,
  ...simulation,
  ...productionLines,
  ...planVsActual,
  ...csvExport,
  ...onboarding,
  capacityPlanning,
}
