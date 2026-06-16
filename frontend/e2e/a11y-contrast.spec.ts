import { test, expect } from '@playwright/test'
import { login } from './helpers'
import { collectSamples } from './a11y/collectSamples'
import { SCREENS, ALLOWLIST } from './a11y/screens'
import { findViolations, type Violation } from '../src/utils/contrastAudit'

const THEMES = ['light', 'dark'] as const

// Settle colors before sampling (no transition/animation mid-flight).
const FREEZE_CSS = '*,*::before,*::after{transition:none !important;animation:none !important}'

for (const theme of THEMES) {
  test.describe(`a11y contrast — ${theme}`, () => {
    test(`every key screen meets WCAG-AA (${theme})`, async ({ page }) => {
      test.slow() // 13 screens × audit; allow generous time
      await page.setViewportSize({ width: 1440, height: 900 })
      await page.addInitScript(
        (d) => localStorage.setItem('kpi-theme', JSON.stringify({ isDark: d })),
        theme === 'dark',
      )
      await login(page, 'admin')

      const all: Violation[] = []
      for (const screen of SCREENS) {
        await page.goto(screen.path)
        await page.waitForLoadState('networkidle').catch(() => {})
        await page.waitForTimeout(800)
        await page.addStyleTag({ content: FREEZE_CSS }).catch(() => {})
        const samples = await collectSamples(page, screen.name, theme)
        all.push(...findViolations(samples, ALLOWLIST))
      }

      const msg = all
        .map(
          (v) =>
            `  [${v.screen}/${v.theme}] ${v.ratio} (<${v.threshold}) "${v.text}" ${v.color} on ${v.bgUsed} .${v.cls}`,
        )
        .join('\n')
      expect(all, `WCAG-AA contrast violations (${theme}):\n${msg}`).toEqual([])
    })
  })
}
