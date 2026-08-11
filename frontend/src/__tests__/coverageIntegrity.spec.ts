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
    } else if (
      exts.some((x) => e.name.endsWith(x)) &&
      !/\.d\.(ts|mts|cts)$/.test(e.name) // declaration files are not source
    ) {
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

/**
 * NOT implemented, deliberately: TS/NodeNext `./foo.js` -> `foo.ts` rewriting.
 * The codebase contains no such specifiers, and adding the mapping would make
 * the guard PASS on an import Vite itself may refuse to resolve — trading a
 * theoretical false positive for a real false negative, which is the wrong
 * direction for a gate-integrity check. Revisit only if that style appears.
 */
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
 * Matches `from` / `import` / `require`, optionally followed by `(`.
 *
 * The lookbehind rejects member access, so `Array.from('./x')`,
 * `obj.import('./x')` and `obj.require('./x')` are not mistaken for module
 * specifiers. (`Array.from` appears 9 times in this codebase.)
 */
const IMPORT_TAIL = /(?<![.\w$])(from|import|require)\s*\(?\s*$/

/**
 * Extracts module specifiers in a single pass: static `from '...'`,
 * side-effect `import '...'`, dynamic `import('...')` and `require('...')`.
 *
 * A string literal counts as a specifier only when the code immediately
 * before it ends in `from`, `import` or `require`. Deciding by preceding
 * token — rather than regexing the file text — is what makes
 * `const s = "import './x'"` inert: the scanner sees one literal whose
 * preceding token is `=`, and never reads the text inside it as code.
 * Multi-line forms and trailing import attributes fall out for free, since
 * nothing depends on what follows the specifier.
 *
 * Comments are skipped inline, so `/* c *​/ import './x'` is still seen while
 * `const a = 1 // import './x'` is not.
 *
 * Performance matters here: this runs over every coverage-measured file, and
 * an earlier version that concatenated char-by-char and built whole stripped
 * copies blew the 5s test timeout under parallel workers. This keeps only a
 * short rolling tail of recent code characters instead.
 */
function extractSpecifiers(code: string): string[] {
  const specs = new Set<string>()
  const TAIL = 24 // enough to hold "require(" / "} from " plus whitespace
  let tail = ''
  let i = 0

  // Runs of whitespace collapse to one char, so the fixed-size window cannot
  // be flushed by indentation alone. Without this, a deeply indented
  // `import(\n<lots of spaces>'./x')` would push the keyword out of `tail`
  // and the specifier would be missed entirely.
  const pushTail = (s: string) => {
    if (/\s/.test(s) && tail.endsWith(' ')) return
    tail = (tail + (/\s/.test(s) ? ' ' : s)).slice(-TAIL)
  }

  while (i < code.length) {
    const c = code[i]
    const next = code[i + 1]

    if (c === '/' && next === '/') {
      while (i < code.length && code[i] !== '\n') i++
      pushTail(' ')
      continue
    }

    if (c === '/' && next === '*') {
      const end = code.indexOf('*/', i + 2)
      i = end === -1 ? code.length : end + 2
      pushTail(' ')
      continue
    }

    if (c === '"' || c === "'" || c === '`') {
      const isSpecifier = IMPORT_TAIL.test(tail)
      const quote = c
      i++
      let value = ''
      while (i < code.length && code[i] !== quote) {
        if (code[i] === '\\') {
          value += code[i + 1] ?? ''
          i += 2
          continue
        }
        value += code[i]
        i++
      }
      i++ // closing quote
      if (isSpecifier) specs.add(value)
      pushTail('"') // a literal is a value; it must not look like a keyword
      continue
    }

    pushTail(c)
    i++
  }

  return [...specs].filter(
    (s) =>
      !IGNORED_PREFIXES.some((p) => s.startsWith(p)) &&
      // Interpolated template specifiers (`./${name}.vue`) have no single
      // resolvable target. Reporting one as "missing" would be a false
      // failure; leaving it unguarded is the safer direction.
      !s.includes('${'),
  )
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
