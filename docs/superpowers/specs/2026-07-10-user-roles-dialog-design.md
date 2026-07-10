# Add-User Dialog — Expose All Six Roles + Role-Aware Client Assignment — Design

**Date:** 2026-07-10
**Status:** Design approved (user, 2026-07-10) — pending implementation plan
**Trigger:** During SAMPLE-REF onboarding-data setup on the live VM, the Add-User dialog was found to expose only 3 of the platform's 6 roles — AND to mislabel one of them.

## Problem

`frontend/src/views/admin/AdminUsers.vue` `roleOptions` (lines 253-257) offers only three choices, and the middle one is **mislabeled**:

```js
const roleOptions = computed(() => [
  { title: t('admin.users.roleAdmin'),      value: 'admin' },
  { title: t('admin.users.roleSupervisor'), value: 'poweruser' },   // label "Supervisor" → value poweruser (!)
  { title: t('admin.users.roleOperator'),   value: 'operator' },
])
```

Consequences, verified on the live VM:
- `supervisor`, `leader`, `viewer` are **unreachable** from the UI.
- Selecting "Supervisor" stores **`role=poweruser`**. The sample user `sample_supervisor` is currently `role=poweruser` with `client_id_assigned=SAMPLE_REF` — a **contradiction**, because `poweruser` is an all-client role (per the role model, `client_id_assigned` is NULL for admin/poweruser).

The backend is **not** the constraint: `backend/schemas/user.py` already validates `role` against `^(admin|poweruser|leader|supervisor|operator|viewer)$` (lines 50, 99). This is a frontend defect plus a missing API-level role↔client invariant.

## Role model (authoritative — `backend/orm/user.py`)

Six roles, write authority descending `ADMIN > POWERUSER > LEADER ≈ SUPERVISOR > OPERATOR > VIEWER`:
- **admin, poweruser** — access ALL clients; `client_id_assigned` is NULL (no scope).
- **leader** — MULTIPLE clients; `client_id_assigned` is a comma-separated list.
- **supervisor, operator, viewer** — single client; `client_id_assigned` is one client_id. Viewer is read-only.

## Design

### 1. Frontend — role list corrected & complete (`AdminUsers.vue` + i18n)

`roleOptions` becomes all six, ordered by descending authority, with correct label→value mapping:

| # | Label key | en | es | value |
|---|-----------|----|----|-------|
| 1 | `roleAdmin` | Admin | Admin | `admin` |
| 2 | `rolePoweruser` (new) | Power User | Superusuario | `poweruser` |
| 3 | `roleLeader` (new) | Leader | Líder | `leader` |
| 4 | `roleSupervisor` | Supervisor | Supervisor | `supervisor` |
| 5 | `roleOperator` | Operator | Operador | `operator` |
| 6 | `roleViewer` (new) | Viewer | Visor | `viewer` |

- Add `rolePoweruser`, `roleLeader`, `roleViewer` to both `frontend/src/i18n/locales/{en,es}.json` under `admin.users`.
- **Fix the mislabel:** `roleSupervisor` now maps to value `supervisor` (not `poweruser`); `poweruser` gets its own `rolePoweruser` label.
- `formatRole` (line ~295) and `getRoleColor` (line ~287) gain entries for all six values. Colors: pick from the existing palette, one per role, no two scoped roles sharing a color where avoidable (cosmetic).
- The same `roleOptions` feeds the role **filter** dropdown, so filtering also covers all six for free.

### 2. Frontend — role-aware client-assignment field

The tier rules live in a **pure module** `frontend/src/composables/useUserRoleForm.ts` (importable + unit-testable without reaching `<script setup>` internals — per the project's frontend-testing convention). It exports:

```ts
export const ALL_CLIENT_ROLES = ['admin', 'poweruser'] as const      // client_id_assigned = null
export const MULTI_CLIENT_ROLES = ['leader'] as const                // comma-separated list
export const SCOPED_ROLES = ['leader', 'supervisor', 'operator', 'viewer'] as const

export function clientFieldMode(role: string): 'hidden' | 'single' | 'multi'
// 'hidden' for admin/poweruser; 'multi' for leader; 'single' for supervisor/operator/viewer

export function clientRequired(role: string): boolean   // true for every SCOPED_ROLES member
```

`AdminUsers.vue` consumes these:
- **On every role change**, reset `userFormData.client_id_assigned` to empty (`null`). This is the single, unambiguous rule — it forces a deliberate re-pick under the new role's field and guarantees an all-client role can never keep a stale scope. No value is silently carried between single/multi/hidden modes.
- `clientFieldMode(role) === 'hidden'` (admin/poweruser) → do not render the Assigned-Client field; the value stays `null`.
- `'single'` (supervisor/operator/viewer) → render the current single-select `v-autocomplete`, **required**.
- `'multi'` (leader) → render a multi-select `v-autocomplete` (`multiple` + chips). The component maps the selected array ↔ the comma-separated `client_id_assigned` string (join on save; split on edit-load).
- `formValid` gains a rule: when `clientRequired(role)` is true, `client_id_assigned` must be non-empty.

### 3. Backend — shared role↔client invariant guard

A helper `validate_role_client_assignment(role: str, client_id_assigned: str | None) -> None` (in `backend/schemas/user.py` or a small `backend/auth/role_rules.py`), raising `ValueError` (surfaced as HTTP 422) on violation:
- `role in {admin, poweruser}` and `client_id_assigned` is truthy → error "all-client roles carry no client assignment".
- `role in {leader, supervisor, operator, viewer}` and `client_id_assigned` is falsy → error "this role requires at least one assigned client".

Called by:
- `create_user` (`backend/routes/users.py`) — always (both fields present).
- `update_user` — compute the **effective** role and client (incoming value if present, else the persisted user's current value) and validate the resulting pair, so a partial update can't produce an invalid combination.

This makes the API enforce the same invariant as the UI (defense in depth); the schema regex still gates the role vocabulary.

### 4. Tests

- **Frontend unit** — `frontend/src/composables/__tests__/useUserRoleForm.spec.ts`: for each of the six roles assert `clientFieldMode` ('hidden' for admin/poweruser, 'multi' for leader, 'single' for supervisor/operator/viewer) and `clientRequired` (true for the four scoped roles, false for admin/poweruser). Pure-function tests, no component mount.
- **Backend unit** — extend `backend/tests/test_routes/` (or `test_api/`): `create_user` returns 422 for `admin`+client, `poweruser`+client, and each scoped role with no client; returns 201 for `admin` (no client), `operator`+one client, `leader`+`"C1,C2"`. `update_user`: setting role to an all-client role while a client is still assigned → 422; the reverse → 422. Assert ONE exact status per test (no permissive assertions).
- **i18n gates** — the existing referenced-keys gate and `@intlify/vue-i18n/no-raw-text` gate stay green because all new keys are added to both `en.json` and `es.json`.

## Definition of done

- The Add-User (and Edit-User) dialog lists all six roles with correct labels/values in en + es; selecting a role stores that exact role.
- The client field is hidden for admin/poweruser (and cleared), single-select-required for supervisor/operator/viewer, multi-select-required for leader.
- `create_user`/`update_user` reject invalid role↔client combinations with 422.
- Frontend + backend unit tests cover the matrix; full suites green (backend ≥ 75%; frontend thresholds); i18n gates green; all 7 CI checks green; `/code-review` + `/cross-review`; merge on user confirmation.
- Post-merge: deploy to the VM; then, as part of the SAMPLE-REF dataset build, correct `sample_supervisor` (poweruser+SAMPLE_REF → supervisor+SAMPLE_REF) and create the remaining role examples.

## Out of scope

- Correcting existing mis-roled users is a data task done during the SAMPLE-REF dataset build (item 2A), not this code PR.
- Role-based *authorization* changes (guard tiers in `backend/auth/jwt.py`) — unchanged; this fix only aligns user *creation/editing* with the existing model.
- Any redesign of the user table, permissions matrix, or the register endpoint.
