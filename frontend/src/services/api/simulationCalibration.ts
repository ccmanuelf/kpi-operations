/**
 * D4 — Historical calibration API client.
 *
 * Pre-fills a SimulationConfig from the platform's own production /
 * quality / downtime history. The UI exposes this as a "Pre-fill from
 * history" button on the Simulation V2 workbench: the planner picks
 * a client + period, the backend returns a config dict + per-field
 * provenance, and the form populates from it.
 *
 * The response intentionally mirrors the backend Pydantic model
 * (`backend/schemas/simulation_calibration.py`). The `config` is
 * treated as opaque on this layer — the workbench validates it on
 * "Run".
 */

import api from './client'
import type { SimulationConfig } from './simulationV2'

export interface CalibrationSource {
  source: string
  sample_size: number
  period: string
  /** "high" | "medium" | "low" | "none" — confidence chips key on this. */
  confidence: 'high' | 'medium' | 'low' | 'none' | string
}

export interface CalibrationPeriod {
  start: string
  end: string
  days: number
}

export interface CalibrationResponse {
  client_id: string
  period: CalibrationPeriod
  config: SimulationConfig
  /** Keyed by dotted field path (e.g. "products.Polo Shirt", "schedule"). */
  sources: Record<string, CalibrationSource>
  warnings: string[]
}

export interface CalibrateOptions {
  client_id: string
  /** ISO date (YYYY-MM-DD). Optional — defaults server-side to -30d. */
  period_start?: string
  /** ISO date (YYYY-MM-DD). Optional — defaults server-side to today. */
  period_end?: string
}

export const calibrateFromHistory = async (
  opts: CalibrateOptions,
): Promise<CalibrationResponse> => {
  const params: Record<string, unknown> = { client_id: opts.client_id }
  if (opts.period_start) params.period_start = opts.period_start
  if (opts.period_end) params.period_end = opts.period_end
  const response = await api.get('/v2/simulation/calibration', { params })
  return response.data
}

export default {
  calibrateFromHistory,
}
