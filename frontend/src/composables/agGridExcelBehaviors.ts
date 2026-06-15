// Single, flag-isolated home for Excel-like AG Grid behaviors (spec §3e).
// The ONLY place that emits Excel-behavior gridOptions fragments. Flip `master`
// (or a per-feature flag) off and the corresponding shim disappears so AG Grid
// Enterprise's native feature can take over with no conflicting handler.
// See docs/frontend/ag-grid-excel-behaviors.md.

export interface ExcelBehaviorFlags {
  master: boolean
  keyboardNav: boolean
  excelPaste: boolean
  csvImport: boolean
  csvExport: boolean
  xlsxExport: boolean
  undoRedo: boolean
  copy: boolean
  cellEditing: boolean
  freezePanes: boolean
  quickFind: boolean
}

export const DEFAULT_EXCEL_BEHAVIOR_FLAGS: ExcelBehaviorFlags = {
  master: true,
  keyboardNav: true,
  excelPaste: true,
  csvImport: true,
  csvExport: true,
  xlsxExport: true,
  undoRedo: true,
  copy: true,
  cellEditing: true,
  freezePanes: true,
  quickFind: false,
}

export type ExcelBehaviorKey = Exclude<keyof ExcelBehaviorFlags, 'master'>

export interface ExcelBehaviorEntry {
  key: ExcelBehaviorKey
  excelFeature: string
  communityMechanism: string
  enterpriseEquivalent: string
  enabled: boolean
}

// Metadata for every behavior — drives both the registry and the docs table.
const BEHAVIOR_META: Omit<ExcelBehaviorEntry, 'enabled'>[] = [
  {
    key: 'keyboardNav',
    excelFeature: 'Enter moves down, Tab moves right',
    communityMechanism: 'navigateToNextCell gridOption',
    enterpriseEquivalent: 'Built-in AG Grid cell navigation (disable shim, use native)',
  },
  {
    key: 'excelPaste',
    excelFeature: 'Paste tabular data copied from Excel',
    communityMechanism: 'clipboard read + clipboardParser + paste-preview dialog',
    enterpriseEquivalent: 'Enterprise clipboard (processDataFromClipboard)',
  },
  {
    key: 'csvImport',
    excelFeature: 'Import a CSV file into the grid',
    communityMechanism: 'file read -> TSV -> shared paste pipeline',
    enterpriseEquivalent: 'n/a (Community-capable; no Enterprise overlap)',
  },
  {
    key: 'csvExport',
    excelFeature: 'Export the grid to CSV',
    communityMechanism: 'api.exportDataAsCsv (Community)',
    enterpriseEquivalent: 'n/a (Community-capable; no Enterprise overlap)',
  },
  {
    key: 'xlsxExport',
    excelFeature: 'Export the grid to .xlsx',
    communityMechanism: 'exceljs over row data (utils/excelExport)',
    enterpriseEquivalent: 'Enterprise api.exportDataAsExcel',
  },
  {
    key: 'undoRedo',
    excelFeature: 'Undo / redo cell edits (Ctrl+Z / Ctrl+Y)',
    communityMechanism: 'undoRedoCellEditing gridOption (limit 20)',
    enterpriseEquivalent: 'Same native AG Grid option (no shim; flag stays on)',
  },
  {
    key: 'copy',
    excelFeature: 'Copy focused cell or whole selected rows (Ctrl+C)',
    communityMechanism: 'AG default cell copy + suppressCopyRowsToClipboard:false',
    enterpriseEquivalent: 'Enterprise clipboard (richer range copy — see PR3c)',
  },
  {
    key: 'cellEditing',
    excelFeature: 'Type-to-edit, Esc cancels, commit on blur',
    communityMechanism: 'stopEditingWhenCellsLoseFocus + AG default key editing',
    enterpriseEquivalent: 'n/a (Community-capable; no Enterprise overlap)',
  },
  {
    key: 'freezePanes',
    excelFeature: 'Freeze columns + header row',
    communityMechanism: 'per-grid colDef pinned + sticky header (no extra option)',
    enterpriseEquivalent: 'Same native pinning',
  },
  {
    key: 'quickFind',
    excelFeature: 'Instant global filter (Ctrl+F style)',
    communityMechanism: 'deferred — per-screen Search box covers this (off by default)',
    enterpriseEquivalent: 'n/a (Community-capable; deferred by product choice)',
  },
]

// Excel-style cell navigation: Enter commits + moves down the same column;
// Tab keeps AG Grid's suggested next cell (moves right). Moved here from
// useAGGridBase so it lives behind the keyboardNav flag.
const excelNavigateToNextCell = (params: {
  key: number
  nextCellPosition: unknown
  previousCellPosition: { rowIndex: number; column: unknown }
}) => {
  if (params.key === 13) {
    return {
      rowIndex: params.previousCellPosition.rowIndex + 1,
      column: params.previousCellPosition.column,
    }
  }
  return params.nextCellPosition
}

export interface ExcelBehaviorsResult {
  gridOptions: Record<string, unknown>
  registry: ExcelBehaviorEntry[]
}

export function useAgGridExcelBehaviors(flags: ExcelBehaviorFlags): ExcelBehaviorsResult {
  const on = (key: ExcelBehaviorKey): boolean => flags.master && flags[key]
  const gridOptions: Record<string, unknown> = {}
  if (on('keyboardNav')) {
    gridOptions.navigateToNextCell = excelNavigateToNextCell
  }
  if (on('undoRedo')) {
    gridOptions.undoRedoCellEditing = true
    gridOptions.undoRedoCellEditingLimit = 20
  }
  if (on('copy')) {
    // Single-cell Ctrl+C is the AG default; this makes whole-row copy explicit.
    // Enterprise: native clipboard / range copy (PR3c) supersedes — flag off then.
    gridOptions.suppressCopyRowsToClipboard = false
  }
  if (on('cellEditing')) {
    // Excel-style commit-on-blur; type-to-edit + Esc-cancel are AG defaults.
    gridOptions.stopEditingWhenCellsLoseFocus = true
  }
  // freezePanes = per-grid pinned columns + sticky header; quickFind = deferred.
  // Neither emits a gridOptions fragment — they are registry/doc entries only.
  const registry: ExcelBehaviorEntry[] = BEHAVIOR_META.map((m) => ({
    ...m,
    enabled: on(m.key),
  }))
  return { gridOptions, registry }
}
