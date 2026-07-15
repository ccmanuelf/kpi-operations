export interface OocReason {
  key: string
  args: Record<string, number>
}
export interface OocPoint {
  date: string
  value: number
  ooc: boolean
  reasons: OocReason[]
}
export interface OocThreshold {
  target?: number | null
  warning?: number | null
  critical?: number | null
  higher_is_better?: boolean
}
export interface OocResult {
  points: OocPoint[]
  mean: number | null
  ucl: number | null
  lcl: number | null
  target: number | null
  critical: number | null
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function computeOutOfControl(
  raw: { date: string; value: number }[],
  threshold: OocThreshold | null,
  opts: { minSpcPoints?: number } = {},
): OocResult {
  const minSpc = opts.minSpcPoints ?? 8
  const points: OocPoint[] = raw.map((p) => ({ date: p.date, value: p.value, ooc: false, reasons: [] }))

  const critical = threshold && isNum(threshold.critical) ? (threshold.critical as number) : null
  const target = threshold && isNum(threshold.target) ? (threshold.target as number) : null
  const higherBetter = threshold?.higher_is_better !== false // default true

  // Threshold arm
  if (critical !== null) {
    for (const p of points) {
      if (!isNum(p.value)) continue
      if (higherBetter && p.value < critical) {
        p.ooc = true
        p.reasons.push({ key: 'kpi.ooc.belowCritical', args: { value: p.value, critical } })
      } else if (!higherBetter && p.value > critical) {
        p.ooc = true
        p.reasons.push({ key: 'kpi.ooc.aboveCritical', args: { value: p.value, critical } })
      }
    }
  }

  // SPC arm
  let mean: number | null = null
  let ucl: number | null = null
  let lcl: number | null = null
  const finite = points.filter((p) => isNum(p.value))
  if (finite.length >= minSpc) {
    const vals = finite.map((p) => p.value)
    mean = vals.reduce((a, b) => a + b, 0) / vals.length
    // Sigma estimated from the average moving range (classic individuals/I-MR control-chart
    // method), not the raw sample stddev: a plain sample stddev is inflated by a lone outlier
    // (it appears in its own variance term), which can mask the very point it should flag.
    // The moving range only exposes an outlier to its two adjacent differences, so it stays
    // sensitive even with a single spike in the window.
    // Moving ranges are computed between temporally-adjacent points of the ORIGINAL series
    // (not the finite-filtered one): a pair spanning a missing/non-finite point contributes
    // no moving range, so the two points flanking a gap are never spliced together as if
    // adjacent.
    let mrSum = 0
    let mrCount = 0
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1].value
      const curr = points[i].value
      if (isNum(prev) && isNum(curr)) {
        mrSum += Math.abs(curr - prev)
        mrCount++
      }
    }
    const mrBar = mrCount > 0 ? mrSum / mrCount : 0
    const sd = mrBar / 1.128 // d2 constant for moving range of size 2
    if (sd > 0) {
      ucl = mean + 3 * sd
      lcl = mean - 3 * sd
      for (const p of points) {
        if (!isNum(p.value)) continue
        if (p.value > ucl) {
          p.ooc = true
          p.reasons.push({ key: 'kpi.ooc.beyondUcl', args: { value: p.value, limit: ucl } })
        } else if (p.value < lcl) {
          p.ooc = true
          p.reasons.push({ key: 'kpi.ooc.beyondLcl', args: { value: p.value, limit: lcl } })
        }
      }
    }
  }

  return { points, mean, ucl, lcl, target, critical }
}
