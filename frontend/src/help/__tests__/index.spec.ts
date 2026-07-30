import { describe, it, expect } from 'vitest'
import { computeContentUnavailable, getAllDocs, type HelpDoc } from '../index'

function doc(overrides: Partial<HelpDoc> = {}): HelpDoc {
  return {
    id: '01-getting-started',
    filename: '01-getting-started.md',
    order: '01',
    title: 'Getting Started',
    body: 'Some body text.',
    raw: '# Getting Started\n\nSome body text.',
    ...overrides,
  }
}

describe('computeContentUnavailable', () => {
  it('is false for a normal, non-empty doc set', () => {
    expect(computeContentUnavailable([doc()])).toBe(false)
  })

  // ISSUE-018: the Docker build context previously omitted docs/user-guide,
  // so import.meta.glob resolved to zero modules and the Help Center
  // rendered "No matches found" for every search — silently, with no
  // indication anything was wrong.
  it('is true when zero docs are loaded', () => {
    expect(computeContentUnavailable([])).toBe(true)
  })

  // Belt-and-braces: detect the SPA-fallback signature (nginx
  // `try_files ... /index.html`) leaking into what should be doc content.
  it('is true when a doc\'s raw content is an HTML document (SPA fallback)', () => {
    const htmlFallback = doc({
      raw: '<!doctype html>\n<html><head></head><body><div id="app"></div></body></html>',
    })
    expect(computeContentUnavailable([htmlFallback])).toBe(true)
  })

  it('is true when a doc starts with a bare <html> tag', () => {
    const htmlFallback = doc({ raw: '<html><body>fallback</body></html>' })
    expect(computeContentUnavailable([htmlFallback])).toBe(true)
  })

  it('is false when a doc legitimately contains an inline <html> mention mid-body', () => {
    const legit = doc({ raw: '# Getting Started\n\nUse `<html>` tags sparingly in examples.' })
    expect(computeContentUnavailable([legit])).toBe(false)
  })
})

describe('getAllDocs (real build-time glob)', () => {
  // Sanity check against the actual repo checkout: proves the loader itself
  // works end-to-end in this environment (separate from the Docker-context
  // fix, which build-level tooling can't reach — verified live in Task 11).
  it('loads a non-empty, non-HTML doc set from docs/user-guide', () => {
    const docs = getAllDocs()
    expect(computeContentUnavailable(docs)).toBe(false)
    expect(docs.length).toBeGreaterThan(0)
  })
})
