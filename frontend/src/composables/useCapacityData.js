/**
 * Composable for Capacity Planning workbook data management.
 * Handles: client selection, workbook loading, store interactions,
 * keyboard shortcuts, save/reset, analysis, schedule, and component check.
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'
import { useAuthStore } from '@/stores/authStore'
import { useRoute } from 'vue-router'
import api from '@/services/api/client'

export function useCapacityData() {
  const store = useCapacityPlanningStore()
  const authStore = useAuthStore()
  const route = useRoute()

  // Client selection
  const clients = ref([])
  const selectedClient = ref(null)
  const clientsLoading = ref(false)

  // Tab navigation
  const activeTab = ref('orders')

  // Dialog visibility
  const showAnalysisDialog = ref(false)
  const showScheduleDialog = ref(false)
  const showResetDialog = ref(false)

  // Analysis form
  const analysisStartDate = ref('')
  const analysisEndDate = ref('')

  // Schedule form
  const scheduleName = ref('')
  const scheduleStartDate = ref('')
  const scheduleEndDate = ref('')

  // Helpers
  const worksheetIsDirty = (key) => {
    return store.worksheets[key]?.dirty || false
  }

  // Client loading
  const loadClients = async () => {
    clientsLoading.value = true
    try {
      const response = await api.get('/clients')
      clients.value = response.data || []
    } catch (error) {
      console.error('Failed to load clients:', error)
    } finally {
      clientsLoading.value = false
    }
  }

  const onClientChange = async (clientId) => {
    if (clientId) {
      localStorage.setItem('selectedClientId', clientId)
      try {
        await store.loadWorkbook(clientId)
      } catch (error) {
        console.error('Failed to load workbook:', error)
      }
    }
  }

  // Watch for client selection changes
  watch(selectedClient, (newValue) => {
    if (newValue) {
      onClientChange(newValue)
    }
  })

  // Keyboard shortcuts
  const handleKeyDown = (e) => {
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

  const handleBeforeUnload = (e) => {
    if (store.hasUnsavedChanges) {
      e.preventDefault()
      e.returnValue = ''
    }
  }

  // Lifecycle
  onMounted(async () => {
    await loadClients()

    let clientId = route.query.client_id || localStorage.getItem('selectedClientId')

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

    // Set default dates for analysis and schedule
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

  // Actions
  const saveAll = async () => {
    try {
      await store.saveAllDirty()
    } catch (error) {
      console.error('Failed to save:', error)
    }
  }

  const runComponentCheck = async () => {
    try {
      await store.runComponentCheck()
      activeTab.value = 'componentCheck'
    } catch (error) {
      console.error('Component check failed:', error)
    }
  }

  const runCapacityAnalysis = async () => {
    showAnalysisDialog.value = false
    try {
      await store.runCapacityAnalysis(analysisStartDate.value, analysisEndDate.value)
      activeTab.value = 'capacityAnalysis'
    } catch (error) {
      console.error('Capacity analysis failed:', error)
    }
  }

  const generateSchedule = async () => {
    showScheduleDialog.value = false
    try {
      await store.generateSchedule(
        scheduleName.value || 'New Schedule',
        scheduleStartDate.value,
        scheduleEndDate.value
      )
      activeTab.value = 'productionSchedule'
    } catch (error) {
      console.error('Schedule generation failed:', error)
    }
  }

  const handleCommitSchedule = async (kpiCommitments) => {
    try {
      await store.commitSchedule(store.activeSchedule.id, kpiCommitments)
    } catch (error) {
      console.error('Schedule commit failed:', error)
    }
  }

  const handleReset = () => {
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
