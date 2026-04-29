/**
 * Composable for Part Opportunities form handling and CRUD.
 * Create/edit dialogs, validation rules, save/delete, CSV upload,
 * template download.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export interface PartOpportunityFormData {
  part_number: string
  opportunities_per_unit: number
  part_description: string
  complexity: string
  client_id: string | number | null
  notes: string
  is_active: boolean
  part_opportunities_id?: string | number
}

export interface PartOpportunityRow extends PartOpportunityFormData {
  part_opportunities_id: string | number
  [key: string]: unknown
}

interface FormHandle {
  reset?: () => void
  validate?: () => Promise<{ valid: boolean }>
}

type ValidationRule = (v: unknown) => true | string

interface ValidationRules {
  required: ValidationRule
  maxLength50: ValidationRule
  positive: ValidationRule
}

type SnackbarFn = (message: string, color: string) => void

const DEFAULT_FORM_DATA = (): PartOpportunityFormData => ({
  part_number: '',
  opportunities_per_unit: 10,
  part_description: '',
  complexity: '',
  client_id: null,
  notes: '',
  is_active: true,
})

export function usePartOpportunitiesForms(
  selectedClient: Ref<string | number | null>,
  loadPartOpportunities: () => Promise<void>,
  showSnackbar: SnackbarFn,
) {
  const { t } = useI18n()

  const editDialog = ref(false)
  const uploadDialog = ref(false)
  const deleteDialog = ref(false)
  const isEditing = ref(false)
  const deleteTarget = ref<PartOpportunityRow | null>(null)

  const saving = ref(false)
  const uploading = ref(false)
  const deleting = ref(false)

  const form = ref<FormHandle | null>(null)
  const formValid = ref(false)
  const formData = ref<PartOpportunityFormData>(DEFAULT_FORM_DATA())

  const uploadFile = ref<File | null>(null)
  const replaceExisting = ref(false)

  const complexityOptions: string[] = ['Simple', 'Standard', 'Complex', 'Very Complex']

  const rules: ValidationRules = {
    required: (v) => !!v || t('validation.required'),
    maxLength50: (v) =>
      !v ||
      (typeof v === 'string' && v.length <= 50) ||
      t('validation.maxLength', { max: 50 }),
    positive: (v) => (typeof v === 'number' && v > 0) || t('validation.positive'),
  }

  const openCreateDialog = (): void => {
    isEditing.value = false
    formData.value = {
      ...DEFAULT_FORM_DATA(),
      complexity: 'Standard',
      client_id: selectedClient.value,
    }
    editDialog.value = true
  }

  const openEditDialog = (item: PartOpportunityRow): void => {
    isEditing.value = true
    formData.value = { ...item }
    editDialog.value = true
  }

  const closeEditDialog = (): void => {
    editDialog.value = false
    form.value?.reset?.()
  }

  const savePartOpportunity = async (): Promise<void> => {
    if (!formValid.value) return

    saving.value = true
    try {
      if (isEditing.value && formData.value.part_opportunities_id) {
        await api.put(
          `/part-opportunities/${formData.value.part_opportunities_id}`,
          formData.value,
        )
        showSnackbar(t('success.updated'), 'success')
      } else {
        await api.post('/part-opportunities', formData.value)
        showSnackbar(t('success.saved'), 'success')
      }
      closeEditDialog()
      await loadPartOpportunities()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      saving.value = false
    }
  }

  const confirmDelete = (item: PartOpportunityRow): void => {
    deleteTarget.value = item
    deleteDialog.value = true
  }

  const deletePartOpportunity = async (): Promise<void> => {
    if (!deleteTarget.value) return

    deleting.value = true
    try {
      await api.delete(`/part-opportunities/${deleteTarget.value.part_opportunities_id}`)
      showSnackbar(t('success.deleted'), 'success')
      deleteDialog.value = false
      await loadPartOpportunities()
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
    if (!uploadFile.value) return

    uploading.value = true
    try {
      const formDataUpload = new FormData()
      formDataUpload.append('file', uploadFile.value)
      formDataUpload.append('replace_existing', String(replaceExisting.value))
      if (selectedClient.value) {
        formDataUpload.append('client_id', String(selectedClient.value))
      }

      const res = await api.post('/part-opportunities/upload', formDataUpload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      showSnackbar(t('csv.success', { count: res.data.created || 0 }), 'success')
      closeUploadDialog()
      await loadPartOpportunities()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('csv.error'), 'error')
    } finally {
      uploading.value = false
    }
  }

  const downloadTemplate = (): void => {
    const csvHeaders = [
      'part_number',
      'opportunities_per_unit',
      'part_description',
      'complexity',
      'notes',
    ]
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
    editDialog,
    uploadDialog,
    deleteDialog,
    isEditing,
    deleteTarget,
    saving,
    uploading,
    deleting,
    form,
    formValid,
    formData,
    uploadFile,
    replaceExisting,
    complexityOptions,
    rules,
    openCreateDialog,
    openEditDialog,
    closeEditDialog,
    savePartOpportunity,
    confirmDelete,
    deletePartOpportunity,
    openUploadDialog,
    closeUploadDialog,
    uploadCSV,
    downloadTemplate,
  }
}
