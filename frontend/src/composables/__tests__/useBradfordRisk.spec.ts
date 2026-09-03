import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  bradfordBand,
  bradfordAlertLevel,
  bradfordChipColor,
  MEDIUM_RISK_ABOVE,
  HIGH_RISK_ABOVE,
  CRITICAL_ABOVE,
} from '../useBradfordRisk'

describe('Bradford Factor risk banding', () => {
  it('classifies the two scores the old thresholds got wrong', () => {
    // The regression this exists for. The widget carried 50/200/400, so it
    // read 150 as "Monitor" where the server says formal action is required,
    // and 300 as "Action Required" where the server says final warning. Both
    // errors under-reported the risk.
    expect(bradfordBand(150)).toBe('actionRequired')
    expect(bradfordBand(300)).toBe('critical')
  })

  it('bands each boundary on the side the server puts it', () => {
    // The server uses strict `>` at each threshold, so the boundary value
    // itself stays in the LOWER band.
    expect(bradfordBand(50)).toBe('lowRisk')
    expect(bradfordBand(51)).toBe('monitor')
    expect(bradfordBand(125)).toBe('monitor')
    expect(bradfordBand(126)).toBe('actionRequired')
    expect(bradfordBand(250)).toBe('actionRequired')
    expect(bradfordBand(251)).toBe('critical')
    expect(bradfordBand(0)).toBe('lowRisk')
  })

  it('colours escalate with the band and never disagree with it', () => {
    const pairs: Array<[number, string, string]> = [
      [10, 'normal', 'success'],
      [100, 'warning', 'warning'],
      [200, 'orange', 'orange'],
      [500, 'error', 'error'],
    ]
    for (const [score, alert, chip] of pairs) {
      expect(bradfordAlertLevel(score)).toBe(alert)
      expect(bradfordChipColor(score)).toBe(chip)
    }
  })

  it('the thresholds are the ones the backend actually applies', () => {
    // Two-sided against the source of truth rather than against a copy of it.
    // The frontend cannot import Python, so this reads the route and asserts
    // the same numbers appear in its comparisons. If someone retunes the
    // server bands, this fails here instead of the UI quietly under-reporting
    // risk again.
    const routePath = resolve(__dirname, '../../../../backend/routes/attendance.py')
    const src = readFileSync(routePath, 'utf-8')
    const bands = src.slice(src.indexOf('interpretation = "Low risk"'))
    expect(bands).toContain(`if score > ${CRITICAL_ABOVE}:`)
    expect(bands).toContain(`elif score > ${HIGH_RISK_ABOVE}:`)
    expect(bands).toContain(`elif score > ${MEDIUM_RISK_ABOVE}:`)
  })
})
