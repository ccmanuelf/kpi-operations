/**
 * Composable for Workflow Config form handling and mutation
 * operations. Edit dialog, template application, form state,
 * save, snackbar.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { updateWorkflowConfig, applyWorkflowTemplate } from '@/services/api/workflow'

export interface WorkflowConfigFormData {
  workflow_statuses: string[]
  workflow_transitions: Record<string, string[]>
  workflow_optional_statuses: string[]
  workflow_closure_trigger: string
}

export interface WorkflowConfig extends WorkflowConfigFormData {
  [key: string]: unknown
}

export interface WorkflowTemplate {
  template_id: string | number
  name?: string
  [key: string]: unknown
}

interface SnackbarState {
  show: boolean
  text: string
  color: string
}

interface FormHandle {
  validate?: () => Promise<{ valid: boolean }>
  resetValidation?: () => void
}

const DEFAULT_FORM_DATA = (): WorkflowConfigFormData => ({
  workflow_statuses: [],
  workflow_transitions: {},
  workflow_optional_statuses: [],
  workflow_closure_trigger: 'at_shipment',
})

export default function useWorkflowConfigForms(
  selectedClientId: Ref<string | number | null>,
  workflowConfig: Ref<WorkflowConfig | null>,
  loadClientConfig: () => Promise<void>,
) {
  const { t } = useI18n()

  const editDialog = ref(false)
  const confirmTemplateDialog = ref(false)
  const selectedTemplate = ref<WorkflowTemplate | null>(null)
  const formValid = ref(true)
  const configForm = ref<FormHandle | null>(null)

  const saving = ref(false)
  const applyingTemplate = ref(false)

  const formData = ref<WorkflowConfigFormData>(DEFAULT_FORM_DATA())

  const snackbar = ref<SnackbarState>({ show: false, text: '', color: 'success' })

  const showSnackbar = (text: string, color: string): void => {
    snackbar.value = { show: true, text, color }
  }

  const openEditDialog = (): void => {
    if (workflowConfig.value) {
      formData.value = {
        workflow_statuses: [...(workflowConfig.value.workflow_statuses || [])],
        workflow_transitions: JSON.parse(
          JSON.stringify(workflowConfig.value.workflow_transitions || {}),
        ),
        workflow_optional_statuses: [
          ...(workflowConfig.value.workflow_optional_statuses || []),
        ],
        workflow_closure_trigger:
          workflowConfig.value.workflow_closure_trigger || 'at_shipment',
      }
    }
    editDialog.value = true
  }

  const saveConfig = async (): Promise<void> => {
    if (!selectedClientId.value) return

    saving.value = true
    try {
      await updateWorkflowConfig(selectedClientId.value, {
        workflow_statuses: formData.value.workflow_statuses,
        workflow_transitions: formData.value.workflow_transitions,
        workflow_optional_statuses: formData.value.workflow_optional_statuses,
        workflow_closure_trigger: formData.value.workflow_closure_trigger,
      })
      showSnackbar(t('admin.workflowConfig.success.updated'), 'success')
      editDialog.value = false
      await loadClientConfig()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to save config:', error)
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(
        ax?.response?.data?.detail || t('admin.workflowConfig.errors.save'),
        'error',
      )
    } finally {
      saving.value = false
    }
  }

  const confirmApplyTemplate = (template: WorkflowTemplate): void => {
    selectedTemplate.value = template
    confirmTemplateDialog.value = true
  }

  const applyTemplate = async (): Promise<void> => {
    if (!selectedTemplate.value || !selectedClientId.value) return

    applyingTemplate.value = true
    try {
      await applyWorkflowTemplate(
        selectedClientId.value,
        selectedTemplate.value.template_id,
      )
      showSnackbar(t('admin.workflowConfig.success.templateApplied'), 'success')
      confirmTemplateDialog.value = false
      await loadClientConfig()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to apply template:', error)
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(
        ax?.response?.data?.detail || t('admin.workflowConfig.errors.applyTemplate'),
        'error',
      )
    } finally {
      applyingTemplate.value = false
    }
  }

  return {
    editDialog,
    confirmTemplateDialog,
    selectedTemplate,
    formValid,
    configForm,
    saving,
    applyingTemplate,
    formData,
    snackbar,
    showSnackbar,
    openEditDialog,
    saveConfig,
    confirmApplyTemplate,
    applyTemplate,
  }
}
