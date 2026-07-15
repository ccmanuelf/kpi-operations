import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, startOfWeek, endOfWeek, subWeeks, startOfMonth, endOfMonth, subMonths, subDays } from 'date-fns'

export type KpiRangeKey = 'thisWeek' | 'lastWeek' | 'lastMonth' | 'last90Days'
export const KPI_RANGE_KEYS: KpiRangeKey[] = ['thisWeek', 'lastWeek', 'lastMonth', 'last90Days']

const WEEK_OPTS = { weekStartsOn: 1 as const } // Monday, manufacturing-week convention
const fmt = (d: Date) => format(d, 'yyyy-MM-dd')

export function computeKpiRange(key: KpiRangeKey, today: Date = new Date()): { start: string; end: string } {
  switch (key) {
    case 'thisWeek':
      return { start: fmt(startOfWeek(today, WEEK_OPTS)), end: fmt(today) }
    case 'lastWeek': {
      const lw = subWeeks(today, 1)
      return { start: fmt(startOfWeek(lw, WEEK_OPTS)), end: fmt(endOfWeek(lw, WEEK_OPTS)) }
    }
    case 'lastMonth': {
      const lm = subMonths(today, 1)
      return { start: fmt(startOfMonth(lm)), end: fmt(endOfMonth(lm)) }
    }
    case 'last90Days':
      return { start: fmt(subDays(today, 89)), end: fmt(today) }
  }
}

export function useKpiChartRange() {
  const { t } = useI18n()
  const options = computed(() =>
    KPI_RANGE_KEYS.map((key) => ({
      value: key,
      title: t(`kpi.${key}`),
    })),
  )
  return { options }
}
