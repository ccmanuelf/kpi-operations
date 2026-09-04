import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { HOLD_REASON_CODES } from '../useHoldGridData'

/**
 * The hold-reason dropdown against the catalog that gates it.
 *
 * Hold creation is refused server-side for any reason not active in the
 * client's catalog (routes/holds.py → 422 "Reason X not found in client
 * catalog"), so the dropdown is now fetched per client. This array remains
 * only as the offline fallback — and as a fallback it must still be a SUBSET
 * of what the backend seeds, or the fallback itself offers reasons that 422.
 */
describe('hold reason fallback vs the seeded catalog', () => {
  const seededCodes = () => {
    const src = readFileSync(
      resolve(__dirname, '../../../../backend/crud/hold_catalog.py'),
      'utf-8',
    )
    const block = src.slice(src.indexOf('DEFAULT_HOLD_REASONS = ['), src.indexOf(']', src.indexOf('DEFAULT_HOLD_REASONS = [')))
    return [...block.matchAll(/\("([A-Z_]+)"/g)].map((m) => m[1])
  }

  it('offers nothing the backend would reject', () => {
    // One-directional on purpose: the fallback may be a subset (a tenant can
    // deactivate reasons), but it must never contain a code the defaults do
    // not, or an offline user picks a reason that fails on save.
    const unknown = HOLD_REASON_CODES.filter((c) => !seededCodes().includes(c))
    expect(unknown, `fallback codes absent from DEFAULT_HOLD_REASONS: ${unknown.join(', ')}`).toEqual([])
  })

  it('records which seeded reasons the fallback omits', () => {
    // Not a failure — the fallback is deliberately the common subset. This
    // asserts the omission is the KNOWN one, so a future edit to either side
    // surfaces here rather than silently changing what an offline user sees.
    const missing = seededCodes().filter((c) => !HOLD_REASON_CODES.includes(c))
    expect(missing.sort()).toEqual(['ENGINEERING_CHANGE', 'MATERIAL_SHORTAGE', 'PENDING_APPROVAL'])
  })
})
