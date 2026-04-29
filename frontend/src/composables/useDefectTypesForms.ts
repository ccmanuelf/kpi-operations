/**
 * Composable for Defect Types form handling, CRUD, CSV upload,
 * and template download.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import type { DefectType, Severity } from './useDefectTypesData'

export interface DefectTypeFormData {
  defect_code: string
  defect_name: string
  description: string
  category: string
  severity_default: Severity
  industry_standard_code: string
  sort_order: number
  is_active: boolean
  defect_type_id?: string | number
}

export interface SnackbarState {
  show: boolean
  message: string
  color: string
}

interface FormHandle {
  reset?: () => void
  validate?: () => Promise<{ valid: boolean }>
}

interface DefectTemplate {
  template: {
    columns: string[]
    example_rows: Record<string, string>[]
  }
}

const DEFAULT_FORM_DATA = (): DefectTypeFormData => ({
  defect_code: '',
  defect_name: '',
  description: '',
  category: '',
  severity_default: 'MAJOR',
  industry_standard_code: '',
  sort_order: 0,
  is_active: true,
})

export default function useDefectTypesForms(
  selectedClient: Ref<string | number | null>,
  defectTypes: Ref<DefectType[]>,
  loadDefectTypes: () => Promise<void>,
) {
  const { t } = useI18n()

  const editDialog = ref(false)
  const uploadDialog = ref(false)
  const deleteDialog = ref(false)
  const isEditing = ref(false)
  const deleteTarget = ref<(DefectType & { defect_type_id: string | number }) | null>(null)

  const form = ref<FormHandle | null>(null)
  const formValid = ref(false)
  const formData = ref<DefectTypeFormData>(DEFAULT_FORM_DATA())

  const uploadFile = ref<File | null>(null)
  const replaceExisting = ref(false)

  const saving = ref(false)
  const uploading = ref(false)
  const deleting = ref(false)

  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const openCreateDialog = (): void => {
    isEditing.value = false
    formData.value = {
      ...DEFAULT_FORM_DATA(),
      sort_order: defectTypes.value.length + 1,
    }
    editDialog.value = true
  }

  const openEditDialog = (item: DefectType): void => {
    isEditing.value = true
    // The DefectType row may be missing form-only fields (description,
    // sort_order, etc.); merge over a fresh defaults baseline so any
    // missing keys read sensible values instead of undefined.
    formData.value = {
      ...DEFAULT_FORM_DATA(),
      ...(item as Partial<DefectTypeFormData>),
    }
    editDialog.value = true
  }

  const closeEditDialog = (): void => {
    editDialog.value = false
    form.value?.reset?.()
  }

  const saveDefectType = async (): Promise<void> => {
    if (!formValid.value) return

    saving.value = true
    try {
      if (isEditing.value && formData.value.defect_type_id) {
        await api.updateDefectType(formData.value.defect_type_id, formData.value)
        showSnackbar(t('admin.defectTypes.defectTypeUpdated'), 'success')
      } else {
        await api.createDefectType({
          ...formData.value,
          client_id: selectedClient.value,
        })
        showSnackbar(t('admin.defectTypes.defectTypeCreated'), 'success')
      }
      closeEditDialog()
      await loadDefectTypes()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      saving.value = false
    }
  }

  const confirmDelete = (
    item: DefectType & { defect_type_id: string | number },
  ): void => {
    deleteTarget.value = item
    deleteDialog.value = true
  }

  const deleteDefectType = async (): Promise<void> => {
    if (!deleteTarget.value) return

    deleting.value = true
    try {
      await api.deleteDefectType(deleteTarget.value.defect_type_id)
      showSnackbar(t('admin.defectTypes.defectTypeDeleted'), 'success')
      deleteDialog.value = false
      await loadDefectTypes()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      deleting.value = false
    }
  }

  const openUploadDialog = (): void => {
    uploadFile.value = null
    replaceExisting.value = false
    uploadDialog.value = true
  }

  const closeUploadDialog = (): void => {
    uploadDialog.value = false
    uploadFile.value = null
  }

  const uploadCSV = async (): Promise<void> => {
    if (!uploadFile.value || !selectedClient.value) return

    uploading.value = true
    try {
      const res = await api.uploadDefectTypes(
        selectedClient.value,
        uploadFile.value,
        replaceExisting.value,
      )
      const data = res.data as { created: number; skipped: number }
      showSnackbar(
        `${t('admin.defectTypes.uploadComplete')}: ${data.created} ${t(
          'admin.defectTypes.created',
        )}, ${data.skipped} ${t('admin.defectTypes.skipped')}`,
        'success',
      )
      closeUploadDialog()
      await loadDefectTypes()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      uploading.value = false
    }
  }

  const downloadTemplate = async (): Promise<void> => {
    try {
      const res = await api.getDefectTypeTemplate()
      const template = res.data as DefectTemplate

      const csvHeaders = template.template.columns.join(',')
      const rows = template.template.example_rows.map((row) =>
        template.template.columns
          .map((col) => {
            const val = row[col] || ''
            return val.includes(',') ? `"${val}"` : val
          })
          .join(','),
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
    } catch {
      showSnackbar(t('errors.general'), 'error')
    }
  }

  return {
    editDialog,
    uploadDialog,
    deleteDialog,
    isEditing,
    deleteTarget,
    form,
    formValid,
    formData,
    uploadFile,
    replaceExisting,
    saving,
    uploading,
    deleting,
    snackbar,
    showSnackbar,
    openCreateDialog,
    openEditDialog,
    closeEditDialog,
    saveDefectType,
    confirmDelete,
    deleteDefectType,
    openUploadDialog,
    closeUploadDialog,
    uploadCSV,
    downloadTemplate,
  }
}
