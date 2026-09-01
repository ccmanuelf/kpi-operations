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
  // Every background-image gradient found walking from the element outwards,
  // nearest-first, each tagged with the depth in `bgStack` of the node that
  // carries it. Depth is what makes a stop scoreable: it identifies the
  // surface the stop is painted ON, so a translucent stop can be composited
  // over it rather than mistaken for an opaque colour.
  gradients: GradientLayer[]
}

export interface GradientLayer {
  depth: number // index into bgStack of the node carrying this gradient
  stops: string[]
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

// Every background surface the text could be sitting on, so the caller can
// score the worst of them. Two rules decide what belongs in the list.
//
// PAINTING ORDER. Nearest surface first: a gradient paints over its own node's
// background-color, and an opaque background occludes everything behind it.
// An ANCESTOR gradient is therefore only visible when what is in front of it
// is see-through, and must not outrank the element's own surfaces. Getting
// this wrong is what made AG Grid v36 fail this gate: it paints
// `linear-gradient(#fff, #fff)` on `.ag-grid-pinned-right-cells`, so a
// white-on-red delete button in the pinned column was scored against those
// white stops and reported as white-on-white at ratio 1.
//
// COMPOSITING. A stop is a paint, not a surface. `rgba(0,0,0,.2)` over white
// looks light grey; scored as if it were opaque black it reads 21:1 against
// white text and a real failure passes. Every stop is composited over
// `effectiveBg(bgStack.slice(depth))` -- the surface beneath the node that
// carries it. This also handles fully transparent stops correctly: compositing
// one yields its base, which is exactly what shows through, so they no longer
// have to be discarded.
//
// KNOWN APPROXIMATION. `under` is built from background-COLORS only, so a
// translucent gradient stacked over ANOTHER gradient is composited over the
// solid stack rather than over the gradient beneath it. Modelling that needs a
// per-stop cross-product down the layers; it is not worth the complexity while
// a census of all 15 audited screens in both themes finds 172 gradient stops
// and not one translucent.
// A gradient renders every colour BETWEEN its stops, and contrast against it
// is NOT monotonic along the ramp, so the worst point can sit strictly between
// two stops -- and a fixed grid can step straight over it. Black text on
// `rgb(251,0,251) -> rgb(0,251,0)` reads >= 4.52 at every eighth of the way
// across, yet dips to 4.47 at t ~ 0.324, which is a real AA failure a
// stops-only or coarse-grid check passes.
//
// So: scan coarsely to bracket the dip, then refine inside that bracket by
// golden-section search, keeping the refined point only when it actually beats
// the scan. Relative luminance along a stop pair is convex (verified
// numerically over the ramp, minimum second difference 8.2e-07), but the
// contrast ratio built on it is not always unimodal, which is exactly why the
// refinement is guarded rather than trusted.
//
// This is a search, not a proof: no finite method can certify a global minimum
// over a continuum. It is strictly better than the grid alone and never worse.
const COARSE_STEPS = 24
const REFINE_ITERATIONS = 40
const INV_PHI = 0.6180339887498949

function mixRgb(from: Rgb, to: Rgb, t: number): Rgb {
  return {
    r: from.r + (to.r - from.r) * t,
    g: from.g + (to.g - from.g) * t,
    b: from.b + (to.b - from.b) * t,
    a: from.a + (to.a - from.a) * t,
  }
}

// The ratio the caller will compute for this background, replicated here so
// refinement optimises the same quantity rather than a proxy.
function contrastAgainst(fg: Rgb, bg: Rgb): number {
  return ratio(fg.a < 1 ? composite(fg, bg) : fg, bg)
}

// Worst-contrast point of one stop-to-stop segment, as an actual background
// colour. `paint` maps a raw stop colour to what is finally on screen
// (composited over what is behind, then tinted by the layers in front).
function worstPointOnSegment(
  from: Rgb,
  to: Rgb,
  fg: Rgb,
  paint: (_stop: Rgb) => Rgb,
): Rgb {
  const at = (t: number) => paint(mixRgb(from, to, t))
  let bestT = 0
  let best = Infinity
  for (let k = 0; k <= COARSE_STEPS; k++) {
    const t = k / COARSE_STEPS
    const r = contrastAgainst(fg, at(t))
    if (r < best) {
      best = r
      bestT = t
    }
  }
  // Refine within one coarse step either side of the best sample.
  //
  // Golden-section assumes a unimodal minimum, and the contrast RATIO is not
  // guaranteed to be one: where background luminance crosses the foreground's,
  // the ratio has two minima of 1 with a local maximum between them. So the
  // refined point is ACCEPTED ONLY IF IT BEATS the coarse scan, keeping the
  // search monotonically no worse than the grid it started from.
  //
  // Belt and braces rather than a fix for an observed failure: a 40k-case
  // random search over opaque stop pairs and foregrounds found a maximum
  // regression of 3e-6, i.e. float noise. The guard costs one comparison and
  // makes the property exact instead of merely almost always true.
  const step = 1 / COARSE_STEPS
  let lo = Math.max(0, bestT - step)
  let hi = Math.min(1, bestT + step)
  for (let i = 0; i < REFINE_ITERATIONS && hi - lo > 1e-6; i++) {
    const m1 = hi - (hi - lo) * INV_PHI
    const m2 = lo + (hi - lo) * INV_PHI
    if (contrastAgainst(fg, at(m1)) < contrastAgainst(fg, at(m2))) hi = m2
    else lo = m1
  }
  const refined = at((lo + hi) / 2)
  return contrastAgainst(fg, refined) < best ? refined : at(bestT)
}

function backgroundCandidates(s: Sample, solidBg: Rgb, fg: Rgb): Rgb[] {
  const byDepth = new Map((s.gradients ?? []).map((g) => [g.depth, g]))

  // Walk outwards and take the NEAREST painted surface -- the first gradient,
  // or the first opaque background-color, whichever comes first. At a given
  // node the gradient paints over that node's own background-color, so the
  // gradient is checked first.
  //
  // Only the nearest surface is scored. Offering deeper layers as extra
  // candidates would manufacture backgrounds the user never sees: a
  // `rgba(0,0,0,.8)` gradient over a white ancestor composites to a dark grey
  // that white text reads fine against, and separately scoring that white
  // would fail a control that renders correctly -- the same false positive
  // this checker was just fixed for.
  // Translucent background-colors NEARER than whatever the walk settles on are
  // painted in front of it and tint what the eye sees. `rgba(0,0,0,.8)` on the
  // element over a white parent is dark grey, not white, and white text on it
  // is perfectly readable -- returning the bare white would fail a correct
  // control.
  const overlayNearerLayers = (base: Rgb, depth: number): Rgb => {
    let acc = base
    for (let i = depth - 1; i >= 0; i--) {
      const c = parseColor(s.bgStack[i])
      if (c && c.a > 0) acc = composite(c, acc)
    }
    return acc
  }

  for (let d = 0; d < s.bgStack.length; d++) {
    const g = byDepth.get(d)
    if (g) {
      const under = effectiveBg(s.bgStack.slice(d))
      const stops = g.stops.map(parseColor).filter((c): c is Rgb => !!c)
      // No readable stop (oklch and friends) means this gradient contributes
      // nothing and the walk carries on; a gradient with SOME readable stops
      // is scored on those.
      if (stops.length) {
        const paint = (stop: Rgb) => overlayNearerLayers(composite(stop, under), d)
        // The stops themselves, plus the worst point inside each segment.
        const out = stops.map(paint)
        for (let i = 0; i < stops.length - 1; i++) {
          out.push(worstPointOnSegment(stops[i], stops[i + 1], fg, paint))
        }
        return out
      }
    }
    const bg = parseColor(s.bgStack[d])
    // `solidBg` is effectiveBg over the whole stack, which already composites
    // the nearer translucent layers onto this opaque one, so it is the answer
    // here rather than the bare colour.
    if (bg && bg.a >= 1) return [solidBg]
  }

  return [solidBg]
}

export function findViolations(samples: Sample[], allow: AllowEntry[]): Violation[] {
  const out: Violation[] = []
  for (const s of samples) {
    const fg = parseColor(s.color)
    if (!fg) continue
    const solidBg = effectiveBg(s.bgStack)
    const candidates = backgroundCandidates(s, solidBg, fg)
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
