# Seeder Realistic Shift-Time Timestamps (Design)

**Date:** 2026-07-17
**Status:** Approved design → ready for implementation plan
**Context:** The prod-safe demo seeder (`backend/scripts/_seed_operations.py`, `seed_daily_data`) timestamps every seeded entry at **midnight** (`datetime.combine(day, datetime.min.time())`). This is (a) unrealistic — no intraday time — and (b) the reason the just-shipped DateTime date-range boundary fix (#145) can't be demonstrated on live seed data: a same-day query `<= end_date(midnight)` still includes `00:00` rows, so the intraday-drop bug never manifests with midnight-only data.

## Goal

Timestamp seeded operational entries at their **shift's actual start time** instead of midnight, so the demo data is realistic (entries occur during their shift) and the boundary fix is naturally demonstrable (a plain same-day API query exercises intraday rows). Deterministic, prod-safe, existing seeder tests stay green.

## The change

`seed_daily_data` binds `product, shift, line = products[0], shifts[0], lines[0]` and has **two** `day_dt = datetime.combine(day, datetime.min.time())` sites:
1. the per-work-order production/quality/downtime daily loop (~line 340),
2. the attendance per-employee-per-day loop (~line 455).

Replace `datetime.min.time()` with `shift.start_time` at **both** sites:

```python
# before
day_dt = datetime.combine(day, datetime.min.time())
# after
day_dt = datetime.combine(day, shift.start_time)
```

`shift = shifts[0]` is the seeded **"Day"** shift; `Shift.start_time` is a `Time` column and the factory (`create_shift`) stores it via `time.fromisoformat(...)`, so `shift.start_time` is a `datetime.time(6, 0)` object (verified empirically, in-memory and after refresh). No string-coercion guard is needed — `datetime.combine(day, shift.start_time)` yields `day @ 06:00`.

Nothing else changes: same deterministic `rng_for` streams, same PKs, same counts, same INSERT-only prod-safety, allowlist unchanged.

## Why this is safe / correct

- **Deterministic:** `shift.start_time` is seeded and fixed (06:00 for the Day shift); no new randomness; re-seeding is byte-identical.
- **No read-side impact:** every KPI read groups by `func.date(shift_date)` (time-agnostic) or counts entries — none depend on `shift_date` being midnight. The availability trend uses `entries × 8`, unaffected. The date-boundary-fixed endpoints (#145) already handle intraday timestamps correctly.
- **Prod-safe:** no schema/DDL, no drop/create, allowlist and guards unchanged; still INSERT-only.
- **Scope-guarded:** only the two `day_dt` lines change. Spreading entries across the shift (production at start, quality mid-shift, downtime later) is deliberately **out of scope** (YAGNI) — a single realistic non-midnight time meets every goal. The seeder is single-shift (uses `shifts[0]`); multi-shift distribution is not introduced.

## Testing

- **Existing seeder tests stay green:** they assert on dates (`func.date` grouping), counts, determinism, and FK-order — none assert `shift_date == midnight`. The plan verifies this with a full `test_seed_sample_client.py` run.
- **New assertion:** after seeding, a seeded `ProductionEntry.shift_date` (and an `AttendanceEntry.shift_date`) carries the shift's start time — i.e. `.time() == shift.start_time` (non-midnight, `06:00`). This pins the realism change.
- **Deploy = `--reset` re-seed** of the DEMO clients on the VM (same as the seed-credibility polish): `seed_sample_client --reset --days 90 --anchor <today>`.
- **Live boundary demo (the payoff):** after the re-seed, a plain single-day API query for a day with data returns rows whose underlying entries are at 06:00 — the same query on the *pre-#145* code would have dropped them. Concretely, verify a same-day `defects-by-type` / `quality/trend` for a data day is non-empty on the live VM MariaDB (no probe row needed).

## Out of Scope / Deferred

- Per-entry-type or randomized intra-shift times (production vs quality vs downtime at different hours) — YAGNI.
- Multi-shift assignment of daily data — the seeder intentionally uses one shift.
- Night-shift (`shifts[1]`) data — unchanged.

## Related Memory

[[seed-sample-client-feature]] (the seeder + `--reset` re-seed flow), [[kpi-serialization-and-date-boundary-fixes]] (the boundary fix this makes demonstrable + the midnight-timestamp note), [[verify-rigorously-not-sample]] (live-validate on the real DB).
