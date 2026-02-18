/**
 * Composable for Part Opportunities form handling and CRUD operations.
 * Handles: create/edit dialogs, form state, validation rules, save, delete,
 *          CSV upload, template download.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const DEFAULT_FORM_DATA = {
  part_number: '',
  opportunities_per_unit: 10,
  part_description: '',
  complexity: '',
  client_id: null,
  notes: '',
  is_active: true
}

export function usePartOpportunitiesForms(selectedClient, loadPartOpportunities, showSnackbar) {
  const { t } = useI18n()

  // Dialog state
  const editDialog = ref(false)
  const uploadDialog = ref(false)
  const deleteDialog = ref(false)
  const isEditing = ref(false)
  const deleteTarget = ref(null)

  // Loading flags
  const saving = ref(false)
  const uploading = ref(false)
  const deleting = ref(false)

  // Form
  const form = ref(null)
  const formValid = ref(false)
  const formData = ref({ ...DEFAULT_FORM_DATA })

  // Upload
  const uploadFile = ref(null)
  const replaceExisting = ref(false)

  // Options
  const complexityOptions = ['Simple', 'Standard', 'Complex', 'Very Complex']

  // Validation rules
  const rules = {
    required: v => !!v || t('validation.required'),
    maxLength50: v => !v || v.length <= 50 || t('validation.maxLength', { max: 50 }),
    positive: v => (v && v > 0) || t('validation.positive')
  }

  // Dialog actions
  const openCreateDialog = () => {
    isEditing.value = false
    formData.value = {
      ...DEFAULT_FORM_DATA,
      complexity: 'Standard',
      client_id: selectedClient.value
    }
    editDialog.value = true
  }

  const openEditDialog = (item) => {
    isEditing.value = true
    formData.value = { ...item }
    editDialog.value = true
  }

  const closeEditDialog = () => {
    editDialog.value = false
    form.value?.reset()
  }

  // CRUD operations
  const savePartOpportunity = async () => {
    if (!formValid.value) return

    saving.value = true
    try {
      if (isEditing.value) {
        await api.put(`/part-opportunities/${formData.value.part_opportunities_id}`, formData.value)
        showSnackbar(t('success.updated'), 'success')
      } else {
        await api.post('/part-opportunities', formData.value)
        showSnackbar(t('success.saved'), 'success')
      }
      closeEditDialog()
      await loadPartOpportunities()
    } catch (error) {
      showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      saving.value = false
    }
  }

  const confirmDelete = (item) => {
    deleteTarget.value = item
    deleteDialog.value = true
  }

  const deletePartOpportunity = async () => {
    if (!deleteTarget.value) return

    deleting.value = true
    try {
      await api.delete(`/part-opportunities/${deleteTarget.value.part_opportunities_id}`)
      showSnackbar(t('success.deleted'), 'success')
      deleteDialog.value = false
      await loadPartOpportunities()
    } catch (error) {
      showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      deleting.value = false
    }
  }

  // CSV operations
  const openUploadDialog = () => {
    uploadFile.value = null
    replaceExisting.value = false
    uploadDialog.value = true
  }

  const closeUploadDialog = () => {
    uploadDialog.value = false
    uploadFile.value = null
  }

  const uploadCSV = async () => {
    if (!uploadFile.value) return

    uploading.value = true
    try {
      const formDataUpload = new FormData()
      formDataUpload.append('file', uploadFile.value)
      formDataUpload.append('replace_existing', replaceExisting.value)
      if (selectedClient.value) {
        formDataUpload.append('client_id', selectedClient.value)
      }

      const res = await api.post('/part-opportunities/upload', formDataUpload, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      showSnackbar(t('csv.success', { count: res.data.created || 0 }), 'success')
      closeUploadDialog()
      await loadPartOpportunities()
    } catch (error) {
      showSnackbar(error.response?.data?.detail || t('csv.error'), 'error')
    } finally {
      uploading.value = false
    }
  }

  const downloadTemplate = () => {
    const csvHeaders = ['part_number', 'opportunities_per_unit', 'part_description', 'complexity', 'notes']
    const example = ['PART-001', '15', 'Standard T-Shirt', 'Standard', 'Basic garment']
    const csv = [csvHeaders.join(','), example.join(',')].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'part_opportunities_template.csv'
    a.click()
    URL.revokeObjectURL(url)

    showSnackbar(t('success.downloaded'), 'success')
  }

  return {
    // Dialog state
    editDialog,
    uploadDialog,
    deleteDialog,
    isEditing,
    deleteTarget,

    // Loading flags
    saving,
    uploading,
    deleting,

    // Form
    form,
    formValid,
    formData,

    // Upload
    uploadFile,
    replaceExisting,

    // Options & rules
    complexityOptions,
    rules,

    // Methods
    openCreateDialog,
    openEditDialog,
    closeEditDialog,
    savePartOpportunity,
    confirmDelete,
    deletePartOpportunity,
    openUploadDialog,
    closeUploadDialog,
    uploadCSV,
    downloadTemplate
  }
}
