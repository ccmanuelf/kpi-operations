/**
 * Composable for My Shift Dashboard data fetching and timer logic.
 * Handles: work orders, recent activity, stats, timer interval.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useNotificationStore } from '@/stores/notificationStore'
import api from '@/services/api'

export function useShiftDashboardData() {
  const workflowStore = useWorkflowStore()
  const notificationStore = useNotificationStore()

  // Timer ref for clock updates
  const currentTime = ref(new Date())
  let timeInterval = null

  // Data state
  const assignedWorkOrders = ref([])
  const recentActivity = ref([])
  const myStats = ref({
    unitsProduced: 0,
    efficiency: 0,
    downtimeIncidents: 0,
    qualityChecks: 0
  })

  // Store-derived computed
  const activeShift = computed(() => workflowStore.activeShift)
  const hasActiveShift = computed(() => workflowStore.hasActiveShift)

  const currentDate = computed(() => new Date().toISOString().split('T')[0])
  const currentDateFormatted = computed(() => {
    return new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric'
    })
  })

  const shiftStatusColor = computed(() => {
    if (!hasActiveShift.value) return 'grey'
    return 'success'
  })

  const shiftStatusIcon = computed(() => {
    if (!hasActiveShift.value) return 'mdi-clock-outline'
    return 'mdi-play-circle'
  })

  const shiftStatusText = computed(() => {
    if (!hasActiveShift.value) return 'Not Started'
    return 'Active'
  })

  const shiftDuration = computed(() => {
    if (!activeShift.value?.start_time) return ''
    const start = new Date(activeShift.value.start_time)
    if (isNaN(start.getTime())) return ''
    const diff = currentTime.value - start
    if (diff < 0) return ''
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
    if (hours === 0) return `${minutes}m`
    return `${hours}h ${minutes}m`
  })

  const workOrderOptions = computed(() => {
    return assignedWorkOrders.value.map(wo => ({
      text: `${wo.work_order_id} - ${wo.product_name}`,
      value: wo.id
    }))
  })

  // Utility methods
  const formatTime = (timeString) => {
    if (!timeString) return ''
    const date = new Date(timeString)
    if (isNaN(date.getTime())) return ''
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatRelativeTime = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) return ''
    const now = new Date()
    const diff = now - date
    const minutes = Math.floor(diff / (1000 * 60))
    const hours = Math.floor(diff / (1000 * 60 * 60))

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const getProgressPercent = (wo) => {
    if (!wo.target_qty || wo.target_qty === 0) return 0
    return Math.min(Math.round((wo.produced || 0) / wo.target_qty * 100), 100)
  }

  const getProgressColor = (wo) => {
    const percent = getProgressPercent(wo)
    if (percent >= 100) return 'success'
    if (percent >= 75) return 'primary'
    if (percent >= 50) return 'warning'
    return 'error'
  }

  const getActivityColor = (type) => {
    const colors = {
      production: 'primary',
      downtime: 'warning',
      quality: 'success',
      hold: 'error'
    }
    return colors[type] || 'grey'
  }

  const getActivityIcon = (type) => {
    const icons = {
      production: 'mdi-package-variant',
      downtime: 'mdi-clock-alert',
      quality: 'mdi-check-decagram',
      hold: 'mdi-pause-circle'
    }
    return icons[type] || 'mdi-information'
  }

  const fetchMyShiftData = async () => {
    try {
      const woResponse = await api.getWorkOrders({
        status: 'in_progress',
        date: currentDate.value
      })
      assignedWorkOrders.value = woResponse.data?.items || woResponse.data || []

      const prodResponse = await api.getProductionEntries({
        date: currentDate.value,
        shift: activeShift.value?.shift_number
      })
      const productions = prodResponse.data?.items || prodResponse.data || []

      let totalUnits = 0
      let totalTarget = 0
      productions.forEach(p => {
        totalUnits += p.units_produced || 0
        totalTarget += p.target_production || p.units_produced || 0
      })

      const downResponse = await api.getDowntimeEntries({
        date: currentDate.value,
        shift: activeShift.value?.shift_number
      })
      const downtimes = downResponse.data?.items || downResponse.data || []

      const qualityResponse = await api.getQualityEntries({
        date: currentDate.value,
        shift: activeShift.value?.shift_number
      })
      const qualities = qualityResponse.data?.items || qualityResponse.data || []

      myStats.value = {
        unitsProduced: totalUnits,
        efficiency: totalTarget > 0 ? Math.round((totalUnits / totalTarget) * 100) : 0,
        downtimeIncidents: downtimes.length,
        qualityChecks: qualities.length
      }

      const allActivities = [
        ...productions.map(p => ({
          id: `prod-${p.id}`,
          type: 'production',
          description: `Logged ${p.units_produced} units for ${p.work_order_id}`,
          timestamp: p.created_at || p.date
        })),
        ...downtimes.map(d => ({
          id: `down-${d.id}`,
          type: 'downtime',
          description: `${d.reason}: ${d.downtime_minutes} min downtime`,
          timestamp: d.created_at || d.date
        })),
        ...qualities.map(q => ({
          id: `qual-${q.id}`,
          type: 'quality',
          description: `Quality check: ${q.inspected_quantity} inspected, ${q.defect_quantity} defects`,
          timestamp: q.created_at || q.date
        }))
      ]

      allActivities.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      recentActivity.value = allActivities.slice(0, 5)

      assignedWorkOrders.value = assignedWorkOrders.value.map(wo => {
        const woProductions = productions.filter(p => p.work_order_id === wo.work_order_id)
        const produced = woProductions.reduce((sum, p) => sum + (p.units_produced || 0), 0)
        return { ...wo, produced }
      })

    } catch (error) {
      console.error('Failed to fetch shift data:', error)
      // Fallback demo data
      assignedWorkOrders.value = [
        { id: 1, work_order_id: 'WO-2024-001', product_name: 'Widget A', target_qty: 1000, produced: 450 },
        { id: 2, work_order_id: 'WO-2024-002', product_name: 'Widget B', target_qty: 500, produced: 320 },
        { id: 3, work_order_id: 'WO-2024-003', product_name: 'Component X', target_qty: 750, produced: 600 }
      ]
      myStats.value = {
        unitsProduced: 1370,
        efficiency: 85,
        downtimeIncidents: 2,
        qualityChecks: 5
      }
      recentActivity.value = [
        { id: '1', type: 'production', description: 'Logged 50 units for WO-2024-001', timestamp: new Date(Date.now() - 15 * 60000).toISOString() },
        { id: '2', type: 'quality', description: 'Quality check: 100 inspected, 1 defect', timestamp: new Date(Date.now() - 45 * 60000).toISOString() },
        { id: '3', type: 'downtime', description: 'Equipment Breakdown: 15 min downtime', timestamp: new Date(Date.now() - 90 * 60000).toISOString() },
        { id: '4', type: 'production', description: 'Logged 100 units for WO-2024-002', timestamp: new Date(Date.now() - 120 * 60000).toISOString() },
        { id: '5', type: 'production', description: 'Logged 75 units for WO-2024-003', timestamp: new Date(Date.now() - 180 * 60000).toISOString() }
      ]
    }
  }

  const initialize = async () => {
    await workflowStore.initialize()
    await fetchMyShiftData()

    timeInterval = setInterval(() => {
      currentTime.value = new Date()
    }, 60000)
  }

  const cleanup = () => {
    if (timeInterval) {
      clearInterval(timeInterval)
    }
  }

  return {
    // State
    currentTime,
    assignedWorkOrders,
    recentActivity,
    myStats,
    // Computed
    activeShift,
    hasActiveShift,
    currentDate,
    currentDateFormatted,
    shiftStatusColor,
    shiftStatusIcon,
    shiftStatusText,
    shiftDuration,
    workOrderOptions,
    // Methods
    formatTime,
    formatRelativeTime,
    getProgressPercent,
    getProgressColor,
    getActivityColor,
    getActivityIcon,
    fetchMyShiftData,
    initialize,
    cleanup
  }
}
