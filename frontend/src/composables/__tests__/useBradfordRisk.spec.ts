import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  bradfordBand,
  bradfordAlertLevel,
  bradfordChipColor,
  bradfordTextClass,
  bradfordCardBackground,
  bradfordAlertType,
  bradfordAlertIcon,
  bradfordEscalation,
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

// Found by the adversarial cross-model review: three computeds moved to the
// server's bands and four did not, so one score was coloured two ways in the
// same widget — 150 was an orange chip on a warning bar, 300 an error chip on
// an orange bar. Both disagreements under-reported, the costly direction.
describe('every band-derived helper uses the SAME boundaries', () => {
  const helpers = [
    bradfordAlertLevel,
    bradfordChipColor,
    bradfordTextClass,
    bradfordAlertType,
    bradfordAlertIcon,
    bradfordEscalation,
  ]

  // Two-sided: each helper must give the SAME answer everywhere inside a band
  // and a DIFFERENT one across the boundary. The scores are picked to sit in
  // the gap between the server's bands and the stale 50/200/400 copy, so a
  // helper left on the old numbers groups 150 with 100, or 300 with 200, and
  // fails the second assertion.
  it.each([
    [150, 200, 100, 'actionRequired', 'above HIGH_RISK_ABOVE, below the old 200'],
    [300, 500, 200, 'critical', 'above CRITICAL_ABOVE, below the old 400'],
  ])('classifies %i consistently (%s)', (score, sameBand, otherBand, expectedBand) => {
    expect(bradfordBand(score)).toBe(expectedBand)
    expect(bradfordBand(sameBand)).toBe(expectedBand)
    expect(bradfordBand(otherBand)).not.toBe(expectedBand)

    for (const fn of helpers) {
      expect(fn(score), `${fn.name} disagrees within the band`).toBe(fn(sameBand))
      expect(fn(score), `${fn.name} does not separate the bands`).not.toBe(fn(otherBand))
    }
  })

  it('tints the card only from the action band up', () => {
    expect(bradfordCardBackground(10)).toBeUndefined()
    expect(bradfordCardBackground(100)).toBeUndefined()
    expect(bradfordCardBackground(150)).toBe('orange-lighten-5')
    expect(bradfordCardBackground(300)).toBe('error-lighten-5')
  })
})
