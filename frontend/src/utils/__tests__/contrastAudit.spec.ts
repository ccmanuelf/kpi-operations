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
    const base = { fontWeight: 400, bgStack: ['rgb(255,255,255)'], gradients: [] }
    const samples: Sample[] = [
      { ...base, screen: 'x', theme: 'light', text: 'bad', cls: 'a', color: 'rgb(241,194,27)', fontSize: 14 },
      { ...base, screen: 'x', theme: 'light', text: 'ok', cls: 'b', color: 'rgb(22,22,22)', fontSize: 14 },
      // Text over a blue gradient banner. The element itself is transparent
      // -- which is what collectSamples reports for banner text -- so the
      // ancestor gradient is what is actually visible behind it.
      { screen: 'y', theme: 'light', text: 'My Shift', cls: 'text-h5', color: 'rgb(255,255,255)', fontSize: 32, fontWeight: 600, bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'], gradients: [{ depth: 1, stops: ['rgb(25,118,210)'] }] },
    ]
    const v = findViolations(samples, [])
    expect(v.map((x) => x.text)).toEqual(['bad'])
  })

  // Regression: AG Grid v36 paints `linear-gradient(#fff, #fff)` on
  // `.ag-grid-pinned-right-cells`. Before the painting-order fix those white
  // stops replaced the delete button's own red background and the button was
  // reported as white-on-white at ratio 1, failing the WCAG-AA gate on a
  // control that renders correctly.
  it('an opaque background on the element itself outranks an ancestor gradient', () => {
    const deleteButton: Sample = {
      screen: 'work-orders',
      theme: 'light',
      text: '\u2715',
      cls: 'ag-grid-delete-btn',
      color: 'rgb(255,255,255)',
      fontSize: 12,
      fontWeight: 400,
      // nearest-first: the button's own red, then transparent wrappers, then
      // the pinned-column container that carries the white gradient.
      bgStack: ['rgb(198,40,40)', 'rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 2, stops: ['rgb(255,255,255)', 'rgb(255,255,255)'] }],
    }
    expect(findViolations([deleteButton], [])).toEqual([])
  })

  it("an element's OWN gradient still outranks its own background-color", () => {
    // White text on an element whose own gradient paints white over its own
    // red background-color IS unreadable -- the own-background rule must not
    // swallow this case.
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'invisible',
      cls: 'own-gradient',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgb(198,40,40)'],
      gradients: [{ depth: 0, stops: ['rgb(255,255,255)'] }],
    }
    expect(findViolations([sample], [])).toHaveLength(1)
  })

  it('a transparent element still resolves through to the ancestor gradient', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'on banner',
      cls: 'banner-text',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 1, stops: ['rgb(255,255,255)'] }],
    }
    // White on a white ancestor gradient is a real violation, still caught.
    expect(findViolations([sample], [])).toHaveLength(1)
  })

  // The false negative this compositing pass exists to close. A 20%-black
  // gradient over white LOOKS light grey; scored as though the stop were an
  // opaque black it reads 21:1 against white text and a real WCAG-AA failure
  // sails through.
  it('composites a translucent gradient stop over the surface beneath it', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'washed out',
      cls: 'translucent-overlay',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 1, stops: ['rgba(0,0,0,0.2)', 'rgba(0,0,0,0.2)'] }],
    }
    const [v] = findViolations([sample], [])
    expect(v).toBeDefined()
    // 20% black over white composites to ~rgb(204,204,204), not black.
    expect(v.bgUsed).toBe('rgb(204,204,204)')
    expect(v.ratio).toBeLessThan(2)
  })

  it('a fully transparent stop resolves to what shows through, not discarded', () => {
    // A `#000 -> transparent` gradient over a white ancestor: the transparent
    // end leaves white behind it, so white text there is unreadable. Dropping
    // zero-alpha stops used to hide exactly this.
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'fades out',
      cls: 'fade',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 1, stops: ['rgb(0,0,0)', 'rgba(0,0,0,0)'] }],
    }
    const [v] = findViolations([sample], [])
    expect(v).toBeDefined()
    expect(v.bgUsed).toBe('rgb(255,255,255)')
  })

  it('the nearest gradient is the visible surface; layers behind it are not scored', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'covered',
      cls: 'stacked',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [
        { depth: 1, stops: ['rgb(25,118,210)'] }, // opaque blue, nearest
        { depth: 2, stops: ['rgba(255,255,255,0.5)'] }, // behind it, invisible
      ],
    }
    // Scored against the blue only. The layer behind must not add a near-white
    // candidate: white text on this blue is fine, and flagging it would be the
    // same false positive that broke this gate on AG Grid v36.
    expect(findViolations([sample], [])).toEqual([])
  })

  it('a stop in an unreadable colour syntax falls through, it does not score wrong', () => {
    // parseColor returns null for oklch. The stop must not be treated as some
    // default colour -- with no readable stop the gradient contributes nothing
    // and the walk continues to the background-color behind it.
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'exotic',
      cls: 'oklch-gradient',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 0, stops: ['oklch(0.5 0.1 200)'] }],
    }
    const [v] = findViolations([sample], [])
    expect(v).toBeDefined()
    expect(v.bgUsed).toBe('rgb(255,255,255)')
  })

  // Regression for a false positive: a translucent background-color on the
  // element sits IN FRONT of the opaque one behind it, so the visible surface
  // is the composite, not the opaque layer. Returning the opaque white here
  // would flag white text that actually sits on dark grey.
  it('composites translucent background-colors in front of the opaque one', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'readable',
      cls: 'scrim',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0.8)', 'rgb(255,255,255)'],
      gradients: [],
    }
    // 80% black over white composites to ~rgb(51,51,51); white text on that
    // is ~13:1 and must NOT be reported.
    expect(findViolations([sample], [])).toEqual([])
  })

  it('composites translucent background-colors in front of a gradient too', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'tinted',
      cls: 'scrim-over-gradient',
      color: 'rgb(255,255,255)',
      fontSize: 14,
      fontWeight: 400,
      // element carries a heavy dark scrim; the white gradient is behind it
      bgStack: ['rgba(0,0,0,0.8)', 'rgba(0,0,0,0)'],
      gradients: [{ depth: 1, stops: ['rgb(255,255,255)'] }],
    }
    // White gradient, then the scrim painted over it -> dark. Scoring the
    // bare white stop would falsely flag this.
    expect(findViolations([sample], [])).toEqual([])
  })

  // A gradient's worst contrast can fall BETWEEN its stops. #767676 clears AA
  // at both ends of a black-to-white gradient -- 4.62:1 on black, 4.54:1 on
  // white -- and collapses to 1.15:1 against the mid grey. Scoring only the
  // stop colours passes this; sampling the segment catches it.
  // The counterexample that killed fixed-grid sampling. Black text on
  // magenta->green reads >= 4.52 at every eighth of the ramp -- so an
  // 8-sample grid passes it -- but the true minimum is 4.4666 at t ~ 0.3235,
  // a real AA failure. Verified numerically against a 200k-point scan.
  it('finds a dip a fixed sampling grid steps over', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'between samples',
      cls: 'magenta-green',
      color: 'rgb(0,0,0)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 1, stops: ['rgb(251,0,251)', 'rgb(0,251,0)'] }],
    }
    const [v] = findViolations([sample], [])
    expect(v).toBeDefined()
    expect(v.ratio).toBeLessThan(4.5)
    // `ratio` is rounded to 2dp, so it cannot tell a refined answer from a
    // merely-dense one -- both round to 4.47. The colour DOES distinguish
    // them: refinement lands on t~0.3235 -> rgb(170,81,170), while stopping
    // at the coarse grid lands on t=1/3 -> rgb(167,84,167). Asserting the
    // colour is what makes the refinement load-bearing.
    expect(v.bgUsed).toBe('rgb(170,81,170)')
  })

  it('catches a failure that occurs between two stops, not at either one', () => {
    const sample: Sample = {
      screen: 'x',
      theme: 'light',
      text: 'mid-gradient',
      cls: 'ramp',
      color: 'rgb(118,118,118)',
      fontSize: 14,
      fontWeight: 400,
      bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
      gradients: [{ depth: 1, stops: ['rgb(0,0,0)', 'rgb(255,255,255)'] }],
    }
    const [v] = findViolations([sample], [])
    expect(v).toBeDefined()
    expect(v.ratio).toBeLessThan(2)
  })

  // Invariant, not implementation: whatever search runs inside, the reported
  // ratio must never be WORSE than simply sampling the ramp on a grid. This
  // does not fail against today's code -- a 40k-case random search put the
  // largest regression at 3e-6 -- it exists so a future change to the search
  // (wider bracket, different algorithm) cannot silently start reporting a
  // rosier number than a plain grid already disproves.
  it('never reports a better ratio than a plain grid over the ramp finds', () => {
    // deterministic LCG; no Math.random, so failures are reproducible
    let seed = 0x2f6e2b1
    const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) % 256)
    let violationsSeen = 0
    for (let n = 0; n < 120; n++) {
      const from = { r: rnd(), g: rnd(), b: rnd(), a: 1 }
      const to = { r: rnd(), g: rnd(), b: rnd(), a: 1 }
      const fg = { r: rnd(), g: rnd(), b: rnd(), a: 1 }
      const css = (c: typeof from) => `rgb(${c.r},${c.g},${c.b})`
      const sample: Sample = {
        screen: 'x',
        theme: 'light',
        text: 'ramp',
        cls: 'r',
        color: css(fg),
        fontSize: 14,
        fontWeight: 400,
        // transparent element over white, opaque stops -> painted == stop
        bgStack: ['rgba(0,0,0,0)', 'rgb(255,255,255)'],
        gradients: [{ depth: 1, stops: [css(from), css(to)] }],
      }
      let gridWorst = Infinity
      for (let k = 0; k <= 24; k++) {
        const t = k / 24
        const mix = {
          r: from.r + (to.r - from.r) * t,
          g: from.g + (to.g - from.g) * t,
          b: from.b + (to.b - from.b) * t,
          a: 1,
        }
        gridWorst = Math.min(gridWorst, ratio(fg, mix))
      }
      const [v] = findViolations([sample], [])
      if (!v) {
        // no violation reported: the grid must agree nothing failed
        expect(gridWorst).toBeGreaterThanOrEqual(4.49)
        continue
      }
      violationsSeen++
      // +0.006 covers `ratio` being rounded to 2dp before it is reported
      expect(v.ratio).toBeLessThanOrEqual(gridWorst + 0.006)
    }
    // Guard against the test passing by never exercising the branch that
    // matters -- a sweep that silently checks nothing is worse than no sweep.
    expect(violationsSeen).toBeGreaterThan(20)
  })

  it('allow-list excludes a documented false-positive', () => {
    const samples: Sample[] = [
      { screen: 'my-shift', theme: 'light', text: 'Sunday, June 14', cls: 'text-body-2', color: 'rgb(255,255,255)', fontSize: 14, fontWeight: 400, bgStack: ['rgb(255,255,255)'], gradients: [] },
    ]
    expect(findViolations(samples, [])).toHaveLength(1)
    const allow = [{ screen: 'my-shift', classIncludes: 'text-body-2', text: 'Sunday', reason: 'on blue gradient banner' }]
    expect(findViolations(samples, allow)).toHaveLength(0)
  })
})
