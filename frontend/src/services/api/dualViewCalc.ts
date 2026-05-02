/**
 * On-demand dual-view calculation API client — Phase 4c.
 *
 * Wraps POST /api/metrics/calculate/{oee,otd,fpy}. The frontend supplies
 * the raw aggregates (typically derived from the current dashboard state);
 * the backend runs both standard and site_adjusted modes, persists a
 * METRIC_CALCULATION_RESULT row, and returns the new `result_id`. The
 * inspector then loads that row via getMetricLineage.
 */

import api from './client'

export interface DualViewCalculateResponse {
  result_id: number
  metric_name: string
  standard_value: string
  site_adjusted_value: string
  delta: number | null
  delta_pct: number | null
  assumptions_applied_count: number
}

// ---------------------------------------------------------------------- OEE

export interface OEERawInputsPayload {
  scheduled_hours: string | number
  downtime_hours: string | number
  setup_minutes?: string | number
  scheduled_maintenance_hours?: string | number
  units_produced: number
  run_time_hours: string | number
  ideal_cycle_time_hours: string | number
  rolling_90_day_cycle_time_hours?: string | number | null
  demonstrated_best_cycle_time_hours?: string | number | null
  defect_count: number
  scrap_count: number
  units_reworked?: number
}

export interface CalculateOEERequest {
  client_id: string
  period_start: string  // ISO-8601
  period_end: string
  raw_inputs: OEERawInputsPayload
}

export const calculateOEE = (body: CalculateOEERequest) =>
  api.post<DualViewCalculateResponse>('/metrics/calculate/oee', body)

// ---------------------------------------------------------------------- OTD

export interface OrderDelay {
  delay_pct: string | number
}

export interface OTDRawInputsPayload {
  orders: OrderDelay[]
}

export interface CalculateOTDRequest {
  client_id: string
  period_start: string
  period_end: string
  raw_inputs: OTDRawInputsPayload
}

export const calculateOTD = (body: CalculateOTDRequest) =>
  api.post<DualViewCalculateResponse>('/metrics/calculate/otd', body)

// ---------------------------------------------------------------------- FPY

export interface FPYRawInputsPayload {
  total_inspected: number
  units_passed_first_time: number
  units_reworked?: number
}

export interface CalculateFPYRequest {
  client_id: string
  period_start: string
  period_end: string
  raw_inputs: FPYRawInputsPayload
}

export const calculateFPY = (body: CalculateFPYRequest) =>
  api.post<DualViewCalculateResponse>('/metrics/calculate/fpy', body)

// ----------------------------------------------- F.1 from-period variants

/**
 * Aggregate raw inputs from production data + run dual-view calculation in
 * one round-trip. Replaces the Phase 4c sample-input demo path with real
 * aggregates pulled from ProductionEntry / DowntimeEntry / QualityEntry /
 * WorkOrder.
 */

export interface CalculateFromPeriodRequest {
  client_id: string
  period_start: string  // ISO-8601
  period_end: string
}

export const calculateOEEFromPeriod = (body: CalculateFromPeriodRequest) =>
  api.post<DualViewCalculateResponse>('/metrics/calculate/from-period/oee', body)

export const calculateOTDFromPeriod = (body: CalculateFromPeriodRequest) =>
  api.post<DualViewCalculateResponse>('/metrics/calculate/from-period/otd', body)

export const calculateFPYFromPeriod = (body: CalculateFromPeriodRequest) =>
  api.post<DualViewCalculateResponse>('/metrics/calculate/from-period/fpy', body)
