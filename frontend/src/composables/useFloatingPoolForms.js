/**
 * Composable for Floating Pool form/dialog state and CRUD operations
 * (assign dialog, confirm assignment, unassign, edit dialog).
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'

export default function useFloatingPoolForms({ fetchData, showSnackbar }) {
  const { t } = useI18n()

  // --- State ---
  const assigning = ref(false)
  const unassigning = ref(null)
  const showGuide = ref(false)
  const guideTab = ref('overview')

  const assignDialog = ref({
    show: false,
    pool_id: null,
    employee_id: null,
    client_id: null,
    available_from: null,
    available_to: null,
    notes: '',
    error: null
  })

  // --- Methods ---
  const openAssignDialog = (item = null) => {
    assignDialog.value = {
      show: true,
      pool_id: item?.pool_id || null,
      employee_id: item?.employee_id || null,
      client_id: null,
      available_from: item?.available_from ? format(new Date(item.available_from), "yyyy-MM-dd'T'HH:mm") : null,
      available_to: item?.available_to ? format(new Date(item.available_to), "yyyy-MM-dd'T'HH:mm") : null,
      notes: item?.notes || '',
      error: null
    }
  }

  const openEditDialog = (item) => {
    openAssignDialog(item)
  }

  const confirmAssignment = async () => {
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
        notes: assignDialog.value.notes || null
      })

      showSnackbar(t('admin.floatingPool.assignmentSuccess'), 'success')
      assignDialog.value.show = false
      await fetchData()
    } catch (error) {
      console.error('Error assigning employee:', error)
      const errorMessage = error.response?.data?.detail || error.message

      if (errorMessage.includes('already assigned') || errorMessage.includes('double assignment')) {
        assignDialog.value.error = t('admin.floatingPool.doubleAssignmentError')
      } else {
        assignDialog.value.error = errorMessage
      }
    } finally {
      assigning.value = false
    }
  }

  const unassignEmployee = async (item) => {
    unassigning.value = item.pool_id
    try {
      await api.post('/floating-pool/unassign', {
        pool_id: item.pool_id
      })
      showSnackbar(t('admin.floatingPool.unassignmentSuccess'), 'success')
      await fetchData()
    } catch (error) {
      console.error('Error unassigning employee:', error)
      showSnackbar(t('common.error') + ': ' + (error.response?.data?.detail || error.message), 'error')
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
    unassignEmployee
  }
}
