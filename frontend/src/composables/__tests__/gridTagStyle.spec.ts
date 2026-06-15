import { describe, it, expect } from 'vitest'
import { tagStyle } from '../gridTagStyle'

describe('gridTagStyle', () => {
  it('produces a compact square tag (not a pill) with the given color', () => {
    const css = tagStyle('#198038')
    expect(css).toContain('background: #198038')
    expect(css).toContain('border-radius: 3px') // square tag, not the old 12px pill
    expect(css).toContain('font-size: 11px')
    expect(css).toMatch(/padding:\s*1px 6px/) // tighter than the old 2px 8px
    expect(css).toContain('color: #ffffff')
  })
})
