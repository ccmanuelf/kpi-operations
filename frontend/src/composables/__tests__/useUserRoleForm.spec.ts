import { describe, it, expect } from 'vitest'
import { clientFieldMode, clientRequired } from '../useUserRoleForm'

describe('useUserRoleForm', () => {
  it('hides the client field for all-client roles', () => {
    expect(clientFieldMode('admin')).toBe('hidden')
    expect(clientFieldMode('poweruser')).toBe('hidden')
  })

  it('uses a multi-select for leader', () => {
    expect(clientFieldMode('leader')).toBe('multi')
  })

  it('uses a single-select for the single-client scoped roles', () => {
    expect(clientFieldMode('supervisor')).toBe('single')
    expect(clientFieldMode('operator')).toBe('single')
    expect(clientFieldMode('viewer')).toBe('single')
  })

  it('requires a client for every scoped role and none for all-client roles', () => {
    expect(clientRequired('leader')).toBe(true)
    expect(clientRequired('supervisor')).toBe(true)
    expect(clientRequired('operator')).toBe(true)
    expect(clientRequired('viewer')).toBe(true)
    expect(clientRequired('admin')).toBe(false)
    expect(clientRequired('poweruser')).toBe(false)
  })
})
