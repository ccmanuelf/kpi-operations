import { describe, it, expect } from 'vitest'
import { buildMd3Theme, contrastRatio } from '../md3Tonal'
import { carbonSeeds } from '../carbonSeeds'

describe('md3Tonal', () => {
  it('derives light + dark role tokens for every seed', () => {
    const light = buildMd3Theme('light')
    const dark = buildMd3Theme('dark')
    for (const t of [light, dark]) {
      expect(t.colors.primary).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(t.colors['on-primary']).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(t.colors.surface).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(t.colors.error).toMatch(/^#[0-9a-fA-F]{6}$/)
    }
    expect(light.dark).toBe(false)
    expect(dark.dark).toBe(true)
  })

  it('keeps the Carbon primary recognizable in the seed (blue dominant)', () => {
    // The derived primary need not equal the seed exactly (MD3 tonal), but must
    // stay in the Carbon blue family — assert it is bluish, not drifted to another hue.
    const { colors } = buildMd3Theme('light')
    const r = parseInt(colors.primary.slice(1, 3), 16)
    const b = parseInt(colors.primary.slice(5, 7), 16)
    expect(b).toBeGreaterThan(r) // blue dominant
  })

  it('on-* roles meet WCAG AA (>=4.5) against their backgrounds, light + dark', () => {
    for (const mode of ['light', 'dark'] as const) {
      const c = buildMd3Theme(mode).colors
      expect(contrastRatio(c['on-primary'], c.primary)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(c['on-surface'], c.surface)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(c['on-error'], c.error)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('exposes the seeds it was built from', () => {
    expect(Object.keys(carbonSeeds)).toContain('primary')
  })
})
