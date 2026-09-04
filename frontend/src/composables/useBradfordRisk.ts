/**
 * Bradford Factor risk banding — the SERVER's bands, in one place.
 *
 * `backend/routes/attendance.py::get_bradford_factor` classifies a score as
 * >250 critical, >125 high, >50 medium, else low, and returns that wording as
 * `interpretation`. The widget carried its own copy at 50/200/400, which
 * disagreed by roughly one band in the dangerous direction: a score of 150 is
 * "formal action required" server-side and read as "Monitor" on screen; 300 is
 * "final warning/termination" server-side and read as merely "Action
 * Required". Bradford drives absence discipline, so under-reporting it is the
 * costly direction to be wrong in.
 *
 * Extracted from the SFC because `<script setup>` internals are not reachable
 * through a VTU wrapper, so a copy living inside the component could not be
 * unit-tested and drifted unnoticed.
 */

/** Above this, the server stops calling the score low risk. */
export const MEDIUM_RISK_ABOVE = 50
/** Above this, the server escalates from medium to high. */
export const HIGH_RISK_ABOVE = 125
/** Above this, the server escalates from high to critical. */
export const CRITICAL_ABOVE = 250

export type BradfordBand = 'lowRisk' | 'monitor' | 'actionRequired' | 'critical'

/** The band a score falls in, using the server's boundaries. */
export function bradfordBand(score: number): BradfordBand {
  if (score <= MEDIUM_RISK_ABOVE) return 'lowRisk'
  if (score <= HIGH_RISK_ABOVE) return 'monitor'
  if (score <= CRITICAL_ABOVE) return 'actionRequired'
  return 'critical'
}

/** Vuetify colour for a band. `normal` means "no alert colour". */
export function bradfordAlertLevel(score: number): 'normal' | 'warning' | 'orange' | 'error' {
  const band = bradfordBand(score)
  if (band === 'lowRisk') return 'normal'
  if (band === 'monitor') return 'warning'
  if (band === 'actionRequired') return 'orange'
  return 'error'
}

/** Text colour class for a band. */
export function bradfordTextClass(
  score: number,
): 'text-success' | 'text-warning' | 'text-orange' | 'text-error' {
  const band = bradfordBand(score)
  if (band === 'lowRisk') return 'text-success'
  if (band === 'monitor') return 'text-warning'
  if (band === 'actionRequired') return 'text-orange'
  return 'text-error'
}

/**
 * Card tint, or undefined below the action threshold.
 *
 * Only the two escalated bands tint the card — matching the original
 * intent, which drew nothing for low risk and monitor.
 */
export function bradfordCardBackground(score: number): string | undefined {
  const band = bradfordBand(score)
  if (band === 'critical') return 'error-lighten-5'
  if (band === 'actionRequired') return 'orange-lighten-5'
  return undefined
}

/**
 * The escalation banner's tri-state.
 *
 * The banner collapses the four bands into three: critical, high (the
 * action-required band), and elevated (everything below). Its type, icon,
 * title and message all key off this one function so they cannot drift.
 */
export type BradfordEscalation = 'critical' | 'high' | 'elevated'

export function bradfordEscalation(score: number): BradfordEscalation {
  const band = bradfordBand(score)
  if (band === 'critical') return 'critical'
  if (band === 'actionRequired') return 'high'
  return 'elevated'
}

/** v-alert type for the escalation banner. */
export function bradfordAlertType(score: number): 'info' | 'warning' | 'error' {
  const level = bradfordEscalation(score)
  if (level === 'critical') return 'error'
  if (level === 'high') return 'warning'
  return 'info'
}

/** Icon for the escalation banner. */
export function bradfordAlertIcon(score: number): string {
  const level = bradfordEscalation(score)
  if (level === 'critical') return 'mdi-alert-octagon'
  if (level === 'high') return 'mdi-alert'
  return 'mdi-information'
}

/** Chip colour for a band. */
export function bradfordChipColor(score: number): 'success' | 'warning' | 'orange' | 'error' {
  const band = bradfordBand(score)
  if (band === 'lowRisk') return 'success'
  if (band === 'monitor') return 'warning'
  if (band === 'actionRequired') return 'orange'
  return 'error'
}
