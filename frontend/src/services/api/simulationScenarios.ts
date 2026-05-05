/**
 * D3 — SimulationScenario API service.
 *
 * Persistent scenarios for SimPy V2 + MiniZinc. Save the current
 * SimulationConfig under a name; load it back into the workbench;
 * run a saved scenario and have the result summary pinned on the
 * record so the list view can show throughput/coverage at a glance.
 *
 * All endpoints are tenant-scoped server-side; this client is dumb
 * about tenancy.
 */

import api from './client'
import type { SimulationConfig } from './simulationV2'

export interface ScenarioRunSummary {
  daily_throughput_pcs: number | null
  daily_demand_pcs: number | null
  daily_coverage_pct: number | null
  avg_cycle_time_min: number | null
  avg_wip_pcs: number | null
  duration_seconds: number | null
}

export interface ScenarioSummary {
  id: number
  client_id: string | null
  name: string
  description: string | null
  last_run_summary: ScenarioRunSummary | null
  last_run_at: string | null
  tags: string[] | null
  is_active: boolean
  created_by: string | null
  created_at: string
  updated_at: string | null
}

export interface ScenarioFull extends ScenarioSummary {
  config_json: SimulationConfig
  updated_by: string | null
}

export interface ScenarioCreatePayload {
  name: string
  description?: string | null
  client_id?: string | null
  config_json: SimulationConfig
  tags?: string[] | null
}

export interface ScenarioUpdatePayload {
  name?: string
  description?: string | null
  config_json?: SimulationConfig
  tags?: string[] | null
  is_active?: boolean
}

const BASE = '/v2/simulation/scenarios'

export const listScenarios = async (
  opts: { include_inactive?: boolean; client_id?: string | null; skip?: number; limit?: number } = {},
): Promise<ScenarioSummary[]> => {
  const params: Record<string, unknown> = {}
  if (opts.include_inactive) params.include_inactive = true
  if (opts.client_id) params.client_id = opts.client_id
  if (opts.skip != null) params.skip = opts.skip
  if (opts.limit != null) params.limit = opts.limit
  const response = await api.get(BASE, { params })
  return response.data
}

export const getScenario = async (id: number): Promise<ScenarioFull> => {
  const response = await api.get(`${BASE}/${id}`)
  return response.data
}

export const createScenario = async (payload: ScenarioCreatePayload): Promise<ScenarioFull> => {
  const body: Record<string, unknown> = {
    name: payload.name,
    config_json: payload.config_json,
  }
  if (payload.description != null) body.description = payload.description
  if (payload.client_id !== undefined) body.client_id = payload.client_id
  if (payload.tags != null) body.tags = payload.tags
  const response = await api.post(BASE, body)
  return response.data
}

export const updateScenario = async (
  id: number,
  payload: ScenarioUpdatePayload,
): Promise<ScenarioFull> => {
  const response = await api.put(`${BASE}/${id}`, payload)
  return response.data
}

export const deleteScenario = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/${id}`)
}

export const duplicateScenario = async (id: number, newName?: string): Promise<ScenarioFull> => {
  const params: Record<string, unknown> = {}
  if (newName) params.new_name = newName
  const response = await api.post(`${BASE}/${id}/duplicate`, null, { params })
  return response.data
}

export const runScenario = async (id: number): Promise<ScenarioFull> => {
  const response = await api.post(`${BASE}/${id}/run`)
  return response.data
}

export default {
  listScenarios,
  getScenario,
  createScenario,
  updateScenario,
  deleteScenario,
  duplicateScenario,
  runScenario,
}
