/**
 * History Manager for Undo/Redo support.
 *
 * Maintains a stack of serialised worksheet snapshots and provides
 * undo / redo traversal.  Used by the main capacity planning store.
 */

export const createHistoryManager = (maxHistory = 50) => ({
  past: [],
  future: [],
  maxHistory,

  push(state) {
    this.past.push(JSON.stringify(state))
    if (this.past.length > this.maxHistory) {
      this.past.shift()
    }
    this.future = [] // Clear redo stack on new action
  },

  undo() {
    if (this.past.length === 0) return null
    const current = this.past.pop()
    this.future.push(current)
    return this.past.length > 0 ? JSON.parse(this.past[this.past.length - 1]) : null
  },

  redo() {
    if (this.future.length === 0) return null
    const state = this.future.pop()
    this.past.push(state)
    return JSON.parse(state)
  },

  canUndo() {
    return this.past.length > 0
  },

  canRedo() {
    return this.future.length > 0
  },

  clear() {
    this.past = []
    this.future = []
  }
})
