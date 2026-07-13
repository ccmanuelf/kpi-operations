import { describe, it, expect } from 'vitest'
import { clientFieldMode, clientRequired, buildUserUpdatePayload } from '../useUserRoleForm'

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

describe('buildUserUpdatePayload', () => {
  it('omits password when blank', () => {
    const payload = buildUserUpdatePayload({ username: 'alice', password: '' })
    expect('password' in payload).toBe(false)
  })

  it('keeps password when non-empty', () => {
    const payload = buildUserUpdatePayload({ username: 'alice', password: 'Str0ng#1' })
    expect(payload.password).toBe('Str0ng#1')
  })

  it('passes other fields through unchanged', () => {
    const payload = buildUserUpdatePayload({
      username: 'alice',
      email: 'alice@example.com',
      role: 'operator',
      password: ''
    })
    expect(payload.username).toBe('alice')
    expect(payload.email).toBe('alice@example.com')
    expect(payload.role).toBe('operator')
  })
})
