/**
 * Status classifier — categorizes workflow statuses into types for
 * styling and validation, and provides Mermaid shape/class lookups.
 */

export type StatusType = 'start' | 'normal' | 'terminal' | 'hold' | 'optional'

export interface StatusStyle {
  backgroundColor: string
  borderColor: string
  textColor: string
  icon: string
}

export interface MermaidShape {
  open: string
  close: string
}

export const STATUS_TYPES = {
  START: 'start',
  NORMAL: 'normal',
  TERMINAL: 'terminal',
  HOLD: 'hold',
  OPTIONAL: 'optional',
} as const

const STATUS_CLASSIFICATIONS: Record<string, StatusType> = {
  RECEIVED: STATUS_TYPES.START,

  CLOSED: STATUS_TYPES.TERMINAL,
  CANCELLED: STATUS_TYPES.TERMINAL,
  REJECTED: STATUS_TYPES.TERMINAL,

  ON_HOLD: STATUS_TYPES.HOLD,
  HOLD: STATUS_TYPES.HOLD,
  PAUSED: STATUS_TYPES.HOLD,

  SHIPPED: STATUS_TYPES.OPTIONAL,
  DEMOTED: STATUS_TYPES.OPTIONAL,
  REWORK: STATUS_TYPES.OPTIONAL,

  DISPATCHED: STATUS_TYPES.NORMAL,
  IN_WIP: STATUS_TYPES.NORMAL,
  IN_PROGRESS: STATUS_TYPES.NORMAL,
  COMPLETED: STATUS_TYPES.NORMAL,
  READY: STATUS_TYPES.NORMAL,
  PENDING: STATUS_TYPES.NORMAL,
  APPROVED: STATUS_TYPES.NORMAL,
  RELEASED: STATUS_TYPES.NORMAL,
  SCHEDULED: STATUS_TYPES.NORMAL,
  STARTED: STATUS_TYPES.NORMAL,
  FINISHED: STATUS_TYPES.NORMAL,
}

export function classifyStatus(status: string | null | undefined): StatusType {
  const normalized = status?.toUpperCase().replace(/[\s-]+/g, '_') ?? ''
  return STATUS_CLASSIFICATIONS[normalized] || STATUS_TYPES.NORMAL
}

export function isTerminalStatus(status: string): boolean {
  return classifyStatus(status) === STATUS_TYPES.TERMINAL
}

export function isStartStatus(status: string): boolean {
  return classifyStatus(status) === STATUS_TYPES.START
}

export function isHoldStatus(status: string): boolean {
  return classifyStatus(status) === STATUS_TYPES.HOLD
}

export function isOptionalStatus(status: string): boolean {
  return classifyStatus(status) === STATUS_TYPES.OPTIONAL
}

export function getStatusTypeStyle(statusType: StatusType): StatusStyle {
  const styles: Record<StatusType, StatusStyle> = {
    [STATUS_TYPES.START]: {
      backgroundColor: '#d4edda',
      borderColor: '#28a745',
      textColor: '#155724',
      icon: 'mdi-play-circle',
    },
    [STATUS_TYPES.NORMAL]: {
      backgroundColor: '#cce5ff',
      borderColor: '#007bff',
      textColor: '#004085',
      icon: 'mdi-checkbox-blank-circle',
    },
    [STATUS_TYPES.TERMINAL]: {
      backgroundColor: '#f8d7da',
      borderColor: '#dc3545',
      textColor: '#721c24',
      icon: 'mdi-stop-circle',
    },
    [STATUS_TYPES.HOLD]: {
      backgroundColor: '#fff3cd',
      borderColor: '#ffc107',
      textColor: '#856404',
      icon: 'mdi-pause-circle',
    },
    [STATUS_TYPES.OPTIONAL]: {
      backgroundColor: '#e2e3e5',
      borderColor: '#6c757d',
      textColor: '#383d41',
      icon: 'mdi-skip-next-circle',
    },
  }

  return styles[statusType] || styles[STATUS_TYPES.NORMAL]
}

export function getMermaidShape(statusType: StatusType): MermaidShape {
  const shapes: Record<StatusType, MermaidShape> = {
    [STATUS_TYPES.START]: { open: '([', close: '])' },
    [STATUS_TYPES.NORMAL]: { open: '[', close: ']' },
    [STATUS_TYPES.TERMINAL]: { open: '[[', close: ']]' },
    [STATUS_TYPES.HOLD]: { open: '{{', close: '}}' },
    [STATUS_TYPES.OPTIONAL]: { open: '[/', close: '/]' },
  }

  return shapes[statusType] || shapes[STATUS_TYPES.NORMAL]
}

export function getMermaidClassName(statusType: StatusType): string {
  const classNames: Record<StatusType, string> = {
    [STATUS_TYPES.START]: 'start',
    [STATUS_TYPES.NORMAL]: 'normal',
    [STATUS_TYPES.TERMINAL]: 'terminal',
    [STATUS_TYPES.HOLD]: 'hold',
    [STATUS_TYPES.OPTIONAL]: 'optional',
  }

  return classNames[statusType] || 'normal'
}

export default {
  STATUS_TYPES,
  classifyStatus,
  isTerminalStatus,
  isStartStatus,
  isHoldStatus,
  isOptionalStatus,
  getStatusTypeStyle,
  getMermaidShape,
  getMermaidClassName,
}
