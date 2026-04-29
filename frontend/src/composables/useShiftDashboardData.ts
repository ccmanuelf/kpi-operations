/**
 * Composable for My Shift Dashboard data fetching and timer logic.
 * Work orders, recent activity, stats, clock interval.
 */
import { ref, computed, type Ref } from 'vue'
import { useWorkflowStore } from '@/stores/workflowStore'
import api from '@/services/api'

export interface ShiftWorkOrderRow {
  id: string | number
  work_order_id: string | number
  product_name?: string
  target_qty?: number
  produced?: number
  [key: string]: unknown
}

export interface ProductionRow {
  id?: string | number
  work_order_id?: string | number
  units_produced?: number
  target_production?: number
  date?: string
  created_at?: string
  [key: string]: unknown
}

export interface DowntimeRow {
  id?: string | number
  reason?: string
  downtime_minutes?: number
  date?: string
  created_at?: string
  [key: string]: unknown
}

export interface QualityRow {
  id?: string | number
  inspected_quantity?: number
  defect_quantity?: number
  date?: string
  created_at?: string
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
  const workflowStore = useWorkflowStore()

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

  const activeShift = computed(() => workflowStore.activeShift)
  const hasActiveShift = computed(() => workflowStore.hasActiveShift)

  const currentDate = computed(() => new Date().toISOString().split('T')[0])
  const currentDateFormatted = computed(() =>
    new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    }),
  )

  const shiftStatusColor = computed(() => (hasActiveShift.value ? 'success' : 'grey'))

  const shiftStatusIcon = computed(() =>
    hasActiveShift.value ? 'mdi-play-circle' : 'mdi-clock-outline',
  )

  const shiftStatusText = computed(() => (hasActiveShift.value ? 'Active' : 'Not Started'))

  const shiftDuration = computed<string>(() => {
    const startRaw = (activeShift.value as { start_time?: string } | null)?.start_time
    if (!startRaw) return ''
    const start = new Date(startRaw)
    if (isNaN(start.getTime())) return ''
    const diff = currentTime.value.getTime() - start.getTime()
    if (diff < 0) return ''
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
    if (hours === 0) return `${minutes}m`
    return `${hours}h ${minutes}m`
  })

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
    return date.toLocaleTimeString('en-US', {
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
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
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

  // Demo fallback data — preserved verbatim for parity with the
  // JS version when the API is unavailable.
  const fallbackData = (): void => {
    assignedWorkOrders.value = [
      {
        id: 1,
        work_order_id: 'WO-2024-001',
        product_name: 'Widget A',
        target_qty: 1000,
        produced: 450,
      },
      {
        id: 2,
        work_order_id: 'WO-2024-002',
        product_name: 'Widget B',
        target_qty: 500,
        produced: 320,
      },
      {
        id: 3,
        work_order_id: 'WO-2024-003',
        product_name: 'Component X',
        target_qty: 750,
        produced: 600,
      },
    ]
    myStats.value = {
      unitsProduced: 1370,
      efficiency: 85,
      downtimeIncidents: 2,
      qualityChecks: 5,
    }
    recentActivity.value = [
      {
        id: '1',
        type: 'production',
        description: 'Logged 50 units for WO-2024-001',
        timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
      },
      {
        id: '2',
        type: 'quality',
        description: 'Quality check: 100 inspected, 1 defect',
        timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
      },
      {
        id: '3',
        type: 'downtime',
        description: 'Equipment Breakdown: 15 min downtime',
        timestamp: new Date(Date.now() - 90 * 60000).toISOString(),
      },
      {
        id: '4',
        type: 'production',
        description: 'Logged 100 units for WO-2024-002',
        timestamp: new Date(Date.now() - 120 * 60000).toISOString(),
      },
      {
        id: '5',
        type: 'production',
        description: 'Logged 75 units for WO-2024-003',
        timestamp: new Date(Date.now() - 180 * 60000).toISOString(),
      },
    ]
  }

  const fetchMyShiftData = async (): Promise<void> => {
    try {
      const woResponse = await api.getWorkOrders({
        status: 'in_progress',
        date: currentDate.value,
      })
      assignedWorkOrders.value =
        (woResponse.data as { items?: ShiftWorkOrderRow[] })?.items ||
        (woResponse.data as ShiftWorkOrderRow[]) ||
        []

      const shiftNumber = (activeShift.value as { shift_number?: number } | null)
        ?.shift_number

      const prodResponse = await api.getProductionEntries({
        date: currentDate.value,
        shift: shiftNumber,
      })
      const productions: ProductionRow[] =
        (prodResponse.data as { items?: ProductionRow[] })?.items ||
        (prodResponse.data as ProductionRow[]) ||
        []

      let totalUnits = 0
      let totalTarget = 0
      productions.forEach((p) => {
        totalUnits += p.units_produced || 0
        totalTarget += p.target_production || p.units_produced || 0
      })

      const downResponse = await api.getDowntimeEntries({
        date: currentDate.value,
        shift: shiftNumber,
      })
      const downtimes: DowntimeRow[] =
        (downResponse.data as { items?: DowntimeRow[] })?.items ||
        (downResponse.data as DowntimeRow[]) ||
        []

      const qualityResponse = await api.getQualityEntries({
        date: currentDate.value,
        shift: shiftNumber,
      })
      const qualities: QualityRow[] =
        (qualityResponse.data as { items?: QualityRow[] })?.items ||
        (qualityResponse.data as QualityRow[]) ||
        []

      myStats.value = {
        unitsProduced: totalUnits,
        efficiency: totalTarget > 0 ? Math.round((totalUnits / totalTarget) * 100) : 0,
        downtimeIncidents: downtimes.length,
        qualityChecks: qualities.length,
      }

      const allActivities: ActivityEntry[] = [
        ...productions.map((p) => ({
          id: `prod-${p.id}`,
          type: 'production' as const,
          description: `Logged ${p.units_produced} units for ${p.work_order_id}`,
          timestamp: p.created_at || p.date || '',
        })),
        ...downtimes.map((d) => ({
          id: `down-${d.id}`,
          type: 'downtime' as const,
          description: `${d.reason}: ${d.downtime_minutes} min downtime`,
          timestamp: d.created_at || d.date || '',
        })),
        ...qualities.map((q) => ({
          id: `qual-${q.id}`,
          type: 'quality' as const,
          description: `Quality check: ${q.inspected_quantity} inspected, ${q.defect_quantity} defects`,
          timestamp: q.created_at || q.date || '',
        })),
      ]

      allActivities.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      )
      recentActivity.value = allActivities.slice(0, 5)

      assignedWorkOrders.value = assignedWorkOrders.value.map((wo) => {
        const woProductions = productions.filter(
          (p) => p.work_order_id === wo.work_order_id,
        )
        const produced = woProductions.reduce(
          (sum, p) => sum + (p.units_produced || 0),
          0,
        )
        return { ...wo, produced }
      })
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to fetch shift data:', error)
      fallbackData()
    }
  }

  const initialize = async (): Promise<void> => {
    await workflowStore.initialize()
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
    activeShift,
    hasActiveShift,
    currentDate,
    currentDateFormatted,
    shiftStatusColor,
    shiftStatusIcon,
    shiftStatusText,
    shiftDuration,
    workOrderOptions,
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
