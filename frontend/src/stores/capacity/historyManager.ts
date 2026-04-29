/**
 * History manager for undo/redo support. Holds a stack of
 * serialized worksheet snapshots and walks through them on demand.
 * The capacity worksheet-ops sub-store uses this to support cell
 * and row mutations with undo coverage.
 */

export interface HistoryState<T = unknown> {
  worksheetName: string
  data: T
  [key: string]: unknown
}

export interface HistoryManager<T = unknown> {
  past: string[]
  future: string[]
  maxHistory: number
  push(state: HistoryState<T>): void
  undo(): HistoryState<T> | null
  redo(): HistoryState<T> | null
  canUndo(): boolean
  canRedo(): boolean
  clear(): void
}

export const createHistoryManager = <T = unknown>(maxHistory = 50): HistoryManager<T> => ({
  past: [] as string[],
  future: [] as string[],
  maxHistory,

  push(state: HistoryState<T>) {
    this.past.push(JSON.stringify(state))
    if (this.past.length > this.maxHistory) {
      this.past.shift()
    }
    this.future = []
  },

  undo(): HistoryState<T> | null {
    if (this.past.length === 0) return null
    const current = this.past.pop()
    if (current !== undefined) {
      this.future.push(current)
    }
    return this.past.length > 0
      ? (JSON.parse(this.past[this.past.length - 1]) as HistoryState<T>)
      : null
  },

  redo(): HistoryState<T> | null {
    if (this.future.length === 0) return null
    const state = this.future.pop()
    if (state === undefined) return null
    this.past.push(state)
    return JSON.parse(state) as HistoryState<T>
  },

  canUndo(): boolean {
    return this.past.length > 0
  },

  canRedo(): boolean {
    return this.future.length > 0
  },

  clear() {
    this.past = []
    this.future = []
  },
})
