// Re-export the base axios client
export { default as api, api as axiosInstance } from './client'

// Re-export all domain modules
export * from './auth'
export * from './production'
export * from './kpi'
export * from './dataEntry'
export * from './reports'
export * from './reference'
export * from './admin'
export * from './preferences'
export * from './qr'
export * from './predictions'
export * from './workOrders'
export * from './myShift'

// Import all modules for default export object
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

// Default export object with all methods for backward compatibility
// This allows: import api from '@/services/api' + api.login(...)
export default {
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
  ...myShift
}
