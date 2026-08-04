# Justified-Delay Flag — Cycle 2 Design

**Date:** 2026-08-04
**Status:** Approved (user-reviewed brainstorm)
**Roadmap:** Cycle 2 of `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`; answers management question **Q3** (`docs/reporting/reporting-capabilities-and-gaps.md` §4): *justified vs unjustified lateness* — the concept behind PGI's Delivery Performance exclusion, never its layout (permanent no-carbon-copy position).

## 1. Problem

Delivery performance today is a single gross number: `calculate_true_otd` / the standard OTD service count every late order identically. Management practice distinguishes *justified* delays (customer-caused, force majeure) from *unjustified* ones — without the distinction, the metric punishes the plant for delays it did not cause, and there is no data to argue otherwise. Nothing in the model records why a late order was late.

## 2. Decisions (settled in this brainstorm)

1. **3-state classification, unclassified default.** Nullable `delay_classification` on `WORK_ORDER`: `NULL` = unclassified (default), `justified`, `unjustified`. No order is silently labeled unjustified; unclassified is a visible completeness signal (optional-first capture policy).
2. **Static reason enum + note.** Justification reasons are a small controlled vocabulary (Cycle 1 pattern: static enum, i18n en+es), plus an optional free-text note. No catalog table.
3. **Capture in the WO edit dialog, late-only, supervisory tier.** Section renders only for late orders; editable by admin/poweruser/leader/supervisor; backend rejects classification on non-late orders.
4. **Minimal reporting rollup:** OTD gains net-of-justified alongside gross, late-state counts, and a justified-by-reason breakdown. Pivots wait for Cycle 4.

## 3. Data model

### 3.1 Taxonomy module — `backend/orm/delay_taxonomy.py` (mirrors `downtime_taxonomy.py`)

- `DelayClassificationEnum(str, Enum)`: `JUSTIFIED = "justified"`, `UNJUSTIFIED = "unjustified"`. (Unclassified is the ABSENCE of a value — never an enum member, never offered in UI.)
- `JustifiedDelayReasonEnum(str, Enum)`: `CUSTOMER_REQUEST = "customer_request"`, `CUSTOMER_CHANGE_ORDER = "customer_change_order"`, `MATERIAL_SUPPLIER_DELAY = "material_supplier_delay"`, `FORCE_MAJEURE = "force_majeure"`, `UPSTREAM_HOLD = "upstream_hold"`, `OTHER = "other"`.

### 3.2 `WORK_ORDER` columns (all nullable — no default backfill needed)

| Column | Type | Meaning |
|---|---|---|
| `delay_classification` | String(20) | NULL / `justified` / `unjustified` |
| `justified_delay_reason` | String(40) | reason enum value; only meaningful (and only stored) when classification = `justified` |
| `delay_classification_note` | Text | optional free text, either classification |

ORM `@validates` on both enum columns (None allowed; non-enum values raise `ValueError`) — same Cycle 1 pattern that closed the seeder bypass.

### 3.3 Migration

Alembic revision `0003_justified_delay_columns`, `down_revision = "0002_downtime_taxonomy"` — the **first DDL revision since the baseline**: three `add_column` calls (SQLite + MariaDB portable; nullable columns need no batch/table-rebuild). Downgrade drops them. The baseline-equality CI guard (`upgrade head == Base.metadata`) continues to hold because metadata gains the same columns. No data pass.

## 4. Lateness rule — one shared definition

New helper in `backend/calculations/otd.py`:

```
def is_late(work_order, as_of: date) -> bool
```

using the existing `infer_planned_delivery_date` chain (`planned_ship_date → required_date → calculated`): late iff
- delivered (`actual_delivery_date` set) after the inferred planned date, **or**
- undelivered and the inferred planned date < `as_of`.

If no planned date can be inferred (`inference_source == "none"`), the order is not late (cannot be classified). This single function gates classification eligibility (API + UI `is_late` response field) and feeds the §6 metrics. No second lateness definition may exist — the plan adds a guard-style test asserting the API eligibility check and the metric layer call the same helper.

## 5. API rules (`WorkOrderUpdate` + update path)

`WorkOrderUpdate` gains `delay_classification: Optional[DelayClassificationEnum]`, `justified_delay_reason: Optional[JustifiedDelayReasonEnum]`, `delay_classification_note: Optional[str]`. Invariants enforced in the work-order update path (service/crud layer, with exact 4xx codes):

1. **Late-only:** any attempt to set/change `delay_classification` (or reason/note) on an order where `is_late(...)` is false → **422** naming the rule. Clearing (explicit `null`) is always allowed.
2. **Reason iff justified:** classification `justified` without a valid reason → **422**; classification `unjustified` or cleared → reason and note are cleared server-side (never stored inconsistently).
3. **Supervisory-tier fields:** if the payload touches any of the three fields and the caller is not in the supervisory tier (admin/poweruser/leader/supervisor) → **403**; other `WorkOrderUpdate` fields keep the route's existing guard untouched.
4. `WorkOrderResponse` gains the three fields plus computed `is_late: bool` (server-evaluated with `as_of = today`), so the UI never re-implements the lateness rule.

Update semantics follow the existing `exclude_unset=True` pattern: omitted fields are no-ops; explicit `null` clears.

## 6. Metrics — gross + net-of-justified

Both OTD calculation paths (`calculate_true_otd` in `backend/calculations/otd.py` and the standard/dual-view service `backend/services/dual_view/otd_service.py`) return, alongside the existing gross values:

- **`otd_net_of_justified`**: justified-late orders are treated as on-time — formula: `(on_time + justified_late) / total_delivered × 100` (denominator unchanged; only the late set shrinks). True-OTD mode applies the same adjustment to its inferred-date on-time set.
- **`late_counts`**: `{total, justified, unjustified, unclassified}` over the late orders in range.
- **`justified_by_reason`**: `{reason_value: count}` over justified-late orders in range.

Surfaced on: `GET /api/kpi/otd` (and its dual-view endpoints), the Excel comprehensive report's OTD row (gross + net side by side), and the KPI dashboard OTD card (net as secondary value). Undelivered-past-due orders participate in `late_counts` (they are classifiable) but not in OTD percentages (both gross and net remain delivered-based — unchanged semantics).

## 7. Entry UI

- **Work-order edit dialog** (existing WorkOrderManagement dialog): a "Delay classification" section rendered only when the selected order's `is_late` is true. Controls: classification select (Unclassified/–, Justified, Unjustified — where "Unclassified" submits `null`), reason select (visible + required iff Justified), note textarea. Disabled (read-only display) for non-supervisory roles.
- **Grid badge:** late rows show a compact chip — `unclassified` (warning tone), `justified` (info/success tone), `unjustified` (error tone) — driven by `is_late` + `delay_classification` from the response. Non-late rows show nothing.
- i18n en+es, static keys (`delay.*` block); referenced-keys gate.
- Frontend mirror constants `frontend/src/constants/delayTaxonomy.ts` (Cycle 1 pattern; lockstep comment).

## 8. Seeder

`_seed_operations.py` (sample client): the deterministic late orders from the #143 OTD-dip shaping get classifications — a fixed pattern of justified (cycling through real reasons), unjustified, and some left unclassified (completeness demo). `init_demo_database.py` gets the same treatment on its late orders. Both stay deterministic; enum members imported from the taxonomy module (never string literals).

## 9. Testing

- Taxonomy/ORM: enum membership, validator accept/reject, None allowed.
- Migration: upgrade adds columns (SQLite + MariaDB CI lanes); baseline-equality + no-create-all guards stay green; downgrade drops.
- Lateness helper: delivered-late / delivered-on-time / undelivered-past-due / undelivered-not-due / no-inferable-date cases, exact expected booleans.
- API invariants: late-only 422, reason-iff-justified 422, clear-cascades, field-level 403 (added to `test_permission_matrix.py`), happy paths per role tier — one expected code per test.
- Metrics: exact gross vs net derivations on a seeded set (e.g. 10 delivered, 2 justified-late, 1 unjustified-late, 1 unclassified-late → gross 60%, net 80% — derivation comments); by-reason counts.
- Frontend: dialog-section logic via extracted composable helpers (script-setup convention), badge state mapping; one Playwright guard: open a late WO, classify justified + reason, badge updates.
- Gates: i18n referenced-keys, `openapi_surface.json` regen only if route surface changes (schema-only change expected → likely untouched; verified via test_bootstrap), coverage ≥75%.

## 10. Delivery & success criteria

Single PR on `feat/justified-delay-flag`; standard pipeline (plan → SDD execution → /cross-review → PR → 7-check CI → user-confirmed merge → deploy Render + VM → live-verify). Live verification on VM MariaDB: migration adds columns, classify a real late order via the dialog, OTD card/endpoint shows gross vs net shift, Excel OTD row carries both. Concept register Q3 "Justified vs unjustified lateness": **missing → have** (re-graded in the living doc in this PR).

## 11. Out of scope

- Late-order review queue screen (Cycle 4's pivot layer is the natural home).
- Per-client reason catalogs; audit table for classification history (`updated_by` suffices).
- Any change to gross OTD semantics; priority-adherence metrics (separate concept).
- Flip-to-required for classification (capture policy: separate later change).
