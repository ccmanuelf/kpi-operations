# Add-User Dialog — All Six Roles + Role-Aware Client Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the admin Add/Edit-User dialog expose all six platform roles with correct labels, and make the client-assignment field behave per the role model, enforced by a backend invariant guard — fixing the mislabel that stored "Supervisor" selections as `poweruser`.

**Architecture:** A backend helper `validate_role_client_assignment` enforces role↔client consistency on create/update. A frontend pure module `useUserRoleForm.ts` exposes the tier rules (testable without mounting the component). `AdminUsers.vue` lists all six roles and renders the client field as hidden/single/multi per role, resetting on user-initiated role change.

**Tech Stack:** Vue 3.5 `<script setup>` + Vuetify 4, vue-i18n (en/es), vitest; FastAPI + Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-07-10-user-roles-dialog-design.md`.

## Global Constraints

- Six roles, exact strings: `admin`, `poweruser`, `leader`, `supervisor`, `operator`, `viewer` (backend `UserRole`, `backend/schemas/user.py` regex already accepts all six).
- Client-assignment rule: `admin`/`poweruser` → NO client (`client_id_assigned` empty/null); `leader` → multiple (comma-separated); `supervisor`/`operator`/`viewer` → exactly one. Violations rejected with **HTTP 422**.
- On **user-initiated** role change the client selection resets to empty; on **edit-load** an all-client role's stray client is dropped to null (do NOT reset a scoped user's client on load).
- i18n: every new key added to BOTH `frontend/src/i18n/locales/en.json` and `es.json` (referenced-keys gate + `@intlify/vue-i18n/no-raw-text` gate must stay green).
- Permissive assertions forbidden: each test asserts ONE exact value/status (no `in [...]`).
- Backend tests from `backend/`: `pytest tests/…`, coverage ≥ 75%. Frontend: `npm run test`, `npm run lint`; coverage thresholds 32/25/25/34.
- Conventional commits. Files under 500 lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/auth/role_rules.py` | Create | `validate_role_client_assignment` + role tier sets (single source of truth) |
| `backend/schemas/user.py` | Modify | `UserCreate` model-validator calls the helper |
| `backend/routes/users.py` | Modify (`update_user` ~L77-97) | validate effective role+client on partial update → 422 |
| `backend/tests/test_api/test_user_role_client_validation.py` | Create | create/update invariant matrix |
| `frontend/src/composables/useUserRoleForm.ts` | Create | `clientFieldMode`, `clientRequired`, tier constants |
| `frontend/src/composables/__tests__/useUserRoleForm.spec.ts` | Create | per-role unit tests |
| `frontend/src/views/admin/AdminUsers.vue` | Modify | 6-role list, `formatRole`/`getRoleColor`, role-aware client field |
| `frontend/src/i18n/locales/en.json`, `es.json` | Modify | `rolePoweruser`, `roleLeader`, `roleViewer`, `assignedClients` |

---

### Task 1: Backend role↔client invariant guard

**Files:**
- Create: `backend/auth/role_rules.py`
- Modify: `backend/schemas/user.py`, `backend/routes/users.py`
- Test: `backend/tests/test_api/test_user_role_client_validation.py`

**Interfaces:**
- Produces: `validate_role_client_assignment(role: str, client_id_assigned: str | None) -> None` (raises `ValueError` on violation); `ALL_CLIENT_ROLES`, `SCOPED_ROLES` frozensets.

- [ ] **Step 1: Write the failing backend tests**

Create `backend/tests/test_api/test_user_role_client_validation.py`:

```python
"""Role ↔ client-assignment invariant on the admin user API (all-client roles carry
no client; scoped roles require one). Backend mirror of the Add-User UI rules."""

STRONG = "Str0ng#Pass1"  # pragma: allowlist secret


def _payload(**over):
    base = {
        "username": "rc_user",
        "email": "rc_user@example.com",
        "password": STRONG,
        "full_name": "RC User",
        "role": "operator",
        "client_id_assigned": "CLIENT-A",
    }
    base.update(over)
    return base


class TestCreateRoleClientInvariant:
    def test_admin_with_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="a1", email="a1@e.com", role="admin"), headers=admin_auth_headers)
        assert r.status_code == 422

    def test_poweruser_with_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="p1", email="p1@e.com", role="poweruser"), headers=admin_auth_headers)
        assert r.status_code == 422

    def test_operator_without_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="o1", email="o1@e.com", role="operator", client_id_assigned=None), headers=admin_auth_headers)
        assert r.status_code == 422

    def test_viewer_without_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="v1", email="v1@e.com", role="viewer", client_id_assigned=""), headers=admin_auth_headers)
        assert r.status_code == 422

    def test_admin_without_client_ok(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="a2", email="a2@e.com", role="admin", client_id_assigned=None), headers=admin_auth_headers)
        assert r.status_code == 201

    def test_operator_with_client_ok(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="o2", email="o2@e.com", role="operator"), headers=admin_auth_headers)
        assert r.status_code == 201

    def test_leader_with_multi_client_ok(self, test_client, admin_auth_headers):
        r = test_client.post("/api/users", json=_payload(username="l1", email="l1@e.com", role="leader", client_id_assigned="C1,C2"), headers=admin_auth_headers)
        assert r.status_code == 201


class TestUpdateRoleClientInvariant:
    def _create_operator(self, test_client, admin_auth_headers, uname):
        r = test_client.post("/api/users", json=_payload(username=uname, email=f"{uname}@e.com", role="operator", client_id_assigned="CLIENT-A"), headers=admin_auth_headers)
        assert r.status_code == 201
        return r.json()["user_id"]

    def test_update_to_admin_keeping_client_rejected(self, test_client, admin_auth_headers):
        uid = self._create_operator(test_client, admin_auth_headers, "u_upd1")
        r = test_client.put(f"/api/users/{uid}", json={"role": "admin"}, headers=admin_auth_headers)
        assert r.status_code == 422

    def test_update_to_admin_clearing_client_ok(self, test_client, admin_auth_headers):
        uid = self._create_operator(test_client, admin_auth_headers, "u_upd2")
        r = test_client.put(f"/api/users/{uid}", json={"role": "admin", "client_id_assigned": ""}, headers=admin_auth_headers)
        assert r.status_code == 200

    def test_update_clearing_client_on_scoped_role_rejected(self, test_client, admin_auth_headers):
        uid = self._create_operator(test_client, admin_auth_headers, "u_upd3")
        r = test_client.put(f"/api/users/{uid}", json={"client_id_assigned": ""}, headers=admin_auth_headers)
        assert r.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_api/test_user_role_client_validation.py -v`
Expected: FAIL — several 201/200 where 422 expected (guard not implemented yet).

- [ ] **Step 3: Write the helper**

Create `backend/auth/role_rules.py`:

```python
"""Role ↔ client-assignment invariants — single source of truth.

Mirrors the role model in backend/orm/user.py:
  admin, poweruser              → access ALL clients; client_id_assigned must be empty.
  leader, supervisor, operator, viewer → client-scoped; require an assignment
                                         (leader may list several, comma-separated).
"""

ALL_CLIENT_ROLES = frozenset({"admin", "poweruser"})
SCOPED_ROLES = frozenset({"leader", "supervisor", "operator", "viewer"})


def validate_role_client_assignment(role: str, client_id_assigned: str | None) -> None:
    """Raise ValueError if the role/client pairing violates the tenant model."""
    assigned = bool(client_id_assigned and str(client_id_assigned).strip())
    if role in ALL_CLIENT_ROLES and assigned:
        raise ValueError(f"role '{role}' accesses all clients and must not be assigned a client")
    if role in SCOPED_ROLES and not assigned:
        raise ValueError(f"role '{role}' is client-scoped and requires at least one assigned client")
```

- [ ] **Step 4: Wire into `UserCreate` (schema-level → automatic 422)**

In `backend/schemas/user.py`: add `model_validator` to the import on line 5, and the shared import near the top:

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
```

Add near the top-level imports (after line 9):

```python
from backend.auth.role_rules import validate_role_client_assignment
```

Then add to the `UserCreate` class (after the `validate_password_policy` validator, still inside the class):

```python
    @model_validator(mode="after")
    def _validate_role_client(self):
        validate_role_client_assignment(self.role, self.client_id_assigned)
        return self
```

- [ ] **Step 5: Wire into `update_user` (partial → effective pair → 422)**

In `backend/routes/users.py`, add the import near the other imports at the top:

```python
from backend.auth.role_rules import validate_role_client_assignment
```

In `update_user`, replace the body between loading `user` and the `update_data` loop (currently around lines 88-93) so the effective role/client are validated first:

```python
    update_data = user_data.model_dump(exclude_unset=True)

    effective_role = update_data.get("role", user.role)
    effective_client = update_data.get("client_id_assigned", user.client_id_assigned)
    try:
        validate_role_client_assignment(effective_role, effective_client)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    for field, value in update_data.items():
        if field == "password" and value:
            setattr(user, "password_hash", get_password_hash(value))
        elif hasattr(user, field):
            setattr(user, field, value)
```

(Leave the `user.updated_at = …`, `db.commit()`, `db.refresh(user)`, `return user` lines below unchanged.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_api/test_user_role_client_validation.py -v`
Expected: 10 passed.

- [ ] **Step 7: Run the full backend suite (coverage gate + no regressions)**

Run: `cd backend && pytest tests/ -q`
Expected: all pass, coverage ≥ 75%. (If a pre-existing user-creation test now sends an invalid role/client combo, that test was asserting behavior this fix deliberately changes — report it as a plan/reality conflict rather than weakening the guard.)

- [ ] **Step 8: Commit**

```bash
git add backend/auth/role_rules.py backend/schemas/user.py backend/routes/users.py backend/tests/test_api/test_user_role_client_validation.py
git commit -m "feat(users): enforce role↔client-assignment invariant on create/update (422)"
```

---

### Task 2: Frontend `useUserRoleForm` pure module + tests

**Files:**
- Create: `frontend/src/composables/useUserRoleForm.ts`
- Test: `frontend/src/composables/__tests__/useUserRoleForm.spec.ts`

**Interfaces:**
- Produces: `clientFieldMode(role: string): 'hidden' | 'single' | 'multi'`; `clientRequired(role: string): boolean`; `ALL_CLIENT_ROLES`, `MULTI_CLIENT_ROLES`, `SCOPED_ROLES` string arrays.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/composables/__tests__/useUserRoleForm.spec.ts`:

```ts
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/composables/__tests__/useUserRoleForm.spec.ts`
Expected: FAIL — cannot resolve `../useUserRoleForm`.

- [ ] **Step 3: Write the module**

Create `frontend/src/composables/useUserRoleForm.ts`:

```ts
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/composables/__tests__/useUserRoleForm.spec.ts`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useUserRoleForm.ts frontend/src/composables/__tests__/useUserRoleForm.spec.ts
git commit -m "feat(users-ui): useUserRoleForm — role-aware client-field rules"
```

---

### Task 3: `AdminUsers.vue` six-role list + role-aware client field + i18n

**Files:**
- Modify: `frontend/src/views/admin/AdminUsers.vue`
- Modify: `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/es.json`

**Interfaces:**
- Consumes: `clientFieldMode` from `@/composables/useUserRoleForm` (Task 2); the backend 422 guard (Task 1) is the safety net if the UI is bypassed.

- [ ] **Step 1: Add i18n keys (both locales)**

In `frontend/src/i18n/locales/en.json`, under `admin.users`, add alongside the existing `roleAdmin`/`roleSupervisor`/`roleOperator`:

```json
        "rolePoweruser": "Power User",
        "roleLeader": "Leader",
        "roleViewer": "Viewer",
        "assignedClients": "Assigned Clients",
```

In `frontend/src/i18n/locales/es.json`, same location:

```json
        "rolePoweruser": "Superusuario",
        "roleLeader": "Líder",
        "roleViewer": "Visor",
        "assignedClients": "Clientes Asignados",
```

(Keep the existing `roleSupervisor` = "Supervisor"/"Supervisor" and `assignedClient` singular keys.)

- [ ] **Step 2: Update the script — imports, roleOptions, formatRole, getRoleColor, client handling**

In `frontend/src/views/admin/AdminUsers.vue`:

(a) Extend the Vue import (line 208) — add `watch` is NOT needed (we use an event handler); import the composable. After line 212 (`import api from '@/services/api'`) add:

```javascript
import { clientFieldMode } from '@/composables/useUserRoleForm'
```

(b) Replace `roleOptions` (lines 253-257) with all six, correctly mapped:

```javascript
const roleOptions = computed(() => [
  { title: t('admin.users.roleAdmin'), value: 'admin' },
  { title: t('admin.users.rolePoweruser'), value: 'poweruser' },
  { title: t('admin.users.roleLeader'), value: 'leader' },
  { title: t('admin.users.roleSupervisor'), value: 'supervisor' },
  { title: t('admin.users.roleOperator'), value: 'operator' },
  { title: t('admin.users.roleViewer'), value: 'viewer' }
])
```

(c) Replace `getRoleColor` (lines 287-292):

```javascript
const getRoleColor = (role) => {
  const colors = {
    admin: 'error',
    poweruser: 'warning',
    leader: 'primary',
    supervisor: 'info',
    operator: 'success',
    viewer: 'secondary'
  }
  // 'secondary' is a real theme tonal palette (dark text on a light container = AA).
  return colors[role] || 'secondary'
}
```

(d) Replace `formatRole` (lines 294-297):

```javascript
const formatRole = (role) => {
  const labels = {
    admin: t('admin.users.roleAdmin'),
    poweruser: t('admin.users.rolePoweruser'),
    leader: t('admin.users.roleLeader'),
    supervisor: t('admin.users.roleSupervisor'),
    operator: t('admin.users.roleOperator'),
    viewer: t('admin.users.roleViewer')
  }
  return labels[role] || role
}
```

(e) Add a `clientMulti` computed (array ↔ comma-string proxy) and an `onRoleChange` handler. Add them right after the `rules` object (after line 268):

```javascript
const clientMulti = computed({
  get: () => {
    const v = userFormData.value.client_id_assigned
    return v ? v.split(',') : []
  },
  set: (arr) => {
    userFormData.value.client_id_assigned = arr && arr.length ? arr.join(',') : null
  }
})

// User-initiated role change (NOT programmatic edit-load) always resets the client
// selection, so a stale scope can never survive a role switch.
const onRoleChange = () => {
  userFormData.value.client_id_assigned = null
}
```

(f) Extend the `rules` object (lines 264-268) to add a multi-select rule:

```javascript
const rules = {
  required: v => !!v || t('admin.users.fieldRequired'),
  clientsRequired: v => (Array.isArray(v) && v.length > 0) || t('admin.users.fieldRequired'),
  email: v => /.+@.+\..+/.test(v) || t('admin.users.invalidEmail'),
  password: v => (v && v.length >= 8) || t('admin.users.passwordMinLength')
}
```

(g) In `editUser` (lines 341-352), normalize the loaded client for all-client roles so editing a mis-scoped user drops the stray client:

```javascript
const editUser = (user) => {
  editingUser.value = user
  userFormData.value = {
    username: user.username,
    email: user.email,
    full_name: user.full_name,
    password: '',
    role: user.role,
    client_id_assigned: clientFieldMode(user.role) === 'hidden' ? null : user.client_id_assigned
  }
  userDialog.value = true
}
```

- [ ] **Step 3: Update the template — role select handler + conditional client field**

In `frontend/src/views/admin/AdminUsers.vue`, the role `v-select` (lines 149-158) gains the change handler — add this attribute inside that `<v-select>` (e.g. after the `v-model` line):

```html
              @update:model-value="onRoleChange"
```

Replace the single client `<v-select>` (lines 159-169) with the mode-driven pair:

```html
            <v-select
              v-if="clientFieldMode(userFormData.role) === 'single'"
              v-model="userFormData.client_id_assigned"
              :items="clients"
              item-title="client_name"
              item-value="client_id"
              :label="t('admin.users.assignedClient')"
              prepend-icon="mdi-domain"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
            <v-select
              v-else-if="clientFieldMode(userFormData.role) === 'multi'"
              v-model="clientMulti"
              :items="clients"
              item-title="client_name"
              item-value="client_id"
              :label="t('admin.users.assignedClients')"
              prepend-icon="mdi-domain"
              multiple
              chips
              :rules="[rules.clientsRequired]"
              variant="outlined"
              density="comfortable"
            />
```

(admin/poweruser render no client field; `client_id_assigned` stays `null`.)

- [ ] **Step 4: Lint + run the frontend unit suite**

Run: `cd frontend && npm run lint && npx vitest run src/composables/__tests__/useUserRoleForm.spec.ts`
Expected: lint clean (no raw-text / unresolved-i18n-key errors — new keys exist in both locales), composable tests pass.

- [ ] **Step 5: Full frontend test + typecheck**

Run: `cd frontend && npm run test && npm run typecheck`
Expected: all pass; coverage thresholds (32/25/25/34) still met; `vue-tsc` clean (the `clientMulti` computed + composable types resolve).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/admin/AdminUsers.vue frontend/src/i18n/locales/en.json frontend/src/i18n/locales/es.json
git commit -m "fix(users-ui): expose all six roles + role-aware client field (fixes Supervisor→poweruser mislabel)"
```

---

## Verification (whole-PR definition of done)

1. `cd backend && pytest tests/` — all pass, coverage ≥ 75%.
2. `cd frontend && npm run test && npm run lint && npm run typecheck` — all pass, thresholds met.
3. Dialog lists all six roles (correct labels, en + es); selecting "Supervisor" stores `supervisor` (not `poweruser`); admin/poweruser hide the client field; leader is multi-select; the API rejects invalid role/client combos with 422.
4. Only the files in the File Structure table changed (`git diff main...HEAD --stat`).
5. Final whole-branch review + `/code-review` + `/cross-review`; all 7 CI checks green; merge on user confirmation.
6. Post-merge: deploy to the VM; then correct `sample_supervisor` (poweruser+SAMPLE_REF → supervisor+SAMPLE_REF) via the fixed Edit-User dialog as part of the SAMPLE-REF dataset build.
