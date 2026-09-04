import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * The work-order status filter must offer the statuses that exist.
 *
 * It offered five of the eleven `WorkOrderStatus` members, and the five it
 * offered were the emptiest: RECEIVED, RELEASED, IN_PROGRESS, SHIPPED and
 * CLOSED had no option at all, while ACTIVE — a legacy alias nothing is
 * written as — did. On the seeded demo that is 330 of 400 orders unreachable
 * by the filter, and four of five choices matching nothing.
 */
describe('work-order status filter coverage', () => {
  const enumMembers = () => {
    const src = readFileSync(
      resolve(__dirname, '../../../../backend/orm/work_order.py'),
      'utf-8',
    )
    const body = src.slice(src.indexOf('class WorkOrderStatus'), src.indexOf('class WorkOrder(Base)'))
    return [...body.matchAll(/^\s{4}([A-Z_]+)\s*=\s*"([A-Z_]+)"/gm)].map((m) => m[2])
  }

  const offered = () => {
    const src = readFileSync(resolve(__dirname, '../useOrderStatusOptions.ts'), 'utf-8')
    // Bounded to this function only: the priority options follow it in the
    // same file, and slicing to end-of-file swept URGENT/HIGH/NORMAL in.
    const start = src.indexOf('export function useWorkOrderStatusOptions')
    const after = src.indexOf('export function', start + 1)
    const body = src.slice(start, after === -1 ? undefined : after)
    return [...body.matchAll(/value:\s*'([A-Z_]+)'/g)].map((m) => m[1])
  }

  it('offers every status the backend defines', () => {
    // Two-sided against the enum itself, so adding a status server-side fails
    // here instead of quietly becoming unfilterable.
    const missing = enumMembers().filter((s) => !offered().includes(s))
    expect(missing, `statuses with no filter option: ${missing.join(', ')}`).toEqual([])
  })

  it('offers nothing the backend does not define', () => {
    const invalid = offered().filter((s) => !enumMembers().includes(s))
    expect(invalid, `filter options matching no status: ${invalid.join(', ')}`).toEqual([])
  })

  it('covers the statuses the seeded demo actually holds', () => {
    // The six a full seed writes. Regression guard for the specific symptom:
    // filtering by status returned nothing for almost every real order.
    for (const s of ['RECEIVED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'SHIPPED', 'CLOSED']) {
      expect(offered()).toContain(s)
    }
  })
})
