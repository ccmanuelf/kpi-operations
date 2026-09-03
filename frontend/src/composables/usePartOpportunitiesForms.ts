/**
 * Composable for Part Opportunities form handling and CRUD.
 * Create/edit dialogs, validation rules, save/delete, CSV upload,
 * template download.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as Papa from 'papaparse'
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

type ValidationRule = (_v: unknown) => true | string

interface ValidationRules {
  required: ValidationRule
  maxLength50: ValidationRule
  positive: ValidationRule
}

type SnackbarFn = (_message: string, _color: string) => void

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
    uploadDialog.value = true
  }

  const closeUploadDialog = (): void => {
    uploadDialog.value = false
    uploadFile.value = null
  }

  const uploadCSV = async (): Promise<void> => {
    if (!uploadFile.value) return

    // POST /api/part-opportunities/bulk-import takes JSON — a
    // { opportunities: PartOpportunityCreate[] } body — not multipart. This
    // used to post a file to `/part-opportunities/upload`, a path with no
    // server route, so every upload 404'd and surfaced as the generic
    // t('csv.error') toast with nothing to act on. There is no file-upload
    // endpoint for this resource; the CSV is parsed here and sent as rows.
    if (!selectedClient.value) {
      showSnackbar(t('csv.selectClientFirst'), 'error')
      return
    }

    uploading.value = true
    try {
      const text = await uploadFile.value.text()
      const parsed = Papa.parse<Record<string, string>>(text, {
        header: true,
        skipEmptyLines: true,
      })

      const opportunities = parsed.data
        .map((row) => ({
          part_number: (row.part_number ?? '').trim(),
          client_id_fk: String(selectedClient.value),
          // Required and must be > 0 server-side; NaN would be rejected row by
          // row with a less obvious message than the count below.
          opportunities_per_unit: Number.parseInt(row.opportunities_per_unit ?? '', 10),
          part_description: row.part_description?.trim() || null,
          // `complexity` is what older templates emitted for this column.
          part_category: (row.part_category ?? row.complexity)?.trim() || null,
          notes: row.notes?.trim() || null,
        }))
        .filter((o) => o.part_number && Number.isFinite(o.opportunities_per_unit))

      if (opportunities.length === 0) {
        showSnackbar(t('csv.noValidRows'), 'error')
        return
      }

      const res = await api.post('/part-opportunities/bulk-import', { opportunities })
      const { success_count: created = 0, failure_count: failed = 0, errors = [] } = res.data ?? {}

      if (failed > 0) {
        // Report the partial outcome rather than a bare success: the endpoint
        // imports row by row and returns what it could not take.
        showSnackbar(
          t('csv.partialSuccess', { count: created, failed }) + (errors[0] ? ` — ${errors[0]}` : ''),
          'warning'
        )
      } else {
        showSnackbar(t('csv.success', { count: created }), 'success')
      }
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
    // `part_category`, not `complexity`: the schema has no complexity field,
    // so the old template taught a column the import silently dropped.
    const csvHeaders = [
      'part_number',
      'opportunities_per_unit',
      'part_description',
      'part_category',
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
