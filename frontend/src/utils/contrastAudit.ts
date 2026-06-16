// Pure WCAG-AA contrast logic for the a11y e2e gate. All math runs in Node from
// raw samples collected in-page (e2e/a11y/collectSamples.ts) — no in-page math,
// no duplication. Mirrors the gradient-aware audit proven during the Vuetify 4
// migration. See docs/superpowers/specs/2026-06-15-a11y-contrast-e2e-gate-design.md.

export interface Rgb {
  r: number
  g: number
  b: number
  a: number
}

export interface Sample {
  screen: string
  theme: 'light' | 'dark'
  text: string
  cls: string
  color: string // computed CSS color of the text
  fontSize: number // px
  fontWeight: number
  bgStack: string[] // ancestor backgroundColors, nearest-first
  gradientStops: string[] // colors from any ancestor background-image gradient
}

export interface Violation extends Sample {
  ratio: number
  threshold: number
  bgUsed: string
}

export interface AllowEntry {
  screen: string
  classIncludes: string
  text: string // substring match
  reason: string
}

export function parseColor(c: string | null | undefined): Rgb | null {
  if (!c) return null
  const s = c.trim()
  if (s === 'transparent') return { r: 0, g: 0, b: 0, a: 0 }
  if (s.startsWith('color(')) {
    const m = s.match(/[\d.]+/g)
    if (!m || m.length < 3) return null
    return { r: +m[0] * 255, g: +m[1] * 255, b: +m[2] * 255, a: m[3] === undefined ? 1 : +m[3] }
  }
  if (s.startsWith('rgb')) {
    const m = s.match(/[\d.]+/g)
    if (!m) return null
    return { r: +m[0], g: +m[1], b: +m[2], a: m[3] === undefined ? 1 : +m[3] }
  }
  if (s.startsWith('#')) {
    let h = s.slice(1)
    if (h.length === 3) h = h.split('').map((x) => x + x).join('')
    if (h.length < 6) return null
    return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: 1 }
  }
  return null // unknown (e.g. oklch) — skip rather than miscompute
}

function composite(fg: Rgb, bg: Rgb): Rgb {
  return {
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  }
}

function luminance(c: Rgb): number {
  const f = (v: number) => {
    v /= 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
}

export function ratio(a: Rgb, b: Rgb): number {
  const la = luminance(a)
  const lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

export function isLargeText(fontSizePx: number, fontWeight: number): boolean {
  return fontSizePx >= 24 || (fontSizePx >= 18.66 && fontWeight >= 700)
}

// Composite the ancestor background stack (nearest-first) over white.
function effectiveBg(bgStack: string[]): Rgb {
  const parsed = bgStack.map(parseColor).filter((c): c is Rgb => !!c && c.a > 0)
  let acc: Rgb = { r: 255, g: 255, b: 255, a: 1 }
  for (let i = parsed.length - 1; i >= 0; i--) acc = composite(parsed[i], acc)
  return acc
}

export function findViolations(samples: Sample[], allow: AllowEntry[]): Violation[] {
  const out: Violation[] = []
  for (const s of samples) {
    const fg = parseColor(s.color)
    if (!fg) continue
    const solidBg = effectiveBg(s.bgStack)
    // gradient-aware: an ancestor gradient paints OVER the solid backgroundColor,
    // so when gradient stops exist they ARE the visible background — evaluate
    // worst-case across the stops; otherwise use the composited solid bg.
    const stops = s.gradientStops.map(parseColor).filter((c): c is Rgb => !!c && c.a > 0)
    const candidates: Rgb[] = stops.length ? stops : [solidBg]
    let worst = Infinity
    let bgUsed = solidBg
    for (const cand of candidates) {
      const eff = fg.a < 1 ? composite(fg, cand) : fg
      const r = ratio(eff, cand)
      if (r < worst) {
        worst = r
        bgUsed = cand
      }
    }
    const threshold = isLargeText(s.fontSize, s.fontWeight) ? 3 : 4.5
    if (worst < threshold - 0.01) {
      const allowed = allow.some(
        (a) => a.screen === s.screen && s.cls.includes(a.classIncludes) && s.text.includes(a.text),
      )
      if (!allowed) {
        out.push({
          ...s,
          ratio: +worst.toFixed(2),
          threshold,
          bgUsed: `rgb(${Math.round(bgUsed.r)},${Math.round(bgUsed.g)},${Math.round(bgUsed.b)})`,
        })
      }
    }
  }
  return out
}
