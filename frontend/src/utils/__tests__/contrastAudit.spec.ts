import { describe, it, expect } from 'vitest'
import { parseColor, ratio, isLargeText, findViolations, type Sample } from '../contrastAudit'

describe('contrastAudit math', () => {
  it('parseColor handles rgb(), color(srgb 0-1), hex, transparent', () => {
    expect(parseColor('rgb(255, 255, 255)')).toEqual({ r: 255, g: 255, b: 255, a: 1 })
    expect(parseColor('rgba(0,0,0,0.5)')).toEqual({ r: 0, g: 0, b: 0, a: 0.5 })
    const c = parseColor('color(srgb 0.894118 0.886275 0.882353 / 0.6)')!
    expect(Math.round(c.r)).toBe(228)
    expect(c.a).toBeCloseTo(0.6)
    expect(parseColor('#0f62fe')).toEqual({ r: 15, g: 98, b: 254, a: 1 })
    expect(parseColor('transparent')).toEqual({ r: 0, g: 0, b: 0, a: 0 })
    expect(parseColor('oklch(0.5 0.1 200)')).toBeNull()
  })

  it('ratio matches known WCAG pairs', () => {
    expect(ratio({ r: 0, g: 0, b: 0, a: 1 }, { r: 255, g: 255, b: 255, a: 1 })).toBeCloseTo(21, 0)
    expect(ratio({ r: 255, g: 255, b: 255, a: 1 }, { r: 15, g: 98, b: 254, a: 1 })).toBeGreaterThan(4.5)
  })

  it('isLargeText: >=24px, or >=18.66px bold', () => {
    expect(isLargeText(24, 400)).toBe(true)
    expect(isLargeText(19, 700)).toBe(true)
    expect(isLargeText(16, 700)).toBe(false)
    expect(isLargeText(14, 400)).toBe(false)
  })

  it('findViolations flags below-AA, respects large-text threshold + gradients + allow-list', () => {
    const base = { fontWeight: 400, bgStack: ['rgb(255,255,255)'], gradientStops: [] as string[] }
    const samples: Sample[] = [
      { ...base, screen: 'x', theme: 'light', text: 'bad', cls: 'a', color: 'rgb(241,194,27)', fontSize: 14 },
      { ...base, screen: 'x', theme: 'light', text: 'ok', cls: 'b', color: 'rgb(22,22,22)', fontSize: 14 },
      { screen: 'y', theme: 'light', text: 'My Shift', cls: 'text-h5', color: 'rgb(255,255,255)', fontSize: 32, fontWeight: 600, bgStack: ['rgb(255,255,255)'], gradientStops: ['rgb(25,118,210)'] },
    ]
    const v = findViolations(samples, [])
    expect(v.map((x) => x.text)).toEqual(['bad'])
  })

  it('allow-list excludes a documented false-positive', () => {
    const samples: Sample[] = [
      { screen: 'my-shift', theme: 'light', text: 'Sunday, June 14', cls: 'text-body-2', color: 'rgb(255,255,255)', fontSize: 14, fontWeight: 400, bgStack: ['rgb(255,255,255)'], gradientStops: [] },
    ]
    expect(findViolations(samples, [])).toHaveLength(1)
    const allow = [{ screen: 'my-shift', classIncludes: 'text-body-2', text: 'Sunday', reason: 'on blue gradient banner' }]
    expect(findViolations(samples, allow)).toHaveLength(0)
  })
})
