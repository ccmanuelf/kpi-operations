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

/** Chip colour for a band. */
export function bradfordChipColor(score: number): 'success' | 'warning' | 'orange' | 'error' {
  const band = bradfordBand(score)
  if (band === 'lowRisk') return 'success'
  if (band === 'monitor') return 'warning'
  if (band === 'actionRequired') return 'orange'
  return 'error'
}
