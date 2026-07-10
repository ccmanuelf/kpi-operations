/**
 * Role ↔ client-assignment UI rules (single source of truth for the Add/Edit-User
 * dialog). Mirrors backend/auth/role_rules.py and the role model in
 * backend/orm/user.py. Pure functions — unit-tested without mounting the component.
 *
 *   admin, poweruser              → access ALL clients; no client field.
 *   leader                        → multiple clients (comma-separated); multi-select.
 *   supervisor, operator, viewer  → single client; single-select, required.
 */

export const ALL_CLIENT_ROLES = ['admin', 'poweruser'] as const
export const MULTI_CLIENT_ROLES = ['leader'] as const
export const SCOPED_ROLES = ['leader', 'supervisor', 'operator', 'viewer'] as const

export type ClientFieldMode = 'hidden' | 'single' | 'multi'

export function clientFieldMode(role: string): ClientFieldMode {
  if ((ALL_CLIENT_ROLES as readonly string[]).includes(role)) return 'hidden'
  if ((MULTI_CLIENT_ROLES as readonly string[]).includes(role)) return 'multi'
  return 'single'
}

export function clientRequired(role: string): boolean {
  return (SCOPED_ROLES as readonly string[]).includes(role)
}
