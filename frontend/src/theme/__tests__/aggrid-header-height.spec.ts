import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

// Source-parsing guard (mirrors contrast.a11y.spec.ts): the header row height is
// set in JS (useAGGridBase headerHeight) AND the theme var (--ag-header-height);
// when they disagree the legacy theme clips the header text. Pin them equal, and
// pin the label rules that keep the text vertically centered and un-clipped.

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const css = readFileSync(resolve(__dirname, '../../assets/aggrid-theme.css'), 'utf8')
const base = readFileSync(
  resolve(__dirname, '../../composables/useAGGridBase.ts'),
  'utf8',
)

/** The desktop JS header height = the final integer in the headerHeight ternary. */
function jsDesktopHeaderHeight(src: string): number {
  const line = src.split('\n').find((l) => l.includes('headerHeight:'))
  if (!line) throw new Error('headerHeight not found in useAGGridBase.ts')
  const ints = line.match(/\d+/g)
  if (!ints || ints.length === 0) throw new Error('no integer in headerHeight line')
  return Number(ints[ints.length - 1]) // desktop is the trailing ternary value
}

/** The base (desktop) --ag-header-height = the first declaration in the file
 *  (inside `.ag-theme-material {}`, before the @media / compact overrides). */
function cssBaseHeaderHeight(src: string): number {
  const m = src.match(/--ag-header-height:\s*(\d+)px/)
  if (!m) throw new Error('--ag-header-height not found in aggrid-theme.css')
  return Number(m[1])
}

describe('AG-Grid header height consistency (anti-clipping)', () => {
  it('base --ag-header-height equals the JS desktop headerHeight', () => {
    expect(cssBaseHeaderHeight(css)).toBe(jsDesktopHeaderHeight(base))
  })

  it('the header label is vertically centered', () => {
    // .ag-header-cell-label { ... align-items: center ... }
    expect(css).toMatch(/\.ag-header-cell-label\s*\{[^}]*align-items:\s*center/)
  })

  it('the header text uses a self-contained line-height so it cannot clip', () => {
    // .ag-header-cell-text { ... line-height: normal ... }
    expect(css).toMatch(/\.ag-header-cell-text\s*\{[^}]*line-height:\s*normal/)
  })
})
