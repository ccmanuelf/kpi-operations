// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { contrastRatio } from '../md3Tonal'

// WCAG-AA contrast gate for the Carbon design tokens (carbon-tokens.css).
//
// This is the deterministic CI half of the a11y story: it locks the color
// *contracts* the app depends on — every brand/status text token must clear
// 4.5:1 on the surfaces it lands on, and every solid brand/status background
// must clear 4.5:1 against the on-color we pair it with — in BOTH themes.
// (The exhaustive per-screen DOM sweep lives in the on-demand browser harness
// under frontend/.visual-baseline/; this spec is what guards CI.)
//
// It reads the real CSS so it can never drift from the source: change a token
// to a non-AA value and this test fails.

const css = readFileSync(
  fileURLToPath(new URL('../../assets/carbon-tokens.css', import.meta.url)),
  'utf-8',
)

/** Extract the `--name: value;` declarations from the first block matching `selector`. */
function block(selector: RegExp): Record<string, string> {
  const m = css.match(selector)
  if (!m) throw new Error(`token block not found: ${selector}`)
  const out: Record<string, string> = {}
  for (const decl of m[1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    out[decl[1]] = decl[2].trim()
  }
  return out
}

/** Resolve a value through any var() indirection into a concrete #rrggbb. */
function resolve(value: string, map: Record<string, string>, depth = 0): string {
  if (depth > 10) throw new Error(`var() cycle resolving ${value}`)
  const v = value.trim()
  const ref = v.match(/^var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)$/)
  if (ref) {
    const target = map[ref[1]] ?? ref[2]
    if (target == null) throw new Error(`unresolved var ${ref[1]}`)
    return resolve(target, map, depth + 1)
  }
  return v
}

const lightRaw = block(/:root\s*\{([^}]*)\}/)
const darkRaw = block(/\[data-theme="dark"\]\s*\{([^}]*)\}/)
// Dark only redefines a subset; unredefined tokens fall through to :root.
const darkRaw_merged = { ...lightRaw, ...darkRaw }

const light = (name: string) => resolve(`var(${name})`, lightRaw)
const dark = (name: string) => resolve(`var(${name})`, darkRaw_merged)

/** A literal on-color used in the main.css `overrides` layer / on solid surfaces. */
const WHITE = '#ffffff'
const NEAR_BLACK = '#161616'

describe('Carbon token WCAG-AA contrast contracts', () => {
  it('light theme: brand/status text is AA on its surfaces', () => {
    const bg = light('--cds-background') // #ffffff
    const layer = light('--cds-layer-01') // #f4f4f4 (off-white worst case)
    const pass = (fg: string, on: string) => expect(contrastRatio(fg, on)).toBeGreaterThanOrEqual(4.5)

    pass(light('--cds-text-primary'), bg)
    pass(light('--cds-text-secondary'), bg)
    pass(light('--cds-text-secondary'), layer)
    pass(light('--cds-text-warning'), bg) // amber, not the unreadable yellow
    pass(light('--cds-text-warning'), layer)
    pass(light('--cds-link-primary'), bg) // text-primary utility
    pass(light('--cds-link-primary'), layer)
    pass(light('--cds-support-error'), bg) // text-danger / text-error
    pass(light('--cds-text-error'), bg)
    pass(light('--cds-text-error'), layer)
    pass(light('--cds-support-success'), bg) // text-success
  })

  it('light theme: solid brand/status backgrounds carry an AA on-color', () => {
    expect(contrastRatio(WHITE, light('--cds-interactive'))).toBeGreaterThanOrEqual(4.5) // .bg-primary
    expect(contrastRatio(NEAR_BLACK, light('--cds-support-warning'))).toBeGreaterThanOrEqual(4.5) // .bg-warning
  })

  it('dark theme: brand/status text is AA on its surfaces', () => {
    const bg = dark('--cds-background') // #161616
    const layer = dark('--cds-layer-02') // #393939 (lightest dark surface = worst case)
    const pass = (fg: string, on: string) => expect(contrastRatio(fg, on)).toBeGreaterThanOrEqual(4.5)

    pass(dark('--cds-text-primary'), bg)
    pass(dark('--cds-text-primary'), layer)
    pass(dark('--cds-text-secondary'), layer)
    pass(dark('--cds-text-warning'), layer) // bright yellow is fine on dark
    pass(dark('--cds-link-primary'), bg)
    pass(dark('--cds-link-primary'), layer)
    pass(dark('--cds-support-error'), layer)
    pass(dark('--cds-text-error'), bg)
    pass(dark('--cds-text-error'), layer)
    pass(dark('--cds-support-success'), layer)
  })

  it('dark theme: solid brand/status backgrounds carry an AA on-color', () => {
    expect(contrastRatio(WHITE, dark('--cds-interactive'))).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(NEAR_BLACK, dark('--cds-support-warning'))).toBeGreaterThanOrEqual(4.5)
  })

  it('error text is AA on the tinted alert chip, not just on plain surfaces', () => {
    // The regression this token was added for. support-error is AA on white
    // (5.00) and passed every check here, yet rendered at 3.95 on the alert
    // dashboard: the urgent chip paints rgba(220,38,38,0.1) behind the text,
    // and no surface in this file models that. These two literals are the
    // composited backgrounds the browser gate actually measured.
    const LIGHT_URGENT_CHIP = '#f8e4e3' // 10% red over white
    const DARK_URGENT_CHIP = '#382626' // 10% red over layer-01
    // `.stat .label` carries opacity 0.8, which composites the text toward the
    // chip and costs real contrast: red-40 measures 6.01 solid on the dark chip
    // but only 4.39 composited. Checking the solid colour alone reported a pass
    // for a label that renders below AA.
    const LABEL_OPACITY = 0.8
    const over = (fg: string, alpha: number, bg: string): string => {
      const ch = (hex: string, i: number) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16)
      const mix = (i: number) => Math.round(ch(fg, i) * alpha + ch(bg, i) * (1 - alpha))
      return '#' + [0, 1, 2].map((i) => mix(i).toString(16).padStart(2, '0')).join('')
    }
    expect(contrastRatio(light('--cds-support-error'), LIGHT_URGENT_CHIP)).toBeLessThan(4.5)
    expect(
      contrastRatio(over(light('--cds-text-error'), LABEL_OPACITY, LIGHT_URGENT_CHIP), LIGHT_URGENT_CHIP),
    ).toBeGreaterThanOrEqual(4.5)
    expect(
      contrastRatio(over(dark('--cds-text-error'), LABEL_OPACITY, DARK_URGENT_CHIP), DARK_URGENT_CHIP),
    ).toBeGreaterThanOrEqual(4.5)
  })

  it('the warning text token is theme-aware (amber on light, brighter on dark)', () => {
    // Guards the specific regression that started this sweep: warning rendered
    // as raw Carbon yellow text (1.68:1 on white).
    expect(light('--cds-text-warning')).not.toBe(light('--cds-support-warning'))
    expect(contrastRatio(light('--cds-text-warning'), '#ffffff')).toBeGreaterThanOrEqual(4.5)
  })
})
