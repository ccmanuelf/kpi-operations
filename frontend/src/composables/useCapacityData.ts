/**
 * Composable for Capacity Planning workbook data management.
 * Client selection, workbook loading, store interactions,
 * keyboard shortcuts, save/reset, analysis, schedule, MRP.
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'
import { useAuthStore } from '@/stores/authStore'
import { useRoute } from 'vue-router'
import api from '@/services/api/client'

export interface CapacityClient {
  client_id: string | number
  client_name?: string
  [key: string]: unknown
}

export function useCapacityData() {
  const store = useCapacityPlanningStore()
  const authStore = useAuthStore()
  const route = useRoute()

  const clients = ref<CapacityClient[]>([])
  const selectedClient = ref<string | number | null>(null)
  const clientsLoading = ref(false)

  const activeTab = ref('orders')

  const showAnalysisDialog = ref(false)
  const showScheduleDialog = ref(false)
  const showResetDialog = ref(false)

  const analysisStartDate = ref('')
  const analysisEndDate = ref('')

  const scheduleName = ref('')
  const scheduleStartDate = ref('')
  const scheduleEndDate = ref('')

  // The wrapper's worksheets type is `Record<string, { data, ... }>`
  // with a string-indexed `unknown`, so `dirty` is `unknown` here.
  // Coerce to boolean for the view's binding contract.
  const worksheetIsDirty = (key: string): boolean =>
    !!store.worksheets[key]?.dirty

  const loadClients = async (): Promise<void> => {
    clientsLoading.value = true
    try {
      const response = await api.get('/clients')
      clients.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
    } finally {
      clientsLoading.value = false
    }
  }

  const onClientChange = async (clientId: string | number): Promise<void> => {
    if (clientId) {
      localStorage.setItem('selectedClientId', String(clientId))
      try {
        await store.loadWorkbook(clientId)
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to load workbook:', error)
      }
    }
  }

  watch(selectedClient, (newValue) => {
    if (newValue) {
      onClientChange(newValue)
    }
  })

  const handleKeyDown = (e: KeyboardEvent): void => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey) {
      if (e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        store.undo()
      } else if (e.key === 'z' && e.shiftKey) {
        e.preventDefault()
        store.redo()
      } else if (e.key === 'y') {
        e.preventDefault()
        store.redo()
      }
    }
  }

  const handleBeforeUnload = (e: BeforeUnloadEvent): void => {
    if (store.hasUnsavedChanges) {
      e.preventDefault()
      e.returnValue = ''
    }
  }

  onMounted(async () => {
    await loadClients()

    let clientId: string | number | null =
      (route.query.client_id as string | undefined) ||
      localStorage.getItem('selectedClientId')

    const user = authStore.currentUser
    if (!clientId && user?.client_id_assigned) {
      clientId = user.client_id_assigned
    }

    if (!clientId && clients.value.length > 0) {
      clientId = clients.value[0].client_id
    }

    if (clientId) {
      selectedClient.value = clientId
    }

    const today = new Date()
    const thirtyDaysLater = new Date(today)
    thirtyDaysLater.setDate(thirtyDaysLater.getDate() + 30)

    analysisStartDate.value = today.toISOString().slice(0, 10)
    analysisEndDate.value = thirtyDaysLater.toISOString().slice(0, 10)
    scheduleStartDate.value = today.toISOString().slice(0, 10)
    scheduleEndDate.value = thirtyDaysLater.toISOString().slice(0, 10)

    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('keydown', handleKeyDown)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
    window.removeEventListener('keydown', handleKeyDown)
  })

  const saveAll = async (): Promise<void> => {
    try {
      await store.saveAllDirty()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to save:', error)
    }
  }

  const runComponentCheck = async (): Promise<void> => {
    try {
      await store.runComponentCheck()
      activeTab.value = 'componentCheck'
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Component check failed:', error)
    }
  }

  const runCapacityAnalysis = async (): Promise<void> => {
    showAnalysisDialog.value = false
    try {
      await store.runCapacityAnalysis(analysisStartDate.value, analysisEndDate.value)
      activeTab.value = 'capacityAnalysis'
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Capacity analysis failed:', error)
    }
  }

  const generateSchedule = async (): Promise<void> => {
    showScheduleDialog.value = false
    try {
      await store.generateSchedule(
        scheduleName.value || 'New Schedule',
        scheduleStartDate.value,
        scheduleEndDate.value,
      )
      activeTab.value = 'productionSchedule'
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Schedule generation failed:', error)
    }
  }

  const handleCommitSchedule = async (
    kpiCommitments: Record<string, unknown>,
  ): Promise<void> => {
    try {
      const activeId = (store.activeSchedule as { id?: string | number } | null)?.id
      if (!activeId) return
      await store.commitSchedule(activeId, kpiCommitments)
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Schedule commit failed:', error)
    }
  }

  const handleReset = (): void => {
    showResetDialog.value = false
    store.reset()
  }

  return {
    store,
    clients,
    selectedClient,
    clientsLoading,
    activeTab,
    showAnalysisDialog,
    showScheduleDialog,
    showResetDialog,
    analysisStartDate,
    analysisEndDate,
    scheduleName,
    scheduleStartDate,
    scheduleEndDate,
    worksheetIsDirty,
    saveAll,
    runComponentCheck,
    runCapacityAnalysis,
    generateSchedule,
    handleCommitSchedule,
    handleReset,
  }
}
