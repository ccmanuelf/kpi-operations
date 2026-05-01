# `yield_baseline_source`

**Allowed values:** `theoretical`, `demonstrated`, `contractual`
**Default:** `theoretical`
**Owner:** Quality leadership (proposes), Finance (approves)

## What it is

Decides which baseline the **Quality Score** (a 0–100 weighted index) is
graded against:

- `theoretical`: the engineering / design-of-experiments yield target —
  what the process *should* achieve under ideal conditions.
- `demonstrated`: the best yield the site has actually run.
- `contractual`: the yield commitment in the customer contract or service
  agreement.

This assumption does **not** change the numeric Quality Score itself — that
is determined by FPY × 0.40 + RTY × 0.30 + scrap_score × 0.20 + escape_score
× 0.10. It changes the **interpretation / grade band** (A+, A, B+, …)
applied to the score.

## When to adjust it

Use `demonstrated` when:
- The site is in continuous-improvement mode and grades should reflect "are
  we maintaining our best?" rather than "are we hitting design intent?".

Use `contractual` when:
- The customer relationship is governed by an SLA with explicit yield
  thresholds.
- Quality reporting is used as evidence of contract compliance.

Stay on `theoretical` when:
- The site is in startup or qualification mode and engineering intent is
  the appropriate bar.

## What it affects

- **Quality Score** — only the grade band, not the numeric value.

## Future scope

Phase 5 (Variance Reporting) will surface the gap between the actual score
and each baseline alternative, regardless of which is selected. Until then,
this assumption only affects the grade label.
