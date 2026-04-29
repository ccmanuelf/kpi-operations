import { defineStore } from 'pinia'
import { ref } from 'vue'

export type NotificationType = 'success' | 'error' | 'warning' | 'info'
export type SnackbarColor = NotificationType

export interface Notification {
  id: number
  message: string
  type: NotificationType
  timestamp: string
}

export interface SnackbarState {
  show: boolean
  message: string
  color: SnackbarColor
  timeout: number
}

export interface ShowOptions {
  message: string
  type?: NotificationType
  timeout?: number
}

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([])
  const snackbar = ref<SnackbarState>({
    show: false,
    message: '',
    color: 'info',
    timeout: 4000,
  })

  let nextId = 1

  function show({ message, type = 'info', timeout = 4000 }: ShowOptions) {
    const validTypes: NotificationType[] = ['success', 'error', 'warning', 'info']
    const color: SnackbarColor = (validTypes as string[]).includes(type) ? type : 'info'

    snackbar.value = {
      show: true,
      message,
      color,
      timeout,
    }

    notifications.value.unshift({
      id: nextId++,
      message,
      type,
      timestamp: new Date().toISOString(),
    })

    if (notifications.value.length > 50) {
      notifications.value = notifications.value.slice(0, 50)
    }
  }

  function showSuccess(message: string) {
    show({ message, type: 'success' })
  }

  function showError(message: string) {
    show({ message, type: 'error', timeout: 6000 })
  }

  function showWarning(message: string) {
    show({ message, type: 'warning' })
  }

  function showInfo(message: string) {
    show({ message, type: 'info' })
  }

  function hide() {
    snackbar.value.show = false
  }

  function clearHistory() {
    notifications.value = []
  }

  return {
    notifications,
    snackbar,
    show,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    hide,
    clearHistory,
  }
})
