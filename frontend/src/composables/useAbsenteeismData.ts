/**
 * Composable for Absenteeism KPI data fetching, reactive state, and
 * helpers (color tokens, formatters, attendance history loader).
 *
 * NOTE: thresholds are INVERTED — lower absenteeism rate is better.
 * `rate <= 5` is healthy (green), `rate <= 10` is warning, else error.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

interface ClientOption {
  client_id?: string | number
  [key: string]: unknown
}

interface TableHeader {
  title: string
  key: string
  sortable: boolean
}

interface AttendanceRecord {
  is_absent?: boolean
  status?: string
  [key: string]: unknown
}

export default function useAbsenteeismData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const attendanceHistory = ref<AttendanceRecord[]>([])

  const absenteeismData = computed(() => kpiStore.absenteeism)

  const statusColor = computed<string>(() => {
    const rate = (absenteeismData.value?.rate as number) || 0
    if (rate <= 5) return 'success'
    if (rate <= 10) return 'amber-darken-3'
    return 'error'
  })

  const reasonHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.reason'), key: 'reason', sortable: true },
    { title: t('kpi.headers.count'), key: 'count', sortable: true },
    { title: t('kpi.headers.percentage'), key: 'percentage', sortable: true },
  ])

  const deptHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.department'), key: 'department', sortable: true },
    { title: t('kpi.headers.workforce'), key: 'workforce', sortable: true },
    { title: t('kpi.headers.absences'), key: 'absences', sortable: true },
    { title: t('kpi.headers.rate'), key: 'rate', sortable: true },
  ])

  const alertHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.employeeId'), key: 'employee_id', sortable: true },
    { title: t('kpi.headers.department'), key: 'department', sortable: true },
    { title: t('kpi.headers.absenceDays'), key: 'absence_count', sortable: true },
    { title: t('kpi.headers.lastAbsence'), key: 'last_absence', sortable: true },
  ])

  const attendanceHistoryHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.date'), key: 'shift_date', sortable: true },
    { title: t('kpi.headers.employeeId'), key: 'employee_id', sortable: true },
    { title: t('kpi.headers.hoursScheduled'), key: 'scheduled_hours', sortable: true },
    { title: t('kpi.headers.hoursWorked'), key: 'actual_hours', sortable: true },
    { title: t('kpi.headers.status'), key: 'status', sortable: true },
  ])

  const formatValue = (value: number | null | undefined): string =>
    value !== null && value !== undefined ? Number(value).toFixed(1) : t('common.na')

  const formatDate = (dateStr: string): string => {
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  // Inverted threshold — lower rate is better.
  const getAbsenteeismColor = (rate: number): string => {
    if (rate <= 5) return 'success'
    if (rate <= 10) return 'amber-darken-3'
    return 'error'
  }

  const loadClients = async (): Promise<void> => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
    }
  }

  const loadAttendanceHistory = async (): Promise<void> => {
    try {
      const params: Record<string, unknown> = {
        start_date: startDate.value,
        end_date: endDate.value,
      }
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const response = await api.getAttendanceEntries(params)
      // Transform data to add a computed `status` field.
      attendanceHistory.value = ((response.data || []) as AttendanceRecord[]).map(
        (record) => ({
          ...record,
          status: record.is_absent ? 'ABSENT' : 'PRESENT',
        }),
      )
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load attendance history:', error)
      attendanceHistory.value = []
    }
  }

  const refreshData = async (): Promise<void> => {
    loading.value = true
    try {
      await Promise.all([kpiStore.fetchAbsenteeism(), loadAttendanceHistory()])
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to refresh data:', error)
    } finally {
      loading.value = false
    }
  }

  const onClientChange = (): void => {
    kpiStore.setClient(selectedClient.value)
    refreshData()
  }

  const onDateChange = (): void => {
    kpiStore.setDateRange(startDate.value, endDate.value)
    refreshData()
  }

  const initialize = async (): Promise<void> => {
    loading.value = true
    try {
      await loadClients()
      kpiStore.setDateRange(startDate.value, endDate.value)
      await refreshData()
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    clients,
    selectedClient,
    startDate,
    endDate,
    tableSearch,
    attendanceHistory,
    absenteeismData,
    statusColor,
    reasonHeaders,
    deptHeaders,
    alertHeaders,
    attendanceHistoryHeaders,
    formatValue,
    formatDate,
    getAbsenteeismColor,
    onClientChange,
    onDateChange,
    refreshData,
    initialize,
  }
}
