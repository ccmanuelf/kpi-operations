// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

const src = readFileSync(
  fileURLToPath(new URL('../../components/grids/AGGridBase.vue', import.meta.url)),
  'utf-8',
)

describe('Excel cell behaviors are sourced from the isolation module, not hardcoded', () => {
  it('AGGridBase.vue no longer hardcodes undoRedoCellEditing props', () => {
    expect(src).not.toContain('undoRedoCellEditing')
  })

  it('AGGridBase.vue no longer hardcodes stopEditingWhenCellsLoseFocus (now from cellEditing flag)', () => {
    expect(src).not.toContain('stopEditingWhenCellsLoseFocus')
  })
})
