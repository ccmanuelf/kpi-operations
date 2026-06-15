# AG Grid Excel behaviors

All Excel-like grid behaviors live in one isolated module
(`frontend/src/composables/agGridExcelBehaviors.ts`), gated by per-feature flags
plus a `master` switch. Flip a flag off and that shim disappears so AG Grid
Enterprise's native feature can take over with no conflicting handler. This file
documents every registered behavior; a test asserts it covers each registry key.

| Flag (key) | Excel feature | Community mechanism | Enterprise equivalent to defer to |
|---|---|---|---|
| `keyboardNav` | Enter moves down, Tab moves right | `navigateToNextCell` gridOption | Built-in AG Grid cell navigation (disable shim, use native) |
| `excelPaste` | Paste tabular data copied from Excel | clipboard read + clipboardParser + paste-preview dialog | Enterprise clipboard (processDataFromClipboard) |
| `csvImport` | Import a CSV file into the grid | file read → TSV → shared paste pipeline | n/a (Community-capable; no Enterprise overlap) |
| `csvExport` | Export the grid to CSV | `api.exportDataAsCsv` (Community) | n/a (Community-capable; no Enterprise overlap) |
| `xlsxExport` | Export the grid to .xlsx | exceljs over row data (`utils/excelExport`) | Enterprise `api.exportDataAsExcel` |

To disable everything (e.g. when adopting Enterprise), set `master: false` in the
flags passed to `useAgGridExcelBehaviors`; to defer a single behavior, set its
per-feature flag false. PR3b adds undo/redo, quick-find, copy, and freeze panes;
PR3c adds range selection + copy.
