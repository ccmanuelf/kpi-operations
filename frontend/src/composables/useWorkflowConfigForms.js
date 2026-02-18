/**
 * Composable for Workflow Config form handling and mutation operations.
 * Handles: edit dialog, template application, form state, save, snackbar.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  updateWorkflowConfig,
  applyWorkflowTemplate
} from '@/services/api/workflow'

const DEFAULT_FORM_DATA = {
  workflow_statuses: [],
  workflow_transitions: {},
  workflow_optional_statuses: [],
  workflow_closure_trigger: 'at_shipment'
}

export default function useWorkflowConfigForms(selectedClientId, workflowConfig, loadClientConfig) {
  const { t } = useI18n()

  // Dialog state
  const editDialog = ref(false)
  const confirmTemplateDialog = ref(false)
  const selectedTemplate = ref(null)
  const formValid = ref(true)
  const configForm = ref(null)

  // Loading flags
  const saving = ref(false)
  const applyingTemplate = ref(false)

  // Form data
  const formData = ref({ ...DEFAULT_FORM_DATA })

  // Snackbar
  const snackbar = ref({ show: false, text: '', color: 'success' })

  const showSnackbar = (text, color) => {
    snackbar.value = { show: true, text, color }
  }

  // Form operations
  const openEditDialog = () => {
    if (workflowConfig.value) {
      formData.value = {
        workflow_statuses: [...(workflowConfig.value.workflow_statuses || [])],
        workflow_transitions: JSON.parse(JSON.stringify(workflowConfig.value.workflow_transitions || {})),
        workflow_optional_statuses: [...(workflowConfig.value.workflow_optional_statuses || [])],
        workflow_closure_trigger: workflowConfig.value.workflow_closure_trigger || 'at_shipment'
      }
    }
    editDialog.value = true
  }

  const saveConfig = async () => {
    saving.value = true
    try {
      await updateWorkflowConfig(selectedClientId.value, {
        workflow_statuses: formData.value.workflow_statuses,
        workflow_transitions: formData.value.workflow_transitions,
        workflow_optional_statuses: formData.value.workflow_optional_statuses,
        workflow_closure_trigger: formData.value.workflow_closure_trigger
      })
      showSnackbar(t('admin.workflowConfig.success.updated'), 'success')
      editDialog.value = false
      await loadClientConfig()
    } catch (error) {
      console.error('Failed to save config:', error)
      showSnackbar(error.response?.data?.detail || t('admin.workflowConfig.errors.save'), 'error')
    } finally {
      saving.value = false
    }
  }

  const confirmApplyTemplate = (template) => {
    selectedTemplate.value = template
    confirmTemplateDialog.value = true
  }

  const applyTemplate = async () => {
    if (!selectedTemplate.value) return

    applyingTemplate.value = true
    try {
      await applyWorkflowTemplate(selectedClientId.value, selectedTemplate.value.template_id)
      showSnackbar(t('admin.workflowConfig.success.templateApplied'), 'success')
      confirmTemplateDialog.value = false
      await loadClientConfig()
    } catch (error) {
      console.error('Failed to apply template:', error)
      showSnackbar(error.response?.data?.detail || t('admin.workflowConfig.errors.applyTemplate'), 'error')
    } finally {
      applyingTemplate.value = false
    }
  }

  return {
    // Dialog state
    editDialog,
    confirmTemplateDialog,
    selectedTemplate,
    formValid,
    configForm,

    // Loading
    saving,
    applyingTemplate,

    // Form
    formData,

    // Snackbar
    snackbar,
    showSnackbar,

    // Operations
    openEditDialog,
    saveConfig,
    confirmApplyTemplate,
    applyTemplate
  }
}
