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
    screen: 'work-orders',
    covering: /v-btn--elevated.*v-btn--icon/,
    why: "the global quick-actions FAB (position:fixed, bottom/right 24px, z-index 1000) sits over the grid's Actions column, so rows level with it cannot be deleted -- clicking the row's ✕ opens the FAB instead. Fixing it is a design decision about a global component, not a mechanical change: the page scrolls under a fixed FAB, so reserving space does not help.",
  },
  {
    screen: 'plan-vs-actual',
    covering: /v-btn--elevated.*v-btn--icon/,
    why: 'same FAB overlap as work-orders.',
  },
  {
    screen: 'admin-users',
    covering: /v-btn--elevated.*v-btn--icon/,
    why: 'same FAB overlap as work-orders.',
  },
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

interface Blocked {
  screen: string
  control: string
  covering: string
}

const INTERACTIVE = 'button, [role="button"], a[href], input, select, textarea, .v-select, .v-field'

test.describe('reachability: controls are not covered by other elements', () => {
  test('every audited screen has clickable controls', async ({ page }) => {
    test.setTimeout(600000)
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
            if (r.bottom < 0 || r.top > window.innerHeight) continue
            if (r.right < 0 || r.left > window.innerWidth) continue
            const cs = getComputedStyle(e)
            if (cs.visibility === 'hidden' || cs.display === 'none' || cs.pointerEvents === 'none') continue
            if (parseFloat(cs.opacity || '1') < 0.1) continue

            const x = Math.min(Math.max(r.left + r.width / 2, 1), window.innerWidth - 1)
            const y = Math.min(Math.max(r.top + r.height / 2, 1), window.innerHeight - 1)
            const hit = document.elementFromPoint(x, y)
            if (!hit) continue
            // Reachable if the hit is the control, inside it, or contains it
            // (a wrapper answering for its own child is fine).
            if (hit === e || e.contains(hit) || hit.contains(e)) continue
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
