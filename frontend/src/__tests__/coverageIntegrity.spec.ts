// @vitest-environment node
/**
 * Guards the frontend coverage gate against SILENT file exclusion.
 *
 * Failure mode this exists to prevent (found 2026-08-11):
 * `WidgetGrid.vue` dynamically imported 11 components from a `./widgets/`
 * directory that never existed. Vite's transform throws on the unresolvable
 * specifier; @vitest/coverage-v8 swallows that with `.catch(() => null)`
 * (provider.js `getSources`), falls back to reading the RAW .vue source, and
 * then fails to parse it as JavaScript at byte 0 — logging
 * "Failed to parse <file>. Excluding it from coverage." and moving on.
 *
 * The run stays GREEN while a file silently leaves the denominator, which
 * inflates the reported percentage against the configured thresholds. No
 * existing test could catch that, because the file simply vanishes.
 *
 * This guard resolves every relative and `@/`-aliased import specifier in the
 * source files the coverage config measures, and fails if any target is
 * missing.
 *
 * NOTE on scope: bare package specifiers are deliberately NOT validated. A
 * missing npm dependency fails loudly at install or build time, so it is not
 * part of the silent-drop class this guard targets; resolving them here would
 * duplicate npm's job and drift from it.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync, statSync, readdirSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { dirname, resolve, join } from 'node:path'

const SRC = fileURLToPath(new URL('..', import.meta.url))

/**
 * Mirrors `coverage.include` in vitest.config.ts as (directory, extensions)
 * pairs. Kept in sync deliberately: a file measured for coverage must be
 * resolvable, or it can vanish from the denominator silently.
 */
const COVERED_TREES: Array<{ dir: string; exts: string[] }> = [
  { dir: 'services', exts: ['.js', '.ts'] },
  { dir: 'stores', exts: ['.js', '.ts'] },
  { dir: 'utils', exts: ['.js', '.ts'] },
  { dir: 'composables', exts: ['.js', '.ts'] },
  { dir: 'components', exts: ['.vue'] },
  { dir: 'views', exts: ['.vue'] },
]

/** Dependency-free recursive walk (no fast-glob in this project's deps). */
function walk(dir: string, exts: string[], out: string[] = []): string[] {
  let entries
  try {
    entries = readdirSync(dir, { withFileTypes: true })
  } catch (err) {
    // Only a genuinely absent directory is tolerable. Swallowing every error
    // would let an unreadable subtree vanish while the file-count sanity check
    // still passed — the exact silent-skip failure this guard exists to stop.
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return out
    throw err
  }
  for (const e of entries) {
    const full = join(dir, e.name)
    if (e.isDirectory()) {
      if (e.name === '__tests__' || e.name === 'node_modules') continue
      walk(full, exts, out)
    } else if (exts.some((x) => e.name.endsWith(x)) && !e.name.endsWith('.d.ts')) {
      out.push(full)
    }
  }
  return out
}

/**
 * Files knowingly excluded from this guard, with the reason they are exempt.
 * Entries here are DEBT, not policy — each one is a file the coverage gate
 * cannot measure. Removing an entry is the goal; adding one needs a reason.
 */
const KNOWN_UNRESOLVABLE: Record<string, string> = {
  'components/dashboard/WidgetGrid.vue':
    'Half-built custom-dashboard widget system: imports 11 components from ' +
    './widgets/, a directory that has never existed in git history. The file ' +
    'is unmounted dead code (only the dashboard barrel references it, and ' +
    'nothing imports that barrel), so this is inert until the feature is ' +
    'either finished or retired. Tracked as its own decision.',
}

const IGNORED_PREFIXES = ['node:', 'http:', 'https:', 'data:', 'virtual:']

/** Specifiers we own: project-relative and `@/`-aliased. */
function isOwnedSpecifier(spec: string): boolean {
  return spec.startsWith('./') || spec.startsWith('../') || spec.startsWith('@/')
}

const EXT_CANDIDATES = ['.ts', '.js', '.vue', '.mjs', '.mts', '.cts', '.tsx', '.jsx', '.json']

function resolveSpecifier(spec: string, fromFile: string): string | null {
  // Vite specifiers may carry a resource query or hash (`./a.css?inline`,
  // `./a.vue?raw`). Strip it before touching the filesystem, or valid imports
  // are reported as missing — a false failure is as damaging as a missed one.
  const clean = spec.split('?')[0].split('#')[0]

  let base: string
  if (clean.startsWith('@/')) base = resolve(SRC, clean.slice(2))
  else if (clean.startsWith('./') || clean.startsWith('../')) base = resolve(dirname(fromFile), clean)
  else return null // bare package specifier — npm's job, see NOTE below

  const candidates = [
    base,
    ...EXT_CANDIDATES.map((e) => `${base}${e}`),
    ...EXT_CANDIDATES.map((e) => `${base}/index${e}`),
  ]
  for (const c of candidates) {
    if (existsSync(c) && statSync(c).isFile()) return c
  }
  return null
}

/**
 * Static `from '...'`, side-effect `import '...'`, dynamic `import('...')`
 * and `require('...')`.
 *
 * Scanned line by line with comment lines skipped: a commented-out import of
 * a since-deleted path would otherwise fail the guard for no reason. Full
 * fidelity would need an AST, which is not worth the weight here — the cost
 * of a miss is one unguarded file, whereas the cost of a false positive is a
 * red build nobody can action.
 */
function extractSpecifiers(code: string): string[] {
  const specs = new Set<string>()
  const patterns = [
    /\bfrom\s+['"]([^'"]+)['"]/g,
    /\bimport\s+['"]([^'"]+)['"]/g, // side-effect import
    /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  ]

  let inBlockComment = false
  for (const rawLine of code.split('\n')) {
    const line = rawLine.trim()
    if (inBlockComment) {
      if (line.includes('*/')) inBlockComment = false
      continue
    }
    if (line.startsWith('/*')) {
      if (!line.includes('*/')) inBlockComment = true
      continue
    }
    if (line.startsWith('//') || line.startsWith('*')) continue

    for (const re of patterns) {
      re.lastIndex = 0
      let m: RegExpExecArray | null
      while ((m = re.exec(line)) !== null) specs.add(m[1])
    }
  }
  return [...specs].filter((s) => !IGNORED_PREFIXES.some((p) => s.startsWith(p)))
}

const files = COVERED_TREES.flatMap(({ dir, exts }) => walk(resolve(SRC, dir), exts)).sort()

describe('coverage integrity: every measured file must be resolvable', () => {
  it('finds the coverage-included source files', () => {
    // Sanity: if the globs ever stop matching, the guard would pass vacuously.
    expect(files.length).toBeGreaterThan(100)
  })

  it('has no unresolvable import in any coverage-measured file', () => {
    const failures: string[] = []

    for (const file of files) {
      const rel = file.slice(SRC.length).replace(/\\/g, '/')
      if (rel in KNOWN_UNRESOLVABLE) continue

      const code = readFileSync(file, 'utf-8')
      for (const spec of extractSpecifiers(code)) {
        if (isOwnedSpecifier(spec) && resolveSpecifier(spec, file) === null) {
          failures.push(`${rel} -> ${spec}`)
        }
      }
    }

    expect(
      failures,
      'Unresolvable imports make vite\'s transform throw. @vitest/coverage-v8 ' +
        'swallows that error and drops the file from coverage WITHOUT failing ' +
        'the run, silently inflating the reported percentage. Fix the import, ' +
        'or add the file to KNOWN_UNRESOLVABLE with a reason.',
    ).toEqual([])
  })

  it('keeps every KNOWN_UNRESOLVABLE entry honest', () => {
    for (const [rel, reason] of Object.entries(KNOWN_UNRESOLVABLE)) {
      // The exemption must point at a file that still exists...
      expect(existsSync(resolve(SRC, rel)), `stale exemption: ${rel} no longer exists`).toBe(true)
      // ...and must still actually be broken, so fixed files cannot sit here
      // collecting dust and quietly staying out of the coverage denominator.
      const code = readFileSync(resolve(SRC, rel), 'utf-8')
      const broken = extractSpecifiers(code).filter(
        (s) => isOwnedSpecifier(s) && resolveSpecifier(s, resolve(SRC, rel)) === null,
      )
      expect(
        broken.length,
        `${rel} now resolves cleanly — remove it from KNOWN_UNRESOLVABLE so coverage measures it again`,
      ).toBeGreaterThan(0)
      expect(reason.length).toBeGreaterThan(30)
    }
  })
})
