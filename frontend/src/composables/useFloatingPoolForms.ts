/**
 * Composable for the Floating Pool admin form/dialog state and
 * CRUD (assign, confirm, unassign, edit).
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'

export interface FloatingPoolItem {
  pool_id?: string | number
  employee_id?: string | number
  client_id?: string | number | null
  available_from?: string | null
  available_to?: string | null
  notes?: string | null
  [key: string]: unknown
}

export interface AssignDialogState {
  show: boolean
  pool_id: string | number | null
  employee_id: string | number | null
  client_id: string | number | null
  available_from: string | null
  available_to: string | null
  notes: string
  error: string | null
}

export interface FloatingPoolFormsOptions {
  fetchData: () => Promise<void> | void
  showSnackbar: (message: string, color: string) => void
}

const datetimeLocalFormat = (raw: string): string =>
  format(new Date(raw), "yyyy-MM-dd'T'HH:mm")

export default function useFloatingPoolForms({
  fetchData,
  showSnackbar,
}: FloatingPoolFormsOptions) {
  const { t } = useI18n()

  const assigning = ref(false)
  const unassigning = ref<string | number | null>(null)
  const showGuide = ref(false)
  const guideTab = ref('overview')

  const assignDialog = ref<AssignDialogState>({
    show: false,
    pool_id: null,
    employee_id: null,
    client_id: null,
    available_from: null,
    available_to: null,
    notes: '',
    error: null,
  })

  const openAssignDialog = (item: FloatingPoolItem | null = null): void => {
    assignDialog.value = {
      show: true,
      pool_id: item?.pool_id ?? null,
      employee_id: item?.employee_id ?? null,
      client_id: null,
      available_from: item?.available_from ? datetimeLocalFormat(item.available_from) : null,
      available_to: item?.available_to ? datetimeLocalFormat(item.available_to) : null,
      notes: item?.notes || '',
      error: null,
    }
  }

  const openEditDialog = (item: FloatingPoolItem): void => {
    openAssignDialog(item)
  }

  const confirmAssignment = async (): Promise<void> => {
    if (!assignDialog.value.client_id) {
      assignDialog.value.error = t('admin.floatingPool.selectClientRequired')
      return
    }

    assigning.value = true
    assignDialog.value.error = null

    try {
      await api.post('/floating-pool/assign', {
        employee_id: assignDialog.value.employee_id,
        client_id: assignDialog.value.client_id,
        available_from: assignDialog.value.available_from || null,
        available_to: assignDialog.value.available_to || null,
        notes: assignDialog.value.notes || null,
      })

      showSnackbar(t('admin.floatingPool.assignmentSuccess'), 'success')
      assignDialog.value.show = false
      await fetchData()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error assigning employee:', error)
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      const errorMessage = ax?.response?.data?.detail || ax?.message || ''

      if (
        errorMessage.includes('already assigned') ||
        errorMessage.includes('double assignment')
      ) {
        assignDialog.value.error = t('admin.floatingPool.doubleAssignmentError')
      } else {
        assignDialog.value.error = errorMessage
      }
    } finally {
      assigning.value = false
    }
  }

  const unassignEmployee = async (item: FloatingPoolItem): Promise<void> => {
    unassigning.value = item.pool_id ?? null
    try {
      await api.post('/floating-pool/unassign', {
        pool_id: item.pool_id,
      })
      showSnackbar(t('admin.floatingPool.unassignmentSuccess'), 'success')
      await fetchData()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error unassigning employee:', error)
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      showSnackbar(
        t('common.error') + ': ' + (ax?.response?.data?.detail || ax?.message || ''),
        'error',
      )
    } finally {
      unassigning.value = null
    }
  }

  return {
    assigning,
    unassigning,
    showGuide,
    guideTab,
    assignDialog,
    openAssignDialog,
    openEditDialog,
    confirmAssignment,
    unassignEmployee,
  }
}
