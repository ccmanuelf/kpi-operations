# `otd_carrier_buffer_pct`

**Allowed values:** numeric, range `[0, 100]` (percent)
**Default:** _no buffer_ — the assumption is unset
**Owner:** Logistics / customer success (proposes), Finance (approves)

## What it is

A **percentage buffer** added to the planned delivery date before judging
on-time. It compensates for **carrier-side variability** (transit time
spread, weekend/holiday gaps) that is outside the manufacturing site's
control.

Storage format: a single number. `5` means "extend the planned delivery
date by 5% of the order's lead-time before judging on-time".

## When to adjust it

Set a non-zero buffer when:
- A specific lane has documented carrier variability (e.g., trucking lanes
  with unpredictable border crossings).
- Customer contracts explicitly recognize a carrier window (e.g., "delivery
  considered on-time within 2 business days of confirmed ship date").
- Leadership wants a separate **manufacturing-controlled OTD** number —
  i.e., "did we ship on time?" vs. "did the carrier deliver on time?".

Leave at 0 when:
- The site uses a single national carrier with consistent transit.
- Customer contracts measure to a fixed date with no carrier allowance.

## What it affects

- **OTD** — only metric directly affected. Buffer is applied to
  `total_orders` filter window (an order ships on-time if
  `actual_ship_date <= planned_ship_date + buffer`).

## Range guidance

- `0–5%`: typical for stable domestic carriers.
- `5–15%`: lanes with known variability or international shipping.
- `15%+`: warrants a separate carrier-performance review rather than a
  blanket buffer. Document the lane-specific reason in the rationale field.

## Audit note

Any buffer above 15% requires explicit Finance sign-off in the rationale
field. The auto-retire-on-approval rule means a new buffer value retires
the previous one; the change log preserves history.
