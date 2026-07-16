# Uniform Client-Scope Authorization (Design)

**Date:** 2026-07-16
**Status:** Approved design → ready for implementation plan
**Class:** Broken Access Control (horizontal privilege / cross-tenant read) — pre-existing, discovered during the SP2 (#142) and seed-polish (#143) reviews.

## The bug

28 read endpoints across 12 route files repeat this inline block verbatim:

```python
effective_client_id = client_id
if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
    effective_client_id = current_user.client_id_assigned
```

It trusts a caller-supplied `client_id` and only falls back to the user's assignment when **none** is passed. So a scoped user (leader/supervisor/operator/viewer) can pass `?client_id=<other-tenant>` and read another client's data. It is doubly broken: `role != "admin"` omits **`poweruser`** (also an all-clients role), and `client_id_assigned` is a **comma-separated list** used as a scalar (so a multi-client `leader` gets nothing even on the fallback path).

## Goal

Replace all 28 inline blocks with one shared, correct client-scope authorization dependency. A scoped user requesting an unauthorized `client_id` gets **403**. Admin/poweruser keep all-client access; `leader` keeps legitimate multi-client access. No existing behavior for authorized requests changes; the full test suite stays green; the change is validated end-to-end from the real user's standpoint in a browser.

## Role model (authoritative)

`backend/orm/user.py` `UserRole` + `backend/auth/role_rules.py`:
- **All-client roles** (`ALL_CLIENT_ROLES = {"admin", "poweruser"}`): see every client. `client_id_assigned` is NULL.
- **Scoped roles** (`{"leader", "supervisor", "operator", "viewer"}`): restricted to assigned client(s). `leader` may be assigned **multiple** clients (`MULTI_CLIENT_ROLES = {"leader"}`); the others effectively one.
- `client_id_assigned`: `String(500)`, nullable, **comma-separated list**. The authoritative parse is `middleware/client_auth.py:get_user_client_filter(user, db)`.

## Design

### 1. Core unit — `ClientScope` + `resolve_client_scope` (new, in `backend/auth/jwt.py`)

Co-located with the existing `get_current_*` guards; delegates the authorization decision to the already-correct `middleware/client_auth.py` helpers (`get_user_client_filter`, `ClientAccessError`).

```python
from dataclasses import dataclass
from typing import Optional
from fastapi import Query
from sqlalchemy import true
from backend.middleware.client_auth import get_user_client_filter, ClientAccessError

@dataclass(frozen=True)
class ClientScope:
    """Resolved, authorized set of clients for a request.
    client_ids is None => all clients (admin/poweruser); otherwise the exact
    authorized tuple (length 1 for a scoped single-client or a narrowed request,
    >1 for a leader querying their full set)."""
    client_ids: Optional[tuple[str, ...]]

    def filter(self, column):
        """SQLAlchemy clause scoping `column` to this scope. `true()` = no filter (all)."""
        return true() if self.client_ids is None else column.in_(self.client_ids)

    def as_single(self) -> Optional[str]:
        """Scalar client_id for legacy scalar-consuming service functions.
        None = all (admin/poweruser). Exactly one = that client. Multiple
        (a leader who did not narrow) => 400 asking them to specify a client_id."""
        if self.client_ids is None:
            return None
        if len(self.client_ids) == 1:
            return self.client_ids[0]
        raise HTTPException(status_code=400, detail="Multiple clients in scope; specify a client_id")

def resolve_client_scope(
    client_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientScope:
    allowed = get_user_client_filter(current_user, db)  # None=all; list=scoped; raises 403 if scoped & unassigned
    if client_id is not None:
        if allowed is not None and client_id not in allowed:
            raise ClientAccessError(detail=f"Not authorized for client {client_id}")  # 403
        return ClientScope((client_id,))
    return ClientScope(None if allowed is None else tuple(allowed))
```

Resolution matrix:

| Caller | `client_id` passed | Result |
|---|---|---|
| admin / poweruser | none | `ClientScope(None)` → all clients |
| admin / poweruser | any | `ClientScope((client_id,))` → narrowed to that client |
| scoped (operator/viewer/supervisor) | their own | `ClientScope((client_id,))` |
| scoped | someone else's | **403** |
| scoped, no assignment | any / none | **403** (from `get_user_client_filter`) |
| leader (multi) | one of theirs | `ClientScope((client_id,))` |
| leader | not theirs | **403** |
| leader | none | `ClientScope((c1, c2, ...))` → their full set (`.in_`) |

`Query` must be added to the `fastapi` import in `jwt.py`; `true` from `sqlalchemy`; `get_user_client_filter`/`ClientAccessError` from `middleware.client_auth`. `HTTPException`, `Depends`, `User`, `get_db`, `get_current_user` are already in scope.

### 2. Endpoint migration (28 sites, two patterns)

Each endpoint drops its own `client_id: Optional[str] = None` parameter and the inline block, and adds `scope: ClientScope = Depends(resolve_client_scope)`. Endpoints that use `current_user` only for scoping may drop that param; those that use it for anything else keep it (FastAPI de-dupes the shared sub-dependency).

- **SQL-filter endpoints (~24)** — replace
  `if effective_client_id: q = q.filter(Model.client_id == effective_client_id)`
  with `q = q.filter(scope.filter(Model.client_id))`.
  For `DefectDetail`, the column is `client_id_fk` (`scope.filter(DefectDetail.client_id_fk)`).
  `kpi/dashboard.py` applies `scope.filter(...)` to each of its ~7 heterogeneous sub-queries; `attendance.py` likewise across its shift/reason/dept/high-absence sub-queries.
- **Scalar-service endpoints (~4)** — `kpi/cause.py` (`driver(db, scope.as_single(), date)`), `jobs.py:223` (`calculate_job_rty_summary(..., scope.as_single())`), `quality/ppm_dpmo.py:276` (`calculate_dpmo_with_part_lookup(..., scope.as_single())`), `data_completeness.py:125` (`calculate_expected_entries(..., scope.as_single())`). The service signatures (`Optional[str]`) are unchanged.

### 3. The `onboarding._resolve_client_id` variant

`routes/onboarding.py:32` is a helper (not the inline block) with the same trust-the-caller flaw but different semantics (raises 400, admin must pass explicitly). Reconcile it to validate a caller-supplied `client_id` against the user's authorized set (403 on mismatch) using the same `get_user_client_filter` primitive, preserving its "admin must specify" behavior. It stays a helper (not the FastAPI dependency) because its call sites are not endpoint signatures — but it must no longer trust an arbitrary `client_id`.

### 4. Behavior preservation

- The `client_id` query parameter remains on every endpoint (now declared by the dependency's `Query(None)`), so the OpenAPI **route set and tags are unchanged** → the golden-master (`test_openapi_surface.py`, which compares route paths + tags) does **not** need regenerating and must stay green.
- Authorized requests (admin any client; scoped users on their own/assigned clients) return exactly what they did before.
- `true()` renders portably on SQLite + MariaDB; `.in_(tuple)` is portable.

## Testing

### Unit
- `ClientScope.filter`: `None` → `true()`; `("A",)` → `col.in_(("A",))`; `("A","B")` → `col.in_(("A","B"))`.
- `ClientScope.as_single`: `None`→`None`; `("A",)`→`"A"`; `("A","B")`→ raises 400.
- `resolve_client_scope` against the conftest fixtures (admin, operator-CLIENT-A, operator-CLIENT-B, leader "CLIENT-A,CLIENT-B"): every row of the resolution matrix, especially the **403** paths (operator→other client, unassigned scoped user) and the leader multi-client set.

### Integration (HTTP, per representative endpoint)
- operator-CLIENT-A + `?client_id=CLIENT-B` → **403** on a SQL-filter endpoint (e.g. `/api/kpi/efficiency/trend`) **and** a scalar-service endpoint (`/api/kpi/oee/cause` or `/api/kpi/quality/cause`).
- operator-CLIENT-A + `?client_id=CLIENT-A` (own) → **200**, data scoped to A.
- admin + `?client_id=CLIENT-B` → **200**, data scoped to B (narrowing works).
- leader "CLIENT-A,CLIENT-B" + `?client_id=CLIENT-B` → **200**; + `?client_id=CLIENT-C` → **403**.
- Rewrite `tests/test_api/test_data_completeness.py:454-468` (it reimplements the buggy block) to assert the corrected dependency behavior instead.

### Whole-suite
- `cd backend && pytest tests/` — coverage ≥75%, all green. Existing tenant-isolation tests (`test_all_endpoints.py` 403 gates, `test_hold_catalog_tenant_isolation.py`) must stay green.

### End-to-end browser smoke test (REQUIRED — user standpoint)
After the code is merged and deployed to the VM, run a **full browser-agent e2e smoke test from the real user's standpoint** — not just API assertions. This is a hard gate on "done": the fix touches the tenant boundary the whole app relies on, and prior live-validation caught bugs unit tests missed. The browser smoke test must:
1. **Log in as an all-client user** (admin/poweruser — `verify_bot`) and confirm the KPI dashboard + diagnostic charts load across clients, the client selector switches clients, and cause tooltips still render (SP2 unbroken).
2. **Log in as a scoped user** (an operator/viewer bound to one DEMO client) and confirm: (a) they see only their client's data; (b) the client selector does not expose, and the app does not load, another client's data; (c) attempting another client's data (via the selector if present, or a crafted request) is refused (no cross-tenant data appears).
3. Exercise the **previously-fixed surfaces** in the same pass so this is a genuine full regression from the user standpoint: WIP-Aging shows credible aging, OTD shows its out-of-control dip with the SP2 cause tooltip, and the 10 diagnostic charts render — for the logged-in user's authorized scope.
4. Report the walked steps, what was observed per role, and screenshots/DOM evidence. Any cross-tenant leakage visible to a scoped user is a release blocker.

If a scoped DEMO user does not already exist for the smoke test, create one on the VM (scoped to one DEMO client) as a confirmed, non-destructive step — do not alter existing users.

## Out of Scope / Deferred (YAGNI)

- CSV and capacity routes (gated by `get_current_planner`/supervisor, planner-only) — not in the vulnerable set.
- Write endpoints (`floating_pool.py` already forces the user's own client) — not vulnerable.
- No change to the role model, JWT contents, or the `client_auth.py` primitives themselves (only consumed).
- No new UI for client selection — the fix is server-side enforcement.

## Related Memory

[[user-roles-dialog-fix]] (the six-role model + `validate_role_client_assignment`), [[diagnostic-kpi-charts]] (SP2, the /cause endpoint this scopes), [[verify-rigorously-not-sample]] (validate against the running app), [[production-deployment-planning]] (single-tenancy policy on the VM).
