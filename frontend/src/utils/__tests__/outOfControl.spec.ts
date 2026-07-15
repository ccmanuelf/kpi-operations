import { describe, it, expect } from 'vitest'
import { computeOutOfControl } from '../outOfControl'

const pts = (vals: number[]) => vals.map((v, i) => ({ date: `2026-06-${(i + 1).toString().padStart(2, '0')}`, value: v }))

describe('computeOutOfControl', () => {
  it('threshold arm (higher-is-better): flags below critical', () => {
    const r = computeOutOfControl(pts([90, 55, 88]), { critical: 60, higher_is_better: true })
    expect(r.points.map((p) => p.ooc)).toEqual([false, true, false])
    expect(r.points[1].reasons[0].key).toContain('belowCritical')
  })

  it('threshold arm (lower-is-better): flags above critical', () => {
    const r = computeOutOfControl(pts([5000, 21000, 4000]), { critical: 20000, higher_is_better: false })
    expect(r.points.map((p) => p.ooc)).toEqual([false, true, false])
    expect(r.points[1].reasons[0].key).toContain('aboveCritical')
  })

  it('SPC arm: flags points beyond ±3σ when >= 8 points', () => {
    // 8 points ~84 with one outlier at 20
    const r = computeOutOfControl(pts([84, 85, 83, 86, 84, 85, 20, 84]), null)
    expect(r.ucl).not.toBeNull()
    expect(r.points[6].ooc).toBe(true)
    expect(r.points[6].reasons[0].key).toContain('beyondLcl')
  })

  it('degrades: < 8 points and no threshold -> no flags, no SPC limits', () => {
    const r = computeOutOfControl(pts([84, 20, 85]), null)
    expect(r.ucl).toBeNull()
    expect(r.points.every((p) => !p.ooc)).toBe(true)
  })

  it('flat series (sd=0) -> no SPC flags', () => {
    const r = computeOutOfControl(pts([80, 80, 80, 80, 80, 80, 80, 80]), null)
    expect(r.points.every((p) => !p.ooc)).toBe(true)
  })

  it('union: point flagged by either arm; reasons accumulate', () => {
    const r = computeOutOfControl(pts([84, 85, 83, 86, 84, 85, 40, 84]), { critical: 60, higher_is_better: true })
    expect(r.points[6].ooc).toBe(true)
    expect(r.points[6].reasons.length).toBeGreaterThanOrEqual(1)
  })

  it('ignores non-finite values without throwing', () => {
    const r = computeOutOfControl([{ date: 'x', value: NaN }, ...pts([84, 85])], { critical: 60, higher_is_better: true })
    expect(r.points[0].ooc).toBe(false)
  })
})
