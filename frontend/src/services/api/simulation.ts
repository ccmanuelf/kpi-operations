import api from './client'

// The legacy Simulation V1 client functions (/simulation/*) were removed with
// the V1 API (Run 7 M-3). Simulation lives in simulationV2.ts; this module
// only retains the floating-pool insights call, which targets the separate
// /floating-pool router.

export const getFloatingPoolSimulationInsights = (params?: { target_date?: string }) =>
  api.get('/floating-pool/simulation/insights', { params })
