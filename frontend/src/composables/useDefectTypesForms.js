/**
 * Composable for Defect Types form handling and CRUD/upload operations.
 * Handles: create/edit dialog, upload dialog, delete dialog, save, CSV upload/download, snackbar.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const DEFAULT_FORM_DATA = {
  defect_code: '',
  defect_name: '',
  description: '',
  category: '',
  severity_default: 'MAJOR',
  industry_standard_code: '',
  sort_order: 0,
  is_active: true
}

export default function useDefectTypesForms(selectedClient, defectTypes, loadDefectTypes) {
  const { t } = useI18n()

  // Dialog state
  const editDialog = ref(false)
  const uploadDialog = ref(false)
  const deleteDialog = ref(false)
  const isEditing = ref(false)
  const deleteTarget = ref(null)

  // Form state
  const form = ref(null)
  const formValid = ref(false)
  const formData = ref({ ...DEFAULT_FORM_DATA })

  // Upload state
  const uploadFile = ref(null)
  const replaceExisting = ref(false)

  // Loading flags
  const saving = ref(false)
  const uploading = ref(false)
  const deleting = ref(false)

  // Snackbar
  const snackbar = ref({ show: false, message: '', color: 'success' })

  const showSnackbar = (message, color = 'success') => {
    snackbar.value = { show: true, message, color }
  }

  // Create/Edit operations
  const openCreateDialog = () => {
    isEditing.value = false
    formData.value = {
      ...DEFAULT_FORM_DATA,
      sort_order: defectTypes.value.length + 1
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

  const saveDefectType = async () => {
    if (!formValid.value) return

    saving.value = true
    try {
      if (isEditing.value) {
        await api.updateDefectType(formData.value.defect_type_id, formData.value)
        showSnackbar(t('admin.defectTypes.defectTypeUpdated'), 'success')
      } else {
        await api.createDefectType({
          ...formData.value,
          client_id: selectedClient.value
        })
        showSnackbar(t('admin.defectTypes.defectTypeCreated'), 'success')
      }
      closeEditDialog()
      await loadDefectTypes()
    } catch (error) {
      showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      saving.value = false
    }
  }

  // Delete operations
  const confirmDelete = (item) => {
    deleteTarget.value = item
    deleteDialog.value = true
  }

  const deleteDefectType = async () => {
    if (!deleteTarget.value) return

    deleting.value = true
    try {
      await api.deleteDefectType(deleteTarget.value.defect_type_id)
      showSnackbar(t('admin.defectTypes.defectTypeDeleted'), 'success')
      deleteDialog.value = false
      await loadDefectTypes()
    } catch (error) {
      showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      deleting.value = false
    }
  }

  // Upload operations
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
    if (!uploadFile.value || !selectedClient.value) return

    uploading.value = true
    try {
      const res = await api.uploadDefectTypes(
        selectedClient.value,
        uploadFile.value,
        replaceExisting.value
      )
      showSnackbar(
        `${t('admin.defectTypes.uploadComplete')}: ${res.data.created} ${t('admin.defectTypes.created')}, ${res.data.skipped} ${t('admin.defectTypes.skipped')}`,
        'success'
      )
      closeUploadDialog()
      await loadDefectTypes()
    } catch (error) {
      showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      uploading.value = false
    }
  }

  const downloadTemplate = async () => {
    try {
      const res = await api.getDefectTypeTemplate()
      const template = res.data

      const csvHeaders = template.template.columns.join(',')
      const rows = template.template.example_rows.map(row =>
        template.template.columns.map(col => {
          const val = row[col] || ''
          return val.includes(',') ? `"${val}"` : val
        }).join(',')
      )
      const csv = [csvHeaders, ...rows].join('\n')

      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'defect_types_template.csv'
      a.click()
      URL.revokeObjectURL(url)

      showSnackbar(t('admin.defectTypes.templateDownloaded'), 'success')
    } catch (error) {
      showSnackbar(t('errors.general'), 'error')
    }
  }

  return {
    // Dialog state
    editDialog,
    uploadDialog,
    deleteDialog,
    isEditing,
    deleteTarget,

    // Form state
    form,
    formValid,
    formData,

    // Upload state
    uploadFile,
    replaceExisting,

    // Loading
    saving,
    uploading,
    deleting,

    // Snackbar
    snackbar,
    showSnackbar,

    // Operations
    openCreateDialog,
    openEditDialog,
    closeEditDialog,
    saveDefectType,
    confirmDelete,
    deleteDefectType,
    openUploadDialog,
    closeUploadDialog,
    uploadCSV,
    downloadTemplate
  }
}
