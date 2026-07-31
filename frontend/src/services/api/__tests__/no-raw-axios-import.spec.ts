/**
 * Structural gate: no file under frontend/src imports the raw `axios`
 * package directly, except the one module that's allowed to construct it
 * (services/api/client.ts).
 *
 * Regression coverage for the ISSUE-020 class (databaseConfigStore.ts,
 * Task 5) recurring across 7 more files (Task 6 follow-up):
 * `useDashboardOverviewData.ts`, `AttendanceKPIs.vue`, `AbsenteeismAlert.vue`,
 * `BradfordFactorWidget.vue`, `ReworkByOperationWidget.vue`,
 * `DowntimeImpactWidget.vue`, `QualityByOperatorWidget.vue`. A bare
 * `axios.get(...)` call bypasses the shared client's request interceptor
 * (`services/api/client.ts`), which is the only place that attaches the
 * `Authorization: Bearer <token>` header — every such call silently sends
 * an unauthenticated request in production (401s that get swallowed by
 * dev-only `console.warn`/`console.error` catch blocks, widgets falling
 * back to a fabricated "0 data" state with no visible error). Pattern
 * follows the existing `i18n/__tests__/referenced-keys.spec.ts` gate:
 * walk the source tree, grep, assert no findings.
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// ESM-safe dir resolution (Vitest does not reliably define __dirname)
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../../')

// The only module allowed to import the raw axios package — it constructs
// the shared, interceptor-equipped client every other module must use.
const ALLOWED = resolve(SRC, 'services/api/client.ts')

function walk(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) {
      if (/node_modules|__tests__|[/\\]test([/\\]|$)/.test(p)) continue
      out.push(...walk(p))
    } else if (/\.(ts|vue)$/.test(p) && !/\.(spec|test)\.ts$/.test(p) && !/\.d\.ts$/.test(p)) {
      out.push(p)
    }
  }
  return out
}

// Matches `import axios from 'axios'` and `import ... from "axios"` (any
// named/default import shape), not the shared `@/services/api*` modules.
const RAW_AXIOS_IMPORT_RE = /import\s[^;]*\sfrom\s+['"]axios['"]/

describe('no file imports the raw axios package (except the shared client)', () => {
  it('every axios import goes through services/api/client.ts', () => {
    const offenders: string[] = []
    for (const file of walk(SRC)) {
      if (file === ALLOWED) continue
      const src = readFileSync(file, 'utf8')
      if (RAW_AXIOS_IMPORT_RE.test(src)) {
        offenders.push(file.replace(SRC + '/', ''))
      }
    }
    expect(offenders).toEqual([])
  })
})
