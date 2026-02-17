# KPI Operations Frontend

Vue 3 + Vuetify + AG Grid enterprise manufacturing dashboard.

## Tech Stack

- **Framework:** Vue 3.4 (Composition API)
- **State:** Pinia 3
- **UI:** Vuetify 3 + AG Grid Community 35
- **Router:** vue-router 5
- **i18n:** vue-i18n 11
- **Charts:** Mermaid 11, Vue Flow
- **Build:** Vite 7.3
- **Testing:** Vitest 4 (unit), Playwright (E2E)
- **Lint:** ESLint 10 (flat config)
- **CSS:** Tailwind CSS 4

## Setup

```bash
npm ci --legacy-peer-deps
npm run dev
```

Requires backend running at `http://localhost:8000` (configured in `vite.config.ts` proxy).

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Development server (port 5173) |
| `npm run build` | Production build |
| `npm run lint` | ESLint check + fix |
| `npm run test` | Unit tests (Vitest) |
| `npm run test:coverage` | Unit tests with coverage |
| `npm run test:e2e` | E2E tests (Playwright) |
| `npm run test:e2e:headed` | E2E tests in browser |
| `npm run test:e2e:sqlite` | E2E tests against SQLite backend |

## Project Structure

```
src/
  views/              # Page-level components
    CapacityPlanning/  # 13-tab workbook (grids, panels, dialogs)
    admin/             # Database config, migration
    kpi/               # KPI sub-views
  components/          # Shared components
  stores/              # Pinia stores
  services/api/        # Backend API clients
  composables/         # Vue composables
  router/              # Route definitions + guards
  i18n/                # Internationalization
  plugins/             # Vuetify, Pinia setup
e2e/                   # Playwright E2E specs
```

## Key Views

- **DashboardView** - Main operations dashboard
- **ProductionEntry** - Production data entry with AG Grid
- **CapacityPlanning** - 13-worksheet workbook (MRP, scenarios, analysis)
- **SimulationV2View** - Production simulation engine
- **WorkOrderManagement** - Work order lifecycle and workflow
- **KPIDashboard** - KPI metrics and charts
- **AlertsView** - Real-time alert management

## Testing

- **Unit tests:** 1516 tests across 55 test files
- **E2E tests:** 595 Playwright specs (Chromium + Firefox)
- **Coverage:** V8 provider with thresholds in `vitest.config.ts`
- **Login helper:** Shared `e2e/helpers.ts` for E2E authentication

## Environment

- Node 20 (see `.nvmrc`)
- `--legacy-peer-deps` required for ESLint 10 peer conflicts
