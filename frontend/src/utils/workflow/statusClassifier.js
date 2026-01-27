/**
 * Status Classifier
 * Classifies workflow statuses into types for styling and validation
 */

// Status type definitions
export const STATUS_TYPES = {
  START: 'start',
  NORMAL: 'normal',
  TERMINAL: 'terminal',
  HOLD: 'hold',
  OPTIONAL: 'optional'
}

// Known status classifications
const STATUS_CLASSIFICATIONS = {
  // Entry point
  RECEIVED: STATUS_TYPES.START,

  // Terminal statuses (end points)
  CLOSED: STATUS_TYPES.TERMINAL,
  CANCELLED: STATUS_TYPES.TERMINAL,
  REJECTED: STATUS_TYPES.TERMINAL,

  // Hold statuses (pause points)
  ON_HOLD: STATUS_TYPES.HOLD,
  HOLD: STATUS_TYPES.HOLD,
  PAUSED: STATUS_TYPES.HOLD,

  // Optional statuses (can be skipped)
  SHIPPED: STATUS_TYPES.OPTIONAL,
  DEMOTED: STATUS_TYPES.OPTIONAL,
  REWORK: STATUS_TYPES.OPTIONAL,

  // Normal flow statuses
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
  FINISHED: STATUS_TYPES.NORMAL
}

/**
 * Classify a status into its type
 * @param {string} status - Status name
 * @returns {string} Status type
 */
export function classifyStatus(status) {
  const normalized = status?.toUpperCase().replace(/[\s-]+/g, '_')
  return STATUS_CLASSIFICATIONS[normalized] || STATUS_TYPES.NORMAL
}

/**
 * Check if a status is a terminal (end) status
 * @param {string} status - Status name
 * @returns {boolean}
 */
export function isTerminalStatus(status) {
  return classifyStatus(status) === STATUS_TYPES.TERMINAL
}

/**
 * Check if a status is the start status
 * @param {string} status - Status name
 * @returns {boolean}
 */
export function isStartStatus(status) {
  return classifyStatus(status) === STATUS_TYPES.START
}

/**
 * Check if a status is a hold status
 * @param {string} status - Status name
 * @returns {boolean}
 */
export function isHoldStatus(status) {
  return classifyStatus(status) === STATUS_TYPES.HOLD
}

/**
 * Check if a status is optional
 * @param {string} status - Status name
 * @returns {boolean}
 */
export function isOptionalStatus(status) {
  return classifyStatus(status) === STATUS_TYPES.OPTIONAL
}

/**
 * Get styling for a status type
 * @param {string} statusType - Status type
 * @returns {Object} Style object with colors
 */
export function getStatusTypeStyle(statusType) {
  const styles = {
    [STATUS_TYPES.START]: {
      backgroundColor: '#d4edda',
      borderColor: '#28a745',
      textColor: '#155724',
      icon: 'mdi-play-circle'
    },
    [STATUS_TYPES.NORMAL]: {
      backgroundColor: '#cce5ff',
      borderColor: '#007bff',
      textColor: '#004085',
      icon: 'mdi-checkbox-blank-circle'
    },
    [STATUS_TYPES.TERMINAL]: {
      backgroundColor: '#f8d7da',
      borderColor: '#dc3545',
      textColor: '#721c24',
      icon: 'mdi-stop-circle'
    },
    [STATUS_TYPES.HOLD]: {
      backgroundColor: '#fff3cd',
      borderColor: '#ffc107',
      textColor: '#856404',
      icon: 'mdi-pause-circle'
    },
    [STATUS_TYPES.OPTIONAL]: {
      backgroundColor: '#e2e3e5',
      borderColor: '#6c757d',
      textColor: '#383d41',
      icon: 'mdi-skip-next-circle'
    }
  }

  return styles[statusType] || styles[STATUS_TYPES.NORMAL]
}

/**
 * Get Mermaid shape for a status type
 * @param {string} statusType - Status type
 * @returns {Object} Mermaid shape tokens
 */
export function getMermaidShape(statusType) {
  const shapes = {
    [STATUS_TYPES.START]: { open: '([', close: '])' },      // Stadium shape
    [STATUS_TYPES.NORMAL]: { open: '[', close: ']' },       // Rectangle
    [STATUS_TYPES.TERMINAL]: { open: '[[', close: ']]' },   // Subroutine shape
    [STATUS_TYPES.HOLD]: { open: '{{', close: '}}' },       // Hexagon
    [STATUS_TYPES.OPTIONAL]: { open: '[/', close: '/]' }    // Parallelogram
  }

  return shapes[statusType] || shapes[STATUS_TYPES.NORMAL]
}

/**
 * Get Mermaid class name for a status type
 * @param {string} statusType - Status type
 * @returns {string} CSS class name
 */
export function getMermaidClassName(statusType) {
  const classNames = {
    [STATUS_TYPES.START]: 'start',
    [STATUS_TYPES.NORMAL]: 'normal',
    [STATUS_TYPES.TERMINAL]: 'terminal',
    [STATUS_TYPES.HOLD]: 'hold',
    [STATUS_TYPES.OPTIONAL]: 'optional'
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
  getMermaidClassName
}
