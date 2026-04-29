/**
 * Dashboard preferences store — role-based dashboard layouts with
 * drag-drop widget customization. localStorage + API sync.
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import api from '@/services/api'
import i18n from '@/i18n'
import { useAuthStore } from './authStore'
import { useNotificationStore } from './notificationStore'

export type DashboardLayout = 'grid' | 'list' | 'compact'
export type UserRole = 'operator' | 'leader' | 'poweruser' | 'admin'

export interface Widget {
  widget_key: string
  widget_name: string
  widget_order: number
  is_visible: boolean
  custom_config?: Record<string, unknown>
}

export interface WidgetMetadata {
  name: string
  description: string
  icon: string
  minRole: UserRole
}

export interface AvailableWidget extends WidgetMetadata {
  widget_key: string
}

// Pinia stores can't use the composition useI18n() outside setup, so
// route translation through the global i18n instance instead.
const t = (key: string): string => i18n.global.t(key)

const STORAGE_KEY = 'kpi-dashboard-preferences'

const ROLE_DEFAULTS: Record<UserRole, Widget[]> = {
  operator: [
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 1, is_visible: true },
    { widget_key: 'my_kpis', widget_name: 'My KPIs', widget_order: 2, is_visible: true },
    { widget_key: 'data_entry_shortcuts', widget_name: 'Data Entry', widget_order: 3, is_visible: true },
    { widget_key: 'recent_entries', widget_name: 'Recent Entries', widget_order: 4, is_visible: true },
  ],
  leader: [
    { widget_key: 'client_overview', widget_name: 'Client Overview', widget_order: 1, is_visible: true },
    { widget_key: 'team_kpis', widget_name: 'Team KPIs', widget_order: 2, is_visible: true },
    { widget_key: 'bradford_factor', widget_name: 'Bradford Factor', widget_order: 3, is_visible: true },
    { widget_key: 'efficiency_trends', widget_name: 'Efficiency Trends', widget_order: 4, is_visible: true },
    { widget_key: 'attendance_summary', widget_name: 'Attendance', widget_order: 5, is_visible: true },
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 6, is_visible: true },
  ],
  poweruser: [
    { widget_key: 'all_kpis_grid', widget_name: 'All KPIs', widget_order: 1, is_visible: true },
    { widget_key: 'predictions', widget_name: 'Predictions', widget_order: 2, is_visible: true },
    { widget_key: 'bradford_factor', widget_name: 'Bradford Factor', widget_order: 3, is_visible: true },
    { widget_key: 'analytics_deep_dive', widget_name: 'Analytics', widget_order: 4, is_visible: true },
    { widget_key: 'reports', widget_name: 'Reports', widget_order: 5, is_visible: true },
    { widget_key: 'efficiency_trends', widget_name: 'Trends', widget_order: 6, is_visible: true },
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 7, is_visible: true },
  ],
  admin: [
    { widget_key: 'system_health', widget_name: 'System Health', widget_order: 1, is_visible: true },
    { widget_key: 'user_stats', widget_name: 'User Stats', widget_order: 2, is_visible: true },
    { widget_key: 'bradford_factor', widget_name: 'Bradford Factor', widget_order: 3, is_visible: true },
    { widget_key: 'all_kpis_grid', widget_name: 'All KPIs', widget_order: 4, is_visible: true },
    { widget_key: 'audit_log', widget_name: 'Audit Log', widget_order: 5, is_visible: true },
    { widget_key: 'predictions', widget_name: 'Predictions', widget_order: 6, is_visible: true },
    { widget_key: 'qr_scanner', widget_name: 'QR Scanner', widget_order: 7, is_visible: true },
  ],
}

const ALL_WIDGETS: Record<string, WidgetMetadata> = {
  qr_scanner: { name: 'QR Scanner', description: 'Scan QR codes for quick data entry', icon: 'mdi-qrcode-scan', minRole: 'operator' },
  my_kpis: { name: 'My KPIs', description: 'Your assigned client KPIs', icon: 'mdi-chart-box', minRole: 'operator' },
  data_entry_shortcuts: { name: 'Data Entry', description: 'Quick links to entry forms', icon: 'mdi-form-select', minRole: 'operator' },
  recent_entries: { name: 'Recent Entries', description: 'Your recent data entries', icon: 'mdi-history', minRole: 'operator' },
  client_overview: { name: 'Client Overview', description: 'Multi-client summary', icon: 'mdi-domain', minRole: 'leader' },
  team_kpis: { name: 'Team KPIs', description: 'Team performance metrics', icon: 'mdi-account-group', minRole: 'leader' },
  bradford_factor: { name: 'Bradford Factor', description: 'Employee absence patterns and risk scores', icon: 'mdi-account-clock-outline', minRole: 'leader' },
  efficiency_trends: { name: 'Efficiency Trends', description: 'Efficiency over time', icon: 'mdi-trending-up', minRole: 'leader' },
  attendance_summary: { name: 'Attendance', description: 'Team attendance summary', icon: 'mdi-account-clock', minRole: 'leader' },
  all_kpis_grid: { name: 'All KPIs', description: 'Complete KPI dashboard', icon: 'mdi-view-grid', minRole: 'poweruser' },
  predictions: { name: 'Predictions', description: 'AI-powered forecasts', icon: 'mdi-crystal-ball', minRole: 'poweruser' },
  analytics_deep_dive: { name: 'Analytics', description: 'Deep analytics view', icon: 'mdi-chart-areaspline', minRole: 'poweruser' },
  reports: { name: 'Reports', description: 'Generate reports', icon: 'mdi-file-document-outline', minRole: 'poweruser' },
  system_health: { name: 'System Health', description: 'System status and metrics', icon: 'mdi-server', minRole: 'admin' },
  user_stats: { name: 'User Stats', description: 'User activity statistics', icon: 'mdi-account-cog', minRole: 'admin' },
  audit_log: { name: 'Audit Log', description: 'System audit trail', icon: 'mdi-clipboard-text-clock', minRole: 'admin' },
}

const ROLE_HIERARCHY: UserRole[] = ['operator', 'leader', 'poweruser', 'admin']

export const useDashboardStore = defineStore('dashboard', () => {
  const authStore = useAuthStore()

  const layout = ref<DashboardLayout>('grid')
  const widgets = ref<Widget[]>([])
  const theme = ref('default')
  const isCustomizing = ref(false)
  const isLoading = ref(false)
  const isSynced = ref(false)
  const lastSyncedAt = ref<Date | null>(null)

  const visibleWidgets = computed(() =>
    widgets.value
      .filter((w) => w.is_visible)
      .sort((a, b) => a.widget_order - b.widget_order),
  )

  const hiddenWidgets = computed(() => widgets.value.filter((w) => !w.is_visible))

  const userRole = computed<UserRole>(() => {
    const role = (authStore.currentUser?.role || 'operator').toLowerCase()
    return (ROLE_HIERARCHY as string[]).includes(role) ? (role as UserRole) : 'operator'
  })

  const availableWidgets = computed<AvailableWidget[]>(() => {
    const userRoleIndex = ROLE_HIERARCHY.indexOf(userRole.value)

    return Object.entries(ALL_WIDGETS)
      .filter(([, widget]) => {
        const widgetRoleIndex = ROLE_HIERARCHY.indexOf(widget.minRole)
        return widgetRoleIndex <= userRoleIndex
      })
      .map(([key, widget]) => ({ widget_key: key, ...widget }))
  })

  const loadFromLocalStorage = (): boolean => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored) as {
          layout?: DashboardLayout
          widgets?: Widget[]
          theme?: string
        }
        layout.value = data.layout || 'grid'
        widgets.value = data.widgets || []
        theme.value = data.theme || 'default'
        return true
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load dashboard preferences from localStorage:', e)
    }
    return false
  }

  const saveToLocalStorage = (): void => {
    try {
      const data = {
        layout: layout.value,
        widgets: widgets.value,
        theme: theme.value,
        savedAt: new Date().toISOString(),
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to save dashboard preferences to localStorage:', e)
    }
  }

  const loadFromAPI = async (): Promise<boolean> => {
    try {
      isLoading.value = true
      const response = await api.getDashboardPreferences()
      if (response.data) {
        const d = response.data as {
          layout?: DashboardLayout
          widgets?: Widget[]
          theme?: string
        }
        layout.value = d.layout || 'grid'
        widgets.value = d.widgets || []
        theme.value = d.theme || 'default'
        isSynced.value = true
        lastSyncedAt.value = new Date()
        saveToLocalStorage()
        return true
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load dashboard preferences from API:', e)
      useNotificationStore().showError(t('notifications.dashboard.loadFailed'))
    } finally {
      isLoading.value = false
    }
    return false
  }

  const saveToAPI = async (): Promise<boolean> => {
    try {
      isLoading.value = true
      await api.saveDashboardPreferences({
        layout: layout.value,
        widgets: widgets.value,
        theme: theme.value,
      })
      isSynced.value = true
      lastSyncedAt.value = new Date()
      saveToLocalStorage()
      return true
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to save dashboard preferences to API:', e)
      useNotificationStore().showError(t('notifications.dashboard.saveFailed'))
      return false
    } finally {
      isLoading.value = false
    }
  }

  const applyRoleDefaults = (): void => {
    const defaults = ROLE_DEFAULTS[userRole.value] || ROLE_DEFAULTS.operator
    widgets.value = defaults.map((w, index) => ({
      ...w,
      widget_order: index + 1,
    }))
    saveToLocalStorage()
  }

  const initializePreferences = async (): Promise<void> => {
    const hasLocal = loadFromLocalStorage()

    if (!hasLocal || widgets.value.length === 0) {
      applyRoleDefaults()
    }

    if (authStore.isAuthenticated) {
      await loadFromAPI()
    }
  }

  const resetToDefaults = async (): Promise<void> => {
    applyRoleDefaults()
    if (authStore.isAuthenticated) {
      try {
        await api.resetDashboardPreferences()
        isSynced.value = true
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Failed to reset preferences on server:', e)
        useNotificationStore().showError(t('notifications.dashboard.resetFailed'))
      }
    }
  }

  const moveWidget = (fromIndex: number, toIndex: number): void => {
    const visibleList = [...visibleWidgets.value]
    const [moved] = visibleList.splice(fromIndex, 1)
    visibleList.splice(toIndex, 0, moved)

    visibleList.forEach((w, idx) => {
      const widget = widgets.value.find((x) => x.widget_key === w.widget_key)
      if (widget) widget.widget_order = idx + 1
    })

    saveToLocalStorage()
    isSynced.value = false
  }

  const toggleWidgetVisibility = (widgetKey: string): void => {
    const widget = widgets.value.find((w) => w.widget_key === widgetKey)
    if (widget) {
      widget.is_visible = !widget.is_visible
      saveToLocalStorage()
      isSynced.value = false
    }
  }

  const addWidget = (widgetKey: string): void => {
    const existing = widgets.value.find((w) => w.widget_key === widgetKey)
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
          custom_config: {},
        })
      }
    }
    saveToLocalStorage()
    isSynced.value = false
  }

  const removeWidget = (widgetKey: string): void => {
    const index = widgets.value.findIndex((w) => w.widget_key === widgetKey)
    if (index !== -1) {
      widgets.value[index].is_visible = false
      saveToLocalStorage()
      isSynced.value = false
    }
  }

  const setLayout = (newLayout: DashboardLayout): void => {
    layout.value = newLayout
    saveToLocalStorage()
    isSynced.value = false
  }

  const setTheme = (newTheme: string): void => {
    theme.value = newTheme
    saveToLocalStorage()
    isSynced.value = false
  }

  const startCustomizing = (): void => {
    isCustomizing.value = true
  }

  const finishCustomizing = async (): Promise<void> => {
    isCustomizing.value = false
    await saveToAPI()
  }

  const cancelCustomizing = (): void => {
    isCustomizing.value = false
    loadFromLocalStorage()
  }

  watch(
    () => authStore.currentUser,
    async (newUser, oldUser) => {
      if (newUser && newUser.user_id !== oldUser?.user_id) {
        await initializePreferences()
      }
    },
  )

  return {
    layout,
    widgets,
    theme,
    isCustomizing,
    isLoading,
    isSynced,
    lastSyncedAt,
    visibleWidgets,
    hiddenWidgets,
    userRole,
    availableWidgets,
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
    ALL_WIDGETS,
    ROLE_DEFAULTS,
  }
})
