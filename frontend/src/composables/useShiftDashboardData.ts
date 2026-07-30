/**
 * Composable for My Shift Dashboard data fetching and timer logic.
 * Work orders, recent activity, stats, clock interval.
 */
import { ref, computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { formatLocaleDateIntl, formatLocaleTimeIntl } from '@/utils/localeDate'
import { useNotificationStore } from '@/stores/notificationStore'

export interface ShiftWorkOrderRow {
  id: string | number
  work_order_id: string | number
  product_name?: string
  target_qty?: number
  produced?: number
  [key: string]: unknown
}

export type ActivityType = 'production' | 'downtime' | 'quality' | 'hold' | string

export interface ActivityEntry {
  id: string
  type: ActivityType
  description: string
  timestamp: string
}

export interface MyStats {
  unitsProduced: number
  efficiency: number
  downtimeIncidents: number
  qualityChecks: number
}

interface WorkOrderOption {
  text: string
  value: string | number
}

export function useShiftDashboardData() {
  const { t, locale } = useI18n()
  const notificationStore = useNotificationStore()
  const currentTime = ref(new Date())
  let timeInterval: ReturnType<typeof setInterval> | null = null

  const assignedWorkOrders: Ref<ShiftWorkOrderRow[]> = ref([])
  const recentActivity: Ref<ActivityEntry[]> = ref([])
  const myStats = ref<MyStats>({
    unitsProduced: 0,
    efficiency: 0,
    downtimeIncidents: 0,
    qualityChecks: 0,
  })

  const currentDate = computed(() => new Date().toISOString().split('T')[0])
  const currentDateFormatted = computed(() =>
    formatLocaleDateIntl(new Date(), locale.value, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    }),
  )

  const workOrderOptions = computed<WorkOrderOption[]>(() =>
    assignedWorkOrders.value.map((wo) => ({
      text: `${wo.work_order_id} - ${wo.product_name}`,
      value: wo.id,
    })),
  )

  const formatTime = (timeString: string | null | undefined): string => {
    if (!timeString) return ''
    const date = new Date(timeString)
    if (isNaN(date.getTime())) return ''
    return formatLocaleTimeIntl(date, locale.value, {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatRelativeTime = (timestamp: string | null | undefined): string => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) return ''
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / (1000 * 60))
    const hours = Math.floor(diff / (1000 * 60 * 60))

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return formatLocaleDateIntl(date, locale.value, { month: 'short', day: 'numeric' })
  }

  const getProgressPercent = (wo: ShiftWorkOrderRow): number => {
    if (!wo.target_qty || wo.target_qty === 0) return 0
    return Math.min(Math.round(((wo.produced || 0) / wo.target_qty) * 100), 100)
  }

  const getProgressColor = (wo: ShiftWorkOrderRow): string => {
    const percent = getProgressPercent(wo)
    if (percent >= 100) return 'success'
    if (percent >= 75) return 'primary'
    if (percent >= 50) return 'warning'
    return 'error'
  }

  const getActivityColor = (type: ActivityType): string => {
    const colors: Record<string, string> = {
      production: 'primary',
      downtime: 'warning',
      quality: 'success',
      hold: 'error',
    }
    return colors[type] || 'grey'
  }

  const getActivityIcon = (type: ActivityType): string => {
    const icons: Record<string, string> = {
      production: 'mdi-package-variant',
      downtime: 'mdi-clock-alert',
      quality: 'mdi-check-decagram',
      hold: 'mdi-pause-circle',
    }
    return icons[type] || 'mdi-information'
  }

  // Whether the shift screen has any real assignment to show. Drives the
  // honest empty state — the screen must never invent records when this
  // is false (e.g. a user with no line/shift mapping for today).
  const hasAssignments = computed(() => assignedWorkOrders.value.length > 0)

  // A failed fetch and a genuinely empty (no assignments) shift must render
  // differently — otherwise a transient backend/network failure is
  // indistinguishable from "you have nothing today," which is its own kind
  // of dishonesty. Reset on every fetch attempt so a successful retry clears
  // a prior failure.
  const hasLoadError = ref(false)

  interface MyShiftSummaryResponse {
    stats?: {
      units_produced?: number
      efficiency?: number
      downtime_incidents?: number
      quality_checks?: number
    }
    assigned_work_orders?: ShiftWorkOrderRow[]
    recent_activity?: ActivityEntry[]
  }

  const fetchMyShiftData = async (): Promise<void> => {
    try {
      // Single source of truth: the backend's own /my-shift/summary endpoint
      // (backend/routes/my_shift.py), which is purpose-built for this screen
      // and already applies client-scope authorization. It returns real,
      // possibly-empty data — never fabricated records.
      const response = await api.getMyShiftSummary({ shift_date: currentDate.value })
      const summary = response.data as MyShiftSummaryResponse

      assignedWorkOrders.value = summary.assigned_work_orders || []
      recentActivity.value = summary.recent_activity || []
      myStats.value = {
        unitsProduced: summary.stats?.units_produced ?? 0,
        efficiency: summary.stats?.efficiency ?? 0,
        downtimeIncidents: summary.stats?.downtime_incidents ?? 0,
        qualityChecks: summary.stats?.quality_checks ?? 0,
      }
      hasLoadError.value = false
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to fetch shift data:', error)
      // Honest failure: never invent records. Reset to the real empty state
      // and surface a distinct error indicator — a failed fetch must not
      // look identical to "no work orders assigned" (that's its own kind of
      // fabrication-by-omission).
      assignedWorkOrders.value = []
      recentActivity.value = []
      myStats.value = { unitsProduced: 0, efficiency: 0, downtimeIncidents: 0, qualityChecks: 0 }
      hasLoadError.value = true
      notificationStore.showError(t('notifications.myShift.loadFailed'))
    }
  }

  const initialize = async (): Promise<void> => {
    await fetchMyShiftData()

    timeInterval = setInterval(() => {
      currentTime.value = new Date()
    }, 60000)
  }

  const cleanup = (): void => {
    if (timeInterval) {
      clearInterval(timeInterval)
      timeInterval = null
    }
  }

  return {
    currentTime,
    assignedWorkOrders,
    recentActivity,
    myStats,
    currentDate,
    currentDateFormatted,
    workOrderOptions,
    hasAssignments,
    hasLoadError,
    formatTime,
    formatRelativeTime,
    getProgressPercent,
    getProgressColor,
    getActivityColor,
    getActivityIcon,
    fetchMyShiftData,
    initialize,
    cleanup,
  }
}
