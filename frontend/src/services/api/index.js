// Re-export the base axios client
import axiosClient from './client'
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
export * from './alerts'
export * from './workflow'
export * from './simulation'

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
import * as alerts from './alerts'
import * as workflow from './workflow'
import * as simulation from './simulation'

// Default export object with all methods for backward compatibility
// This allows: import api from '@/services/api' + api.login(...)
// Also includes axios methods (get, post, put, delete) for direct API calls
export default {
  // Axios instance methods for direct API calls
  get: axiosClient.get.bind(axiosClient),
  post: axiosClient.post.bind(axiosClient),
  put: axiosClient.put.bind(axiosClient),
  delete: axiosClient.delete.bind(axiosClient),
  patch: axiosClient.patch.bind(axiosClient),
  // All domain-specific functions
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
  ...alerts,
  ...workflow,
  ...simulation
}
