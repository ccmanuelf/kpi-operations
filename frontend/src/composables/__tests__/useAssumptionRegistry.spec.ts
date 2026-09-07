/**
 * Gates for the assumption-registry lifecycle.
 *
 * The load-bearing part is permissions. Each write passes a FastAPI dependency
 * and THEN a narrower check inside AssumptionService, and only the second is
 * the real answer. Gating a button on the route's tier offers approve to a
 * poweruser and 403s them -- the "backend can, UI cannot" defect inverted --
 * so these assert against the SERVICE's tiers, parsed from the Python.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const { mockApi, mockAssumptions } = vi.hoisted(() => ({
  mockApi: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
  mockAssumptions: {
    listAssumptions: vi.fn(() => Promise.resolve({ data: [] })),
    getCatalog: vi.fn(() => Promise.resolve({ data: [] })),
    getAssumptionHistory: vi.fn(() => Promise.resolve({ data: [] })),
    proposeAssumption: vi.fn(() => Promise.resolve({ data: {} })),
    updateProposal: vi.fn(() => Promise.resolve({ data: {} })),
    approveAssumption: vi.fn(() => Promise.resolve({ data: {} })),
    retireAssumption: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))
vi.mock('@/services/api/calculationAssumptions', () => mockAssumptions)

import {
  useAssumptionRegistry,
  canPropose,
  canApprove,
  canEdit,
  isSelfApproval,
  PROPOSER_ROLES,
  APPROVER_ROLES,
} from '../useAssumptionRegistry'

const row = (over: Record<string, unknown> = {}) => ({
  assumption_id: 1,
  client_id: 'C',
  assumption_name: 'setup_treatment',
  value: 'count_as_downtime',
  rationale: null,
  status: 'active',
  proposed_by: 'USR-A',
  ...over,
})

beforeEach(() => vi.clearAllMocks())

describe('permission tiers match the SERVICE, not the route', () => {
  it('lets admin and poweruser propose, and nobody else', () => {
    expect(canPropose('admin')).toBe(true)
    expect(canPropose('poweruser')).toBe(true)
    // The ROUTE admits these two; the service refuses them.
    expect(canPropose('leader')).toBe(false)
    expect(canPropose('supervisor')).toBe(false)
    expect(canPropose('operator')).toBe(false)
    expect(canPropose(undefined)).toBe(false)
  })

  it('lets ONLY admin approve — the route says planner, the service says admin', () => {
    expect(canApprove('admin')).toBe(true)
    // get_current_planner lets a poweruser through; _APPROVER_ROLES does not.
    expect(canApprove('poweruser')).toBe(false)
    expect(canApprove('leader')).toBe(false)
  })

  it('matches the tiers the Python service actually enforces', () => {
    // Two-sided against the source of truth. The frontend cannot import
    // Python, so this reads the service and asserts the same role sets.
    const src = readFileSync(
      resolve(__dirname, '../../../../backend/services/assumption_service.py'),
      'utf-8',
    )
    const parse = (name: string): string[] => {
      const match = src.match(new RegExp(`^${name} = \\{([^}]*)\\}`, 'm'))
      expect(match, `${name} not found in assumption_service.py`).not.toBeNull()
      return [...match![1].matchAll(/"([a-z]+)"/g)].map((m) => m[1]).sort()
    }
    expect(parse('_PROPOSER_ROLES')).toEqual([...PROPOSER_ROLES].sort())
    expect(parse('_APPROVER_ROLES')).toEqual([...APPROVER_ROLES].sort())
  })
})

describe('canEdit', () => {
  it('allows the proposer to edit their own PROPOSED record', () => {
    expect(canEdit(row({ status: 'proposed', proposed_by: 'USR-A' }), 'USR-A', 'poweruser')).toBe(true)
  })

  it('allows an admin to edit anyone else’s proposal', () => {
    expect(canEdit(row({ status: 'proposed', proposed_by: 'USR-B' }), 'USR-A', 'admin')).toBe(true)
  })

  it('refuses a different poweruser', () => {
    expect(canEdit(row({ status: 'proposed', proposed_by: 'USR-B' }), 'USR-A', 'poweruser')).toBe(false)
  })

  it.each(['active', 'retired'])('refuses to edit a %s record — the API answers 409', (status) => {
    expect(canEdit(row({ status, proposed_by: 'USR-A' }), 'USR-A', 'admin')).toBe(false)
  })
})

describe('isSelfApproval', () => {
  it('is true when the approver proposed the record', () => {
    // The backend permits it -- approve() never reads proposed_by -- so the
    // screen warns rather than implying a separation of duties that is not
    // enforced.
    expect(isSelfApproval(row({ proposed_by: 'USR-A' }), 'USR-A')).toBe(true)
  })

  it('is false for a different approver, and for an unknown user', () => {
    expect(isSelfApproval(row({ proposed_by: 'USR-B' }), 'USR-A')).toBe(false)
    expect(isSelfApproval(row({ proposed_by: 'USR-A' }), undefined)).toBe(false)
  })
})

describe('useAssumptionRegistry', () => {
  it('asks for retired records so they can be shown on demand', async () => {
    mockAssumptions.listAssumptions.mockResolvedValue({ data: [] })
    const reg = useAssumptionRegistry()
    reg.selectedClient.value = 'DEMO-PIECE'
    await reg.load()
    expect(mockAssumptions.listAssumptions).toHaveBeenCalledWith({
      client_id: 'DEMO-PIECE',
      include_inactive: true,
    })
  })

  it('hides retired records until asked, without re-fetching', async () => {
    mockAssumptions.listAssumptions.mockResolvedValue({
      data: [row({ assumption_id: 1, status: 'active' }), row({ assumption_id: 2, status: 'retired' })],
    })
    const reg = useAssumptionRegistry()
    reg.selectedClient.value = 'C'
    await reg.load()

    expect(reg.visible.value.map((r) => r.assumption_id)).toEqual([1])
    reg.includeRetired.value = true
    expect(reg.visible.value.map((r) => r.assumption_id)).toEqual([1, 2])
    expect(mockAssumptions.listAssumptions).toHaveBeenCalledTimes(1)
  })

  it('surfaces proposals awaiting a decision', async () => {
    mockAssumptions.listAssumptions.mockResolvedValue({
      data: [row({ assumption_id: 1, status: 'active' }), row({ assumption_id: 2, status: 'proposed' })],
    })
    const reg = useAssumptionRegistry()
    reg.selectedClient.value = 'C'
    await reg.load()

    expect(reg.pending.value.map((r) => r.assumption_id)).toEqual([2])
    expect(reg.byStatus.value).toEqual({ proposed: 1, active: 1, retired: 0 })
  })

  it('re-reads after every write, so the list reflects the new state', async () => {
    mockAssumptions.listAssumptions.mockResolvedValue({ data: [] })
    const reg = useAssumptionRegistry()
    reg.selectedClient.value = 'C'

    await reg.approve(7, 'looks right')
    expect(mockAssumptions.approveAssumption).toHaveBeenCalledWith(7, 'looks right')
    expect(mockAssumptions.listAssumptions).toHaveBeenCalled()
  })

  it('does not claim a client has no assumptions when the read FAILED', async () => {
    mockAssumptions.listAssumptions.mockRejectedValue(new Error('network down'))
    const reg = useAssumptionRegistry()
    reg.selectedClient.value = 'C'

    await expect(reg.load()).rejects.toThrow('network down')
    expect(reg.loaded.value).toBe(false)
  })
})
