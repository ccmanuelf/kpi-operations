# Seed-Credibility Polish (Design)

**Date:** 2026-07-16
**Status:** Approved design → ready for implementation plan
**Context:** The prod-safe demo seeder (`backend/scripts/seed_sample_client.py` + `_seed_*.py`, shipped #138/#140) populates DEMO clients so the app can be validated as a real user. Live UI validation surfaced two data-credibility gaps that make the WIP-Aging and OTD dashboards read as broken. This polish fixes the *seeded data*, not the read-side metrics.

## Goal

Make WIP-Aging and On-Time-Delivery show credible, non-zero values on the seeded DEMO clients, and — because the diagnostic charts (SP1 #141 + SP2 #142) now render per-metric out-of-control tooltips with data-driven causes — shape the OTD series so it produces at least one **out-of-control point** whose SP2 cause tooltip is demoable.

## The two gaps (root causes, verified live on VM MariaDB)

1. **WIP-Aging shows 0 days.** `seed_holds` (`backend/scripts/_seed_operations.py:216`) sets `hold_date = datetime.combine(anchor, ...)` for **every** hold. The WIP-Aging trend (`backend/routes/holds.py:472`) computes, per day, `avg(date_diff_days(current_date, hold_date))` over holds active that day. With `hold_date == anchor`, active-hold age is 0.
2. **OTD shows ~0%.** The OTD trend (`backend/routes/kpi/trends.py:388`) groups WOs by `func.date(required_date)` over `[start,end]` and scores `on_time = sum(actual_delivery_date <= required_date)`. `seed_work_orders` (`_seed_operations.py:36`) **never sets `required_date`** (it varied `planned_ship_date`, the wrong field) and delivers only the 2 terminal WOs (SHIPPED/CLOSED). With `required_date` NULL everywhere, the OTD query returns nothing.

## Read-side facts the seed must satisfy (do not change these)

- **OTD threshold** (`_seed_reference.py:42`): `("otd", 95.0, 90.0, 80.0, "%", "Y")` → target 95, warning 90, **critical 80**, higher-is-better. A day whose OTD < 80% flags out-of-control (SP1 threshold arm). SP2's OTD cause (`late_work_orders`) then reports the count of WOs due that day that ran late.
- **OTD trend query** counts, per `required_date` day: `total = count(WO)`, `on_time = sum(actual_delivery_date <= required_date)`. An **undelivered** WO (`actual_delivery_date` NULL) counts in `total` but not `on_time` (NULL comparison → miss). Default window last 30 days; the chart's default range is last 90 days.
- **WIP-Aging trend** has **no KPIThreshold row** → SPC-only OOC (I-MR, needs ≥8 daily points, flags beyond ±3σ). A static active-hold set yields a smooth age ramp (near-constant moving range → no SPC flag); an SPC flag requires a **discontinuity** (a hold entering or resuming mid-window). Guaranteeing a 3σ breach is not attempted; realistic non-zero aging is the firm deliverable, the WIP OOC flag is best-effort.

## Design

All changes are confined to `backend/scripts/_seed_operations.py` (`seed_holds` and `seed_work_orders`) plus tests. INSERT-only, deterministic via the existing `rng_for(...)` sha256 helper, prod-safe (no schema/DDL, allowlist unchanged). No ORM or read-side changes.

### 1. Holds → realistic WIP aging (`seed_holds`)

- Replace the flat `hold_date = anchor` with a **deterministic backdate** per hold: `hold_date = anchor − rng_for(cid, "hold_age", i).randint(10, 70)` days (10–70 day spread).
- Guarantee at least one **active** (`ON_HOLD`) hold is **chronic** (~60–70 days old) so WIP-Aging shows a pronounced non-zero age and the hold populates the "overdue" bucket. (Deterministically assign the oldest backdate to an open-status hold.)
- Set `resume_date` on the **resolved** statuses (`RESUMED`, `RELEASED`, `CANCELLED`, `SCRAPPED`) to a deterministic date strictly between that hold's `hold_date` and `anchor`. This is correct inactive semantics (a resolved hold has a resume date) **and** the resume events introduce the avg-age discontinuity that makes an SPC WIP-Aging OOC flag *likely* (best-effort demo).
- Leave `hold_reason="QUALITY_ISSUE"`, `hold_status`, WO linkage, and the deterministic client-scoped PK (`HOLD-{client_id}-{i:03d}`) unchanged.

### 2. Existing 10 WOs → set `required_date` (`seed_work_orders`)

- Set `required_date` on **every** WO, derived from its existing `planned_ship_date` (e.g. `required_date = planned_ship_date`), so all WOs participate in OTD.
- For the delivered terminal WOs (SHIPPED/CLOSED), set `actual_delivery_date` relative to `required_date`: one on-time (`<= required_date`), one late (`> required_date`), deterministically.

### 3. New delivered-history batch → credible + OOC-demoable OTD (`seed_work_orders`)

- Add **~15** lightweight WOs with PK `WO-{cid}-H{n:03d}`, status `SHIPPED`, minimal fields (`planned_quantity`, `style_model` via `TestDataFactory.create_work_order`).
- Spread `required_date` across the **last ~90 days** (relative to anchor) and set `actual_delivery_date` to hit an overall **~70% on-time / ~30% late** split, deterministic via `rng_for(cid, "otd_history", n)`.
- **Shape the series for a guaranteed OOC point:** designate **2–3 specific required-date days** on which multiple orders are all late, so those days' OTD falls **below the 80% critical threshold** → SP1 flags them out-of-control and SP2's cause tooltip reads "N order(s) due today ran late." The remaining days stay healthy (majority on-time). This guarantee is what the test pins.

### Determinism & MariaDB safety

- All dates come from `rng_for` (sha256-seeded, reproducible across processes and runs). No `date.today()`/`random` in the generators.
- New WOs are created with `TestDataFactory.create_work_order` (supplies all non-null columns) inside `seed_work_orders`, which runs **before** `seed_holds`; holds only reference pre-existing WOs, so FK insert order is preserved (no MariaDB FK violation). `required_date`/`actual_delivery_date` are plain columns (no raw-FK-without-relationship concern).
- The idempotency guard (`if existing: return existing` in `seed_work_orders`; `if ...first() is not None: return` in `seed_holds`) is unchanged — a re-run is a no-op.

### Deploy note

The seeder is idempotent, so applying this to the already-seeded VM requires a **`--reset` re-seed** of the DEMO clients (children-first per `RESET_TABLE_ORDER`), run as an explicit, confirmed step at deploy time:
`docker compose -f docker-compose.prod.yml exec backend python -m backend.scripts.seed_sample_client --reset --days 90 --anchor <today>`.

## Testing

Extend `backend/tests/test_scripts/test_seed_sample_client.py`:

- **Holds aging:** after seeding, every active (`ON_HOLD`/open-status) hold has `hold_date < anchor`, ages fall in the 10–70 day band, and at least one active hold is ≥ ~60 days old (chronic). Resolved-status holds have `resume_date` set and `hold_date < resume_date <= anchor`.
- **`required_date` set:** every WorkOrder (existing 10 + history batch) has a non-null `required_date`.
- **Delivered-history batch:** exists (~15 WOs with the `-H` PK marker), all `SHIPPED` with `actual_delivery_date` non-null, and the on-time/late split is approximately 70/30.
- **Guaranteed OTD OOC:** replicate the OTD trend query's per-day aggregation over the seeded WOs and assert **at least one required-date day has OTD < 80%** (so the diagnostic chart will flag it). Deterministic — the same seed always produces the same dip days.
- Keep the existing **determinism guard** (re-seed produces identical rows) and **`RESET_TABLE_ORDER` FK-order guard** green; keep the FK-enforcement (`PRAGMA foreign_keys=ON`) full-seed test green.

## Out of Scope / Deferred (YAGNI)

- No new WIP-Aging KPIThreshold row (would change the read-side; out of scope). WIP OOC stays SPC-only/best-effort.
- No change to daily production/quality/downtime/attendance seeding — those already produce credible availability/oee/quality/absenteeism causes (verified live).
- No guaranteed WIP-Aging OOC point (SPC-dependent; only made *likely* via resume-event discontinuities).

## Related Memory

[[seed-sample-client-feature]] (the seeder + its MariaDB-only bug classes), [[diagnostic-kpi-charts]] (the SP1/SP2 charts this data feeds), [[holds-julianday-mariadb-bug]] (portability), [[verify-rigorously-not-sample]] (live-validate against the running app).
