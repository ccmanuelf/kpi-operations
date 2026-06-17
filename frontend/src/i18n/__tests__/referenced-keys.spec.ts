import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import en from '../locales/en.json'
import es from '../locales/es.json'

// ESM-safe dir resolution (Vitest does not reliably define __dirname)
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../')
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
function get(obj: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((a, k) => (a && typeof a === 'object' ? (a as Record<string, unknown>)[k] : undefined), obj)
}
// literal keys only: t('a.b') / $t("a.b") / keypath="a.b"; skip `${...}` template-literal (dynamic) keys
const KEY_RE = /(?:\$t|[^\w.]t)\(\s*['"]([A-Za-z0-9_.]+)['"]|keypath=["']([A-Za-z0-9_.]+)["']/g

describe('referenced i18n keys resolve in both locales', () => {
  it('every literal t()/$t()/keypath key exists in en and es', () => {
    const missing: string[] = []
    const seen = new Set<string>()
    for (const file of walk(SRC)) {
      const src = readFileSync(file, 'utf8')
      let m: RegExpExecArray | null
      while ((m = KEY_RE.exec(src))) {
        const key = m[1] || m[2]
        if (!key || seen.has(key)) continue
        seen.add(key)
        if (get(en as Record<string, unknown>, key) === undefined || get(es as Record<string, unknown>, key) === undefined) {
          missing.push(key)
        }
      }
    }
    expect(missing).toEqual([])
  })
})
