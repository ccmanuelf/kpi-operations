import { ref, onMounted, onUnmounted } from 'vue'
import { useKeyboardShortcuts } from './useKeyboardShortcuts'

/**
 * Form-specific keyboard shortcuts
 * Handles form navigation, submission, and field management
 */
export function useFormShortcuts(formRef, options = {}) {
  const { registerShortcut } = useKeyboardShortcuts({ registerGlobal: false })
  const formFocused = ref(false)
  const {
    onSave,
    onCancel,
    onReset,
    onNextField,
    onPrevField
  } = options

  /**
   * Check if form is focused
   */
  const checkFormFocus = () => {
    if (!formRef?.value) return false
    const activeElement = document.activeElement
    return formRef.value.contains(activeElement) || formFocused.value
  }

  /**
   * Get all form fields
   */
  const getFormFields = () => {
    if (!formRef?.value) return []

    const fields = formRef.value.querySelectorAll(
      'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])'
    )
    return Array.from(fields)
  }

  /**
   * Get current field index
   */
  const getCurrentFieldIndex = () => {
    const fields = getFormFields()
    const activeElement = document.activeElement
    return fields.findIndex(field => field === activeElement)
  }

  /**
   * Focus next field
   */
  const focusNextField = () => {
    const fields = getFormFields()
    const currentIndex = getCurrentFieldIndex()

    if (currentIndex < fields.length - 1) {
      fields[currentIndex + 1].focus()
      if (fields[currentIndex + 1].select) {
        fields[currentIndex + 1].select()
      }
    } else if (fields.length > 0) {
      // Wrap to first field
      fields[0].focus()
      if (fields[0].select) {
        fields[0].select()
      }
    }
  }

  /**
   * Focus previous field
   */
  const focusPrevField = () => {
    const fields = getFormFields()
    const currentIndex = getCurrentFieldIndex()

    if (currentIndex > 0) {
      fields[currentIndex - 1].focus()
      if (fields[currentIndex - 1].select) {
        fields[currentIndex - 1].select()
      }
    } else if (fields.length > 0) {
      // Wrap to last field
      fields[fields.length - 1].focus()
      if (fields[fields.length - 1].select) {
        fields[fields.length - 1].select()
      }
    }
  }

  /**
   * Focus first invalid field
   */
  const focusFirstInvalidField = () => {
    if (!formRef?.value) return

    const invalidField = formRef.value.querySelector(
      'input:invalid, select:invalid, textarea:invalid, [aria-invalid="true"]'
    )

    if (invalidField) {
      invalidField.focus()
      if (invalidField.select) {
        invalidField.select()
      }
    }
  }

  /**
   * Register form shortcuts
   */
  const registerFormShortcuts = () => {
    // Save form
    if (onSave) {
      registerShortcut('form-save', {
        key: 's',
        ctrl: true,
        description: 'Save form',
        category: 'Form Actions',
        context: checkFormFocus,
        handler: (e) => {
          e.preventDefault()
          onSave()
        }
      })

      // Alternative: Ctrl+Enter to save
      registerShortcut('form-save-alt', {
        key: 'enter',
        ctrl: true,
        description: 'Save form (alternative)',
        category: 'Form Actions',
        context: checkFormFocus,
        handler: (e) => {
          e.preventDefault()
          onSave()
        }
      })
    }

    // Cancel/Escape
    if (onCancel) {
      registerShortcut('form-cancel', {
        key: 'escape',
        description: 'Cancel form editing',
        category: 'Form Actions',
        context: checkFormFocus,
        handler: (e) => {
          e.preventDefault()
          onCancel()
        }
      })
    }

    // Reset form
    if (onReset) {
      registerShortcut('form-reset', {
        key: 'r',
        ctrl: true,
        shift: true,
        description: 'Reset form to initial values',
        category: 'Form Actions',
        context: checkFormFocus,
        handler: (e) => {
          e.preventDefault()
          onReset()
        }
      })
    }

    // Navigate to next field (Ctrl+Down)
    registerShortcut('form-next-field', {
      key: 'arrowdown',
      ctrl: true,
      description: 'Move to next form field',
      category: 'Form Navigation',
      context: checkFormFocus,
      handler: (e) => {
        e.preventDefault()
        if (onNextField) {
          onNextField()
        } else {
          focusNextField()
        }
      }
    })

    // Navigate to previous field (Ctrl+Up)
    registerShortcut('form-prev-field', {
      key: 'arrowup',
      ctrl: true,
      description: 'Move to previous form field',
      category: 'Form Navigation',
      context: checkFormFocus,
      handler: (e) => {
        e.preventDefault()
        if (onPrevField) {
          onPrevField()
        } else {
          focusPrevField()
        }
      }
    })

    // Focus first field (Home)
    registerShortcut('form-first-field', {
      key: 'home',
      ctrl: true,
      description: 'Focus first form field',
      category: 'Form Navigation',
      context: checkFormFocus,
      handler: (e) => {
        e.preventDefault()
        const fields = getFormFields()
        if (fields.length > 0) {
          fields[0].focus()
          if (fields[0].select) {
            fields[0].select()
          }
        }
      }
    })

    // Focus last field (End)
    registerShortcut('form-last-field', {
      key: 'end',
      ctrl: true,
      description: 'Focus last form field',
      category: 'Form Navigation',
      context: checkFormFocus,
      handler: (e) => {
        e.preventDefault()
        const fields = getFormFields()
        if (fields.length > 0) {
          const lastField = fields[fields.length - 1]
          lastField.focus()
          if (lastField.select) {
            lastField.select()
          }
        }
      }
    })

    // Focus first invalid field (Ctrl+E for Error)
    registerShortcut('form-first-error', {
      key: 'e',
      ctrl: true,
      description: 'Focus first invalid field',
      category: 'Form Navigation',
      context: checkFormFocus,
      handler: (e) => {
        e.preventDefault()
        focusFirstInvalidField()
      }
    })

    // Clear current field (Ctrl+Backspace)
    registerShortcut('form-clear-field', {
      key: 'backspace',
      ctrl: true,
      description: 'Clear current field',
      category: 'Form Editing',
      context: checkFormFocus,
      allowInInputs: true,
      handler: (e) => {
        e.preventDefault()
        const activeElement = document.activeElement
        if (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA') {
          activeElement.value = ''
          activeElement.dispatchEvent(new Event('input', { bubbles: true }))
        } else if (activeElement.tagName === 'SELECT') {
          activeElement.selectedIndex = 0
          activeElement.dispatchEvent(new Event('change', { bubbles: true }))
        }
      }
    })

    // Select all text in current field (Ctrl+A when in input)
    registerShortcut('form-select-all', {
      key: 'a',
      ctrl: true,
      description: 'Select all text in field',
      category: 'Form Editing',
      context: checkFormFocus,
      allowInInputs: true,
      preventDefault: false,
      handler: () => {
        const activeElement = document.activeElement
        if (activeElement.select) {
          activeElement.select()
        }
      }
    })
  }

  /**
   * Setup focus tracking
   */
  const setupFocusTracking = () => {
    if (!formRef?.value) return

    formRef.value.addEventListener('focusin', () => {
      formFocused.value = true
    })

    formRef.value.addEventListener('focusout', (e) => {
      if (!formRef.value.contains(e.relatedTarget)) {
        formFocused.value = false
      }
    })
  }

  onMounted(() => {
    registerFormShortcuts()
    setupFocusTracking()
  })

  return {
    formFocused,
    focusNextField,
    focusPrevField,
    focusFirstInvalidField,
    getFormFields,
    registerFormShortcuts
  }
}
