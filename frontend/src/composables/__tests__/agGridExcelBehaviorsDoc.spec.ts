// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import {
  useAgGridExcelBehaviors,
  DEFAULT_EXCEL_BEHAVIOR_FLAGS,
} from '../agGridExcelBehaviors'

const doc = readFileSync(
  fileURLToPath(new URL('../../../../docs/frontend/ag-grid-excel-behaviors.md', import.meta.url)),
  'utf-8',
)

describe('ag-grid-excel-behaviors doc coverage', () => {
  it('documents every registered behavior key', () => {
    const { registry } = useAgGridExcelBehaviors(DEFAULT_EXCEL_BEHAVIOR_FLAGS)
    for (const entry of registry) {
      expect(doc).toContain(`\`${entry.key}\``)
    }
  })

  it('explains the master kill-switch', () => {
    expect(doc).toContain('master: false')
  })
})
