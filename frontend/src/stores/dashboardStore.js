/**
 * Dashboard Preferences Store
 * Manages role-based dashboard layouts with drag-drop widget customization
 * Pattern follows keyboardShortcutsStore.js for localStorage + API sync
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import api from '@/services/api'
import { useAuthStore } from './authStore'

const STORAGE_KEY = 'kpi-dashboard-preferences'

// Default widget configurations by role
const ROLE_DEFAULTS = {
  operator: [
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 1, is_visible: true },
    { widget_key: 'my_kpis', widget_name: 'My KPIs', widget_order: 2, is_visible: true },
    { widget_key: 'data_entry_shortcuts', widget_name: 'Data Entry', widget_order: 3, is_visible: true },
    { widget_key: 'recent_entries', widget_name: 'Recent Entries', widget_order: 4, is_visible: true }
  ],
  leader: [
    { widget_key: 'client_overview', widget_name: 'Client Overview', widget_order: 1, is_visible: true },
    { widget_key: 'team_kpis', widget_name: 'Team KPIs', widget_order: 2, is_visible: true },
    { widget_key: 'efficiency_trends', widget_name: 'Efficiency Trends', widget_order: 3, is_visible: true },
    { widget_key: 'attendance_summary', widget_name: 'Attendance', widget_order: 4, is_visible: true },
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 5, is_visible: true }
  ],
  poweruser: [
    { widget_key: 'all_kpis_grid', widget_name: 'All KPIs', widget_order: 1, is_visible: true },
    { widget_key: 'predictions', widget_name: 'Predictions', widget_order: 2, is_visible: true },
    { widget_key: 'analytics_deep_dive', widget_name: 'Analytics', widget_order: 3, is_visible: true },
    { widget_key: 'reports', widget_name: 'Reports', widget_order: 4, is_visible: true },
    { widget_key: 'efficiency_trends', widget_name: 'Trends', widget_order: 5, is_visible: true },
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 6, is_visible: true }
  ],
  admin: [
    { widget_key: 'system_health', widget_name: 'System Health', widget_order: 1, is_visible: true },
    { widget_key: 'user_stats', widget_name: 'User Stats', widget_order: 2, is_visible: true },
    { widget_key: 'all_kpis_grid', widget_name: 'All KPIs', widget_order: 3, is_visible: true },
    { widget_key: 'audit_log', widget_name: 'Audit Log', widget_order: 4, is_visible: true },
    { widget_key: 'predictions', widget_name: 'Predictions', widget_order: 5, is_visible: true },
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 6, is_visible: true }
  ]
}

// All available widgets with metadata
const ALL_WIDGETS = {
  qr_scanner: { name: 'QR Scanner', description: 'Scan QR codes for quick data entry', icon: 'mdi-qrcode-scan', minRole: 'operator' },
  my_kpis: { name: 'My KPIs', description: 'Your assigned client KPIs', icon: 'mdi-chart-box', minRole: 'operator' },
  data_entry_shortcuts: { name: 'Data Entry', description: 'Quick links to entry forms', icon: 'mdi-form-select', minRole: 'operator' },
  recent_entries: { name: 'Recent Entries', description: 'Your recent data entries', icon: 'mdi-history', minRole: 'operator' },
  client_overview: { name: 'Client Overview', description: 'Multi-client summary', icon: 'mdi-domain', minRole: 'leader' },
  team_kpis: { name: 'Team KPIs', description: 'Team performance metrics', icon: 'mdi-account-group', minRole: 'leader' },
  efficiency_trends: { name: 'Efficiency Trends', description: 'Efficiency over time', icon: 'mdi-trending-up', minRole: 'leader' },
  attendance_summary: { name: 'Attendance', description: 'Team attendance summary', icon: 'mdi-account-clock', minRole: 'leader' },
  all_kpis_grid: { name: 'All KPIs', description: 'Complete KPI dashboard', icon: 'mdi-view-grid', minRole: 'poweruser' },
  predictions: { name: 'Predictions', description: 'AI-powered forecasts', icon: 'mdi-crystal-ball', minRole: 'poweruser' },
  analytics_deep_dive: { name: 'Analytics', description: 'Deep analytics view', icon: 'mdi-chart-areaspline', minRole: 'poweruser' },
  reports: { name: 'Reports', description: 'Generate reports', icon: 'mdi-file-document-outline', minRole: 'poweruser' },
  system_health: { name: 'System Health', description: 'System status and metrics', icon: 'mdi-server', minRole: 'admin' },
  user_stats: { name: 'User Stats', description: 'User activity statistics', icon: 'mdi-account-cog', minRole: 'admin' },
  audit_log: { name: 'Audit Log', description: 'System audit trail', icon: 'mdi-clipboard-text-clock', minRole: 'admin' }
}

export const useDashboardStore = defineStore('dashboard', () => {
  const authStore = useAuthStore()

  // State
  const layout = ref('grid') // 'grid', 'list', 'compact'
  const widgets = ref([])
  const theme = ref('default')
  const isCustomizing = ref(false)
  const isLoading = ref(false)
  const isSynced = ref(false)
  const lastSyncedAt = ref(null)

  // Getters
  const visibleWidgets = computed(() =>
    widgets.value
      .filter(w => w.is_visible)
      .sort((a, b) => a.widget_order - b.widget_order)
  )

  const hiddenWidgets = computed(() =>
    widgets.value.filter(w => !w.is_visible)
  )

  const userRole = computed(() => authStore.currentUser?.role?.toLowerCase() || 'operator')

  const availableWidgets = computed(() => {
    const roleHierarchy = ['operator', 'leader', 'poweruser', 'admin']
    const userRoleIndex = roleHierarchy.indexOf(userRole.value)

    return Object.entries(ALL_WIDGETS)
      .filter(([key, widget]) => {
        const widgetRoleIndex = roleHierarchy.indexOf(widget.minRole)
        return widgetRoleIndex <= userRoleIndex
      })
      .map(([key, widget]) => ({
        widget_key: key,
        ...widget
      }))
  })

  // Actions
  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored)
        layout.value = data.layout || 'grid'
        widgets.value = data.widgets || []
        theme.value = data.theme || 'default'
        return true
      }
    } catch (e) {
      console.error('Failed to load dashboard preferences from localStorage:', e)
    }
    return false
  }

  const saveToLocalStorage = () => {
    try {
      const data = {
        layout: layout.value,
        widgets: widgets.value,
        theme: theme.value,
        savedAt: new Date().toISOString()
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (e) {
      console.error('Failed to save dashboard preferences to localStorage:', e)
    }
  }

  const loadFromAPI = async () => {
    try {
      isLoading.value = true
      const response = await api.getDashboardPreferences()
      if (response.data) {
        layout.value = response.data.layout || 'grid'
        widgets.value = response.data.widgets || []
        theme.value = response.data.theme || 'default'
        isSynced.value = true
        lastSyncedAt.value = new Date()
        saveToLocalStorage()
        return true
      }
    } catch (e) {
      console.error('Failed to load dashboard preferences from API:', e)
    } finally {
      isLoading.value = false
    }
    return false
  }

  const saveToAPI = async () => {
    try {
      isLoading.value = true
      await api.saveDashboardPreferences({
        layout: layout.value,
        widgets: widgets.value,
        theme: theme.value
      })
      isSynced.value = true
      lastSyncedAt.value = new Date()
      saveToLocalStorage()
      return true
    } catch (e) {
      console.error('Failed to save dashboard preferences to API:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  const initializePreferences = async () => {
    // First try localStorage for immediate display
    const hasLocal = loadFromLocalStorage()

    // If no local data, use role defaults
    if (!hasLocal || widgets.value.length === 0) {
      applyRoleDefaults()
    }

    // Then sync with API in background
    if (authStore.isAuthenticated) {
      await loadFromAPI()
    }
  }

  const applyRoleDefaults = () => {
    const defaults = ROLE_DEFAULTS[userRole.value] || ROLE_DEFAULTS.operator
    widgets.value = defaults.map((w, index) => ({
      ...w,
      widget_order: index + 1
    }))
    saveToLocalStorage()
  }

  const resetToDefaults = async () => {
    applyRoleDefaults()
    if (authStore.isAuthenticated) {
      try {
        await api.resetDashboardPreferences()
        isSynced.value = true
      } catch (e) {
        console.error('Failed to reset preferences on server:', e)
      }
    }
  }

  const moveWidget = (fromIndex, toIndex) => {
    const visibleList = [...visibleWidgets.value]
    const [moved] = visibleList.splice(fromIndex, 1)
    visibleList.splice(toIndex, 0, moved)

    // Update order for all visible widgets
    visibleList.forEach((w, idx) => {
      const widget = widgets.value.find(x => x.widget_key === w.widget_key)
      if (widget) widget.widget_order = idx + 1
    })

    saveToLocalStorage()
    isSynced.value = false
  }

  const toggleWidgetVisibility = (widgetKey) => {
    const widget = widgets.value.find(w => w.widget_key === widgetKey)
    if (widget) {
      widget.is_visible = !widget.is_visible
      saveToLocalStorage()
      isSynced.value = false
    }
  }

  const addWidget = (widgetKey) => {
    const existing = widgets.value.find(w => w.widget_key === widgetKey)
    if (existing) {
      existing.is_visible = true
    } else {
      const widgetInfo = ALL_WIDGETS[widgetKey]
      if (widgetInfo) {
        widgets.value.push({
          widget_key: widgetKey,
          widget_name: widgetInfo.name,
          widget_order: widgets.value.length + 1,
          is_visible: true,
          custom_config: {}
        })
      }
    }
    saveToLocalStorage()
    isSynced.value = false
  }

  const removeWidget = (widgetKey) => {
    const index = widgets.value.findIndex(w => w.widget_key === widgetKey)
    if (index !== -1) {
      widgets.value[index].is_visible = false
      saveToLocalStorage()
      isSynced.value = false
    }
  }

  const setLayout = (newLayout) => {
    layout.value = newLayout
    saveToLocalStorage()
    isSynced.value = false
  }

  const setTheme = (newTheme) => {
    theme.value = newTheme
    saveToLocalStorage()
    isSynced.value = false
  }

  const startCustomizing = () => {
    isCustomizing.value = true
  }

  const finishCustomizing = async () => {
    isCustomizing.value = false
    await saveToAPI()
  }

  const cancelCustomizing = () => {
    isCustomizing.value = false
    loadFromLocalStorage() // Revert to last saved state
  }

  // Watch for auth changes to reload preferences
  watch(() => authStore.currentUser, async (newUser, oldUser) => {
    if (newUser && newUser.user_id !== oldUser?.user_id) {
      await initializePreferences()
    }
  })

  return {
    // State
    layout,
    widgets,
    theme,
    isCustomizing,
    isLoading,
    isSynced,
    lastSyncedAt,

    // Getters
    visibleWidgets,
    hiddenWidgets,
    userRole,
    availableWidgets,

    // Actions
    initializePreferences,
    loadFromAPI,
    saveToAPI,
    resetToDefaults,
    moveWidget,
    toggleWidgetVisibility,
    addWidget,
    removeWidget,
    setLayout,
    setTheme,
    startCustomizing,
    finishCustomizing,
    cancelCustomizing,

    // Constants
    ALL_WIDGETS,
    ROLE_DEFAULTS
  }
})
