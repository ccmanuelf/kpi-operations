/**
 * Is every control on every screen actually REACHABLE?
 *
 * The nav-drawer clipping bug was invisible to the whole suite: the page
 * rendered, the DOM was correct, contrast passed, and the first ~280px of each
 * screen could not be clicked because another element sat on top of it. No
 * assertion this repo had could see that, because they all ask what the DOM
 * CONTAINS rather than what a person can reach.
 *
 * This asks the browser the question directly, for every audited screen: for
 * each visible interactive control, is the element at its own centre point
 * itself (or a descendant)? If something else answers, the control is covered
 * and clicking it does something other than what it looks like it does.
 *
 * Also flags horizontal overflow, which is the same failure one step earlier --
 * content pushed outside the viewport cannot be reached at all.
 */
import { test, expect } from '@playwright/test'

import { SCREENS } from './a11y/screens'
import { login } from './helpers'

/**
 * Known-open overlaps, each with the reason it is not a regression.
 *
 * These gate the SHAPE of the problem rather than hiding it: a new covered
 * control anywhere fails, while these specific, already-raised cases do not
 * re-fail the build every run while their fix is decided.
 */
const KNOWN: { screen: string; covering: RegExp; why: string }[] = [
  {
    screen: 'capacity-planning',
    covering: /v-slide-group__next/,
    why: "a tab bar's own scroll arrow overlaying the last visible tab, which is how Vuetify's slide-group is designed to behave -- the arrow scrolls the tab into reach.",
  },
  {
    screen: 'simulation-v2',
    covering: /Got it/,
    why: 'the onboarding tour panel, which is transient and dismissed by the button that covers the control.',
  },
]

const isKnown = (screen: string, covering: string): boolean =>
  KNOWN.some((k) => k.screen === screen && k.covering.test(covering))

/**
 * The navigation drawer is deliberately NOT allowlisted. At the desktop
 * viewport this audit pins, a persistent drawer must never cover content --
 * that was #297, and letting it pass here would retire the gate that caught it.
 */

interface Blocked {
  screen: string
  control: string
  covering: string
}

const INTERACTIVE = 'button, [role="button"], a[href], input, select, textarea, .v-select, .v-field'

test.describe('reachability: controls are not covered by other elements', () => {
  test('every audited screen has clickable controls', async ({ page }) => {
    test.setTimeout(600000)
    // Deliberately NOT widened. Pinning 1440x900 -- as the contrast gate does
    // -- made this audit blind to the defect that prompted it: the dashboard
    // header only runs out of room, and only crushes the dual-view toggle, at
    // the narrower default. A reachability check has to run where things are
    // tight, which is exactly where they break. The drawer overlaps that
    // motivated widening turned out to be clipping, and are handled properly
    // by the scroll-ancestor test below.
    await login(page, 'admin')

    const blocked: Blocked[] = []
    const overflowing: string[] = []
    const skipped: string[] = []

    for (const screen of SCREENS) {
      await page.goto(screen.path, { waitUntil: 'networkidle' }).catch(() => {})
      // Let async data and any transition settle; a control mid-animation is
      // not evidence of anything.
      await page.waitForTimeout(1800)

      const result = await page.evaluate(
        ({ selector }) => {
          const describe = (el: Element | null): string => {
            if (!el) return '(nothing)'
            const e = el as HTMLElement
            const id = e.dataset?.testid ? `[${e.dataset.testid}]` : ''
            const cls = (e.className || '').toString().split(/\s+/).filter(Boolean).slice(0, 3).join('.')
            const text = (e.textContent || '').trim().slice(0, 28)
            return `${e.tagName.toLowerCase()}${id}${cls ? '.' + cls : ''}${text ? ` "${text}"` : ''}`
          }

          const covered: { control: string; covering: string }[] = []
          const controls = Array.from(document.querySelectorAll(selector))

          for (const el of controls) {
            const e = el as HTMLElement
            const r = e.getBoundingClientRect()
            // Only things a person could actually aim at.
            if (r.width < 8 || r.height < 8) continue

            const cs = getComputedStyle(e)
            if (cs.pointerEvents === 'none') continue
            // checkVisibility accounts for ANCESTOR visibility, display and
            // opacity. Reading the element's own computed style misses a
            // control sitting inside a faded-out or collapsed parent, which
            // then gets probed and reported as covered by whatever is on top
            // of its invisible container.
            const visible =
              typeof e.checkVisibility === 'function'
                ? e.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true })
                : cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity || '1') >= 0.1
            if (!visible) continue

            // The TRUE centre, unclamped. Clamping a partially off-screen
            // control into the viewport probes a point that is not its centre,
            // and then reports whatever occupies that edge -- a sticky header,
            // usually -- as covering a control that is perfectly clickable
            // elsewhere. If the centre is off-screen this cannot be judged
            // fairly, so it is not judged.
            const x = r.left + r.width / 2
            const y = r.top + r.height / 2
            if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) continue

            // Clipped by a scrolling ancestor is NOT covered. A control
            // scrolled out of the nav drawer's list, or a tab scrolled off a
            // slide-group strip, is reachable the moment its container is
            // scrolled -- and probing it reports whichever container happens
            // to paint at that point, which says nothing about reachability.
            // Checked against EVERY scrollable ancestor rather than just the
            // one that answered, because the element that answers is often
            // further out than the one doing the clipping.
            let clipped = false
            for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
              const ps = getComputedStyle(p)
              // `auto` and `scroll` ONLY. `overflow:hidden` is not a
              // scroller -- it cuts content off with no way to reveal it, so
              // a control outside a hidden container is genuinely
              // unreachable. Including it here swallowed the dual-view toggle
              // this branch fixes: its buttons overflow their own crushed
              // 27px group, and the audit called that "clipped, fine".
              if (!/(auto|scroll)/.test(ps.overflowY + ps.overflowX)) continue
              const pr = p.getBoundingClientRect()
              if (x < pr.left - 1 || x > pr.right + 1 || y < pr.top - 1 || y > pr.bottom + 1) {
                clipped = true
                break
              }
            }
            if (clipped) continue

            const hit = document.elementFromPoint(x, y)
            if (!hit) continue
            if (hit === e || e.contains(hit)) continue

            if (hit.contains(e)) {
              // An ANCESTOR answered. Two cases are legitimate and one is not.
              //
              // 1. A form wrapper Vuetify paints over its own input; clicking
              //    it focuses the control, so the control is reachable.
              // (Controls clipped by a scrolling ancestor are already
              // filtered above, before the hit test.)
              //
              // Anything else -- a backdrop, an overlay, a wrapper painted on
              // top -- is real coverage and must not be forgiven, which is
              // what exempting every ancestor originally did.
              const h = hit as HTMLElement
              if (h.closest('.v-field, .v-input, label') === h) continue
            }
            covered.push({ control: describe(e), covering: describe(hit) })
          }

          const doc = document.documentElement
          const hOverflow = doc.scrollWidth - doc.clientWidth

          return { covered, hOverflow, controlCount: controls.length }
        },
        { selector: INTERACTIVE },
      )

      if (result.controlCount === 0) {
        skipped.push(`${screen.name} (no controls rendered)`)
        continue
      }
      if (result.hOverflow > 4) {
        overflowing.push(`${screen.name}: ${result.hOverflow}px past the viewport`)
      }
      for (const c of result.covered) {
        if (isKnown(screen.name, c.covering)) continue
        blocked.push({ screen: screen.name, control: c.control, covering: c.covering })
      }
    }

    // eslint-disable-next-line no-console
    console.log(`\n=== reachability audit over ${SCREENS.length} screens ===`)
    if (skipped.length) {
      // eslint-disable-next-line no-console
      console.log(`skipped: ${skipped.join(', ')}`)
    }
    if (overflowing.length) {
      // eslint-disable-next-line no-console
      console.log(`HORIZONTAL OVERFLOW:\n  ${overflowing.join('\n  ')}`)
    }
    if (blocked.length) {
      // eslint-disable-next-line no-console
      console.log(`COVERED CONTROLS (${blocked.length}):`)
      for (const b of blocked.slice(0, 40)) {
        // eslint-disable-next-line no-console
        console.log(`  [${b.screen}] ${b.control}\n      covered by: ${b.covering}`)
      }
    } else {
      // eslint-disable-next-line no-console
      console.log('no covered controls')
    }

    // A screen that rendered NOTHING is not a screen that passed. Without this
    // the audit reports success for a route that failed to load, redirected, or
    // errored -- the whole point being that it should notice unreachable UI,
    // and "no UI at all" is the extreme case.
    expect(
      skipped,
      `${skipped.length} screen(s) rendered no controls at all — they did not load`,
    ).toHaveLength(0)
    expect(blocked, `${blocked.length} control(s) are covered by another element`).toHaveLength(0)
    expect(overflowing, `${overflowing.length} screen(s) overflow horizontally`).toHaveLength(0)
  })
})
