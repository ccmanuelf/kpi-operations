/**
 * Shared types for the workflow utility modules.
 */

export interface WorkflowConfig {
  statuses: string[]
  transitions?: Record<string, string[]>
  closure_trigger?: string
  [key: string]: unknown
}

export interface MermaidValidationResult {
  isValid: boolean
  errors: string[]
}
