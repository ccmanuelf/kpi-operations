# Backend capability the UI cannot reach

Audited 2026-09-03. **17 high, 16 medium, 8 low** confirmed; 10 further claims were refuted and are not listed.

Produced by a five-slice audit of the API surface against `frontend/src`, with every
claimed gap sent to an independent agent whose job was to REFUTE it by finding the
screen, route, link or call that reaches it. Only gaps that survived that are here.

A gap means: the backend implements something real, and a user running the app cannot
invoke it — no route, no link, no call, a read-only surface over a read/write API, or
a control wired to nothing.


---

## HIGH (17)

### Shift master data CRUD — create, update, delete, and overlap-check shifts

**Slice:** masters-admin

**Backend:** backend/routes/shifts.py:66 POST /api/shifts/ (create_shift_endpoint), :96 POST /api/shifts/check-overlap, :150 PUT /api/shifts/{shift_id}, :186 DELETE /api/shifts/{shift_id}. Backed by backend/crud/shift.py:102 create_shift, :167 update_shift, :194 deactivate_shift, :53 check_shift_overlaps, and backend/schemas/shift.py (ShiftCreate/ShiftUpdate/OverlapCheckRequest). ORM backend/orm/shift.py table SHIFT, seeded by backend/seed/writers_master.py:142-145.

**Why unreachable:** The only shift call anywhere in frontend/src is a READ: frontend/src/services/api/reference.ts:31 `api.get('/shifts/')` and frontend/src/composables/useShiftForms.ts:386 `api.get('/shifts')`. `grep -rn "check-overlap" frontend/src frontend/e2e` returns zero hits; no `post('/shifts`, `put('/shifts`, or `delete('/shifts` exists in the repo. frontend/src/router/index.ts has no shift route, and the admin nav group (frontend/src/App.vue:131-141) lists settings/users/employees/clients/defect-types/client-config/part-opportunities/floating-pool/workflow-config/database/variance-report — no Shifts entry. The capacity-planning workbook has no shifts worksheet either (grep 'shift' in frontend/src/services/api/capacityPlanning.ts and stores/capacity/useWorkbookStore.ts returns nothing).

**User impact:** Shifts are core master data: every production, downtime, attendance, quality and hold entry is stamped with a shift, and shift dropdowns appear on every data-entry grid. An admin onboarding a new client, or a plant changing from 2 shifts to 3, or correcting a shift's start/end time, cannot do any of it through the product. Shifts exist only because the seeder wrote them; in a real deployment the shift table would be empty and unfillable. The overlap-validation logic the backend authors wrote (soft warnings on create/update) is likewise never surfaced.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. Endpoint path + last segment. `grep -rn "'/shifts|\"/shifts|`/shifts|/api/shifts|shifts/" frontend/src frontend/e2e` returns exactly 4 non-test hits, all GET reads:
   - frontend/src/services/api/reference.ts:26-32 `getShifts()` -> `api.get('/shifts/')` (cached reference data, 30-min TTL)
   - frontend/src/composables/useShiftForms.ts:386 `api.get('/shifts')` (populates a dropdown)
   - frontend/src/services/api/csvExport.ts:36-37 `exportShifts()` -> `blobGet('/export/shifts')` (read-only CSV export)
   - frontend/e2e/attendance-labor-allocation.spec.ts:105 `fetch('/api/shifts')` (test setup, GET)
   Zero `api.post('/shifts`, `api.put('/shifts`, `api.delete('/shifts` anywhere.

2. Overlap check. `grep -rni "check-overlap|checkOverlap|overlap" frontend/src` -> 6 hits, ALL unrelated: CSS comments in App.vue:336 and QuickActionsFAB.vue:142, "overlapping refresh" test comment in usePivotView.spec.ts:131, and three "no Enterprise overlap" metadata strings in agGridExcelBehaviors.ts:65/71/95. The soft-warning overlap API is never called.

3. Verb/helper synonyms. `grep -rniE "createShift|updateShift|deleteShift|saveShift|editShift|newShift|shiftForm|ShiftCreate|ShiftUpdate" frontend/src` -> only useShiftForms.ts:75 (the read-only dropdown composable, whose writes at lines 245/271/299/337 are `api.createProductionEntry` / `createDowntimeEntry` / `createQualityEntry` — production data, not SHIFT rows) and an i18n string "createShiftRecord" (en.json:2488) meaning "create a production record for this date".

4. Router. frontend/src/router/index.ts — I enumerated every `path:` (lines 25-250). The only shift-adjacent route is line 132 `/my-shift` -> views/MyShiftDashboard.vue, an operator KPI/work-order dashboard (its data comes from services/api/myShift.ts: GET /my-shift/summary, /stats, /activity). There is no /shifts, /admin/shifts, or any parameterized master-data route.

5. Views/nav. `ls frontend/src/views | grep -i shift` -> only MyShiftDashboard.vue. `grep -rni shift frontend/src/views/admin/*.vue frontend/src/views/admin/components/*.vue` -> one hit, FloatingPoolManagement.vue:93 `scenario.units_per_shift` (a display field). The admin nav group App.vue:127-142 lists settings/users/employees/clients/defect-types/client-config/part-opportunities/floating-pool/workflow-config/database/variance-report — no Shifts item. An orphan i18n label `navigation.shifts: "Shifts"` exists at frontend/src/i18n/locales/en.json:128 but `grep -rn "navigation.shifts" frontend/src` returns zero references — a label for a menu entry that was never built.

6. Generic escape hatches ruled out. /admin/database (views/admin/DatabaseConfigView.vue) is entirely read-only — it renders provider name + connection info and an alert "schema managed by migrations"; its store only calls fetchStatus()/fetchProviders(). No generic table editor exists. The CSV upload dialogs (CSVUploadDialogAttendance/Downtime/Quality) consume `shift_id` as a foreign key on transactional rows; backend/endpoints/csv_upload.py has no SHIFT-master importer (its only shift-named importer is `create_shift_coverage` / ShiftCoverageCreate, a different table that itself requires an existing `shift_id`). The capacity workbook's `shifts_available` (stores/capacity/defaults.ts:10,173; composables/useCalendarGridData.ts:125-146) is an integer count per calendar day, not a SHIFT row. simulationV2's `shifts_enabled`/`shift1_hours` (services/api/simulationV2.ts:22-24) is scenario input, not master data.

AGGRAVATING FINDING (beyond the original claim): frontend/src/composables/useOnboarding.ts:32-38 defines the FIRST onboarding checklist step as `{ key: 'shifts_configured', i18nKey: 'onboarding.steps.shifts', icon: 'mdi-clock-outline', route: '/admin/settings' }`. The backend really computes this step (backend/tests/test_routes/test_onboarding_routes.py:186-193 asserts it flips True when SHIFT rows exist). So a new admin is explicitly told to configure shifts and is navigated to /admin/settings — but views/admin/AdminSettings.vue contains no shift UI whatsoever (its cards are General Settings: companyName/timezone/dateFormat/language at lines 14-55; KPI targets at ~292; Data Management: retention/backup at 200-225). The checklist item is therefore permanently un-completable through the product: the only way `shifts_configured` becomes true is the seeder (backend/seed/writers_master.py:142-145) or direct DB access.

IMPACT: supervisor/admin-gated CRUD (get_current_active_supervisor on POST/PUT/DELETE in backend/routes/shifts.py:66-190) plus deliberate soft-validation UX (create/update return `warnings` from format_overlap_warnings, and a dedicated pre-validation endpoint POST /check-overlap) is fully built and fully unreachable. Every production, downtime, attendance, quality and coverage row is stamped with shift_id, and shift dropdowns appear on ProductionEntryGrid.vue:68 and AttendanceEntryGrid.vue:26 — those dropdowns are empty and unfillable on any non-seeded deployment.

</details>

### PRODUCT master data has no write path AT ALL — a different and worse class than the rest of this document

**Slice:** masters-admin

**Status:** NEW, found 2026-09-04 while fixing the shift onboarding step. Not a
"backend can, UI cannot" gap — here NEITHER can, so it does not belong to this
document's main class and cannot be closed by frontend work alone.

**What exists:** reads only. `backend/routes/reference.py:28` GET /products
(ProductListEntry) and `backend/routes/export.py:486` GET /export/products.
`grep -rn "Product(" backend/routes backend/endpoints` finds no constructor —
there is no POST/PUT/DELETE, no CSV importer, and no products router registered
in `backend/bootstrap/routers.py`. PRODUCT rows come from the seeder or from
direct DB access, full stop.

**Why it matters:** `frontend/src/composables/useOnboarding.ts` makes
`products_added` the SECOND onboarding step, and `backend/routes/onboarding.py:86`
really computes it (`db.query(Product).filter(...).count() > 0`). So, exactly
like `shifts_configured` before it was fixed, a new admin is told to add
products and the product offers no way to do it — except that for shifts the
backend capability existed and only the screen was missing, whereas here the
capability itself is absent. The step also pointed (and still points) at
/admin/settings, which has no product UI.

**Not fixed here, deliberately.** Closing it means designing and building
PRODUCT CRUD on the backend first — schemas, CRUD layer, role-guarded routes,
tenancy — which is a product decision, not a UI wiring fix. Flagged for that
decision rather than silently scaffolded.

### Operational production line CRUD — create, update, delete lines in the PRODUCTION_LINE table

**Slice:** masters-admin

**Backend:** backend/routes/production_lines.py:106 POST /api/production-lines/, :269 PUT /api/production-lines/{line_id}, :288 DELETE /api/production-lines/{line_id}. Backed by backend/crud/production_line.py:43 create_production_line, :178 update_production_line, :205 deactivate_production_line and backend/schemas/production_line.py. ORM backend/orm/production_line.py:29 __tablename__ = "PRODUCTION_LINE" — a DIFFERENT table from backend/orm/capacity/production_lines.py:29 "capacity_production_lines", which is the one the Capacity Planning screen edits. Seeded at backend/seed/writers_master.py:125-128.

**Why unreachable:** frontend/src/services/api/productionLines.ts is the whole client surface and exports exactly two reads: `getProductionLines` (GET /production-lines/) and `getProductionLineTree` (GET /production-lines/tree). No POST/PUT/DELETE to /production-lines exists anywhere in frontend/src. No router entry in frontend/src/router/index.ts and no nav item in frontend/src/App.vue:131-141. The Capacity Planning 'Production Lines' tab (frontend/src/views/CapacityPlanning/components/grids/ProductionLinesGrid.vue) writes to a different resource — frontend/src/services/api/capacityPlanning.ts:79/86/93 POST/PUT/DELETE /capacity/lines — so it does not cover this table.

**User impact:** PRODUCTION_LINE rows drive the line selector on the Production Entry, Downtime Entry and Attendance Entry grids (frontend/src/components/common/LineSelector.vue, used by all three) and the KPI Dashboard line filter (frontend/src/views/KPIDashboard.vue:101). A user cannot add a line, rename one, change its capacity/max-operators, or retire a decommissioned one. Every line the operators pick from must have been inserted by the seeder or by hand in SQL. The Capacity Planning line grid looks like it fills this need but silently edits a parallel table, which makes the gap worse — it is invisible.

<details><summary>verification</summary>

SEARCHES PERFORMED AND RESULTS

1) Endpoint path. `grep -rn "production-lines" frontend/ --exclude-dir=node_modules --exclude-dir=dist` returns only 3 real source hits (plus 2 stale coverage-HTML echoes):
   - frontend/src/services/api/productionLines.ts:8  `api.get('/production-lines/', { params: { client_id: clientId } })`
   - frontend/src/services/api/productionLines.ts:12 `api.get('/production-lines/tree', ...)`
   - frontend/src/services/api/dataEntry.ts:26 — a code COMMENT referencing the 307-redirect rationale, not a call.
   The file's `export default { getProductionLines, getProductionLineTree }` is the complete client surface. No e2e/Playwright test references the path either.

2) Sub-capabilities of the same router. backend/routes/production_lines.py also exposes POST /sync-capacity (:160), GET /unlinked (:183), POST /{line_id}/link-capacity (:202), DELETE /{line_id}/link-capacity (:234). `grep -rn "sync-capacity|link-capacity|syncCapacity|linkCapacity|unlinked" frontend/src` → ZERO hits. So not even the capacity-bridge operations are reachable.

3) Symbol/synonym sweep. `grep -rln "production-lines|productionLines|production_lines|ProductionLine|productionLine" frontend/src` → 26 files. Every write-capable one resolves to the capacity resource (capacityPlanningStore.ts, stores/capacity/*, views/CapacityPlanning/**, services/api/capacityPlanning.ts). The read-only ones are useProductionLines.ts, LineSelector.vue, ProductionEntryGrid.vue, DowntimeEntryGrid.vue, AttendanceEntryGrid.vue, KPIDashboard.vue.

4) Router. frontend/src/router/index.ts read verbatim (lines 25-245): 38 paths. The 13 /admin/* routes are settings, users, employees, clients, defect-types, client-config, part-opportunities, floating-pool, workflow-config, workflow-designer/:clientId?, database, variance-report — plus login/home/kpi-*/data-entry-*/work-orders/my-shift/alerts/simulation/simulation-v2/plan-vs-actual/capacity-planning/help/:pathMatch. NO production-lines route of any kind.

5) Nav. frontend/src/App.vue:127-142 (admin v-list-group) enumerates exactly the same twelve admin items. No "Lines"/"Production Lines" nav entry anywhere in the drawer. `grep -rn "line" frontend/src/views/admin/*.vue` (filtering CSS/false positives) returns only `// eslint-disable-next-line` comments and one `mdi-chart-line` icon — no line-management UI in any admin view.

6) Alternate write paths ruled out. The 11 CSV importers (backend/endpoints/csv_upload.py:90,164,253,325,409,471,542,620,682,743,797) cover downtime, holds, attendance, coverage, quality, defects, work-orders, jobs, clients, employees, floating-pool — there is no production-line importer. frontend/src/views/admin/DatabaseConfigView.vue matches zero `api.` calls and zero `@/services` imports, so it is not a generic table editor. Grepping every dynamic-path write in frontend/src/services + frontend/src/stores (`api.post(`/api.put(`/api.delete(` with template literals) surfaces production/, work-orders/, workflow/, clients/, users/, kpi-thresholds/, defect-types/, simulation scenarios — nothing line-related except /capacity/lines.

PROOF THE CAPACITY TAB EDITS A DIFFERENT TABLE (the claim's key assertion, independently verified end-to-end):
   frontend/src/services/api/capacityPlanning.ts:79 POST '/capacity/lines', :86 PUT `/capacity/lines/${lineId}`, :93 DELETE `/capacity/lines/${lineId}`
   -> backend/routes/capacity/lines.py:49 create_production_line, :91 update_production_line, :110 delete_production_line
   -> backend/routes/capacity/lines.py:16 `from backend.crud.capacity import production_lines`
   -> backend/crud/capacity/production_lines.py:15 `from backend.orm.capacity.production_lines import CapacityProductionLine`; :53 `line = CapacityProductionLine(...)` (the ONLY model this module touches — all 38 symbol hits in the file are CapacityProductionLine)
   -> backend/orm/capacity/production_lines.py:30 `__tablename__ = "capacity_production_lines"`
Versus the unreachable capability:
   backend/routes/production_lines.py:38 `APIRouter(prefix="/api/production-lines")`, registered at backend/bootstrap/routers.py:55 (import) and :113 (include_router); POST "/" at :106, PUT "/{line_id}" at :269, DELETE "/{line_id}" at :288 (204)
   -> backend/orm/production_line.py:29 `__tablename__ = "PRODUCTION_LINE"`
The ORM docstring at backend/orm/production_line.py:1-4 says it explicitly: "Distinct from CapacityProductionLine which is used for capacity planning." The two are not even shape-compatible: PRODUCTION_LINE has line_type with a CHECK constraint (DEDICATED/SHARED/SECTION), a self-referential parent_line_id FK, and — decisively — capacity_line_id, a FK to `capacity_production_lines.id` (backend/orm/production_line.py:50-55). A table holding a foreign key to the other table cannot be the same table.

UI COPY CORROBORATES THE SPLIT: frontend/src/i18n/locales/en.json:3689 `capacityPlanningGrids.productionLines` carries addLine/capacityUnitsPerHr/efficiency/maxOperators (the capacity grid's editor strings), while en.json:3774 `productionLines` carries only label/allLines/selectLine/noLines/filterByLine — pure read-only selector vocabulary with no create/edit/delete strings anywhere.

IMPACT VERIFIED: frontend/src/components/common/LineSelector.vue:25 imports useProductionLines; frontend/src/composables/useProductionLines.ts:9 imports getProductionLines from '@/services/api/productionLines', i.e. the PRODUCTION_LINE GET. LineSelector is consumed by ProductionEntryGrid.vue, DowntimeEntryGrid.vue, AttendanceEntryGrid.vue and KPIDashboard.vue:98-103 (the "Filter by Line" control). So the list operators select from is read-only from the UI; rows originate only from backend/seed/writers_master.py:125-128 or manual SQL. This is not a health/metrics endpoint, not cron- or script-owned by design, and is not covered by any other UI surface.

</details>

### Employee lifecycle writes — create employee, delete employee, assign employee to a client, add/remove employee from the floating pool

**Slice:** masters-admin

**Backend:** backend/routes/employees.py:38 POST /api/employees (create_employee_endpoint, EmployeeCreate), :115 DELETE /api/employees/{employee_id}, :128 POST /api/employees/{employee_id}/floating-pool/assign, :139 POST /api/employees/{employee_id}/floating-pool/remove, :150 POST /api/employees/{employee_id}/assign-client (EmployeeAssignmentRequest). Backed by backend/crud/employee/ and backend/schemas/employee.py. Also unused: POST /api/employees/upload/csv (backend/endpoints/csv_upload.py:743).

**Why unreachable:** The Employees admin view frontend/src/views/admin/AdminEmployees.vue does exactly one read — line 81 `api.get('/employees')` — and its only write is a single-field inline edit: frontend/src/composables/useEmployeeAdminGrid.ts:94 `api.put('/employees/${row.employee_id}', { labor_class: value })`. The view template (AdminEmployees.vue:1-46) contains only a search field, a Refresh button and the grid — no Add, no Delete, no assign-client control. `grep -rn "post('/employees\|delete('/employees\|assign-client" frontend/src frontend/e2e` returns zero hits, as does a grep for '/employees/upload/csv'.

**User impact:** New hires cannot be entered into the system and departed employees cannot be removed. Moving an employee between clients — the multi-tenant staffing action the backend explicitly models — is impossible from the UI. Attendance, coverage and absenteeism KPIs all key off the employee roster, so the roster silently ossifies at whatever the seeder or a DBA put there. The screen reads as a full employee admin surface but is effectively a read-only roster with one editable column.

<details><summary>verification</summary>

SEARCHES RUN (repo /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1) Endpoint paths + synonyms across frontend/src and frontend/e2e: grep -rnE "'/employees|\"/employees|/api/employees|floating-pool|assign-client|employees/upload". Only /employees hits are reads — frontend/src/views/admin/AdminEmployees.vue:81 api.get('/employees'), frontend/src/composables/useAttendanceGridData.ts:546 api.get('/employees', {...}), frontend/e2e/attendance-labor-allocation.spec.ts:103 fetch('/api/employees?limit=100') — plus the one write frontend/src/composables/useEmployeeAdminGrid.ts:94 api.put(`/employees/${row.employee_id}`, { labor_class: value }). Zero hits for post('/employees', delete('/employees', assign-client, or /employees/upload/csv.

2) Exhaustive write enumeration: grep -rn "api\.(post|put|delete|patch)(" frontend/src --include=*.ts --include=*.vue (tests excluded), ~120 call sites reviewed. The ONLY employee write in the entire application is the labor_class PUT above.

3) The floating-pool synonym is a DIFFERENT capability, not coverage. frontend/src/composables/useFloatingPoolGridData.ts:156 api.post('/floating-pool/assign', ...) and :180 api.post('/floating-pool/unassign', { pool_id }) hit backend/routes/floating_pool.py (prefix /api/floating-pool), which assigns an existing FLOATING_POOL row to a client. They never touch Employee.is_floating_pool. Grep "is_floating_pool" over backend shows the flag is written at exactly two places — backend/crud/employee/floating_pool.py:68 (= 1) and :104 (= 0) — reachable only from backend/routes/employees.py:128 and :139. This is a blocking prerequisite, not a nicety: backend/crud/floating_pool/core.py:44 and backend/crud/floating_pool/assignments.py:63 both reject an employee whose is_floating_pool is falsy, so pool entries can only ever exist for employees flagged out-of-band (seeder/DBA). Read frontend/src/views/admin/FloatingPoolManagement.vue in full: summary cards, insights panel, 2 filters, Refresh, grid — no add-to-pool control; nothing in the frontend posts POST /api/floating-pool to create an entry either.

4) Route/nav: the screen IS reachable — frontend/src/router/index.ts:208-212 path '/admin/employees' name 'admin-employees', linked from frontend/src/App.vue:134 <v-list-item ... to="/admin/employees" />. The gap is the absent writes, not an absent route.

5) Component sweep: find frontend/src -iname "*mploy*" returns exactly three files — views/admin/AdminEmployees.vue, composables/useEmployeeAdminGrid.ts, composables/__tests__/useEmployeeAdminGrid.spec.ts. No employee form/dialog component exists.

6) Independent i18n oracle: admin.employees in frontend/src/i18n/locales/en.json contains only {title, employeeId, employeeCode, employeeName, department, updateSuccess, errors:{loadFailed, updateFailed}} — no add/create/delete/assign/upload key, versus admin.defectTypes.uploadCsv which does exist for the surface that has an upload button.

7) Grid has no hidden action control: useEmployeeAdminGrid.ts columnDefs = employee_id/employee_code/employee_name/department (all editable:false) + labor_class (editable:true, agSelectCellEditor). No cellRenderer, no action column, no delete. onCellValueChanged early-returns unless field === 'labor_class'.

8) No implicit-creation escape hatch: grep -rn "create_employee" backend (tests/seed excluded) shows the only production callers are backend/routes/employees.py:47 and backend/endpoints/csv_upload.py:773 (create_fn=lambda db_, e, u: create_employee(...)). Attendance/production ingestion does not auto-create employees. The six CSV dialogs that DO exist post to /quality/upload/csv, /attendance/upload/csv, /downtime/upload/csv, /holds/upload/csv, /production/upload/csv and /defect-types/upload/{clientId} — none to /employees/upload/csv.

CONCLUSION: unable to refute. Severity nuance for the report: assign-client has a partial substitute (the floating-pool grid can move an employee between clients) but only for employees already flagged as floaters, and that flag is itself unreachable; create and delete have no substitute at all.

</details>

### Hold status and hold reason catalogs — per-client customizable CRUD plus a seed-defaults action

**Slice:** masters-admin

**Backend:** backend/routes/hold_catalogs.py:46 GET /api/hold-catalogs/statuses, :62 POST, :85 PUT /statuses/{catalog_id}, :104 DELETE /statuses/{catalog_id}, :126 GET /reasons, :142 POST /reasons, :165 PUT /reasons/{catalog_id}, :184 DELETE /reasons/{catalog_id}, :206 POST /seed-defaults. Backed by backend/crud/hold_catalog.py (create/list/update/deactivate for both entities, plus :124 validate_hold_status_for_client and :214 validate_hold_reason_for_client which the hold-entry write path enforces) and backend/schemas/hold_catalog.py. ORM backend/orm/hold_status_catalog.py and backend/orm/hold_reason_catalog.py; both tables are seeded (backend/seed/coverage.py:23-24).

**Why unreachable:** `grep -rn "hold-catalogs" frontend/src frontend/e2e` returns zero hits — no call, no route, no nav item. Instead the hold entry UI hardcodes both vocabularies client-side: frontend/src/composables/useHoldGridData.ts:78-87 `export const HOLD_REASON_CODES = ['QUALITY_ISSUE', ... 'OTHER']` (comment at :77 admits it 'mirrors backend/schemas/hold.py:56-71'), and :104-110 `holdStatusOptions` is a hardcoded five-entry list.

**User impact:** Two-sided failure. A client cannot define its own hold reasons or statuses — the whole point of a per-client catalog — and the seed-defaults bootstrap that would populate a new client's catalog has no button. Worse, if a catalog row were ever created out-of-band it would not appear in the hold dropdowns, because the frontend reads a frozen array rather than the catalog; and because the backend validates submitted codes against the catalog, the hardcoded list can drift out of sync with what the server will accept, producing rejected hold entries with no way for a user to fix the vocabulary.

<details><summary>verification</summary>

SEARCHES RUN (all across frontend/src, frontend/e2e, and the full frontend/ tree):

1. Endpoint path + variants — `grep -rni "hold-catalogs|hold_catalogs|holdCatalog|hold-catalog|HoldCatalog|holdStatusCatalog|holdReasonCatalog|seed-defaults|seedDefaults" frontend/src frontend/e2e` -> ZERO hits.
2. ORM/table names — `grep -rni "hold_status_catalog|hold_reason_catalog" frontend/` -> zero hits in source.
3. Last path segments — `grep -rn "'/.*reasons|'/.*statuses|`/.*reasons|`/.*statuses" frontend/src` -> only frontend/src/services/api/reference.ts:39 `api.get('/downtime-reasons')` (the DOWNTIME catalog, a different feature). No hold analog.
4. Generic synonym — `grep -rni "catalog" frontend/src frontend/e2e` -> hits are only for scenario_type, defect-types, part-opportunities, work-order priority, downtime reasons, and the assumptions catalog. No hold catalog consumer.
5. Dynamic path construction — `grep -rn "api\.(get|post|put|delete)\(\s*`/\$\{" frontend/src` -> ZERO hits, so the path cannot be assembled at runtime from variables.
6. Admin surfaces — `grep -rni "hold" frontend/src/views/admin/ frontend/src/components/admin` -> only "threshold"/"staleThreshold" substring noise. No admin view touches holds. frontend/src/views/admin/ClientConfigView.vue is numeric KPI targets only (efficiency/performance/availability/oee/fpy/rty), no catalog UI.
7. Router — frontend/src/router/index.ts has 38 paths; the admin block (lines 166-232) is settings, users, clients, defect-types, part-opportunities, client-config, floating-pool, employees, workflow-config, workflow-designer, database, variance-report. NO hold-catalog route.
8. e2e — frontend/e2e/ contains admin-defect-types.spec.ts and admin-part-opportunities.spec.ts but no hold-catalog spec; hold-resume.spec.ts covers only hold ENTRY.

BACKEND IS REAL AND REGISTERED:
- backend/routes/hold_catalogs.py:38 `APIRouter(prefix="/api/hold-catalogs")`, with GET/POST/PUT/DELETE on /statuses and /reasons plus :205 `POST /seed-defaults` (guarded by get_current_active_supervisor — a human role, not a cron/script identity).
- Registered in production: backend/bootstrap/routers.py:51 imports it and :128 `app.include_router(hold_catalogs_router)`.
- Enforcement confirmed live on the write path: backend/routes/holds.py:58 and :441 call validate_hold_reason_for_client before accepting a hold create/update, so the server really does gate submissions against the catalog.

THE HARDCODED SUBSTITUTE (confirms the UI reads a frozen array, not the catalog):
- frontend/src/composables/useHoldGridData.ts:76 comment "Canonical HOLD_REASON_CATALOG codes (mirrors backend/schemas/hold.py:56-71)" then :78-87 a literal 8-entry `HOLD_REASON_CODES` array.
- Same file :104-110 `holdStatusOptions` is a hardcoded 5-entry computed list.

AGGRAVATING FINDING (not in the original claim): the shipped Help Center promises this screen. frontend/src/help/index.ts:13 glob-loads docs/user-guide/*.md into the /help route (frontend/src/router/index.ts:238-240), and docs/user-guide/09-admin.md:71 instructs admins to configure "3. **Hold catalogs** — categories of holds (Material, Quality, etc.)" as a per-client setup step, while 09-admin.md:69 lists "hold catalog" under Client Config. docs/user-guide/03-data-entry.md:265 tells users "Each client maintains a `hold catalog` (per `/api/hold-catalogs`)". A user following the official in-app guide will hunt for a Hold Catalogs admin screen that does not exist anywhere in the router.

STRUCTURAL COMPARISON: this codebase already has the exact pattern for sibling per-client catalogs — Defect Types (router:184, AdminDefectTypes.vue, e2e spec) and Part Opportunities (router:190, PartOpportunities.vue, e2e spec). Hold catalogs are the one catalog with full backend CRUD and no screen, so this is an omission from an established pattern, not an intentionally headless design.

The only occurrence of the string "/api/hold-catalogs" anywhere under frontend/ is inside the stale build artifact frontend/dist/assets/HelpCenter-DHkIRkVj.js:683 — which is just the compiled user-guide prose above, i.e. documentation text, not a call site or a control.

</details>

### Part-opportunities CSV upload control is bound to an endpoint that does not exist, while the real bulk-import endpoint is never called

**Slice:** masters-admin

**Backend:** The only bulk ingestion route is backend/routes/part_opportunities.py:119 `@router.post("/bulk-import")` → POST /api/part-opportunities/bulk-import, which takes a JSON BulkImportRequest (backend/schemas/part_opportunities.py) and is backed by bulk_import_opportunities in backend/crud/part_opportunities.py. The route inventory snapshot backend/tests/test_bootstrap/openapi_surface.json contains `POST /api/part-opportunities/bulk-import` and contains NO `/api/part-opportunities/upload` of any kind (backend/endpoints/csv_upload.py registers upload/csv routes for downtime, holds, attendance, coverage, quality, defects, work-orders, jobs, clients, employees and floating-pool — not part opportunities).

**Why unreachable:** frontend/src/views/admin/PartOpportunities.vue:51-54 renders a visible 'Upload CSV' button (`@click="openUploadDialog"`) and :129-165 a full upload dialog with a file input and a submit button wired to `uploadCSV`. That handler, frontend/src/composables/usePartOpportunitiesForms.ts:177, posts multipart form-data to `'/part-opportunities/upload'` — a path with no server route. `grep -rn "bulk-import" frontend/src frontend/e2e` returns zero hits.

**User impact:** An advertised, fully built import workflow is dead on arrival: the user picks a file, clicks Upload, and gets a 404 surfaced through the generic `t('csv.error')` toast with no explanation. Bulk-loading a part-opportunity catalog — the realistic way to populate hundreds of part numbers — is impossible, forcing row-by-row grid entry. The working backend importer sits behind a different path and shape (JSON records, not a file) that nothing in the UI speaks.

<details><summary>verification</summary>

SEARCHES PERFORMED (frontend/src + frontend/e2e):
1. grep -rn "part-opportunities|part_opportunities|partOpportunit|PartOpportunit" -> all hits are singular CRUD: usePartOpportunitiesGridData.ts:146 api.post('/part-opportunities'), :166 api.put('/part-opportunities/{id}'), usePartOpportunitiesForms.ts:114 put, :119 post, :142 delete, :177 api.post('/part-opportunities/upload', formDataUpload). Plus router/index.ts:190 and App.vue:138 (nav link).
2. grep -rn "bulk-import|bulkImport|bulk_import" frontend/src frontend/e2e -> ZERO hits. The BulkImportRequest shape (JSON `opportunities` array) is spoken by nothing in the UI.
3. Synonym/segment sweep on the backend: grep -rn '"/upload|/upload"' backend --include=*.py -> only backend/routes/defect_type_catalog.py:136 ("/upload/{client_id}") and backend/routes/production.py:188 ("/upload/csv"). backend/endpoints/csv_upload.py registers 11 upload routes (lines 90,164,253,325,409,471,542,620,682,743,797) for downtime/holds/attendance/coverage/quality/defects/work-orders/jobs/clients/employees/floating-pool -- none for part opportunities.

RUNTIME PROOF (not just the snapshot):
backend/.venv/bin/python -c "from backend.main import app; s=app.openapi(); ..." ->
  total paths: 362
  PART: ['/api/part-opportunities', '/api/part-opportunities/category/{category}', '/api/part-opportunities/{part_number}', '/api/part-opportunities/bulk-import']
  paths matching part-opportunit AND upload: []
Live probe via fastapi TestClient:
  POST /api/part-opportunities/upload (multipart) -> 405 {"detail":"Method Not Allowed"}
  (405 not 404 because the path matches the /{part_number} template, which registers only GET/PUT/DELETE.)

PATH-PLUMBING RULED OUT: frontend/src/services/api/client.ts:5 baseURL='/api/v1'; backend/bootstrap/app_config.py:53-57 APIVersionMiddleware strips /v1, so /api/v1/part-opportunities/upload -> /api/part-opportunities/upload. vite.config.ts:28 proxies /api with no rewrite. Sibling calls in the same composable (POST /part-opportunities) work, so the base is correct -- only /upload is missing.

BACKEND CAPABILITY IS REAL: backend/routes/part_opportunities.py:119 @router.post("/bulk-import") -> bulk_import_opportunities, schemas BulkImportRequest/BulkImportResponse in backend/schemas/part_opportunities.py, snapshot backend/tests/test_bootstrap/openapi_surface.json:1609.

DEAD CONTROL IS USER-VISIBLE AND REACHABLE: router/index.ts:190-193 (requiresAuth+requiresAdmin), nav link App.vue:138, button frontend/src/views/admin/PartOpportunities.vue:48-54 (@click="openUploadDialog"), dialog :129-168 with v-file-input and submit :158-166 (@click="uploadCSV"). Handler frontend/src/composables/usePartOpportunitiesForms.ts:165-188.

NOT EXEMPT: not health/internal, not cron/admin-script (it is a rendered button), not covered elsewhere (no other caller of bulk-import; the only alternative is row-by-row create).

CORRECTION TO THE AUDITOR'S IMPACT WORDING: the toast shows the raw "Method Not Allowed" string, not t('csv.error') -- usePartOpportunitiesForms.ts:184-186 prefers ax.response.data.detail over the i18n fallback. The failure is 405, not 404. Neither changes the verdict.

E2E DOES NOT COVER IT: frontend/e2e/admin-part-opportunities.spec.ts only asserts the Upload/Template buttons are visible (and even that with a permissive `uploadVisible || dlVisible`); it never opens the dialog or submits, so the dead path is green-while-broken.

</details>

### Calculation Assumption Registry — full write lifecycle (propose, edit, approve, retire) plus per-assumption history, dependency map, and effective-set lookup

**Slice:** kpi-analytics

**Backend:** backend/routes/calculation_assumptions.py:41 mounts prefix "/api/assumptions" (registered in backend/bootstrap/routers.py). Writes: POST "" propose_assumption (line 214, get_current_active_supervisor), PATCH "/{assumption_id}" update_proposal (line 233), POST "/{assumption_id}/approve" (line 256, get_current_planner), POST "/{assumption_id}/retire" (line 269). Reads with no UI: GET "" list_assumptions (line 168), GET "/catalog" (line 91), GET "/dependencies" (line 106), GET "/effective" (line 139), GET "/{assumption_id}" (line 189), GET "/{assumption_id}/history" (line 199). Backed by backend/services/assumption_service.py (AssumptionService.propose/update_proposal/approve/retire) and backend/schemas assumption contracts (AssumptionProposalCreate, AssumptionProposalUpdate, AssumptionApproveRequest, AssumptionRetireRequest).

**Why unreachable:** frontend/src/services/api/calculationAssumptions.ts defines exactly three functions — getCatalog (line 61), getVarianceReport (line 63), listAssumptions (line 68). There is NO client function for POST /assumptions, PATCH /assumptions/{id}, /approve, /retire, /{id}/history, /dependencies, or /effective anywhere in frontend/src. The only consumer is frontend/src/views/admin/AssumptionVarianceReport.vue:176, which calls getVarianceReport only; getCatalog and listAssumptions have zero callers outside their own module. The router (frontend/src/router/index.ts) exposes one assumptions screen, /admin/variance-report, and App.vue:142 links only to that read-only report.

**User impact:** The site_adjusted half of the dual-view architecture is driven entirely by approved assumptions, and there is no way for any user — including an admin — to create, edit, approve, or retire one from the app. The variance report shows deviations and staleness flags but offers no action to fix them; the only way to change an assumption is direct DB access or a hand-rolled API call. The append-only change log (who approved what and why) is also invisible, so the governance trail the backend carefully records can never be read by the people it exists for.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. Path literals — `grep -rn "'/assumptions|\"/assumptions|api/assumptions" frontend/src frontend/e2e` returns only 3 non-test hits, all in frontend/src/services/api/calculationAssumptions.ts: line 61 `/assumptions/catalog`, line 64 `/assumptions/variance`, line 73 `/assumptions`. No POST/PATCH literal exists anywhere; the file contains zero `api.post`/`api.patch` calls (verified by reading the whole file — it ends at line 73).

2. Word search — `grep -rn -i "assumption" frontend/src` (excluding __tests__) yields only: type/interface names in services/api/{calculationAssumptions,metricResults,dualViewCalc,simulationV2}.ts, display-only usage in components/dual_view/MetricInspector.vue:122-168 and DualViewKPIPanel.vue:30, an Excel sheet builder utils/excelExport.ts:237-337 (simulation assumption_log, unrelated ORM), i18n strings, views/admin/AssumptionVarianceReport.vue, and router/index.ts:234.

3. Verb search — `grep -rn -i "approve|retire|propose" frontend/src` (excl. tests): every hit belongs to the WORK-ORDER HOLD approval workflow (composables/useHoldGridForms.ts:404-433 → 'approve-hold'/'approve-resume'), QC flags (WorkOrderDetailDrawer.vue:226-232), a status classifier, or read-only display of `a.approved_by`/`a.approved_at` in MetricInspector.vue:164-168. Nothing calls an assumption approve/retire route.

4. Filename search — `find frontend/src -iname "*assumption*"` returns exactly three files: services/api/calculationAssumptions.ts, its spec, and views/admin/AssumptionVarianceReport.vue. There is no propose/edit/approve/manage view or component.

5. Dead-export check — `grep -rn "getCatalog|listAssumptions" frontend/src` outside the module hits ONLY services/__tests__/calculationAssumptions.spec.ts:21,43,51. Zero production callers, confirming the auditor's claim.

6. Router + nav — frontend/src/router/index.ts:231-236 defines the single route `/admin/variance-report` → views/admin/AssumptionVarianceReport.vue. frontend/src/App.vue:142 is the only nav link (`to="/admin/variance-report"`). No other assumptions route or menu entry exists.

7. The view itself — views/admin/AssumptionVarianceReport.vue imports only `getVarianceReport` (line ~147) and its `loadRows()` calls only that. The template is a v-data-table with 9 read-only columns and cell slots rendering chips/icons; there is no v-btn, dialog, form, or row-action anywhere in the template, so even an inert control does not exist.

8. Alternate write path — `grep -rln "CalculationAssumption" backend --include='*.py'` (excl. tests) hits only orm/calculation_assumption.py, orm/__init__.py, services/assumption_service.py, services/dual_view/{otd,oee,fpy}_service.py (consumers), schemas/metric_calculation_result.py, and routes/metric_results.py (read-only lineage). No other endpoint creates/updates assumption rows, so no other admin screen can be a substitute write surface. AdminSettings.vue writes client THRESHOLDS (`api.deleteClientThreshold`, line 442), a different resource.

9. Partial-coverage check (the strongest refutation candidate, and it fails) — MetricInspector.vue does show `assumptions_applied` with `approved_by`/`approved_at`. But it is fed by composables/useMetricLineage.ts:15,27 → services/api/metricResults.ts:67-68 `api.get('/metrics/results/{id}')`, i.e. backend/routes/metric_results.py, NOT any /api/assumptions endpoint. It shows which assumptions touched one metric value; it exposes no change log (/{id}/history), no dependency map, no effective set, and no write action.

BACKEND SIDE VERIFIED REAL: backend/bootstrap/routers.py:63 imports and :296 includes the router; backend/routes/calculation_assumptions.py:41 sets prefix "/api/assumptions"; the writes at lines 214 (POST "" propose, get_current_active_supervisor), 233 (PATCH "/{assumption_id}"), 256 (POST "/{id}/approve", get_current_planner), 269 (POST "/{id}/retire") each delegate to AssumptionService.propose/update_proposal/approve/retire with real Pydantic bodies, and the reads at 91 (/catalog), 106 (/dependencies), 168 (GET ""), 189 (/{id}), 199 (/{id}/history) are equally live. Not health/metrics, not cron, not admin-script: approve/retire are role-gated human governance actions whose whole purpose is a person deciding.

CONCLUSION: the gap is genuine. An admin can see that an assumption deviates from default and is stale, and cannot do anything about it from the app; the append-only change log is written by the backend and readable by no one.

</details>

### Advanced Analytics API — KPI trend analysis with moving averages/regression/anomaly detection, predictive forecasting, client-to-client benchmarking with percentile ranks, date-x-shift performance heatmap, and defect Pareto (80/20) analysis

**Slice:** kpi-analytics

**Backend:** backend/routes/analytics/__init__.py:23 mounts prefix "/api/analytics" and includes three sub-routers (registered as analytics_router in backend/bootstrap/routers.py). Endpoints: GET /api/analytics/trends (backend/routes/analytics/trends.py:34), GET /api/analytics/predictions (backend/routes/analytics/predictions.py:36), GET /api/analytics/comparisons (backend/routes/analytics/comparisons.py:43), GET /api/analytics/heatmap (comparisons.py:149), GET /api/analytics/pareto (comparisons.py:265). All are real implementations with response models (TrendAnalysisResponse, PredictionResponse, ComparisonResponse, HeatmapResponse, ParetoResponse), client-scope authorization, and helper math in backend/routes/analytics/_helpers.py.

**Why unreachable:** A repo-wide grep of frontend/src for the strings "/analytics", "'/analytics", and "/api/analytics" returns zero API calls — the only "analytics" hits are the unrelated /workflow/analytics/... calls in frontend/src/services/api/workflow.ts:64,67 and cosmetic label strings. There is no analytics service module in frontend/src/services/api/, no analytics store, no Analytics view in frontend/src/views/, no route in frontend/src/router/index.ts, and no nav entry in App.vue.

**User impact:** Five substantial analysis features — anomaly detection, cross-client benchmarking with percentile ranking, the shift-by-date heatmap, and Pareto defect prioritization — are completely invisible. Pareto and benchmarking in particular are the classic tools a plant manager reaches for to decide where to spend improvement effort; the platform computes them and shows none of them.

<details><summary>verification</summary>

SEARCHES RUN (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. `grep -rn "analytics" frontend/ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=coverage -il` — 14 files, ZERO of which touch /api/analytics:
   - frontend/src/services/api/workflow.ts:64,67 — `/workflow/analytics/{clientId}/average-times` and `/stage-durations` (a different backend router, backend/routes/workflow.py)
   - frontend/src/composables/useWorkflowConfigData.ts:3,4,192 — same workflow feature
   - frontend/src/views/admin/{WorkflowConfigView.vue,components/WorkflowAnalyticsCards.vue,components/WorkflowConfigDialogs.vue} — same workflow feature
   - frontend/src/components/DashboardOverview.vue:303 — the string `$t('navigation.analytics')` used purely as an `<h2>` section heading above DowntimeImpactWidget / BradfordFactorWidget / QualityByOperatorWidget / ReworkByOperationWidget; none of those four call /api/analytics
   - frontend/src/i18n/locales/{en,es}.json — label strings only
   - frontend/docs/*keyboard-shortcuts* — unrelated prose

2. Last-path-segment searches: `grep -rn "'/trends'\|\"/trends\"\|/comparisons\|/heatmap\|/pareto" frontend/ --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=coverage` — ZERO hits.

3. Synonym/filename searches: `find frontend/src -iname "AnalyticsDeepDive*" -o -iname "*Heatmap*" -o -iname "*Pareto*" -o -iname "*Benchmark*"` — ZERO files.

4. Hardcoded-URL escape hatch: `grep -rn "fetch(\s*['\`\"]/" frontend/src` and `grep -rn "'/api/\|\`/api/" frontend/src` — hits are only /api/holds, /api/qr, /api/production, /api/clients, /api/metrics. No /api/analytics. (Base URL is `/api/v1` per frontend/src/services/api/client.ts:5, so a call would read `api.get('/analytics/...')` — that string appears nowhere.)

5. Router: `grep -n "path:" frontend/src/router/index.ts` — 38 routes, none analytics-related (/login, /, /production-entry, /kpi-dashboard, /summaries, 8× /kpi/*, 4× /data-entry/*, /work-orders, /my-shift, /alerts, /simulation, /simulation-v2, /plan-vs-actual, /capacity-planning, 11× /admin/*).

6. Nav: frontend/src/App.vue lines 80–142 — full drawer read. Six groups (Planning, Data Entry, Monitoring, KPI Detail, Simulation, Admin). No Analytics entry. App.vue:125 is `navigation.simulation` → /simulation, not analytics.

7. frontend/src/services/api/ directory listing — 29 modules; no analytics.ts. No analytics store in frontend/src/stores/.

WHY THE NEAR-MISSES DO NOT COUNT:
- frontend/src/services/api/predictions.ts:29,32,34,37 calls `/predictions/*`, which is backend/routes/predictions.py (a separate 21KB router, `/api/predictions/benchmarks` at predictions.py:246 returns static *industry* benchmark constants via get_kpi_benchmarks()). That is not backend/routes/analytics/predictions.py:36 (exponential smoothing / trend extrapolation) and not analytics/comparisons.py:43 (client-to-client percentile ranking).
- frontend/src/components/widgets/ReworkByOperationWidget.vue:275 computes `paretoItems` client-side in JS from `/kpi/quality/rework-by-operation` (line 327) with a `/quality` fallback (line 377). That is rework-by-operation, not the defect-type Pareto at backend/routes/analytics/comparisons.py:265.

EXTRA FINDING — INERT CONTROL:
frontend/src/stores/dashboardStore.ts:59 registers a default dashboard widget `analytics_deep_dive` (order 4, visible), and :87 describes it as "Deep analytics view" (icon mdi-chart-areaspline, minRole poweruser). frontend/src/components/dashboard/WidgetGrid.vue:213-216 resolves it via `defineAsyncComponent(() => import('./widgets/AnalyticsDeepDive.vue').catch(() => ({ template: '...placeholder...' })))`. But `ls frontend/src/components/dashboard/` shows only __tests__/, DashboardCustomizer.vue, WidgetContainer.vue, WidgetGrid.vue, index.ts — there is no `widgets/` subdirectory and no AnalyticsDeepDive.vue. The import always rejects, so every poweruser sees a hardcoded icon-plus-label placeholder that fetches nothing. This is a visible, enabled-by-default UI control bound to a component that does not exist.

BACKEND IS REAL AND USER-FACING:
backend/routes/analytics/__init__.py:23 `APIRouter(prefix="/api/analytics", tags=["analytics"])`, including trends_router, predictions_router, comparisons_router; registered at backend/bootstrap/routers.py:231. 756 lines total across the package (trends.py 133, predictions.py 141, comparisons.py 369, _helpers.py 86). Five GET endpoints with response models: trends.py:34 (TrendAnalysisResponse), predictions.py:36 (PredictionResponse), comparisons.py:43 (ComparisonResponse), :149 (HeatmapResponse), :265 (ParetoResponse). Documented as product API at docs/API_DOCUMENTATION.md:883-893, docs/ARCHITECTURE.md:211, and a whole dedicated docs/ANALYTICS_API_DOCUMENTATION.md.

</details>

### Predictions dashboard widgets and the all-KPI prediction dashboard (GET /api/predictions/dashboard/all, /benchmarks, /health/{kpi_type})

**Slice:** kpi-analytics

**Backend:** backend/routes/predictions.py:60 mounts prefix "/api/predictions". GET /dashboard/all (line 362) returns predictions for all 10 KPIs plus an overall health score and priority actions; GET /benchmarks (line 245) returns industry benchmark values; GET /health/{kpi_type} (line 529) returns a per-KPI health assessment.

**Why unreachable:** frontend/src/stores/kpi.ts defines fetchAllPredictions (line 716), fetchBenchmarks (line 760), and fetchKPIHealth (line 772), and none of the three has a single caller in any view, component, or composable (grep across frontend/src, excluding __tests__, finds only their definitions). The intended surface is the dashboard widget system: frontend/src/stores/dashboardStore.ts:57 and :70 make 'predictions' a DEFAULT visible widget for poweruser and admin, and :59 makes 'analytics_deep_dive' a default for poweruser. frontend/src/components/dashboard/WidgetGrid.vue:208 and :213 resolve those keys to './widgets/Predictions.vue' and './widgets/AnalyticsDeepDive.vue' — but the directory frontend/src/components/dashboard/widgets/ does not exist, so both fall into the .catch() branch and render a bare icon-plus-label placeholder div. WidgetGrid.vue itself is imported by no view (grep for 'WidgetGrid' across frontend/src matches only its own file), and the customizer that lets users pick these widgets (frontend/src/views/KPIDashboard.vue:271) emits 'saved' into frontend/src/composables/useKPIDashboardActions.ts:39, whose entire body is a success snackbar.

**User impact:** Powerusers and admins are told by the dashboard customizer that they have 'Predictions — AI-powered forecasts' and 'Analytics — Deep analytics view' widgets on by default, can reorder and save them, and get a success toast — and nothing ever renders. The forecasting engine, benchmark table, and per-KPI health scoring the backend computes have no screen at all. This is the worst kind of gap: a control that looks like it works.

<details><summary>verification</summary>

SEARCHES RUN (frontend/, excluding node_modules, dist, coverage): literal paths 'dashboard/all', 'predictions/benchmarks', 'predictions/health'; service names getAllPredictions, getPredictionBenchmarks, getKPIHealth; store actions fetchAllPredictions, fetchBenchmarks, fetchKPIHealth; synonyms predict/forecast/benchmark/analytics across views/, components/, router/, composables/, i18n/locales/; plus 'WidgetGrid' and 'components/dashboard'.

BACKEND EXISTS: backend/bootstrap/routers.py:236 app.include_router(predictions_router); backend/routes/predictions.py:60 prefix="/api/predictions"; /benchmarks defined ~line 245, /dashboard/all ~line 362, /health/{kpi_type} ~line 529 — all DB-backed with verify_client_access.

ONLY DEFINITIONS + TESTS: frontend/src/services/api/predictions.ts:31-32 (getAllPredictions -> '/predictions/dashboard/all'), :34 (getPredictionBenchmarks -> '/predictions/benchmarks'), :36-37 (getKPIHealth -> '/predictions/health/${kpiType}'); frontend/src/stores/kpi.ts:716, :760, :772. Every other hit is in src/services/__tests__/predictions.spec.ts or src/stores/__tests__/kpi.spec.ts. Zero production callers.

WIDGET PATH IS DEAD: `ls frontend/src/components/dashboard/` yields only DashboardCustomizer.vue, WidgetContainer.vue, WidgetGrid.vue, index.ts — `frontend/src/components/dashboard/widgets/` does not exist, so WidgetGrid.vue:208 import('./widgets/Predictions.vue') and :213 import('./widgets/AnalyticsDeepDive.vue') always fall to .catch() and render an icon+label stub. grep 'WidgetGrid' across frontend/src (excl. tests) matches only frontend/src/components/dashboard/index.ts:3, a re-export — no view imports it. frontend/src/views/KPIDashboard.vue has ZERO matches for widget/Widget/dashboardStore; it imports only DashboardCustomizer (line 329, used line 271). frontend/src/composables/useKPIDashboardActions.ts:38-40 onCustomizerSaved body is solely showSnackbar(t('success.dashboardPreferencesSaved'), 'success').

DEFAULTS ADVERTISED TO USERS: frontend/src/stores/dashboardStore.ts:57 and :70 list widget_key 'predictions' as a default visible widget for poweruser and admin; :59 lists 'analytics_deep_dive' for poweruser; ALL_WIDGETS declares predictions = 'AI-powered forecasts' (minRole poweruser) and analytics_deep_dive = 'Deep analytics view'. DashboardCustomizer.vue:243/248/253 renders those entries from the store, so the picker shows capabilities that can never render.

NO ROUTE, NO NAV: frontend/src/router/index.ts lines 23-240 read in full — no predictions or analytics route. frontend/src/App.vue nav drawer, 33 `v-list-item ... to=` entries at lines 80-140 — no Predictions or Analytics entry.

PARTIAL MITIGATION (does not refute): backend/routes/predictions.py:236-237 embeds health_assessment and benchmark inside ComprehensivePredictionResponse for the reachable GET /api/predictions/{kpi_type}. frontend/src/views/kpi/Efficiency.vue:213-249 and frontend/src/views/kpi/Performance.vue:209-245 render predictionData.health_assessment (health_score, trend, current_vs_target, recommendations) behind a forecast toggle wired through useEfficiencyData.ts:117 / usePerformanceData.ts:113. That covers health scoring for 2 of 10 KPIs via a different endpoint. `grep -rn "benchmark" frontend/src/views frontend/src/composables` (excl. tests) returns NOTHING — the embedded benchmark field is never bound to a template — and no surface anywhere shows /dashboard/all's overall health score, improving/declining/stable counts, or priority actions.

</details>

### Defect detail capture (DEFECT_DETAIL) — per-defect type, category, count, severity, location, description. Full CRUD: POST/GET/PUT/DELETE /api/defects, GET /api/defects/by-quality-entry/{id}, GET /api/defects/summary/by-type, plus POST /api/defects/upload/csv.

**Slice:** operations

**Backend:** backend/routes/defect.py:34 (router prefix /api/defects), :37 POST create_defect, :49 GET list, :64 GET /{id}, :78 GET /by-quality-entry/{id}, :89 PUT, :107 DELETE, :120 GET /summary/by-type. Schemas at backend/schemas/defect_detail.py:17-60 (DefectDetailBase/Create/Update). CRUD at backend/crud/defect_detail.py. CSV import at backend/endpoints/csv_upload.py:471. Registered in backend/bootstrap/routers.py via defect_router.

**Why unreachable:** Zero calls to /defects anywhere in frontend/src — the only matches for the string are pivot labels (frontend/src/composables/pivotPresets.ts:91) and the unrelated read KPI api.get('/quality/kpi/defects-by-type') (frontend/src/services/api/kpi.ts:471). No Vue route, no view, no component. The quality entry surface only captures aggregates: backend/schemas/quality.py:9-45 QualityInspectionCreate has NO nested defect_details, and frontend/src/composables/useQualityGridData.ts:112-113 exposes only units_defective and total_defects_count. No CSVUploadDialogDefect component exists (frontend/src/components/ has only CSVUploadDialog{Attendance,Downtime,Hold,Production,Quality}.vue).

**User impact:** The UI READS DEFECT_DETAIL but can never WRITE it. backend/routes/quality/pareto.py:78-118 (GET /quality/kpi/defects-by-type) and identify_top_defects both query the DefectDetail table, and the Quality view charts that data — so the Pareto/root-cause analysis is permanently driven by seed rows only. Worse, the admin Defect Type Catalog screen (/admin/defect-types) lets a client configure industry-specific defect types that can never be attached to any real defect record. An inspector can record 'we found 12 defects' but never 'which defects', killing root-cause analysis, the platform's headline quality workflow.

<details><summary>verification</summary>

SEARCHES RUN (all across frontend/, node_modules excluded):
1. `grep -rn "'/defects\|\"/defects\|/api/defects\|\`/defects" frontend/` -> ZERO hits. No call to any /api/defects route exists in the frontend, including e2e specs.
2. `grep -rn "by-quality-entry\|summary/by-type\|defect_detail_id\|defect_category" frontend/` -> ZERO hits. None of the distinctive path segments or schema field names appear.
3. `grep -rni "defect_detail\|defectDetail\|defect-detail" frontend/src` -> only 5 hits, all non-functional: frontend/src/i18n/locales/en.json:1142 and es.json:1142 (a label string "Defect detail | Defect details"); frontend/src/services/api/structuredErrors.ts:58 `DEFECT_DETAIL: 'errors.entities.defectDetail'` (an entity-name-to-translation-key map for error rendering, not an API call); and frontend/src/composables/__tests__/useQualityGridData.spec.ts:252 which asserts the ABSENCE of the feature: `it('does NOT expose defect_type_id (separate defect_details table)')`.
4. `ls frontend/src/services/api/` -> 30 modules, none for defects. dataEntry.ts:31-34 exposes only createQualityEntry/getQualityEntries/updateQualityEntry/deleteQualityEntry against `/quality/`.
5. `grep -rn "upload/csv" frontend/src` -> exactly 5 endpoints: /quality/ (CSVUploadDialogQuality.vue:430), /attendance/ (:401), /downtime/ (:396), /holds/ (:393), /production/ (:417) + production.ts:18. No defect uploader. `ls frontend/src/components | grep -i csv` returns exactly those 5 dialog files, so POST /api/defects/upload/csv (backend/endpoints/csv_upload.py:471) has no UI.
6. `grep -n "defect" frontend/src/router/index.ts` -> only lines 184-185, path '/admin/defect-types' (the DEFECT_TYPE_CATALOG admin screen, a different table). Nav link at frontend/src/App.vue:136 points to that same catalog route only.
7. `grep -n "defect|detail" frontend/src/components/grids/QualityEntryGrid.vue` -> 0 matches: the quality entry grid has no master/detail or drill-down into defect rows.

NEAR-MISS EXAMINED AND REJECTED AS A REFUTATION: frontend/src/components/dialogs/ShiftDashboardDialogs.vue:145-148 renders a real v-select defect-type picker bound to `qualityForm.defectType`, sourced from frontend/src/composables/useShiftForms.ts:131-138 — a HARDCODED array ['Dimensional','Visual','Functional','Packaging','Documentation','Other'], not a fetch of the client's catalog. Its submit handler, useShiftForms.ts:337-349, calls api.createQualityEntry({... total_defects_count: defective, notes: qualityForm.value.defectType ? `Defect type: ${qualityForm.value.defectType}` : undefined }). The chosen type lands in a free-text notes string on QUALITY_ENTRY; no DEFECT_DETAIL row is ever created, and that string cannot be read by the Pareto aggregation which groups on DefectDetail.defect_type. This control is therefore inert for this capability and independently confirms the catalog disconnect.

BACKEND CONFIRMS NO IMPLICIT WRITE PATH: backend/schemas/quality.py:11-46 (QualityInspectionCreate) has no nested defect_details field. `grep -rn "DefectDetail" backend --include=*.py` shows the only row-creating sites are backend/crud/defect_detail.py:41 (`db_defect = DefectDetail(**defect_data)`), reached only from backend/routes/defect.py:37/89/107 and backend/endpoints/csv_upload.py:454-503, plus backend/db/factories.py:597-601 (the seeder). Hence every DEFECT_DETAIL row in a running system is seed data.

READ SIDE IS LIVE, PROVING THE ASYMMETRY: backend/routes/quality/pareto.py:64-125 (GET /quality/kpi/defects-by-type) groups `func.sum(DefectDetail.defect_count)` by `DefectDetail.defect_type` joined to QUALITY_ENTRY; backend/crud/analytics.py:223-239 does the same for top-defect identification. The frontend consumes it at frontend/src/services/api/kpi.ts:471 (`api.get('/quality/kpi/defects-by-type')`) and renders it at frontend/src/views/kpi/Quality.vue:508-509 (`:items="qualityData?.defects_by_type || []"`).

IMPACT: the Pareto / root-cause table on the Quality screen is permanently driven by seeded rows. An inspector can record "12 units defective" but never which defects, and the /admin/defect-types catalog (frontend/src/composables/useDefectTypesGridData.ts, reachable at App.vue:136) lets a client define industry-specific defect types that no capture surface ever offers.

</details>

### QC approval on a work order — POST /api/work-orders/{id}/approve-qc. Sets qc_approved/qc_approved_by/qc_approved_date and writes a WorkflowTransitionLog audit row. Documented as 'Phase 3.3: QC Approval as Final Gate for SHIPPED status'.

**Slice:** operations

**Backend:** backend/routes/work_orders.py:496-501 (@router.post('/{work_order_id}/approve-qc')), body at :502-585 with response schema backend/schemas/workorder_contracts.py:171-182 (WorkOrderApproveQCResponse). The gate it feeds: backend/calculations/workflow_engine.py:197-199 — `if to_status == "SHIPPED": if not work_order.qc_approved: return False, "Cannot mark as SHIPPED: QC approval required"`. Also backend/docs/WORKFLOW_STATES.md:63,109.

**Why unreachable:** No call to approve-qc anywhere in frontend/src (searched all api.* and fetch() call sites). frontend/src/components/WorkOrderDetailDrawer.vue:222-238 renders a QC panel that only DISPLAYS state — a v-alert bound to workOrder.qc_approved showing 'QC Approved' or 'Pending QC Approval' with no button, no handler, no emit. The status transition control (frontend/src/components/workflow/WorkOrderStatusChip.vue:104) calls only transitionWorkOrder/getAllowedTransitions.

**User impact:** SHIPPED is unreachable for every work order in the product. A supervisor sees 'Pending QC Approval' forever with nothing to click, and any attempt to transition a work order to SHIPPED is rejected by the workflow engine with 'QC approval required'. The documented final quality gate — and the qc_approved_by/date audit trail behind it — has no control surface at all.

<details><summary>verification</summary>

SEARCHES RUN (all over the repo, absolute root /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. `grep -rn "approve-qc|approveQc|approveQC|approve_qc"` over frontend/ — the ONLY hits are in the stale build output `frontend/dist/assets/HelpCenter-DHkIRkVj.js:1109,1181`, which is compiled Help Center prose sourced from `docs/user-guide/05-work-orders.md:93,165` ("POST /api/work-orders/{id}/approve-qc — the gate before SHIPPED status"). That is documentation rendered as text, not a call site: `frontend/src/views/HelpCenter.vue` merely `marked`-renders markdown docs (line 81), so a user can READ about the endpoint and still has nothing to click. Zero hits in frontend/src.

2. `grep -rni "qc"` over frontend/src (excluding locales) — 6 hits, all in `frontend/src/components/WorkOrderDetailDrawer.vue:221-247`, and all display-only: a `<v-alert>` whose `:type` / `:icon` / label switch on `workOrder.qc_approved` (lines 226, 231, 232) plus an "approved on" caption (234-235). No `<v-btn>`, no `@click`, no emit in that block. The only other "qc" strings in the repo's frontend are an unrelated simulation operation label ('QC', `frontend/src/components/simulation/OperationsGrid.vue:152`) and `simulationV2.ts:561-564` seed text. i18n has only the two display strings `workOrderDrawer.qcApproved` / `pendingQcApproval` (`frontend/src/i18n/locales/en.json:3987`) — no "approve" action label.

3. Service layer: `frontend/src/services/api/workOrders.ts` exposes exactly get/list/date-range/`put /work-orders/{id}` (23)/delete (25)/`put {status}` (28)/progress (30)/timeline (32) — no approve-qc. `frontend/src/services/api/workflow.ts` exposes transition (8), validate (14), allowed-transitions (19), history (22), elapsed-time (58), transition-times (61) — no approve-qc. `grep -rn "work-orders/\\${"` across frontend/src returns 15 call sites, none of which builds an `/approve-qc` suffix and none of which templates the action segment dynamically.

4. The write path that COULD have carried it does not: `backend/schemas/work_order.py:124-126` (WorkOrderUpdate) does accept `qc_approved`, but the only two UI producers of a PUT body are `frontend/src/composables/useWorkOrderGridData.ts:169-180` (`buildUpdatePayload` — a fixed 10-field literal: style_model, planned_quantity, actual_quantity, status, priority, planned_start_date, planned_ship_date, customer_po_number, ideal_cycle_time, notes; no qc_approved) and `WorkOrderDetailDrawer.vue:434` (delay-classification payload only). No grid column, no form field, no dialog anywhere binds qc_approved for write.

5. Reverse check — no dedicated screen: `frontend/src/views/` has no QC/approval view. `frontend/src/views/QualityEntry.vue` (full file read, 26 lines) is a defect-entry wrapper around `QualityEntryGrid` + `CSVUploadDialogQuality` — unrelated. Router entries `/kpi/quality` and `/data-entry/quality` (`frontend/src/router/index.ts:84-86, 114-116`) point at those, not at QC approval.

6. History check: `git log --oneline -S "approve-qc" -- frontend/src` returns NOTHING, while the control `git log -S "transitionWorkOrder" -- frontend/src` returns 3 commits — so the search is sound and the string has never existed in frontend source in any commit.

7. Backend confirms only one writer: `grep -rn "qc_approved" backend/{routes,endpoints,services,crud,orm}` shows the field is set in exactly one place, `backend/routes/work_orders.py:559-561` inside the approve-qc handler (route decorator at :496-501), which also writes the `WorkflowTransitionLog` audit row (:571-581, trigger_source="qc_approval"). No alternate UI-reachable endpoint covers this function.

IMPACT IS REAL, AND SLIGHTLY WORSE THAN CLAIMED. SHIPPED is not merely absent from the UI — it is actively offered and then rejected: `frontend/src/composables/useWorkOrderGridData.ts:67-79` puts 'SHIPPED' in `WORK_ORDER_STATUS_OPTIONS`, used as an `agSelectCellEditor` value list on the editable status column (asserted by `useWorkOrderGridData.spec.ts:179` "status uses select editor over WORK_ORDER_STATUS_OPTIONS"). Selecting it fires `api.put(/work-orders/{id})` at `useWorkOrderGridData.ts:253`, which reaches `backend/crud/work_order.py:235-241` — that path DOES run the state machine (`sm.validate_transition`) and raises `HTTPException(400, "Invalid status transition: Cannot mark as SHIPPED: QC approval required")` from `backend/calculations/workflow_engine.py:197-199`. The drawer's chip path is equally blocked: `WorkOrderStatusChip.vue:104` imports only `getAllowedTransitions`/`transitionWorkOrder`. So the operator gets a dropdown option that always errors, an alert reading "Pending QC Approval" forever, and no control anywhere to clear it.

ADDITIONAL CORROBORATION THAT THIS IS A KNOWN-MISSING CONTROL, NOT A DESIGN DECISION: the repo's own surface inventory asserts the control exists — `docs/audit/entry-surface-inventory.md:108` lists Work Order Management's endpoints as including `POST /work-orders/{id}/approve-qc` and describes the surface as "Work orders (CRUD, QC approval, capacity link)", and `docs/audit/entry-surface-migration-plan.md:135` says to "preserve QC approval ... side-actions as row context-menu". Neither exists in `frontend/src/views/WorkOrderManagement.vue` (grep for approve/qc/link-capacity in that file and its composable: zero hits). The docs describe a control that was never built or was dropped in the grid migration.

NOT DISQUALIFIED BY THE EXCLUSIONS: it is not health/metrics/internal, it is not cron- or script-driven (it stamps `current_user.user_id` into qc_approved_by, so it is inherently an interactive human action), and no other UI surface covers it — it is the sole writer of qc_approved and the sole producer of the qc_approval audit row.

</details>

### Shift Coverage — entire /api/coverage feature. POST create, GET list (with date/shift filters), GET /{id}, GET /by-shift/{shift_id}, PUT /{id}, DELETE /{id}, plus POST /api/coverage/upload/csv.

**Slice:** operations

**Backend:** backend/routes/coverage.py:27 (router prefix /api/coverage), :30 POST, :41 GET, :70 GET /{id}, :84 GET /by-shift/{shift_id}, :113 PUT, :130 DELETE — with role guards (get_current_contributor to write, get_current_active_supervisor to delete). Backed by backend/schemas/coverage.py (ShiftCoverageCreate/Update/Response), backend/crud/coverage.py, backend/services/coverage_service.py. CSV import at backend/endpoints/csv_upload.py:325. Registered in backend/bootstrap/routers.py (coverage_router).

**Why unreachable:** Zero references to /coverage in frontend/src — the single string match is an unrelated doc comment in frontend/src/services/api/simulationScenarios.ts:7. No entry in frontend/src/router/index.ts, no view in frontend/src/views/, no service module, no store, no nav item in frontend/src/App.vue.

**User impact:** Identical shape to the already-confirmed EQUIPMENT gap: a complete, role-guarded, multi-tenant CRUD feature with schemas, CRUD layer, dedicated service module and a CSV importer, and not one pixel of UI. Shift coverage/capacity tracking — required staffing vs. actual per shift, the natural companion to attendance and the floating pool — cannot be viewed, entered, or edited by any user.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations)

1) Endpoint path. `grep -rn "/coverage" frontend/src` returns exactly 3 hits, all unrelated to the API:
   - frontend/src/__tests__/coverageIntegrity.spec.ts:8 and :247 — about @vitest/coverage-v8 (code-coverage tooling)
   - frontend/src/services/api/simulationScenarios.ts:7 — doc comment "throughput/coverage at a glance"
   `grep -rn "api/coverage|'/coverage|\"/coverage|`/coverage"` → zero matches.

2) Schema / ORM / model names. `grep -rn "shiftCoverage|ShiftCoverage|shift_coverage" frontend/src` → only:
   - frontend/src/services/api/structuredErrors.ts:66 `SHIFT_COVERAGE: 'errors.entities.shiftCoverage',` and :91 comment about the `shift_coverage` outlier
   - frontend/src/services/api/__tests__/structuredErrors.spec.ts:110-111 (test of that label)
   - frontend/src/i18n/locales/{en,es}.json:1150 `"shiftCoverage": "Shift coverage record | Shift coverage records"`
   This is a label used to render FK-blocked-delete messages ("Shift coverage records (3)"), not a call to the feature. It is the opposite of a reachability path — the UI can tell a user that shift-coverage rows are blocking them, then offers nowhere to go look at those rows.

3) Synonyms in i18n, then traced every hit back to its owning screen. All belong to other features:
   - en.json:166 `operationsHealth.attendanceCoverage` — a dashboard tile; no backend service reads the ShiftCoverage ORM (see #6)
   - en.json:693-695 `coverage/coveredBy/coverageConfirmed` — attendance-entry column labels
   - en.json:2549-2551 `coverageIssue/coverageMessage/requestCoverage` — MyShift staffing text; `grep -rn "requestCoverage|coverageIssue|coverageMessage" frontend/src --include="*.vue" --include="*.ts"` outside locales → zero matches (these keys are themselves unused)
   - en.json:4011 `floatingPoolCoverage` — used at frontend/src/components/AttendanceKPIs.vue:95, and that is the COVERAGE_ENTRY table (backend/orm/coverage_entry.py, floating-pool assignments), a different table from shift_coverage (backend/orm/coverage.py:19 `__tablename__ = "shift_coverage"`).

4) Router. frontend/src/router/index.ts has 38 `path:` entries (login, /, production-entry, kpi-dashboard, 7 kpi/*, 4 data-entry/*, work-orders, my-shift, alerts, simulation, simulation-v2, plan-vs-actual, capacity-planning, 11 admin/*, help, 404). No coverage/staffing route. `find frontend/src -iname "*coverage*"` → only __tests__/coverageIntegrity.spec.ts (the vitest-tooling test).

5) Services/stores. frontend/src/services/api/ has 28 modules; none is coverage, and frontend/src/services/api/index.ts imports/spreads all 19 namespaces with no coverage among them. frontend/src/stores/ has 13 stores, none coverage. No generic CRUD helper can synthesize the path: the only dynamic endpoint builders are useQRScanner.ts:175, useHoldGridForms.ts:362, useCSVExport.ts:70 (`/export/${entityType}` — its sole caller is usePivotView.ts:62, never with 'coverage'), and simulationScenarios.ts:75-111 (BASE = scenarios).

6) CSV importer. backend/endpoints/csv_upload.py:325 `POST /api/coverage/upload/csv` (get_current_active_supervisor), documented in docs/CSV_UPLOAD_ENDPOINTS.md:35 "#### 4. Shift Coverage Upload". The frontend ships exactly five upload dialogs, and coverage is not one: CSVUploadDialogQuality.vue:430 `/quality/upload/csv`, CSVUploadDialogAttendance.vue:401 `/attendance/upload/csv`, CSVUploadDialogDowntime.vue:396 `/downtime/upload/csv`, CSVUploadDialogHold.vue:393 `/holds/upload/csv`, CSVUploadDialogProduction.vue:417 + services/api/production.ts:18 `/production/upload/csv`. So the documented importer has no file picker anywhere.

7) No alternative backend surface covers it. `grep -rn "ShiftCoverage" backend --include="*.py"` (non-test) shows the ORM is touched ONLY by backend/crud/coverage.py, backend/services/coverage_service.py, backend/routes/coverage.py, backend/endpoints/csv_upload.py, and the seeder. No KPI/dashboard/floating-pool service reads it, so there is no read-only view of this data elsewhere either. The similarly named `/api/floating-pool/simulation/shift-coverage` (docs/API_DOCUMENTATION.md:1036) is a what-if simulator that never queries the shift_coverage table.

8) Registered and live: backend/bootstrap/routers.py:7 imports `coverage_router`, :211 `app.include_router(coverage_router)`.

WHY IT MATTERS MORE THAN EQUIPMENT: the seeder writes these rows on an ongoing basis — backend/seed/emitters_operations.py:871 emits one `ShiftCoverageRecorded` per SHIFT per day, and backend/seed/writers_workforce.py:98-116 inserts each into `shift_coverage` with coverage_percentage. Required-vs-actual headcount per shift, with a computed coverage %, accumulates daily into a table that no user can list, open, correct, or delete. A supervisor who spots a wrong headcount has no remedy short of curl; the DELETE at backend/routes/coverage.py:130 is soft-delete (backend/orm/coverage.py:38 `is_active`), so bad rows silently keep skewing any future consumer.

</details>

### Per-client hold status and hold reason catalogs — /api/hold-catalogs. GET/POST/PUT/DELETE /statuses, GET/POST/PUT/DELETE /reasons, and POST /seed-defaults (seeds 7 statuses + 11 reasons for a client).

**Slice:** operations

**Backend:** backend/routes/hold_catalogs.py:38 (router prefix /api/hold-catalogs), :46/:62/:85/:104 statuses CRUD, :126/:142/:165/:184 reasons CRUD, :206 POST /seed-defaults. Backed by backend/schemas/hold_catalog.py, backend/crud/hold_catalog.py, backend/services/hold_catalog_service.py. This catalog is a hard server-side gate on hold creation: backend/routes/holds.py:58-62 rejects any hold whose reason is not active in the client's catalog (422 'Reason X not found in client catalog'), via backend/crud/hold_catalog.py:214 validate_hold_reason_for_client, which queries the HoldReasonCatalog table. Defaults list at backend/crud/hold_catalog.py:35-47 (11 reasons).

**Why unreachable:** Zero references to hold-catalogs anywhere in frontend/src. No router entry, no view, no service method. Instead the hold-reason dropdown is a hardcoded array: frontend/src/composables/useHoldGridData.ts:76-87 exports HOLD_REASON_CODES with 8 literals and a comment 'mirrors backend/schemas/hold.py:56-71', consumed as cellEditorParams at :226 and as the default value at frontend/src/composables/useHoldGridForms.ts:165,453. hold_status is explicitly read-only in the grid (frontend/src/composables/__tests__/useHoldGridData.spec.ts:141).

**User impact:** Three failures at once. (1) For a client whose catalog was never seeded, EVERY hold creation 422s and no UI can seed it — the Hold/Resume entry screen is silently dead for that tenant. (2) Three of the 11 default reasons (MATERIAL_SHORTAGE, ENGINEERING_CHANGE, PENDING_APPROVAL) exist in the catalog but are absent from the hardcoded dropdown, so they are unpickable. (3) The advertised per-client configurability — custom hold statuses and reasons per tenant — has no admin screen, so any client-specific reason added to the DB is invisible in the picker while any reason removed still shows and then 422s on save.

<details><summary>verification</summary>

SEARCHES RUN (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. `grep -ril "hold-catalog|hold_catalog|holdCatalog|HoldCatalog" frontend/src/` → ZERO matches.
2. `grep -ril "seed-defaults|seedDefaults|seed_defaults" frontend/src/` → ZERO matches.
3. `grep -rn "hold-catalogs" frontend/` → exactly ONE hit, in a build artifact: frontend/dist/assets/HelpCenter-DHkIRkVj.js:683 — descriptive help prose, not an HTTP call. The current source it was built from no longer contains it: `grep -rn "hold catalog|hold-catalogs" frontend/src/i18n frontend/src/help frontend/src/views` → ZERO.
4. `grep -rn -i "hold" frontend/src/views/admin/ frontend/src/stores/` (minus "threshold") → only productionDataStore.ts hold-ENTRY CRUD (:396 fetchHoldEntries, :413 createHoldEntry, :430 updateHoldEntry, :453 deleteHoldEntry) and workflowDesignerStore.ts:163 (an unrelated local `holdStatuses = ['ON_HOLD','HOLD']` literal for node classification). No admin view mentions "hold" at all.
5. `grep -rn "reason_code|status_code|holdReasons|holdStatuses" frontend/src/` → the only `holdReasons` is frontend/src/composables/useHoldGridData.ts:348 `holdReasons: HOLD_REASON_CODES`, consumed by frontend/src/components/grids/HoldEntryGrid.vue:68 `:items="holdReasons"`. No `reason_code`/`status_code` field name appears anywhere in the frontend — i.e. nothing ever deserializes a HoldReasonCatalogResponse.
6. Router: `grep -n -i "hold" frontend/src/router/index.ts` → only lines 120-122, `/data-entry/hold-resume` → HoldResumeEntry.vue. No catalog/admin route.
7. Service layer inventory: `ls frontend/src/services/api/` (30 files) — no hold-catalog module. frontend/src/services/api/dataEntry.ts:41-45 is the entire hold surface (POST/PUT/DELETE/GET /holds, GET /holds/active). frontend/src/services/api/admin.ts and reference.ts cover clients, users, kpi-thresholds, defect-types, products, shifts, downtime-reasons — no hold catalogs. frontend/src/services/api/workflow.ts is work-order status transitions (/workflow/*), a different subsystem.

CONFIRMING THE HARDCODED SUBSTITUTE:
frontend/src/composables/useHoldGridData.ts:76-87 — comment "Canonical HOLD_REASON_CATALOG codes (mirrors backend/schemas/hold.py:56-71)" over a literal array of 8 strings (QUALITY_ISSUE, MATERIAL_INSPECTION, ENGINEERING_REVIEW, CUSTOMER_REQUEST, MISSING_SPECIFICATION, EQUIPMENT_UNAVAILABLE, CAPACITY_CONSTRAINT, OTHER). backend/crud/hold_catalog.py:35-47 DEFAULT_HOLD_REASONS has 11; the 3 missing from the dropdown are MATERIAL_SHORTAGE, ENGINEERING_CHANGE, PENDING_APPROVAL — claim (2) verified. Note backend/schemas/hold.py has NO enum constraint on hold_reason (only a from_legacy_csv mapping dict at :53-70), so the DB catalog is the sole gate, exactly as claimed.

CONFIRMING THE SERVER-SIDE GATE AND THAT NOTHING ELSE SEEDS IT:
backend/routes/holds.py:57-62 — `if hold.hold_reason and not validate_hold_reason_for_client(...)` → 422 "Reason '{x}' not found in client catalog". backend/crud/hold_catalog.py:214 queries HoldReasonCatalog filtered on client_id + is_active.
backend/bootstrap/routers.py:51,128 — router is registered, so the endpoints are live.
`grep -rn "seed_defaults|seed_default_catalogs|DEFAULT_HOLD_REASONS" backend/ scripts/` → callers are ONLY backend/tests/test_crud/test_hold_catalog_crud.py and the route itself. Nothing in the client-creation path (POST /clients, reachable from AdminClients.vue) seeds a catalog.

WHAT I FOUND THAT PARTIALLY CORRECTS THE CLAIMED IMPACT:
The event-sourced seeder does write these tables — backend/seed/writers_master.py:270-298 (`_hold_reason_defined` → sink.add("HOLD_REASON_CATALOG", ...), `_hold_status_defined` → "HOLD_STATUS_CATALOG"), registered in backend/seed/coverage.py:23 and backend/seed/materialize.py:70. So seeded demo tenants DO have a catalog and the Hold/Resume screen works for them; claim (1) is not true of demo data. It remains true for any client created through the UI's own Add-Client flow (frontend/src/views/admin/AdminClients.vue → POST /clients), which never seeds catalogs — that tenant's Hold/Resume screen 422s on every save with no UI able to fix it, since POST /api/hold-catalogs/seed-defaults (backend/routes/hold_catalogs.py:206) is unreachable. Claims (2) and (3) stand as written.

</details>

### Job lifecycle writes — POST /api/jobs (create), PUT /api/jobs/{id} (update), POST /api/jobs/{id}/complete (record completed quantity + actual hours), DELETE /api/jobs/{id}, plus POST /api/jobs/upload/csv.

**Slice:** operations

**Backend:** backend/routes/jobs.py:41 (router prefix /api/jobs), :44 POST create_job_endpoint, :83 PUT update_job_endpoint, :103-120 POST /{job_id}/complete (takes JobComplete with completed_quantity + actual_hours, supervisor-guarded), :122 DELETE. Schemas at backend/schemas/job.py, CRUD at backend/crud/job.py. CSV import at backend/endpoints/csv_upload.py:620.

**Why unreachable:** The complete frontend API-call inventory contains no POST/PUT/DELETE to /jobs at all — only three reads: frontend/src/components/JobLineItems.vue:228 api.get(`/work-orders/${id}/jobs`), :247 api.get(`/work-orders/${id}/rty`), :261 api.get(`/jobs/${job.job_id}/yield`), plus frontend/src/composables/useQualityData.ts:158 api.get('/jobs/kpi/rty-summary'). JobLineItems.vue is the only jobs surface (mounted once, at frontend/src/components/WorkOrderDetailDrawer.vue:263) and its 'actions' column contains only a view-yield button. No CSVUploadDialogJobs component exists.

**User impact:** Jobs are the per-operation routing steps a work order is broken into, and they are strictly read-only in the product: no user can create a job, edit its quantities, mark it complete, or delete it — nor bulk-load them by CSV, though the importer exists. Every job in the system can only come from the seeder or direct DB access. This starves the job-level KPIs the UI already renders (rolled-throughput-yield per work order, job yield, the RTY summary on the Quality screen), which will read the same frozen seed rows forever.

<details><summary>verification</summary>

BACKEND CAPABILITY CONFIRMED (verified line numbers, /Users/mcampos.cerda/Developer/Programming/kpi-operations):
- backend/routes/jobs.py:41 `router = APIRouter(prefix="/api/jobs", tags=["Jobs"])`; :44 POST "" create_job_endpoint (get_current_active_supervisor); :83 PUT "/{job_id}" update_job_endpoint; :103 POST "/{job_id}/complete" complete_job_endpoint (JobComplete -> completed_quantity + actual_hours); :122 DELETE "/{job_id}". Real work behind them: backend/services/job_service.py (create_job_record/update_job_record/delete_job_record/complete_job_record), backend/crud/job.py, backend/schemas/job.py.
- backend/endpoints/csv_upload.py:620 `@router.post("/api/jobs/upload/csv")` -> upload_jobs_csv, mapping 16 columns via _map_jobs_row (:598 JobCreate) into create_job. Documented as a user-facing importer at docs/CSV_UPLOAD_ENDPOINTS.md:67.

SEARCHES RUN ACROSS frontend/src (views, components, composables, services/api, stores, router, tests):
1. `grep -rn "'/jobs|\`/jobs|\"/jobs|/api/jobs" frontend/src` -> exactly TWO hits, both GET: frontend/src/composables/useQualityData.ts:158 `api.get('/jobs/kpi/rty-summary')` and frontend/src/components/JobLineItems.vue:261 `api.get(\`/jobs/${job.job_id}/yield\`)`. Zero hits in frontend/src for "api/jobs".
2. `grep -rn "jobs" frontend/src -i` -> the remaining hits are the two work-order-scoped reads (JobLineItems.vue:228 `api.get(\`/work-orders/${props.workOrderId}/jobs\`)`, :247 `/work-orders/{id}/rty`), i18n label keys (`jobs.*`) in Quality.vue / useWorkOrderData.ts / usePartOpportunities*, and a path-regression spec. No write call anywhere.
3. Synonym sweep `grep -rni "createjob|addjob|newjob|editjob|deletejob|completejob|addLineItem|jobService|jobStore"` over frontend/src -> only the JobLineItems component import/mount in WorkOrderDetailDrawer.vue:263/:359/:447. No service module, no Pinia store: `ls frontend/src/services/api/` has no jobs.ts; `ls frontend/src/stores/` has no jobs store.
4. Router: `grep -in "job" frontend/src/router/index.ts` -> zero matches. No Vue route for jobs at all; the only jobs surface is the embedded JobLineItems panel inside the work-order detail drawer.
5. Inert-control check on that panel: JobLineItems.vue:114-125, the `item.actions` slot contains exactly one v-btn -> `@click="loadJobYield(item)"`, whose handler (:259-271) only does `api.get(\`/jobs/${job.job_id}/yield\`)` and opens a read-only dialog. Headers (:209-217) are job_id/part_number/progress/yield/quantity_scrapped/status/actions — no edit, no complete, no delete, no "add line item".
6. Adjacent write surfaces checked and ruled out: frontend/src/services/api/workOrders.ts has create/update/delete for /work-orders only, nothing nested for jobs; frontend/src/services/api/dataEntry.ts covers downtime/attendance/quality/holds only. WorkOrderManagement.vue contains zero "job" matches.
7. CSV importer check: `grep -rn "upload/csv" frontend/src` -> only five dialogs (quality:430, attendance:401, downtime:396, holds:393, production:417) plus /part-opportunities/upload and /defect-types/upload/{clientId}. `ls frontend/src/components` confirms CSVUploadDialog{Attendance,Downtime,Hold,Production,Quality}.vue and no jobs equivalent. /api/jobs/upload/csv has no caller and no dialog.
8. Best refutation candidate chased and rejected: QRCodeScanner.vue:146 offers a `job` entity type, so I checked backend/routes/qr.py — every job-related QR route is a GET (:53 lookup, :268 /job/{job_id}/image) plus a POST /qr/generate/image that only renders a PNG; frontend/src/services/api/qr.ts exposes only lookupQR (GET) and generateQRImage. Scanning a job QR reads/points at a job, it never creates, updates, completes or deletes one.
9. Second candidate rejected: a "/api/jobs" string appears in the built bundle frontend/dist/assets/HelpCenter-*.js, but it comes from bundled user-guide markdown about the report scheduler ("stores the schedule in the JOB queue (/api/jobs)") — prose, not a call, and it does not appear in frontend/src at all.

IMPACT: the auditor's framing holds. Jobs — the per-operation routing steps of a work order — can only enter or change via the seeder or direct DB access. A supervisor cannot create a routing step, correct a quantity, record completion (completed_quantity + actual_hours, the one write the backend guards for supervisors specifically), delete a bad row, or bulk-load a routing sheet, even though the CSV importer exists and is documented. The job-level KPIs the UI already renders on top of that data — per-work-order RTY (JobLineItems.vue:247), per-job yield (:261), and the RTY summary block on the Quality screen (Quality.vue:362-431 via useQualityData.ts:158) — are therefore permanently pinned to seeded rows.

One nuance I would flag rather than treat as a refutation: production entries carry a job_id (backend/routes/production.py:211), so job-level activity is recorded somewhere reachable, but that path writes production rows, not the Job entity's completed_quantity/actual_hours/is_completed fields that POST /{job_id}/complete sets and that the RTY/yield math reads.

</details>

### Floating-pool membership — POST /api/employees/{id}/floating-pool/assign and POST /api/employees/{id}/floating-pool/remove, which set Employee.is_floating_pool, the flag that determines who is in the pool at all.

**Slice:** operations

**Backend:** backend/routes/employees.py:128-136 (assign_employee_to_floating_pool) and :139-147 (remove_employee_from_floating_pool), both supervisor-guarded, implemented at backend/crud/employee/floating_pool.py:38 and :75 (set is_floating_pool = 1/0). The flag is the roster gate for the whole feature: backend/crud/floating_pool/queries.py:140 — `floating_employees = db.query(Employee).filter(Employee.is_floating_pool.is_(True)).all()` — drives total/available/assigned on GET /floating-pool/summary. Field is writable via PUT /api/employees/{id} too (backend/schemas/employee.py:36).

**Why unreachable:** The string is_floating_pool appears NOWHERE in frontend/src, and no call targets /employees/{id}/floating-pool/*. frontend/src/views/admin/AdminEmployees.vue never exposes the field. The floating-pool screen's own header comment asserts the opposite and is wrong: frontend/src/composables/useFloatingPoolGridData.ts:6-8 and frontend/src/views/admin/FloatingPoolManagement.vue:59-62 both say 'pool membership is set elsewhere (employee admin), so this surface intentionally has no Add Row' — but employee admin has no such control.

**User impact:** Nobody can add an employee to, or remove one from, the floating pool. The /admin/floating-pool screen renders summary cards, a roster grid and simulation insights entirely off a roster that no UI can change — and it deliberately omits an Add Row on the strength of a comment pointing at a screen that doesn't implement it. Both surfaces defer to each other, so the capability falls through the gap and the pool is frozen at whatever the seeder wrote.

<details><summary>verification</summary>

SEARCHES RUN (repo /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. `grep -rn "is_floating_pool|isFloatingPool|floating-pool/assign|floating-pool/remove" frontend/src` -> the only non-test hits target a DIFFERENT endpoint: frontend/src/composables/useFloatingPoolGridData.ts:156 `api.post('/floating-pool/assign', {...})` and :180 `api.post('/floating-pool/unassign', { pool_id })`. Those hit the /api/floating-pool router (assign an already-in-pool employee to a client for a date window — backend/routes/floating_pool.py:201), NOT /api/employees/{id}/floating-pool/*. The literal string `is_floating_pool` appears nowhere in frontend/src.

2. `grep -rn "employees/" frontend/src` (excl. __tests__) -> exactly TWO call sites in the whole app: frontend/src/views/admin/AdminEmployees.vue:81 `api.get('/employees')` (read) and frontend/src/composables/useEmployeeAdminGrid.ts:94 `api.put(`/employees/${row.employee_id}`, { labor_class: value })`. That PUT body is a hardcoded single field. useEmployeeAdminGrid.ts:115-160 defines only 5 columns — employee_id / employee_code / employee_name / department all `editable: false`, labor_class the sole editable one. No POST or DELETE to /employees anywhere.

3. Reverse check on the pool screen: frontend/src/composables/useFloatingPoolData.ts issues only three GETs (:192 '/floating-pool', :193 '/floating-pool/summary', :194 '/clients'). FloatingPoolManagement.vue imports only useFloatingPoolData, useFloatingPoolGridData and FloatingPoolGuideDialog; no create/add handler exists. FloatingPoolGuideDialog.vue is labels only.

4. Router/nav: frontend/src/router/index.ts:202 '/admin/floating-pool' and :208 '/admin/employees' exist, and App.vue:139 links the pool screen in the nav drawer — so both SCREENS are reachable. It is the membership WRITE that has no control.

5. Alternate backend write path found and checked: backend/endpoints/csv_upload.py:735 `is_floating_pool=int(row.get("is_floating_pool", 0))` inside POST /api/employees/upload/csv (documented at :761). `grep -rn "upload/csv" frontend/src` returns upload dialogs for quality, attendance, downtime, holds, production and defect-types ONLY — there is no employees CSV upload UI, so that path is unreachable too.

6. Synonym sweep `grep -ril "floating" frontend/src` -> 20 files, every non-test one accounted for and all read-only: App.vue (nav link), useFloatingPoolData/GridData (read + client-assign), FloatingPoolGuideDialog (labels), AttendanceKPIs.vue:156 (explicitly "Mock floating pool data"), InferenceIndicator.vue:152 (parses a `+floating_pool` provenance string), PartOpportunities.vue:70 (reuses an i18n label), simulation.ts:8 (GET /floating-pool/simulation/insights), router/index.ts, i18n locales.

7. The one control that looks like it: frontend/src/components/alerts/AbsenteeismAlert.vue:207 pushes `{ id: 'activate-floating-pool', label: t('absenteeismAlert.activateFloatingPool') }`, rendered as a button at :90 emitting 'takeAction'. Its only consumer is DashboardOverview.vue:19 -> useDashboardOverviewData.ts:131-134, whose entire body is `console.log('Handling absenteeism action:', actionId)`. Inert — this strengthens the claim rather than refuting it.

BACKEND VERIFIED AS CLAIMED: backend/routes/employees.py:128-136 and :139-147 (both get_current_active_supervisor); backend/crud/employee/floating_pool.py assign_to_floating_pool / remove_from_floating_pool; backend/crud/floating_pool/queries.py:140 `db.query(Employee).filter(Employee.is_floating_pool.is_(True)).all()` drives the summary cards; backend/schemas/employee.py:36-37 exposes the field on EmployeeUpdate.

CIRCULAR DEFERRAL CONFIRMED: useFloatingPoolGridData.ts:5-8 and FloatingPoolManagement.vue:206-209 both say "pool membership is set elsewhere (employee admin), so this surface intentionally has no Add Row", while useEmployeeAdminGrid.ts:2-9 and AdminEmployees.vue:53-63 state they were built to BE that "employee admin" but were scoped "per YAGNI" to labor_class only. Each surface names the other as owner; neither implements it.

ONE CITATION CORRECTION (immaterial): the docstring in FloatingPoolManagement.vue is at lines 206-209, not 59-62; text is verbatim as quoted.

IMPACT: a supervisor can re-assign existing pool members to clients but cannot add anyone to, or remove anyone from, the pool. The total/available/assigned/utilization cards and simulation insights on /admin/floating-pool all render off a roster frozen at whatever the seeder wrote.

</details>

### Full REST CRUD for the six capacity master-data entities: calendar entries, production lines, capacity orders (incl. status transitions), production standards, BOM headers/details, and stock snapshots — roughly 30 endpoints with dedicated CRUD modules and Pydantic schemas behind them. No Vue view, component, store or composable invokes any of the create/update/delete operations.

**Slice:** capacity-simulation

**Backend:** backend/routes/capacity/calendar.py:50 POST /calendar, :92 PUT /calendar/{entry_id}, :112 DELETE /calendar/{entry_id}. backend/routes/capacity/lines.py:49 POST /lines, :92 PUT /lines/{line_id}, :112 DELETE /lines/{line_id}. backend/routes/capacity/orders.py:48 POST /orders, :76 GET /orders/scheduling, :111 PUT /orders/{order_id}, :129 PATCH /orders/{order_id}/status, :147 DELETE /orders/{order_id}. backend/routes/capacity/standards.py:47 POST /standards, :71 GET /standards/style/{style_model}, :83 GET /standards/style/{style_model}/total-sam, :114 PUT /standards/{standard_id}, :132 DELETE /standards/{standard_id}. backend/routes/capacity/bom_stock.py:69 POST /bom, :107 PUT /bom/{header_id}, :125 DELETE /bom/{header_id}, :154 POST /bom/{header_id}/details, :180 PUT /bom/details/{detail_id}, :200 DELETE /bom/details/{detail_id}, :283 POST /stock, :307 GET /stock/item/{item_code}/latest, :326 GET /stock/item/{item_code}/available, :340 GET /stock/shortages, :371 PUT /stock/{snapshot_id}, :391 DELETE /stock/{snapshot_id}. Backing CRUD modules exist: backend/crud/capacity/{calendar,production_lines,orders,standards,bom,stock}.py; schemas in backend/routes/capacity/_models.py and backend/schemas/capacity_contracts.py.

**Why unreachable:** frontend/src/services/api/capacityPlanning.ts wraps every one of these (createCalendarEntry:38, updateCalendarEntry:45, deleteCalendarEntry:51, createProductionLine:76, updateProductionLine:83, deleteProductionLine:90, getOrders:101, getOrdersForScheduling:114, createOrder:126, updateOrder:132, updateOrderStatus:139, deleteOrder:148, getStandards:159, getStandardsByStyle:167, getTotalSAMForStyle:174, createStandard:180, updateStandard:187, deleteStandard:194, getBOMHeaders:205, createBOMHeader:224, updateBOMHeader:231, deleteBOMHeader:238, getBOMDetails:245, createBOMDetail:252, updateBOMDetail:259, deleteBOMDetail:266, getStockSnapshots:288, getLatestStock:296, getAvailableStock:303, getShortageItems:310, createStockSnapshot:317, updateStockSnapshot:324, deleteStockSnapshot:331). Grepping every one of those identifiers across frontend/src/views, /components, /stores and /composables (excluding __tests__) returns zero call sites for all of them except getProductionLines (composables/useProductionLines.ts) and explodeBOM. Reads are served instead by the single GET /capacity/workbook/{client_id} (kpi_workbook.py:112-424); writes have no route at all, because the only write path is the stubbed workbook PUT. There is also no CSV import fallback — grepping backend/endpoints/csv_upload.py for capacity/bom/stock/standards/calendar returns nothing.

**User impact:** Nothing in the capacity module can be created, edited or deleted by a user. Orders cannot be entered or moved through their status lifecycle, production lines cannot be configured, SAM standards cannot be maintained, BOMs cannot be built, stock snapshots cannot be recorded, and calendar/holiday setup is impossible. Since component check, capacity analysis and schedule generation all consume this master data, the entire planning chain can only ever run against whatever a seed script or DBA inserted directly.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations)

1) Every exported identifier in frontend/src/services/api/capacityPlanning.ts, grepped across all *.ts/*.vue in frontend/src excluding __tests__ and the service file itself. 34 identifiers tested (createCalendarEntry, updateCalendarEntry, deleteCalendarEntry, createProductionLine, updateProductionLine, deleteProductionLine, getCalendarEntries, getOrders, getOrdersForScheduling, createOrder, updateOrder, updateOrderStatus, deleteOrder, getStandards, getStandardsByStyle, getTotalSAMForStyle, createStandard, updateStandard, deleteStandard, getBOMHeaders, createBOMHeader, updateBOMHeader, deleteBOMHeader, getBOMDetails, createBOMDetail, updateBOMDetail, deleteBOMDetail, getStockSnapshots, getLatestStock, getAvailableStock, getShortageItems, createStockSnapshot, updateStockSnapshot, deleteStockSnapshot). Result: 33 of 34 => ZERO call sites. The single hit, getProductionLines, resolves to a DIFFERENT service — frontend/src/composables/useProductionLines.ts:9 imports from '@/services/api/productionLines', which calls GET /production-lines/ (services/api/productionLines.ts:8), not /capacity/lines.

2) Raw endpoint paths ('/capacity/calendar', '/capacity/lines', '/capacity/orders', '/capacity/standards', '/capacity/bom', '/capacity/stock') across frontend/src. Every literal occurrence is inside services/api/capacityPlanning.ts. The only other '/capacity' strings in the codebase are the router/nav path '/capacity-planning' (App.vue:80, router/index.ts:160, LoginView.vue:319).

3) All 30 files in frontend/src/services/api/ — no second service touches these paths.

4) Backend CSV fallback: grep -niE "capacity|bom|stock|standard|calendar" backend/endpoints/csv_upload.py exits 1 (no matches). No import path either.

WHAT EXISTS INSTEAD (the reason this is inert, not merely absent)

- Route + nav link are real: router/index.ts:160-164 mounts views/CapacityPlanning/CapacityPlanningView.vue; App.vue:80 renders the drawer item; LoginView.vue:319 even lands powerusers there by default.
- Six editable AG Grid surfaces exist: views/CapacityPlanning/components/grids/{CalendarGrid,ProductionLinesGrid,OrdersGrid,StandardsGrid,BOMGrid,StockGrid}.vue.
- A Save control exists and is bound: CapacityPlanningView.vue:62-66 (@click="saveAll") -> composables/useCapacityData.ts:137-139 store.saveAllDirty() -> stores/capacityPlanningStore.ts:388 -> stores/capacity/useWorkbookStore.ts:158-166 -> :133 capacityApi.saveWorksheet -> services/api/capacityPlanning.ts:16-19, which issues PUT /capacity/workbook/{clientId}/{worksheetName}.
- THAT ENDPOINT IS A STUB. backend/routes/capacity/kpi_workbook.py:426-475: save_worksheet validates the worksheet name, then line 474 comments "This is a placeholder for actual implementation" and line 475 returns {"message": f"Worksheet '{worksheet_name}' saved", "rows_processed": len(data)}. No CRUD call, no db.commit. The user is told it saved; nothing is written.
- Local grid mutations never leave the browser: stores/capacity/useWorksheetOps.ts has zero imports from services/api (grep -c "services/api" = 0). addBOMComponent (:400-419) and removeBOMComponent (:421-430) only push/splice an in-memory array and set dirty=true.
- Only the ANALYSIS sub-store talks to the API: stores/capacity/useAnalysisStore.ts:94-323 calls runComponentCheck, explodeBOM, runCapacityAnalysis, generateSchedule, commitSchedule, getSchedule, createScenario, runScenario, compareScenarios, deleteScenario — all consumers of master data, none of them writers of it.

MISLEADING IN-REPO COMMENTS (worth flagging on their own)
Two source comments assert the wiring exists and are factually wrong given the stub above:
- composables/useBOMGridData.ts:11-16 — "The store action persists both header rows (POST /capacity/bom + PUT /capacity/bom/{id}) and component rows..."
- views/CapacityPlanning/components/grids/BOMGrid.vue:99-104 — "The store's addBOMComponent / removeBOMComponent actions write to the orphaned POST /capacity/bom/{id}/components and PUT /capacity/bom/{id}/components/{cid} endpoints". Neither store action makes any HTTP call, and those two component endpoints do not even exist on the backend — the real ones are POST /capacity/bom/{header_id}/details and PUT /capacity/bom/details/{detail_id} (backend/routes/capacity/bom_stock.py:154, :180).

BACKEND IS LIVE, NOT DEAD CODE
backend/bootstrap/routers.py:271 includes capacity_router. The handlers are genuine implementations, not stubs — e.g. backend/routes/capacity/calendar.py:50-60 create_calendar delegates to crud.capacity.calendar.create_calendar_entry, behind get_current_planner + verify_client_access. Full CRUD modules exist: backend/crud/capacity/{bom.py 13K, calendar.py 8K, orders.py 11.1K, production_lines.py 8.8K, standards.py 10.8K, stock.py 14.4K}.

CONCLUSION
Roughly 30 implemented, registered, authorized endpoints with ~66K of CRUD behind them, and the only write a user can trigger is a placeholder that lies about succeeding. This is both "a UI control exists but is inert" and "the UI can READ but not WRITE" simultaneously. Severity is high: it is worse than a missing screen because it silently discards operator data entry — a planner can spend an afternoon entering orders, standards or BOMs, see a success state, and lose all of it on reload.

</details>

### KPI commitment-versus-actual variance reporting. GET /api/capacity/kpi/variance runs KPIIntegrationService, pulls real efficiency/performance/quality/output/OTD/utilization actuals from production data, and writes actual_value / variance / variance_percent back onto the stored CapacityKPICommitment rows. It is the only code path that ever populates those columns. No UI calls it, and the button that claims to do so is wired to a no-op.

**Slice:** capacity-simulation

**Backend:** backend/routes/capacity/kpi_workbook.py:64-104 defines GET /kpi/variance; it instantiates KPIIntegrationService (line 83) and calls calculate_variance(client_id, schedule_id) or calculate_variance_detailed(client_id) (lines 90-93). backend/services/capacity/kpi_integration_service.py (33.9K) computes actuals in get_actual_kpis (line 159, per-KPI at lines 188/202/216/230/244/258) and persists them onto the commitment rows at line 530 (commitment.actual_value = actual) and line 585 (commitment.actual_value = Decimal(str(actual_value))).

**Why unreachable:** frontend/src/services/api/capacityPlanning.ts:492 exports getKPIVariance; grepping getKPIVariance across frontend/src/views, /components, /stores, /composables (excluding __tests__) returns zero call sites. Meanwhile the KPI Tracking tab renders a 'Load Actuals' button at frontend/src/views/CapacityPlanning/components/panels/KPITrackingPanel.vue:15-20, whose handler (line 154) opens a period-picker dialog and calls store.loadKPIActuals(selectedPeriod). That store action is frontend/src/stores/capacityPlanningStore.ts:549-552:
  async function loadKPIActuals(_period: string): Promise<null> {
    void _period
    return null
  }
with the preceding comment (lines 544-548) stating the analysis sub-store never implemented it and it is 'surfaced here as a no-op stub'. The panel's actual_value / variance_percent / status columns therefore stay permanently null (fed only by GET workbook's kpi_tracking sheet, kpi_workbook.py:382-395, which reads columns nothing ever writes).

**User impact:** After committing a schedule the planner sees KPI targets in the KPI Tracking tab with empty Actual, Variance and Status columns and four summary cards (Total / On Target / Off Target / Critical) that are stuck at 0. Clicking 'Load Actuals' picks a period, closes the dialog, and does nothing — no request, no error, no change. The commit-then-measure loop that is the entire point of KPI commitments cannot be closed from the UI, despite a 34KB backend service that implements it.

<details><summary>verification</summary>

SEARCHES (frontend/src, excluding __tests__):
1. `getKPIVariance` — only definition at services/api/capacityPlanning.ts:492 and barrel re-export at :618. Call sites exist ONLY in tests: services/__tests__/capacityPlanning.spec.ts:1110-1128 and a vi.fn() mock at stores/__tests__/capacityPlanningStore.spec.ts:69.
2. Path string `capacity/kpi` — only capacityPlanning.ts:488 (/capacity/kpi/commitments) and :496 (/capacity/kpi/variance). Both are definitions with no callers.
3. `capacityApi.` in the two stores that import the module (stores/capacity/useWorkbookStore.ts:8, stores/capacity/useAnalysisStore.ts:7) — 13 call sites total (runComponentCheck, explodeBOM, runCapacityAnalysis, generateSchedule, commitSchedule, getSchedule, createScenario, runScenario, compareScenarios, deleteScenario, loadWorkbook, saveWorksheet, saveWorkbook). getKPIVariance and getKPICommitments appear in NEITHER.
4. `loadKPIActuals`/`kpiActuals` — 4 hits: the stub (stores/capacityPlanningStore.ts:549-552), its export (:675), the panel call (KPITrackingPanel.vue:161), and a doc comment (composables/useKPITrackingGridData.ts:9).
5. `variance` across views/components/stores/composables/i18n — all hits belong to other features.
6. frontend/e2e and frontend/tests for `kpi/variance`, `Load Actuals`, `loadActuals` — zero hits.

NEAR-MISSES ELIMINATED:
- /admin/variance-report IS nav-linked (App.vue:142, router/index.ts:232-233) but is a DIFFERENT capability: views/admin/AssumptionVarianceReport.vue:147 imports only from @/services/api/calculationAssumptions, whose paths are /assumptions/catalog (:61), /assumptions/variance (:64), /assumptions (:73). Never /capacity/kpi/variance.
- PlanVsActualView.vue / usePlanVsActual.ts use variance_percentage from the plan-vs-actual endpoint — different backend surface.
- Backend: `grep -rn "KPIIntegrationService" backend --include=*.py` gives exactly one route-layer instantiation, routes/capacity/kpi_workbook.py:83. services/capacity/capacity_service.py:64 also wraps it (calculate_variance at :313), but `grep -rn "CapacityService(" routes/ endpoints/` returns NOTHING — that facade is dead to the HTTP layer.
- The commit flow cannot populate the columns: routes/capacity/analysis.py:402-434 sets only schedule.kpi_commitments_json; it never creates CapacityKPICommitment rows nor calls store_kpi_commitments.
- Manual entry is impossible: composables/useKPITrackingGridData.ts:7-10 documents, and :145/:153/:161 implement, actual_value / variance_percent / status as read-only chip renderers; only kpi_name and target_value are editable.
- The button is verifiably inert: KPITrackingPanel.vue:154 opens the dialog, :158-166 awaits store.loadKPIActuals(selectedPeriod.value), which is capacityPlanningStore.ts:549-552 `{ void _period; return null }` with the comment at :544-548 stating the analysis sub-store never implemented it.

CORRECTION TO THE CLAIM'S IMPACT (does not affect reachability): the columns and summary cards are NOT "stuck at 0" on a seeded demo DB — backend/seed/emitters_capacity.py:373-386 emits CapacityKpiCommitted with hardcoded actual_value/variance/variance_percent. That makes the demo look like the loop works while any real or newly-committed client's columns stay null permanently.

</details>

### Audit trail read API — admin-only entity-level change history (`GET /api/audit` with table/actor/client/date filters + pagination, and `GET /api/audit/{table_name}/{record_pk}` for one record's full history)

**Slice:** alerts-reports

**Backend:** backend/routes/audit.py:19 (`APIRouter(prefix="/api/audit")`), :99 `list_audit_entries`, :137 `get_entity_history` — both `Depends(get_current_admin)`, returning `AuditListResponse`. Backed by a real table: backend/orm/audit_entry.py:24 `class AuditEntry`, schemas at backend/schemas/audit.py. Capture is LIVE in production: backend/bootstrap/app_config.py:113 calls `register_audit_listener()` from backend/audit/capture.py, which writes an AUDIT_ENTRY row on every insert/update/delete across the 14 tables in backend/audit/registry.py:20 (WORK_ORDER, USER, CLIENT, CLIENT_CONFIG, EMPLOYEE, EMPLOYEE_CLIENT_ASSIGNMENT, EMPLOYEE_LINE_ASSIGNMENT, KPI_THRESHOLD, USER_CLIENT_ASSIGNMENT, ALERT_CONFIG, and the three catalogs).

**Why unreachable:** `grep -rn "'/audit|\"/audit|`/audit|api/audit" frontend/src` returns NOTHING. No Vue route: frontend/src/router/index.ts:165-235 registers 14 admin screens (/admin/settings, /admin/users, /admin/clients, /admin/defect-types, /admin/part-opportunities, /admin/client-config, /admin/floating-pool, /admin/employees, /admin/workflow-config, /admin/workflow-designer, /admin/database, /admin/variance-report) and none is an audit view. No view file exists under frontend/src/views/admin/ for audit, no service method in frontend/src/services/api/**.

**User impact:** The system silently accumulates a complete, deliberately-engineered change ledger — who changed a work order's status, who edited a KPI threshold, who granted a user access to a tenant — and no admin can ever look at it from the product. Every compliance, dispute, or 'who broke this' question requires a developer with DB or curl access. It is the single largest amount of engineering in this slice sitting behind no screen (the route module alone carries ~90 lines of documented MariaDB-ordering and overflow-guard reasoning).

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations/frontend/src, case-insensitive, whole tree including views, components, services, stores, router, composables, i18n locales):

1. Endpoint path and last segment — `grep -rn "api/audit|'/audit|\"/audit|\`/audit"` → ZERO matches.
2. ORM/schema vocabulary — `grep -rn "AuditEntry|audit_entry|AUDIT_ENTRY|auditEntries|record_pk|actor_user_id|trail_started_at"` → ZERO matches. (`trail_started_at` and `record_pk` are unique to backend/schemas/audit.py, so no frontend type ever modeled the response.)
3. Bare word — `grep -rni "audit" frontend/src` → 40 hits, ALL of which are either (a) code comments referencing the historical "entry-interface audit" / "_audit/" report exercise, (b) `frontend/src/utils/contrastAudit.ts` (WCAG color-contrast math, unrelated), or (c) the four dead audit-log widget artifacts below. Not one is an API call.
4. Synonyms — history / changelog / trail / historial / bitácora across .ts/.vue/.json → nothing pointing at the change ledger (only `mdi-history` icons and `recent_entries`).
5. Router — `grep -rn "audit" frontend/src/router/index.ts` → ZERO matches (exit 1). The 28 registered paths include /admin/{settings,users,clients,defect-types,part-opportunities,client-config,floating-pool,employees,workflow-config,workflow-designer,database,variance-report}; none is an audit view.
6. Admin views directory — `ls frontend/src/views/admin/` = AdminClients, AdminDefectTypes, AdminEmployees, AdminSettings, AdminUsers, AssumptionVarianceReport, ClientConfigView, DatabaseConfigView, FloatingPoolManagement, PartOpportunities, WorkflowConfigView, WorkflowDesignerView. No audit view. AdminSettings.vue has no audit tab (all 71 `t('admin.settings.*')` keys are general/thresholds/notifications). /admin/database is DatabaseConfigView.vue — a DB *provider* config screen (`databaseConfig.currentProvider`, sqlite vs mariadb), not a generic table browser, so it offers no back-door read of AUDIT_ENTRY.
7. Component tree — `find src -name "*AuditLog*"` → nothing. `find src -type d -name widgets` → only `src/components/widgets/` containing BradfordFactorWidget.vue, DowntimeImpactWidget.vue, QualityByOperatorWidget.vue, ReworkByOperationWidget.vue. No audit component exists anywhere.

THE FOUR DEAD ARTIFACTS (the closest thing to a UI, and each one is inert):
- frontend/src/stores/dashboardStore.ts:91 — `audit_log: { name: 'Audit Log', description: 'System audit trail', icon: 'mdi-clipboard-text-clock', minRole: 'admin' }` in ALL_WIDGETS.
- frontend/src/stores/dashboardStore.ts:69 — `{ widget_key: 'audit_log', widget_name: 'Audit Log', widget_order: 5, is_visible: true }` in the admin default layout. Pure metadata; the store makes no HTTP call for it.
- frontend/src/components/dashboard/WidgetGrid.vue:233-236 — `audit_log: defineAsyncComponent(() => import('./widgets/AuditLog.vue').catch(() => ({ template: '...<v-icon>mdi-clipboard-text-clock</v-icon><p>{{ $t(\'widgets.grid.auditLog\') }}</p>...' })))`. Relative to WidgetGrid.vue that resolves to frontend/src/components/dashboard/widgets/AuditLog.vue — a directory that does not exist (`ls` → "No such file or directory"). The import always throws and the `.catch` yields a static icon-plus-label placeholder that calls nothing.
- i18n keys `admin.auditLog` (en.json:1649 / es.json:1649) and `widgets.grid.auditLog` (en.json:3932 / es.json:3932). `grep -rn "admin\.auditLog" frontend/src` → ZERO consumers; the key is orphaned. Only `widgets.grid.auditLog` is referenced, and only by the placeholder above.

AND THE PLACEHOLDER NEVER EVEN RENDERS: `grep -rn "WidgetGrid" frontend/src` outside the file itself returns only `components/dashboard/index.ts:3` (a barrel export nothing imports — `grep -rn "components/dashboard'"` → ZERO) and a comment in `src/__tests__/coverageIntegrity.spec.ts`. `grep -rn "useDashboardStore"` shows the only non-test consumers are WidgetGrid.vue, WidgetContainer.vue and DashboardCustomizer.vue (which only reference each other), plus composables/useKPIDashboardData.ts:178 which calls exactly one thing — `dashboardStore.initializePreferences()` — and renders no widgets. No view mounts WidgetGrid, so an admin cannot see even the empty "Audit Log" card.

Corroboration that this is a known-dead path: src/__tests__/coverageIntegrity.spec.ts:6-11 documents the 2026-08-11 finding verbatim — "`WidgetGrid.vue` dynamically imported 11 components from a `./widgets/` directory that never existed."

BACKEND CONFIRMED LIVE AND SHIPPED: backend/bootstrap/routers.py:66 `from backend.routes.audit import router as audit_router` and :311 `app.include_router(audit_router)`. backend/routes/audit.py:19 `APIRouter(prefix="/api/audit")`, :99 `list_audit_entries` (table_name/actor_user_id/client_id/start_date/end_date filters, limit 1-500, offset guard, `total`, `trail_started_at`), :137 `get_entity_history(table_name, record_pk)` — both `Depends(get_current_admin)` returning `AuditListResponse`. The module carries ~90 lines of documented MariaDB whole-second-ordering and OFFSET/date.max overflow reasoning, so it was built and hardened for real callers.

NOT AN EXEMPTED CATEGORY: it is not a health/metrics probe, and it is admin-*authenticated*, not admin-*script* — an interactive filtered/paginated query with human-facing affordances (date range, actor, tenant, "trail_started_at" so a human can tell "nothing happened" from "before we were watching"). No other UI surface covers it: no screen anywhere displays who changed a work order, a KPI threshold, or a tenant grant.

IMPACT: an admin default dashboard advertises "Audit Log / System audit trail" as an available widget, so the product implies the ledger is viewable; in reality the widget resolves to nothing and no screen ever issues the request. Every compliance, dispute, or "who changed this" question requires direct DB or curl access.

</details>


---

## MEDIUM (16)

### Employee-to-production-line assignment CRUD (line staffing with allocation percentages)

**Slice:** masters-admin

**Backend:** backend/routes/employee_line_assignments.py:77 GET /api/employee-line-assignments/, :115 GET /employee/{employee_id}, :138 GET /line/{line_id}, :165 POST /, :207 PUT /{assignment_id}, :245 DELETE /{assignment_id}. Backed by backend/crud/employee_line_assignment.py:84 create_assignment, :51 validate_allocation (enforces the 100% allocation ceiling across concurrent assignments), :293 update_assignment, :340 end_assignment, plus backend/schemas/employee_line_assignment.py and backend/orm/employee_line_assignment.py:33 EMPLOYEE_LINE_ASSIGNMENT. Rows are seeded (backend/seed/writers_master.py:240, backend/seed/coverage.py:30) and the table is registered as auditable in backend/audit/registry.py:29 with the comment 'line staffing decisions'.

**Why unreachable:** `grep -rn "employee-line-assignments" frontend/src frontend/e2e` returns zero hits. No Vue route in frontend/src/router/index.ts, no nav item in frontend/src/App.vue:131-141, no view file matching the concept. frontend/src/views/admin/AdminEmployees.vue (the nearest surface) never mentions lines or allocations.

**User impact:** Deciding which employees staff which line, at what allocation percentage, with effective/end dates, is a first-class backend feature with validation and an audit trail — and there is no screen for it at all. Assignments exist only from the seeder. The backend even notes the gap itself: backend/routes/my_shift.py:119 says the operator dashboard resolves lines a cruder way and to 'Wire up via EMPLOYEE_LINE_ASSIGNMENT when needed'.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations)

1. Endpoint path + last path segment + synonyms across frontend/src and frontend/e2e:
   grep -rniE "employee[-_ ]?line|line[-_ ]?assign|lineAssign|allocation|EmployeeLineAssignment|line_assign|lineStaffing|staffing" frontend/src frontend/e2e
   - Every "allocation" hit is a DIFFERENT feature: frontend/src/composables/useAllocationEditor.ts:1-115 and useAttendanceGridData.ts:296-334 are the attendance intra-day LABOR-HOUR allocation ledger (category + hours, AllocationEditorDialog.vue), not line allocation_percentage.
   - Every "staffing" hit is simulation/floating-pool copy: frontend/src/composables/useFloatingPoolData.ts:39 `staffing_scenarios`, i18n keys simulation.staffing.* in frontend/src/i18n/locales/en.json:2323-2331. Not line staffing.
   - Zero hits for the endpoint path, the ORM name, or the schema name in frontend/src.

2. Repo-wide path grep: grep -rn "employee-line-assignments" . --exclude-dir=node_modules --exclude-dir=.git
   Hits are ONLY: backend/routes/employee_line_assignments.py, backend/bootstrap/routers.py:57,115, backend tests (test_routes/test_employee_line_assignment_routes.py, tests/contract/param_specs.py, tests/fixtures/cross_tenant_probe.py), backend/tests/test_bootstrap/openapi_surface.json, coverage HTML, docs/*.md, and one frontend file: frontend/dist/assets/HelpCenter-DHkIRkVj.js.

3. The one frontend hit is NOT a call. I extracted its context: it is the markdown table from docs/user-guide/09-admin.md:255 — "| Employee-line assignments | `/api/employee-line-assignments/*` (4) |" — bundled into the Help Center's rendered docs. frontend/src/views/HelpCenter.vue renders markdown as text (v-list of docs + rendered content pane); it issues no request to that path. A documented path in a help article is not a UI control. (Note the doc itself undercounts: the router exposes 6 operations, not 4.)

4. Router: frontend/src/router/index.ts — enumerated all 30 path entries (lines 25-249). Admin paths are /admin/settings, /users, /clients, /defect-types, /part-opportunities, /client-config, /floating-pool, /employees, /workflow-config, /workflow-designer/:clientId?, /database, /variance-report. No line-assignment route.

5. Nav: frontend/src/App.vue:127-142 admin v-list-group — 11 items, none for line assignments/line staffing.

6. Views: ls frontend/src/views and frontend/src/views/admin — no file matching the concept. frontend/src/views/admin/AdminEmployees.vue (read in full) calls only `api.get('/employees')` (line 81) and, via frontend/src/composables/useEmployeeAdminGrid.ts:94, `api.put('/employees/{id}', {labor_class})`. It never mentions lines, allocation_percentage, effective_date, or is_primary. Its own docstring scopes it to "a read-only roster ... plus the one editable field ... labor_class".

7. Services: enumerated frontend/src/services/api/*. frontend/src/services/api/productionLines.ts has ONLY two GETs (`/production-lines/` and `/production-lines/tree`) — read-only topology, no staffing. frontend/src/services/api/admin.ts has CRUD for clients, users, KPI thresholds, defect types — nothing for line assignments. grep for "'/employee" / "`/employee" across frontend/src returns only the /employees roster calls above.

8. Ruled out the obvious "covered by another surface" defense: FloatingPoolManagement.vue + backend/routes/floating_pool.py is a DIFFERENT capability. Its POST /assign and POST /unassign write FLOATING_POOL.current_assignment, which backend/schemas/floating_pool.py:17 defines as "Current client ID or NULL" — a client-level string. It has no line_id and no allocation_percentage. backend/orm/employee_line_assignment.py:49-67 is a distinct table keyed on (employee_id, line_id, effective_date) with a Numeric(5,2) allocation_percentage and is_primary. Floating pool cannot express "employee X staffs line Y at 60%".

9. E2E: ls frontend/e2e — 22 specs, none touching line assignments; floating-pool.spec.ts covers the client-level pool only.

WHAT IS UNREACHABLE
backend/routes/employee_line_assignments.py:77 GET /, :115 GET /employee/{employee_id}, :138 GET /line/{line_id}, :165 POST /, :207 PUT /{assignment_id}, :245 DELETE /{assignment_id} — registered live at backend/bootstrap/routers.py:57,115, so they are served, not dead code. Real logic sits behind them: backend/crud/employee_line_assignment.py:51 validate_allocation enforces the 100% ceiling across concurrent assignments (:69 SUM of allocation_percentage, :78 exclude-self on update), :84 create_assignment, :293 update_assignment, :340 end_assignment. The route file even carries hand-written cross-tenant hardening (_authorize_assignment, _authorize_employee) — effort spent securing a surface no user can open. The table is registered auditable at backend/audit/registry.py:29 ("line staffing decisions") and is seeded (backend/seed/writers_master.py:240, backend/seed/coverage.py:30), so rows exist in the demo DB with no screen that shows or edits them.

The backend acknowledges the gap itself: backend/routes/my_shift.py:119 — "operator_id is accepted for forward-compatibility but currently ignored ... Wire up via EMPLOYEE_LINE_ASSIGNMENT when needed."

IMPACT: full CRUD, not just a missing write. A user cannot even READ who staffs which line. Line staffing with percentage splits, primary-line designation, and effective/end dating is auditable master data that exists only as seeder output; changing it in production requires direct DB or API access.

</details>

### Break time configuration per shift (name, start offset, duration, applies-to scope)

**Slice:** masters-admin

**Backend:** backend/routes/break_times.py:44 GET /api/break-times, :66 POST /api/break-times, :91 PUT /api/break-times/{break_id}, :119 DELETE /api/break-times/{break_id}. Backed by backend/crud/break_time.py:16 create_break_time, :130 update_break_time, :158 deactivate_break_time, :89 get_total_break_minutes, plus backend/schemas/break_time.py (BreakTimeCreate/Update with validated offsets and an ALL|EMPLOYEE|LINE pattern) and backend/orm/break_time.py. Rows are seeded (backend/seed/coverage.py:61).

**Why unreachable:** `grep -rn "break-times" frontend/src frontend/e2e` returns zero hits. No API service method, no store, no view, no router entry in frontend/src/router/index.ts, no nav item in frontend/src/App.vue:131-141.

**User impact:** Breaks are seeded per shift and are entirely invisible and unmanageable in the product. A plant cannot add a lunch break, change its length, or scope it to a line — even though the backend already computes total break minutes per shift, the input that number depends on can never be edited by a user. This compounds the missing Shifts screen: neither the shift nor its breaks can be configured.

<details><summary>verification</summary>

SEARCHES PERFORMED (all under frontend/):

1. Endpoint path + segment, whole directory: `grep -rniE "break.?times|BREAK_TIME|breakTime" . --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.git` => ZERO hits (src, e2e, public, configs all included).

2. Schema/ORM field names: break_name, breakName, break_id, breakStart, break_duration, applies_to, appliesTo across src + e2e => zero hits.

3. Synonyms both languages: descanso, pausa, lunch, almuerzo, comida, recess, rest-period => zero hits.

4. Bare token "break" across *.vue/*.ts/*.js/*.json in src + e2e: every hit is the JS keyword, a CSS property (word-break/page-break), or the unrelated equipment-failure "breakdown" domain — e.g. src/types/simulationV2.ts:52 BreakdownInput, src/stores/simulationV2Store.ts:237 addBreakdown, src/composables/useQualityData.ts:182 api.get('/quality/kpi/fpy-rty-breakdown'). None reach /api/break-times.

5. i18n: src/i18n/locales/en.json and es.json contain only breakdown* keys (lines 344,353,744,751,2229,3808,4008,4175...). No break-configuration strings exist to label any control.

6. EXHAUSTIVE API PATH INVENTORY: extracted every quoted path and every template-literal path passed to api.get/post/put/delete/patch across all .ts/.vue in src (~180 distinct paths). Full list reviewed; /break-times appears nowhere. Nearest neighbours present are /shifts, /shifts/, /employees, /floating-pool, /client-config/.

7. Router — frontend/src/router/index.ts: 13 admin routes exist (/admin/settings:166, /admin/users:172, /admin/clients:178, /admin/defect-types:184, /admin/part-opportunities:190, /admin/client-config:196, /admin/floating-pool:202, /admin/employees:208, /admin/workflow-config:214, /admin/workflow-designer:220, /admin/database:226, /admin/variance-report:232). No break-times route and no shifts route.

8. Nav — frontend/src/App.vue:131-141: the admin v-list-group holds exactly 11 v-list-items mirroring those routes. No break entry.

9. INDIRECT-REACH RULED OUT (the three plausible carriers):
   - src/services/api/admin.ts: covers only clients, users, kpi-thresholds, defect-types. No break methods.
   - src/views/admin/ClientConfigView.vue: `grep -niE "break|shift"` => ZERO occurrences of either word.
   - src/views/admin/DatabaseConfigView.vue (/admin/database): calls only /admin/database/providers and /admin/database/status — a DB-connection provider screen, NOT a generic table editor, so it cannot act as a back-door CRUD surface for the BREAK_TIME table.

BACKEND CAPABILITY CONFIRMED REAL AND REGISTERED:
- backend/bootstrap/routers.py:53 `from backend.routes.break_times import router as break_times_router`; :107 `app.include_router(break_times_router)`.
- backend/routes/break_times.py: prefix /api/break-times; GET "" (list_breaks, shift_id/client_id filters), POST "" (201, create_break), PUT /{break_id} (update_break), DELETE /{break_id} (204, soft delete). Per-tenant authz via _authorize_break -> verify_client_access.
- backend/schemas/break_time.py:11 BreakTimeCreate, :24 BreakTimeUpdate, :36 BreakTimeResponse; :19 applies_to validated `^(ALL|EMPLOYEE|LINE)$`.
- Service layer backend/services/break_time_service.py; CRUD backend/crud/break_time.py.
- First-class domain resource: BREAK_TIME listed in backend/seed/coverage.py:61 seed allowlist, plus backend/audit/registry.py, backend/db/soft_delete_registry.py, backend/alembic/versions/0001_real_baseline.py.

WRITE-GUARD POINT: POST/PUT/DELETE are guarded by get_current_active_supervisor — built explicitly for an interactive supervisor, which rules out the "admin script or cron by design" exemption. The intended human editor has no screen.

COMPOUNDING CLAIM ALSO VERIFIED: shifts are read-only in the UI. Only GETs exist — src/services/api/reference.ts:31 `api.get('/shifts/')` (30-min cached dropdown reference data) and src/composables/useShiftForms.ts:386 `api.get('/shifts')`. No POST/PUT/DELETE to /shifts anywhere. Neither the shift nor its breaks can be configured by a user.

</details>

### Linking operational production lines to capacity-planning lines (auto-sync, unlinked list, manual link, unlink)

**Slice:** masters-admin

**Backend:** backend/routes/production_lines.py:160 POST /api/production-lines/sync-capacity (auto-match by line_code, returns matched/unmatched), :183 GET /api/production-lines/unlinked, :202 POST /api/production-lines/{line_id}/link-capacity (LinkCapacityRequest with capacity_line_id), :234 DELETE /api/production-lines/{line_id}/link-capacity. Backed by backend/crud/production_line.py:243 link_to_capacity_line, :277 unlink_from_capacity_line, :303 auto_sync_lines, :373 get_unlinked_lines.

**Why unreachable:** `grep -rn "sync-capacity\|link-capacity\|production-lines/unlinked" frontend/src frontend/e2e` returns zero hits. frontend/src/services/api/productionLines.ts exposes only getProductionLines and getProductionLineTree. No admin route or nav item exists for line topology at all.

**User impact:** The product maintains two parallel line tables — PRODUCTION_LINE (operational, feeds data entry) and capacity_production_lines (feeds Capacity Planning) — and the backend ships the entire reconciliation toolkit to bridge them, including a one-click auto-sync and an 'unmatched' report. None of it is reachable. Any KPI or plan-vs-actual comparison that depends on an operational line being tied to its capacity counterpart silently works off whatever links the seeder created, and a user who adds a capacity line has no way to connect it to the floor.

<details><summary>verification</summary>

BACKEND EXISTS: backend/routes/production_lines.py:159 POST /sync-capacity, :183 GET /unlinked, :201 POST /{line_id}/link-capacity, :231 DELETE /{line_id}/link-capacity; CRUD at backend/crud/production_line.py:243 link_to_capacity_line, :277 unlink_from_capacity_line, :303 auto_sync_lines, :373 get_unlinked_lines; ORM column backend/orm/production_line.py:50 capacity_line_id; live route registration backend/tests/test_bootstrap/openapi_surface.json:917, 1629, 1633.

SEARCHES RUN, ALL ZERO HITS in frontend/src + frontend/e2e: (a) endpoint paths "sync-capacity", "link-capacity", "production-lines/unlinked"; (b) model/schema names "capacity_line_id", "capacityLineId", "capacity_production_line", "capacityProductionLine"; (c) synonyms "unlink", "autoSync", "auto-sync", "syncCapacity", "linkCapacity", "topology"; (d) same synonym set against both locale files frontend/src/i18n/locales/en.json and es.json (grep verified live via a control match: "capacity" hits 36x in en.json, "sync" 0x).

ONLY frontend contact with the router prefix: frontend/src/services/api/productionLines.ts:8 api.get('/production-lines/') and :12 api.get('/production-lines/tree'). Its sole consumer frontend/src/composables/useProductionLines.ts is read-only (one getProductionLines call, no writes), used by frontend/src/components/common/LineSelector.vue:25.

NEAR-MISSES RULED OUT: (1) The "productionLines" identifier throughout frontend/src/composables/useProductionLinesGridData.ts and frontend/src/stores/capacity/useWorkbookStore.ts:27 is the CAPACITY workbook worksheet (mapped to sheet 'production_lines', saved via PUT /capacity/workbook/{clientId}/production_lines) — a different table. Its column defs at useProductionLinesGridData.ts:83-145 are line_code, line_name, department, standard_capacity_units_per_hour, max_operators, efficiency_factor, is_active — no link field. (2) POST /work-orders/{id}/link-capacity IS UI-reachable (docs/audit/entry-surface-inventory.md:108, WorkOrderManagement.vue) but is an unrelated work-order capability. (3) No indirect trigger: the only backend callers of the four CRUD fns are these four routes plus pass-through wrappers backend/services/production_line_service.py:58,63,68,73; the capacity workbook save path never calls auto_sync_lines.

UNREACHABLE BY ROUTE/NAV: frontend/src/router/index.ts exposes 13 /admin/* routes (settings:166, users:172, clients:178, defect-types:184, part-opportunities:190, client-config:196, floating-pool:202, employees:208, workflow-config:214, workflow-designer:220, database:226, variance-report:232) — none for production lines or line topology. frontend/src/App.vue:132-142 renders nav items for exactly those, so there is not even an unlinked-but-typeable URL.

AGGRAVATING DETAIL: backend/schemas/production_line.py:26-36 ProductionLineUpdate omits capacity_line_id (only ProductionLineCreate:20 accepts it), so even a hypothetical line-edit screen could not repair a link — the four bridge endpoints are the only write path to that column, and none is reachable.

</details>

### Browsing the history of dual-view metric calculation results (GET /api/metrics/results with client_id / metric_name / period / limit filters)

**Slice:** kpi-analytics

**Backend:** backend/routes/metric_results.py:35 mounts prefix "/api/metrics/results"; GET "" list_results (line 116) is a filtered, client-scoped, ordered, paginated listing of persisted METRIC_CALCULATION_RESULT rows returning MetricResultBrief (standard vs site_adjusted value, delta, delta_pct, has_assumptions, calculated_at). Its sibling GET "/{result_id}" (line 147) returns full MetricLineage.

**Why unreachable:** frontend/src/services/api/metricResults.ts:64 defines listMetricResults, and its only reference anywhere is its own unit test (frontend/src/services/__tests__/metricResults.spec.ts:30) — no view, component, store, or composable calls it. Only the sibling getMetricLineage (metricResults.ts:67) is used, via frontend/src/composables/useMetricLineage.ts:26, and that composable is reached only with a result_id produced in the same session by frontend/src/components/dual_view/DualViewKPIPanel.vue:168-171. There is no route in frontend/src/router/index.ts for a results list and no view that renders one.

**User impact:** Every dual-view calculation is persisted with its inputs, assumptions applied, and standard-vs-adjusted delta, but a user can only inspect the one result the panel just computed on this page load. There is no way to look back at what OEE/OTD/FPY was calculated last week, compare deltas over time, or audit a number someone quoted in a meeting — the stored audit trail is write-only from the UI's point of view.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. Endpoint path + last segment, repo-wide across frontend/ and e2e/ (*.ts, *.vue, *.js, *.json): `grep -rn "metrics/results"` returns exactly four source hits — frontend/src/services/api/metricResults.ts:4 (docstring), :63 (comment), :65 (listMetricResults), :68 (getMetricLineage) — plus frontend/src/services/__tests__/metricResults.spec.ts:27,32,35,40 and one minified string inside the checked-in build output frontend/dist/assets/dualViewCalc-CWtgrvSk.js (which contains only the `/metrics/results/${e}` single-result call, not the list call — confirming the list call is tree-shaken out of the shipped bundle because nothing imports it).

2. Symbol names: `grep -rn "listMetricResults|metricResults|MetricResultBrief"` across frontend/src — `listMetricResults` appears only at services/api/metricResults.ts:64 and services/__tests__/metricResults.spec.ts:20,30. `MetricResultBrief` only at metricResults.ts:9,65. No store, view, or composable import.

3. ORM/model/schema names: `grep -rn "metric_calculation_result|MetricCalculationResult"` in backend/routes + backend/endpoints hits only backend/routes/metric_results.py — no second backend surface exposes the same rows, so no other UI screen can be covering it.

4. Router: frontend/src/router/index.ts has 38 `path:` entries (/kpi/oee, /kpi/quality, /kpi/on-time-delivery, /capacity-planning, /my-shift, /admin/settings, …). None is a metric-results / calculation-history / lineage-list route. `grep -n "results" router/index.ts` → no match.

5. Reverse check (is there a view that just isn't routed?): `ls frontend/src/views | grep -i "hist|audit|result"` → nothing. The only dual-view UI files are components/dual_view/{DualViewKPIPanel,DualViewToggle,MetricInspector}.vue and composables/{useMetricLineage,useDualViewInspector}.ts.

6. i18n: the entire `dualView` block in frontend/src/i18n/locales/en.json contains only `panel.*`, `toggle.*`, and `inspector.*` (title "Calculation Lineage", standard, siteAdjusted, formula, inputs, assumptions, …). There is no key for a results list, history, or browse screen — so no partially-built or hidden surface.

7. Nav/menu: no menu entry references a results list (no matching label in the dualView i18n tree; no route to link to).

WHY THE ONLY REACHABLE SIBLING DOESN'T COVER IT:
- frontend/src/composables/useMetricLineage.ts:15,26 calls only `getMetricLineage(resultId)`.
- Its two callers both feed it an id produced seconds earlier in the same session: components/dual_view/DualViewKPIPanel.vue:188-192 (`handleTileClick` → `inspectorResultId.value = result.result_id` from the just-awaited POST in `fetchAll`), and views/KPIDashboard.vue:275,402 via composables/useDualViewInspector.ts:88-108, whose `openForKpi` POSTs to `/metrics/calculate/from-period/{oee|otd|fpy}` (services/api/dualViewCalc.ts:104-110) and then does `resultId.value = response.data.result_id`. The composable's own header comment (useDualViewInspector.ts:8-15) documents exactly this: calculate → persist a new row → hand back its id.
- So every id the UI can ever pass to the lineage drawer is a row that was created by that same click. There is no code path that discovers an existing result_id.

BACKEND IS REAL AND MOUNTED: backend/routes/metric_results.py:35 `APIRouter(prefix="/api/metrics/results")`; `list_results` at line 116 with client_id/metric_name/period_start/period_end/limit(1-500) filters, `scope.filter(...)` client-scope authz (line 134), `order_by(calculated_at.desc())` (line 143), returning MetricResultBrief. Registered at backend/bootstrap/routers.py:64 and :301. Not health/metrics-internal, not cron/admin-script — it is documented in its own module docstring as the "Inspector API for Phase 4 dual-view UI ... filtered list (for tables/charts)", i.e. it was written for a UI table that was never built.

ONE HONEST QUALIFIER ON IMPACT (does not change reachability): the KPIDashboard inspector passes the user-chosen `dateRange` (KPIDashboard.vue:404), so a user CAN pick last week and click a KPI tile to see standard-vs-adjusted values for that period — but that RECALCULATES and persists a brand-new row rather than reading the stored one. Browsing what was actually calculated and by whom (the audit trail: past result_ids, deltas over time, comparing calculations), which is precisely what list_results provides, has no UI path at all.

</details>

### Per-KPI forecasting (GET /api/predictions/{kpi_type}) for the eight KPI detail screens other than Efficiency and Performance

**Slice:** kpi-analytics

**Backend:** backend/routes/predictions.py:264 GET /api/predictions/{kpi_type} explicitly supports efficiency, performance, availability, oee, ppm, dpmo, fpy, rty, absenteeism, otd, quality, and attendance, each with forecast values, confidence intervals, health assessment, recommendations, and benchmark comparison.

**Why unreachable:** frontend/src/services/api/predictions.ts:29 exposes getPrediction for all ten KPIType values, but it is called from exactly two places: frontend/src/composables/useEfficiencyData.ts:131 and frontend/src/composables/usePerformanceData.ts:127. The corresponding forecast toggle exists only in frontend/src/views/kpi/Efficiency.vue:159 and frontend/src/views/kpi/Performance.vue:155. The other six KPI detail views that the router exposes — views/kpi/OEE.vue, Availability.vue, Quality.vue, Absenteeism.vue, OnTimeDelivery.vue, WIPAging.vue — contain no occurrence of 'forecast' or 'Forecast' and never call getPrediction.

**User impact:** Forecasting is arbitrarily available on two of eight KPI screens. A user who learns the forecast toggle on the Efficiency page will look for it on OEE, Quality, or On-Time Delivery — the metrics people most want to project forward — and find nothing, even though the backend already serves those forecasts.

<details><summary>verification</summary>

SEARCHES RUN (all of frontend/src, case-insensitive): "prediction", "forecast", "getPrediction", "fetchPrediction", "fetchAllPredictions", "getAllPredictions", "getKPIHealth", "getPredictionBenchmarks", "/predictions", "dashboard/all", "crystal-ball", "Predictions" as a filename (find -iname), plus layouts/nav dirs and both i18n locale files.

BACKEND EXISTS AND DOES WORK:
- backend/routes/predictions.py:264 -> @router.get("/{kpi_type}", response_model=ComprehensivePredictionResponse); handler get_kpi_prediction at :298-357.
- backend/routes/predictions.py:322-323 validates kpi_type against [e.value for e in KPIType] + [e.value for e in KPITypePhase5]; backend/schemas/analytics.py:32 KPIType covers efficiency, performance, availability, oee, ppm, dpmo, fpy, rty, quality, absenteeism, otd, attendance. Returns build_comprehensive_prediction(...) with forecast values, confidence intervals, health, recommendations, benchmarks.

UNREACHABLE — PROOF:
- frontend/src/services/api/predictions.ts:28-29 getPrediction(kpiType, params) -> api.get(`/predictions/${kpiType}`).
- grep -rn "getPrediction" frontend/src => production call sites are exactly two: frontend/src/composables/useEfficiencyData.ts:131 (api.getPrediction('efficiency', params)) and frontend/src/composables/usePerformanceData.ts:127. All other hits are __tests__ files.
- UI toggles exist only at frontend/src/views/kpi/Efficiency.vue:148-159 (@change="onForecastToggle", forecastDays v-select @update:model-value="fetchPrediction") and frontend/src/views/kpi/Performance.vue:155.
- grep -rniE "predict|forecast|crystal-ball" over views/kpi/OEE.vue, Availability.vue, Quality.vue, Absenteeism.vue, OnTimeDelivery.vue, WIPAging.vue => EXIT=1, zero matches. Router exposes all of them: frontend/src/router/index.ts:54,60,66,72,78,84,90,96.
- frontend/src/composables/useChartForecastDataset.ts is imported only by useEfficiencyCharts.ts:25 and usePerformanceCharts.ts:27.
- frontend/src/views/KPIDashboard.vue: zero matches for predict|forecast (EXIT=1).
- No nav/menu entry: grep over frontend/src/layouts and frontend/src/components/layout => no such match (dirs absent / no hits).

STORE LAYER IS DEAD CODE OUTSIDE TESTS:
- frontend/src/stores/kpi.ts:144-155 declares a PredictionsMap with slots for all 11 KPIs; :680 fetchPrediction, :716 fetchAllPredictions, :762 getPredictionBenchmarks, :772 fetchKPIHealth. grep shows their only callers are frontend/src/stores/__tests__/kpi.spec.ts:330,344,352,366. No view or composable calls them.
- /predictions/dashboard/all (predictions.ts:31-32), /predictions/benchmarks (:34), /predictions/health/{kpi} (:36-37) likewise have zero non-test callers.

INERT CONTROL (makes it worse, not better):
- frontend/src/stores/dashboardStore.ts:57 and :70 register widget_key 'predictions' as a default-visible dashboard widget; :86 describes it as { name: 'Predictions', description: 'AI-powered forecasts', icon: 'mdi-crystal-ball', minRole: 'poweruser' }.
- frontend/src/components/dashboard/WidgetGrid.vue:208-211 resolves it via defineAsyncComponent(() => import('./widgets/Predictions.vue').catch(() => ({ template: '...AI Predictions...' }))).
- `ls frontend/src/components/dashboard/widgets/` => "No such file or directory". `find frontend/src -iname "*Predictions*"` returns only predictions.ts, its spec, and useChartForecastDataset.ts — no .vue. So the widget always falls through to a static placeholder div: a visible, role-gated dashboard tile that fetches nothing.
- Orphan locale key frontend/src/i18n/locales/en.json:906 "forecastsPredictions": "Forecasts & Predictions" (and es.json:906) is referenced nowhere in frontend/src — leftover intent, not a surface.

SCOPE CORRECTION TO THE AUDITOR'S CLAIM: WIPAging is not a supported kpi_type (no wip_aging in KPIType or KPITypePhase5 at backend/generators/sample_data_phase5.py:32-44), so the genuine gap is five detail screens (OEE, Availability, Quality, Absenteeism, OnTimeDelivery) plus attendance/ppm/dpmo/fpy/rty which have no forecast surface anywhere.

NEAR-MISSES CHECKED AND RULED OUT: SimulationV2View.vue:643,654,724,739 ("predicted_pcs_per_day", simulation output); components/alerts/AlertCard.vue:41-42,118 (alert.predicted_value from the alerts API); components/workflow/WorkOrderElapsedTime.vue:154-172 (metrics.forecast.expected_date from workflow metrics); components/dialogs/EmailReportsDialog.vue:180 (include_predictions flag in a report payload). None issues a request to /api/predictions/{kpi_type}.

</details>

### Floating-pool entry lifecycle and planning — POST /api/floating-pool (create entry), PUT /api/floating-pool/{pool_id}, DELETE /api/floating-pool/{pool_id}, GET /api/floating-pool/available/list, GET /api/floating-pool/check-availability/{employee_id}, GET /api/clients/{client_id}/floating-pool, POST /api/floating-pool/simulation/optimize-allocation, POST /api/floating-pool/simulation/shift-coverage, POST /api/floating-pool/upload/csv.

**Slice:** operations

**Backend:** backend/routes/floating_pool.py:72 POST create (supervisor), :103 GET /available/list, :113 GET /check-availability/{employee_id} (returns is_available + conflict_dates, documented 'Use this before attempting to assign an employee to prevent double-assignment errors'), :167 PUT /{pool_id}, :186 DELETE /{pool_id}, :238 GET /api/clients/{client_id}/floating-pool, :385 POST /simulation/optimize-allocation (optimization_goal maximize_coverage|minimize_overtime|balance_workload), :490 POST /simulation/shift-coverage. CSV import at backend/endpoints/csv_upload.py:797.

**Why unreachable:** The entire frontend touches exactly five floating-pool endpoints: frontend/src/composables/useFloatingPoolData.ts:192-193 api.get('/floating-pool') and api.get('/floating-pool/summary'); frontend/src/composables/useFloatingPoolGridData.ts:156 api.post('/floating-pool/assign') and :180 api.post('/floating-pool/unassign'); plus frontend/src/services/api/simulation.ts:9 api.get('/floating-pool/simulation/insights'). None of the nine endpoints above is called; no CSVUploadDialog for floating pool exists.

**User impact:** A supervisor can only toggle a pool row between assigned and unassigned. They cannot create or delete a pool entry, edit an availability window on an unassigned row (useFloatingPoolGridData.ts:16-18 admits the edit is 'local-only — no endpoint to set window without a client'), see one client's assignments, or bulk-load the pool. The two optimizer endpoints — allocate the pool across shifts to maximize coverage / minimize overtime, and simulate coverage for a specific shift — have no UI at all, so the pool's actual planning value is unreachable. And because check-availability is never called, the UI fires /assign blind and surfaces a double-assignment conflict only as a post-hoc error toast.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations/frontend/src): case-insensitive `floating.?pool|floatingPool|floating_pool` across every file; the literal path segments `floating-pool`, `available/list`, `check-availability`, `checkAvailability`, `optimize`, `shift-coverage`, `shiftCoverage`, `upload/csv`; the ORM/schema names `FloatingPool`, `FloatingPoolCreate`; both i18n locale files; router/index.ts; App.vue nav; every `api.get|post|put|delete` and template-literal (`api.post(\``) call site.

FULL SET OF FRONTEND FILES THAT MENTION FLOATING POOL (20): App.vue, components/AttendanceKPIs.vue, components/admin/FloatingPoolGuideDialog.vue, components/alerts/AbsenteeismAlert.vue, components/kpi/InferenceIndicator.vue, composables/useEmployeeAdminGrid.ts, composables/useFloatingPoolData.ts, composables/useFloatingPoolGridData.ts, services/api/simulation.ts, services/api/structuredErrors.ts, router/index.ts, i18n/locales/{en,es}.json, views/admin/{FloatingPoolManagement,AdminEmployees,PartOpportunities}.vue, plus 4 spec files.

EXACTLY FIVE ENDPOINTS ARE CALLED:
- frontend/src/composables/useFloatingPoolData.ts:192-193 — api.get('/floating-pool'), api.get('/floating-pool/summary')
- frontend/src/composables/useFloatingPoolGridData.ts:156,180 — api.post('/floating-pool/assign'), api.post('/floating-pool/unassign')
- frontend/src/services/api/simulation.ts:9 — api.get('/floating-pool/simulation/insights')
No other call exists, dynamic or literal.

REACHABLE PART (for fairness): frontend/src/App.vue:139 nav item -> frontend/src/router/index.ts:202-204 '/admin/floating-pool' -> views/admin/FloatingPoolManagement.vue. That screen reads entries + summary, renders insights, and inline-edits the Client cell to fire assign/unassign.

CONFIRMED UNREACHABLE, endpoint by endpoint:
1. POST /api/floating-pool (backend/routes/floating_pool.py:72) — no create path. FloatingPoolManagement.vue:216-219 states in its own docstring "pool membership is set elsewhere (employee admin), so this surface intentionally has no Add Row"; but that referenced surface, useEmployeeAdminGrid.ts, exposes only employee_id/employee_code/employee_name/department/labor_class (fields at :119,:126,:133,:139,:145) — is_floating_pool is NOT editable there either (backend/orm/employee.py:33 defines it; backend/schemas/employee.py:36 accepts updates to it; nothing in the UI sends it). Partial mitigation: POST /assign does insert a new row (backend/crud/floating_pool/assignments.py:104-113 `pool_entry = FloatingPool(...); db.add`), but the grid can only fire assign from a row that already came back from GET /floating-pool (useFloatingPoolGridData reads row.employee_id), so an in-pool employee with no FLOATING_POOL row can never get one.
2. PUT /{pool_id} (:167) — never called. useFloatingPoolGridData.ts:16-19 documents that editing available_from/available_to on an *unassigned* row is "local-only (no endpoint to set window without a client)" — the author was unaware PUT exists.
3. DELETE /{pool_id} (:186) — never called, and unassign is not a substitute: backend/crud/floating_pool/assignments.py:145-147 only nulls current_assignment and stamps available_to; the row persists. No UI can remove a pool entry.
4. POST /api/floating-pool/upload/csv (backend/endpoints/csv_upload.py:797) — the only CSV dialogs are Quality, Attendance, Downtime, Hold, Production (components/CSVUploadDialog*.vue:430/401/396/393/417) plus defect-types (services/api/admin.ts:70). No floating-pool dialog, no floating-pool upload call.
5. POST /simulation/optimize-allocation (:385) and 6. POST /simulation/shift-coverage (:490) — zero references. The only optimizer wired to a button is a different one: SimulationV2View.vue:1495-1509 -> services/api/simulationV2.ts:310 POST '/v2/simulation/optimize-operators' (per-station operator counts for a product mix), which does not take shift_requirements and does not consult the pool. The 'Floating Pool Coverage' card in components/AttendanceKPIs.vue:91-112 looks like coverage but is filled from hardcoded values (AttendanceKPIs.vue:156-157, comment "// Mock floating pool data") — it reaches no endpoint at all.
7. GET /check-availability/{employee_id} (:113) — never called; the 409 raised at assignments.py:82-101 is the user's only signal, surfaced post-hoc as an error toast.

WHERE THE CLAIM OVERSTATES (two of nine are covered elsewhere, do not count these):
- GET /available/list (:103) — useFloatingPoolData.ts:113-115 statusOptions + :212-217 filteredEntries filter unassigned rows client-side, and :119-132 availableEmployees reads summary.available_employees. Same information, reachable.
- GET /api/clients/{client_id}/floating-pool (:238) — useFloatingPoolData.ts:219-221 filters entries by client_id from the "Filter by client" v-select (FloatingPoolManagement.vue:159-170). Same result, reachable.

</details>

### Bulk work-order status transition — POST /api/workflow/bulk-transition, moving many work orders to a new status in one validated, audited operation.

**Slice:** operations

**Backend:** backend/routes/workflow.py:161-162 (@router.post('/bulk-transition'), bulk_transition_work_orders_endpoint), taking work_order_ids + to_status + notes and a client_id query param, delegating to the workflow engine's per-order validation.

**Why unreachable:** A service wrapper exists and is fully written — frontend/src/services/api/workflow.ts:25-40 exports bulkTransition, and it is re-exported in the default object at :84 — but it has ZERO callers: the only two occurrences of the identifier in all of frontend/src are its own definition and that re-export. The work-order screen has no multi-select: frontend/src/views/WorkOrderManagement.vue tracks a single `selectedWorkOrder` (:168, :220) feeding a detail drawer, and the only transition control is the per-row chip at frontend/src/components/workflow/WorkOrderStatusChip.vue:104, which calls the single-order transitionWorkOrder.

**User impact:** Classic dead wiring — the API client method was built and then never connected to a control. A planner closing out a shift must open and transition work orders one at a time through a drawer; releasing or completing a batch of 50 orders means 50 round trips. The backend already validates and audits the batch atomically, and none of that is reachable.

<details><summary>verification</summary>

BACKEND IS REAL AND USER-FACING
- backend/routes/workflow.py:161-183 — `@router.post("/bulk-transition", response_model=Dict)` / `bulk_transition_work_orders_endpoint(request: BulkTransitionRequest, client_id: str = Query(...), current_user: User = Depends(get_current_active_supervisor))`, delegating to `bulk_transition_work_orders(...)` then `db.commit()`. Docstring: "Transition multiple work orders to a new status... Returns results for each work order... SECURITY: Requires supervisor role." Not internal/cron/admin-script — it is role-gated for a human supervisor.
- backend/bootstrap/routers.py:42, 189 — `workflow_router` imported and `app.include_router(workflow_router)`, so the route is live.

DEAD CLIENT METHOD — EXACTLY TWO OCCURRENCES
`grep -rn "bulk-transition\|bulkTransition\|bulk_transition" frontend/src/` returns only three lines, all inside the service file itself:
- frontend/src/services/api/workflow.ts:25 (`export const bulkTransition = (`)
- frontend/src/services/api/workflow.ts:32 (the path string `'/workflow/bulk-transition'`)
- frontend/src/services/api/workflow.ts:84 (re-export in the default object)
Corroborating: `grep -rn "work_order_ids" frontend/src/` returns a single hit — workflow.ts:34, the request-body key inside that same unused function.

EVERY IMPORTER OF THE WORKFLOW SERVICE, ENUMERATED
`grep -rn "api/workflow" frontend/src/` yields 9 files; none imports bulkTransition:
- composables/useWorkOrderForms.ts:10 → `transitionWorkOrder` (single order; used at :157-159 `updateStatus`)
- components/workflow/WorkOrderStatusChip.vue:104 → `getAllowedTransitions, transitionWorkOrder` (single order)
- composables/useWorkflowConfigForms.ts:8 → `updateWorkflowConfig, applyWorkflowTemplate`
- composables/useWorkflowConfigData.ts:9-14 → `getWorkflowConfig, getWorkflowTemplates, getStatusDistribution, getClientAverageTimes`
- stores/workflowDesignerStore.ts:7-12 → `getWorkflowConfig, updateWorkflowConfig, getWorkflowTemplates, applyWorkflowTemplate`
- components/workflow/WorkOrderTransitionHistory.vue:125 → `getTransitionHistory`
- components/workflow/WorkOrderElapsedTime.vue:209 → `getWorkOrderElapsedTime`
- services/api/index.ts:31,51 → barrel `export * from './workflow'` / `import * as workflow` (a re-export, not a call; no dynamic dispatch found)

NO MULTI-SELECT ON THE WORK-ORDER SCREEN
- frontend/src/router/index.ts:126-128 exposes `/work-orders` → views/WorkOrderManagement.vue, so the screen exists.
- In that view, `grep -n "selectedWorkOrder\|rowSelection\|selectedRows\|getSelectedRows\|checkboxSelection\|multiple"` returns only :168 and :220 — the singular `selectedWorkOrder` feeding `<WorkOrderDetailDrawer>`. The `<AGGridBase>` at :154-163 passes columnDefs/rowData/pagination/`:enableExcelPaste="false"` and `@cell-value-changed` — no selection config, no bulk-action toolbar, no batch button.
- No fill-down escape hatch either: grep for `fillDown|Ctrl+D|key === 'd'` in composables/agGridExcelBehaviors.ts and composables/useAGGridBase.ts returns nothing.

NO ALTERNATE SURFACE COVERS THE CAPABILITY
- Repo-wide "bulk" search across frontend/src surfaces only unrelated features: attendance `bulkSetStatus` (composables/useAttendanceGridData.ts:659), grid paste helpers, capacity workbook save, CSV-upload copy strings.
- Synonym sweep (`batchTransition|massTransition|transitionMany|statusBatch|batch`) over services/ and stores/ hits only `/production/batch-import` (production.ts:25-26).
- The backend does expose a bulk import at backend/endpoints/csv_upload.py:542 (`/api/work-orders/upload/csv`), but `grep -rn "upload/csv" frontend/src/` lists only quality, attendance, downtime, holds, and production dialogs — there is no work-order CSV dialog, so that is not a covering surface either.

WHAT A USER CAN ACTUALLY DO (the honest nuance, which does not refute)
Status is inline-editable in the grid — composables/useWorkOrderGridData.ts:307-313 defines `field: 'status', editable: true, cellEditor: 'agSelectCellEditor'`. But its handler at :244-253 does `await api.put('/work-orders/${...}', buildUpdatePayload(...))` — one HTTP call per row, through the plain work-order PUT, which bypasses the workflow engine's per-order validation and transition audit entirely. So the batch semantics the endpoint provides (one validated, audited, committed operation over N orders) remain unreachable; the closest UI affordance is N unvalidated single-row writes.

</details>

### Work-order ↔ capacity-order cross-reference — GET /api/work-orders/{id}/capacity-order, POST /api/work-orders/{id}/link-capacity, POST /api/work-orders/{id}/unlink-capacity.

**Slice:** operations

**Backend:** backend/routes/work_orders.py:598-624 GET /{work_order_id}/capacity-order (response schema WorkOrderCapacityOrderResponse, returns linked flag plus order_number, customer, style, quantities, required_date, status, priority), :626-642 POST /link-capacity (requires capacity_order_id), :644-656 POST /unlink-capacity. Backed by backend/services/work_order_service.py get_capacity_order_link / link_to_capacity / unlink_from_capacity.

**Why unreachable:** No call to capacity-order, link-capacity or unlink-capacity anywhere in frontend/src. The only capacity_order_id occurrence is an unrelated v-select item-value in frontend/src/views/PlanVsActualView.vue:123. frontend/src/components/WorkOrderDetailDrawer.vue has no capacity-link section, and the Capacity Planning views (frontend/src/views/CapacityPlanning/) never reference work-order linkage.

**User impact:** The Capacity Planning module and the shop-floor Work Orders module cannot be tied together by any user. Nobody can link a work order to the capacity order it fulfills, unlink a mistaken link, or even see whether a link exists — so plan-vs-actual reconciliation between planned capacity and executed work orders has no user-driven path, despite the backend cross-reference being built (labelled 'Task 3.1') and available.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations)

1. Path strings and identifiers, across all of frontend/ (excluding node_modules, dist — i.e. src, e2e, tests, i18n locales, router included):
   grep -rn "capacity-order|link-capacity|unlink-capacity|capacity_order_id|capacityOrderId|linkCapacity|unlinkCapacity"
   → exactly 2 hits, both the same unrelated line:
     frontend/src/views/PlanVsActualView.vue:123  item-value="capacity_order_id"  (a v-data-table row key, not a call)
     frontend/coverage/views/PlanVsActualView.vue.html:774 (generated coverage mirror of that same line)
   Zero hits in frontend/src/services/**, frontend/src/stores/**, frontend/src/router/index.ts, frontend/e2e/**, frontend/src/i18n/locales/{en,es}.json.

2. Synonyms / model names: greps for "capacity" combined with "link", "workOrder", "work_order", "work-order" across every .vue and .ts in frontend/src → no combination hit. Grep for "capacity|Capacity" inside views/WorkOrderManagement.vue, components/WorkOrderDetailDrawer.vue, components/JobLineItems.vue → 0 matches in all three (the drawer has no capacity-link section, confirming the auditor).

3. The work-order API service is complete and closed: frontend/src/services/api/workOrders.ts (34 lines, read in full) exports exactly getWorkOrders, getWorkOrder, getWorkOrdersByStatus, getWorkOrdersByDateRange, createWorkOrder, updateWorkOrder, deleteWorkOrder, updateWorkOrderStatus, getWorkOrderProgress (/{id}/progress), getWorkOrderTimeline (/{id}/timeline), getClientWorkOrders. No /{id}/capacity-order, no /{id}/link-capacity, no /{id}/unlink-capacity. Its spec file services/__tests__/workOrders.spec.ts asserts the same closed set.

4. Alternative write surface ruled out. backend/schemas/work_order.py:85 (Create) and :137 (Update) do expose capacity_order_id, so a POST/PUT could in principle set the link — but the only frontend WO form does not include the field: frontend/src/composables/useWorkOrderForms.ts:13-26 WorkOrderFormData and :43-55 DEFAULT_FORM_DATA list 12 fields (work_order_id, client_id, style_model, planned_quantity, actual_quantity, status, priority, planned_start_date, planned_ship_date, customer_po_number, ideal_cycle_time, notes) — no capacity_order_id; openEditDialog (:98-113) rebuilds the same 12 and saveWorkOrder (:118-136) posts only that object. The only other writer, components/WorkOrderDetailDrawer.vue:434, sends a payload with no capacity field either.

5. Backend-side confirmation that these routes are the sole mutation path: grep -rn "capacity_order_id" backend --include="*.py" (non-test) shows the assignment sites are only backend/crud/work_order.py:437 (set) and :449 (clear), reached only via backend/services/work_order_service.py:97-99 / unlink_from_capacity, reached only via backend/routes/work_orders.py:626-642 and :644-656. No CSV-upload path, no capacity-side route, no admin script writes it. So no other UI surface can produce or remove a link.

6. Router/nav: frontend/src/router/index.ts has /work-orders (:126-128 → WorkOrderManagement.vue) and /plan-vs-actual (:154-156), and nothing else work-order related; neither view nor any nav entry mentions capacity linkage.

NOT INTERNAL BY DESIGN: all three routes take Depends(get_current_user) (backend/routes/work_orders.py:598-656), return user-facing display fields (order_number, customer_name, style_model, quantities, required_date, status, priority via WorkOrderCapacityOrderResponse in backend/schemas/workorder_contracts.py:38-64), and are labelled "Cross-Reference: Work Orders <-> Capacity Orders (Task 3.1)" — a product feature, not health/cron/admin tooling.

NUANCE THAT SOFTENS ONE CLAUSE OF THE CLAIM: the auditor says nobody can "even see whether a link exists". Aggregate-side, they partly can — backend/services/plan_vs_actual_service.py:97 counts WorkOrder.capacity_order_id == cap_order.id and surfaces it as linked_work_orders, rendered in frontend/src/views/PlanVsActualView.vue (expanded row, i18n key planVsActual.linkedWorkOrders, en.json:3804). That is a count per capacity order on a reachable screen; it does not identify which work orders, does not answer the GET's question (given a work order, which capacity order?), and gives no link/unlink control. The write half of the capability is unreachable without qualification.

</details>

### Bradford Factor absence-risk score — GET /api/attendance/kpi/bradford-factor/{employee_id}, returning bradford_score, absence spells and days from the real attendance history.

**Slice:** operations

**Backend:** backend/routes/attendance.py:568-569 (@router.get('/kpi/bradford-factor/{employee_id}'), response_model BradfordFactorResponse), with schema at backend/schemas/attendance.py:272-292 explicitly documenting the live path as GET /api/attendance/kpi/bradford-factor/{employee_id}, computed by backend/calculations/absenteeism.py::calculate_bradford_factor. It is the only bradford route in the backend.

**Why unreachable:** frontend/src/components/widgets/BradfordFactorWidget.vue:261 calls api.get('/kpi/bradford-factor', { params: { employee_id, ... } }) — wrong prefix (no /attendance) and employee_id as a query param rather than a path segment. No /api/kpi router defines bradford-factor (backend/routes/downtime.py:146 and backend/routes/holds.py:150 are the only /api/kpi routers, serving availability and wip-aging). The 404 is swallowed at :277-281, which logs only under import.meta.env.DEV and silently calls fetchAttendanceAndCalculate() (:283), recomputing the score client-side from raw api.get('/attendance') rows (:286, limit 1000).

**User impact:** The widget is a live, user-facing dashboard tile (registered at frontend/src/stores/dashboardStore.ts:50-82 and lazily mounted at frontend/src/components/dashboard/WidgetGrid.vue:194), so the failure is invisible: it always shows the browser-side fallback, never the server calculation. Numbers can silently disagree with the backend's canonical Bradford scoring, and the fallback is bounded by the client-side page limit of 1000 attendance rows — so for a long window or a busy employee the score is computed on truncated data and quietly understates absence risk.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations)

1. Case-insensitive "bradford" across the whole frontend tree (excluding node_modules/dist). Exactly 8 non-coverage-artifact files hit:
   - frontend/src/components/widgets/BradfordFactorWidget.vue (the only file that makes a network call)
   - frontend/src/components/DashboardOverview.vue:307,318,352 (mounts the widget)
   - frontend/src/components/dashboard/WidgetGrid.vue:194-196 (lazy registration)
   - frontend/src/stores/dashboardStore.ts:50,58,67,82 (widget catalog entry)
   - frontend/src/components/widgets/index.ts:10,25-30,51 (widget registry)
   - frontend/src/i18n/locales/en.json / es.json (copy only)
   - frontend/src/services/api/__tests__/no-raw-axios-import.spec.ts:9 (a comment naming the file)
   Zero hits in frontend/src/views, frontend/src/services, frontend/src/router, frontend/src/composables.

2. Path-shaped greps across frontend/src for "kpi/bradford", "bradford-factor", "attendance/kpi". The only "attendance/kpi" calls are absenteeism (useDashboardOverviewData.ts:77, AttendanceKPIs.vue:144, AbsenteeismAlert.vue:223, services/api/kpi.ts:545,651). Nothing constructs the /attendance/kpi/bradford-factor/{id} path — not by template literal, not by concatenation.

3. Synonyms/model names: searched the widget registry, dashboardStore catalog, router/index.ts, and the views directory for an absence-risk screen. frontend/src/views has one attendance-related file, AttendanceEntry.vue (702B), which contains no bradford reference.

BACKEND CONFIRMED REAL
- backend/routes/attendance.py:568 `@router.get("/kpi/bradford-factor/{employee_id}", response_model=BradfordFactorResponse)`; :569-613 does auth (verify_employee_access), 404s unknown employees, calls calculate_bradford_factor, and returns bradford_score plus a risk interpretation.
- backend/calculations/absenteeism.py:175-231 is the real computation over ATTENDANCE_ENTRY rows (is_absent OR is_late, spell gap detection, S^2 x D).
- backend/schemas/attendance.py:272,282-292 documents the live path.
- It is the ONLY bradford route: grep -rni bradford over backend/routes, backend/endpoints, backend/schemas, backend/crud, backend/calculations returns only attendance.py, absenteeism.py, the schema, and tests.

WHY THE ONE CALLER CANNOT REACH IT
- BradfordFactorWidget.vue:261 calls `api.get('/kpi/bradford-factor', { params: { employee_id, start_date, end_date } })`.
- frontend/src/services/api/client.ts:5 sets baseURL '/api/v1'; backend/bootstrap/app_config.py:35-72 (APIVersionMiddleware) strips /v1, so the request resolves to GET /api/kpi/bradford-factor.
- I enumerated every router mounted at prefix "/api/kpi" (backend/routes/kpi/{calculations,cause,dashboard,efficiency,labor_hours,otd,trends}.py plus holds.py:150 and downtime.py:146) and listed all their GET paths. None is "bradford-factor" and none is a catch-all that could match it (the closest, cause.py:33 "/{metric}/cause", requires a trailing /cause segment). The call is a hard 404. (Note: the auditor's claim that only downtime.py and holds.py mount /api/kpi is inaccurate — there are 10 such routers — but the conclusion holds, none serves bradford-factor.)
- The 404 is swallowed at :275-277 (console.warn gated behind import.meta.env.DEV) and falls through to fetchAttendanceAndCalculate() at :278.

THE FALLBACK IS ALSO DEAD — the widget shows a hardcoded 0, not a degraded estimate
- :286-294 fetches `/attendance` with params { employee_id, start_date, end_date, status: 'Absent', limit: 1000 }. backend/routes/attendance.py:107-119 accepts skip/limit/start_date/end_date/shift_date/employee_id/shift_id/is_absent/client_id — there is no `status` param, so FastAPI ignores it and returns unfiltered rows.
- :303 filters client-side on `r.status === 'Absent' || r.status === 'Late'` and :304/:315/:318 read `r.attendance_date`. backend/schemas/attendance.py:191-231 (AttendanceRecordResponse) has NEITHER field — the absence flags are `is_absent`/`is_late` and the date column is `shift_date`.
- Therefore the filter matches zero rows on every response, :306-311 fires, and score/spells/totalDays are all set to 0. The dashboard tile permanently renders "0 / Low risk" (:180 `if (score.value <= 50) return lowRisk`) regardless of actual absence history.
- Additionally, DashboardOverview.vue:318-323 passes only :date-range/:start-date/:end-date — no :employee-id — so even a fixed call would have no subject employee. And a second catch at :335-341 substitutes fabricated demo values (spells 3, days 8, score 72) while explicitly setting `error.value = null`.

IMPACT: a leader-visible dashboard tile (dashboardStore.ts:82, minRole 'leader') advertising "Employee absence patterns and risk scores" is inert. The backend's real, authorization-scoped Bradford calculation has no UI caller at all, and the screen that claims to show it displays a constant zero — i.e. it actively tells supervisors that nobody is an absence risk. This is a display-fabrication gap on top of an unreachable-capability gap.

</details>

### Per-job KPI endpoints — GET /api/jobs/{id}/efficiency, /performance, /ppm, /dpmo, /kpi-summary.

**Slice:** operations

**Backend:** backend/routes/jobs.py:239-240 get_job_efficiency (JobEfficiencyResponse), :311-312 get_job_performance (JobPerformanceResponse), :367-368 get_job_ppm (JobPPMResponse), :412-413 get_job_dpmo (JobDPMOResponse), :478-479 get_job_kpi_summary (JobKPISummaryResponse) — each a substantive calculation with its own response contract in backend/schemas/job_kpi_contracts.py.

**Why unreachable:** Only one of the six per-job KPI endpoints is ever called: frontend/src/components/JobLineItems.vue:261 api.get(`/jobs/${job.job_id}/yield`), which opens the yield dialog. The complete frontend call inventory contains no /jobs/{id}/efficiency, /performance, /ppm, /dpmo or /kpi-summary. JobLineItems.vue is the only jobs surface in the app and its table columns (:209-217) are job_id, part_number, progress, yield, quantity_scrapped, status, actions.

**User impact:** Job-level diagnosis stops at yield. When a work order's rolled-throughput-yield drops, a supervisor can see which job leaked units but cannot pull that job's efficiency, performance, PPM, DPMO or its consolidated KPI summary — the exact drill-down the endpoints were written for. All five calculations run only if someone hits the API by hand.

<details><summary>verification</summary>

BACKEND (capability is real and user-facing): backend/routes/jobs.py router prefix /api/jobs at :41, registered backend/bootstrap/routers.py:133. Endpoints: :239-240 get_job_efficiency, :311-312 get_job_performance, :367-368 get_job_ppm, :412-413 get_job_dpmo, :478-479 get_job_kpi_summary. Each aggregates ProductionEntry/QualityEntry rows and calls ProductionKPIService / calculate_ppm_pure / calculate_dpmo_pure + calculate_sigma_level_pure (dpmo also resolves part-specific opportunities via get_opportunities_for_part). Distinct response contracts at backend/schemas/job_kpi_contracts.py:124 JobEfficiencyResponse, :151 JobPerformanceResponse, :175 JobPPMResponse, :199 JobDPMOResponse, :281 JobKPISummaryResponse. All are plain Depends(get_current_user) GETs — not internal, cron, or admin-script.

SEARCHES RUN over frontend/src (excluding __tests__):
1. Endpoint paths: grep -rn "kpi-summary|kpi_summary|/dpmo|/ppm|/efficiency|/performance" — every hit is plant-level (/kpi/efficiency/trend, /kpi/performance/by-shift, /quality/kpi/ppm, /quality/kpi/dpmo) or an unrelated '@/utils/performance' import. Zero /jobs/ hits.
2. grep -rn "jobs/" and "${job" — the ENTIRE frontend contains exactly three job-related API calls: frontend/src/composables/useQualityData.ts:158 api.get('/jobs/kpi/rty-summary'); frontend/src/components/JobLineItems.vue:228 api.get(`/work-orders/${props.workOrderId}/jobs`); frontend/src/components/JobLineItems.vue:261 api.get(`/jobs/${job.job_id}/yield`).
3. Router: grep -n "job" frontend/src/router/index.ts returns ZERO lines — no job route exists, so not even URL-typing reaches a job screen directly.
4. Services: ls frontend/src/services/api/ contains no jobs.ts. workOrders.ts exposes /work-orders/{id}/progress and /timeline only.
5. Case-insensitive dpmo|sigma sweep of views/ + components/: only frontend/src/views/admin/components/PartOpportunitiesGuide.vue (static formula explainer, no API call) and frontend/src/components/DashboardOverview.vue:179 (plant-level kpiData.dpmo sourced from /quality/kpi/dpmo via useDashboardOverviewData.ts:79).
6. Dynamic path construction ruled out: grep -rnE 'get(`[^`]*\$\{[^}]+\}[^`]*\$\{[^}]+\}' yields only services/api/simulationScenarios.ts:75 and a non-HTTP Map.get at SimulationV2View.vue:1599.
7. Coverage-by-another-surface ruled out: grep "by-job|by_job|job_id" in frontend/src/services/api/kpi.ts + stores/kpi.ts = no matches; grep "by-job|by_job" in backend/routes/*.py = no matches. Plant-level KPI screens aggregate across plant/client and cannot be narrowed to a job.

UNREACHABILITY PROOF: The only jobs surface is JobLineItems.vue, used in exactly one place (WorkOrderDetailDrawer.vue:263, import at :359). Its headers computed at :209-217 are job_id, part_number, progress, yield, quantity_scrapped, status, actions. Its single row action (:113-122) calls loadJobYield(item) -> :261 /jobs/{id}/yield, opening the dialog at :129-168 which renders only total_units, good_units, scrapped_units, yield_percentage and interpretation. No efficiency, performance, PPM, DPMO or summary field is bound anywhere.

ADDITIONAL (same root cause): because JobLineItems reaches jobs through /work-orders/{id}/jobs, the list endpoint GET /api/jobs (jobs.py:56) and detail GET /api/jobs/{job_id} (jobs.py:71-72) are also never called from the frontend.

IMPACT: a supervisor who sees a job leaking units in the RTY/yield view has no in-app way to pull that job's efficiency, performance, PPM, DPMO or consolidated KPI summary — the drill-down these endpoints were written for runs only via a hand-issued API call.

</details>

### Chronic WIP holds — GET /api/kpi/chronic-holds, identifying holds active beyond a configurable threshold (default 30 days) to surface systemic pipeline problems.

**Slice:** operations

**Backend:** backend/routes/holds.py:391-411 (@wip_aging_router.get('/chronic-holds'), response_model List[ChronicHold], threshold_days param), delegating to identify_chronic_holds with multi-client scope handling.

**Why unreachable:** No call to chronic-holds anywhere in frontend/src. The WIP Aging view consumes only its three siblings — frontend/src/services/api/kpi.ts:167 api.get('/kpi/wip-aging/top'), plus api.get('/kpi/wip-aging') and api.get('/kpi/wip-aging/trend') — see frontend/src/composables/useWipTriadData.ts:10, whose comment names exactly the two endpoints the triad merges. No view or router entry references it.

**User impact:** The WIP Aging screen shows the current age distribution and the worst individual items, but the distinct 'these holds have been stuck past the threshold' analysis — with its own tunable threshold_days and its own calculation — cannot be run by a user. The seeder deliberately backdates chronic 60-70 day holds to make this visible, and the only screen that could show them doesn't ask for them.

<details><summary>verification</summary>

BACKEND EXISTS AND IS LIVE:
- backend/routes/holds.py:391-409 — @wip_aging_router.get("/chronic-holds", response_model=List[ChronicHold]), threshold_days: int = 30, scope-aware, returns identify_chronic_holds(db, threshold_days, client_id=..., client_ids=scope.client_ids).
- backend/calculations/wip_aging.py:426-500 — real query: filter(and_(active_as_of(today), HoldEntry.hold_date < snapshot_cutoff(threshold_date))), per-client fallback threshold = critical_threshold * 2, emits hold_id, work_order, aging_days, hold_reason, hold_category, threshold_days_used.
- backend/schemas/kpi_contracts.py:298-310 — class ChronicHold(BaseModel) with hold_id/work_order/product_id/quantity/aging_days/hold_reason/hold_category.
- backend/bootstrap/routers.py:127 — app.include_router(wip_aging_router) (mounted under /api/kpi).
- Only non-test caller of identify_chronic_holds is that one route (grep -rn "identify_chronic_holds" backend/ --include=*.py → backend/routes/holds.py:25 import, :409 call; all other hits are comments/docstrings). So it is not reachable via any other endpoint either.

SEARCHES PERFORMED, ALL NEGATIVE, ACROSS frontend/src:
1. grep -rin "chronic" frontend/src → exactly 2 hits, BOTH prose in a comment block: frontend/src/composables/useWipTriadData.ts:24 ("A production DB with 4 chronic holds 60-70 days old") and :28 ("no longer drop chronic holds"). Zero code references.
2. grep -rn "threshold_days|thresholdDays|ChronicHold" frontend/src → only admin client-config FIELDS: composables/useClientConfigData.ts:216,219,222,226-227 and useClientConfigForms.ts:23-24,101-102,228,238 (wip_aging_threshold_days / wip_critical_threshold_days). These write config values; none issues a request to chronic-holds.
3. Exhaustive literal-path enumeration: grep -rhno "'/kpi/[^']*'" frontend/src | sort -u → 60 distinct /kpi/* paths; chronic-holds is absent. Only WIP paths present: '/kpi/wip-aging' (kpi.ts:166, useDashboardOverviewData.ts:74), '/kpi/wip-aging/top' (kpi.ts:167,207), '/kpi/wip-aging/trend'.
4. Dynamic-path check: grep -rhno '`/kpi/[^`]*`' frontend/src → only `/kpi/${metricKey}/cause` and `/kpi/calculate/${entryId}`. Neither can ever resolve to chronic-holds.
5. i18n: grep -in "chronic" frontend/src/i18n/locales/en.json frontend/src/i18n/locales/es.json → ZERO hits in both locales. No menu item, tab, button, header, or tooltip label exists for the feature (this repo has an eslint no-raw-text gate, so any real UI surface would necessarily have a key here).
6. Router: frontend/src/router/index.ts has 38 path entries; the only WIP one is lines 60-62 (path '/kpi/wip-aging', name 'kpi-wip-aging', component views/kpi/WIPAging.vue). Nav drawer link is App.vue:119 to="/kpi/wip-aging". No chronic route, named or otherwise.
7. e2e/Playwright specs: no "chronic" reference.
8. Synonym sweep ("stuck", "systemic") in locales: no hits.

THE ONE "chronic" HIT OUTSIDE src IS DOCUMENTATION, NOT A CALL — AND AGGRAVATES THE GAP:
- frontend/dist/assets/HelpCenter-DHkIRkVj.js contains the literal "kpi/chronic-holds" (3 occurrences). Inspection of the surrounding text shows it is bundled user-guide markdown, not an axios call: "chronic holds** report (`/api/kpi/chronic-holds`) flags WOs held > N days", "scan the chronic-holds list and either resume or close out", "| `/api/kpi/chronic-holds` | Holds older than threshold |".
- Source of that text: docs/user-guide/03-data-entry.md:267,273 and docs/user-guide/02-dashboards.md:237, rendered in-app by frontend/src/views/HelpCenter.vue from frontend/src/help/index.ts. The shipped Help Center therefore tells users to work a "chronic-holds dashboard" that has no screen.

NOT COVERED BY THE SIBLING SURFACE (checked, since "fully covered elsewhere" would disqualify):
- WIPAging.vue:220-224 renders :items="wipData?.top_aging" from services/api/kpi.ts:167 api.get('/kpi/wip-aging/top').
- That endpoint is hard-capped: backend/routes/holds.py:268 `limit: int = SMALL_PAGE_SIZE` and backend/constants.py:14 `SMALL_PAGE_SIZE = 10`; the frontend passes no limit override (kpi.ts:167 forwards only date params). Any 11th+ chronic hold is invisible.
- Its columns are work_order/product/age/quantity only (useWIPAgingData.ts:52-57) — no hold_reason, no hold_category, which chronic-holds returns.
- grep -in "threshold" frontend/src/views/kpi/WIPAging.vue → ZERO hits: there is no control to set threshold_days, so the endpoint's tunable-threshold analysis cannot be run at any N.
- The other table (WIPAging.vue:163 :items="holdHistory", loaded via api.getHoldEntries in useWIPAgingData.ts:95-111) is a date-windowed hold log with reason/status, not an age-filtered list of currently-active chronic holds.

NOT AN EXCLUDED CATEGORY: it is not health/metrics/internal (it is a user-facing KPI analysis, authenticated with client scoping and documented in the end-user guide), and no admin script or cron calls it (the only caller is the HTTP route).

</details>

### Listing and reopening previously generated capacity schedules — GET /api/capacity/schedules and GET /api/capacity/schedules/{schedule_id} — and, as a consequence, committing any schedule outside the browser session that generated it (POST /api/capacity/schedules/{schedule_id}/commit).

**Slice:** capacity-simulation

**Backend:** backend/routes/capacity/analysis.py:276 GET /schedules (list, with status_filter/skip/limit), :324 GET /schedules/{schedule_id}, :298 POST /schedules (manual create), :349 POST /schedules/generate, :394 POST /schedules/{schedule_id}/commit. Schedules persist with a status lifecycle (CapacitySchedule.status, DRAFT vs COMMITTED).

**Why unreachable:** frontend/src/services/api/capacityPlanning.ts:407 getSchedules and :415 getSchedule exist; getSchedules has zero call sites anywhere in views/components/stores/composables. getSchedule is reached only by frontend/src/stores/capacity/useAnalysisStore.ts:230-247 (loadSchedule), which is re-exported at frontend/src/stores/capacityPlanningStore.ts:519-521 and 670 but is called by no component — grepping loadSchedule across frontend/src/views and /components returns nothing. store.activeSchedule is assigned in exactly three places (useAnalysisStore.ts:183 in generateSchedule, :239 in the uncalled loadSchedule, :345 reset-to-null); nothing sets it during workbook load. The Commit button is gated on it: frontend/src/views/CapacityPlanning/components/panels/SchedulePanel.vue:26 v-if="store.activeSchedule && store.activeSchedule.status !== 'COMMITTED'". Likewise createSchedule (capacityPlanning.ts:421) has zero call sites.

**User impact:** Schedules are effectively single-session objects. A planner who generates a draft schedule and then reloads the page, navigates away, or comes back the next day loses the Commit button entirely — there is no list, picker or link to reopen the schedule, so the draft can never be committed and its KPI commitments never created. Prior schedules are visible only as a flat, unselectable dump of detail rows in the Production Schedule sheet, with no way to open one, see its header/status, or act on it.

<details><summary>verification</summary>

SEARCHED (frontend/, incl. e2e and coverage, excluding node_modules/dist): terms "capacity/schedules", "getSchedules", "getSchedule", "createSchedule", "loadSchedule", "activeSchedule", "commitSchedule", "schedules"; find -iname "*schedul*"; router/index.ts; App.vue nav.

1) getSchedules — frontend/src/services/api/capacityPlanning.ts:390 (GET '/capacity/schedules' at :394). Only other references repo-wide: barrel re-export :605; unit test src/services/__tests__/capacityPlanning.spec.ts:865,876; vi.fn() mock src/stores/__tests__/capacityPlanningStore.spec.ts:57. No view/component/store/composable/router call site.

2) createSchedule — capacityPlanning.ts:405 (POST '/capacity/schedules'); same pattern: barrel :607 + tests (:898) only. Zero product call sites.

3) getSchedule — capacityPlanning.ts:398; single caller frontend/src/stores/capacity/useAnalysisStore.ts:235 inside loadSchedule (:230), re-exported frontend/src/stores/capacityPlanningStore.ts:519-521 and :670. Grep "loadSchedule" across all frontend/src returns ONLY those store definitions plus stores/__tests__/capacityPlanningStore.spec.ts:1333,1340. The view's composable frontend/src/composables/useCapacityData.ts returns runCapacityAnalysis, generateSchedule, handleCommitSchedule, handleReset — loadSchedule is absent.

4) activeSchedule assigned only at useAnalysisStore.ts:183 (generateSchedule), :239 (uncalled loadSchedule), :345 (reset to null). Read frontend/src/stores/capacity/useWorkbookStore.ts:59-108 in full: loadWorkbook maps the 13 WORKSHEET_MAPPING sheets into wsOps.worksheets and never touches activeSchedule. Commit gate: views/CapacityPlanning/components/panels/SchedulePanel.vue:26 v-if="store.activeSchedule && store.activeSchedule.status !== 'COMMITTED'"; handler useCapacityData.ts:186-187 `const activeId = (store.activeSchedule as {id?: string|number}|null)?.id; if (!activeId) return`.

5) No surface: router/index.ts:160-161 single '/capacity-planning' route, no :scheduleId param; App.vue:80 single nav item to /capacity-planning. find -iname "*schedul*" in frontend/src returns 4 files — SchedulePanel.vue, ScheduleCommitDialog.vue, components/simulation/ScheduleForm.vue (+test); ScheduleForm.vue:193 imports only useSimulationV2Store, no capacity API. SchedulePanel.vue onMounted only seeds default dates; sole entry point is the Generate dialog.

6) Flat-dump confirmed: backend/routes/capacity/kpi_workbook.py:329-345 returns schedule_id/schedule_name/schedule_status into worksheets.productionSchedule.data, rendered by SchedulePanel.vue:229 as a v-data-table with no row-selection handler and no binding to activeSchedule. Supporting defect: the panel's headers request planned_quantity and sequence_number while the backend supplies scheduled_quantity and sequence (confirmed absent from backend/schemas + backend/orm/capacity), so those columns render blank — evidence the surface is unexercised.

Backend capability confirmed real: backend/routes/capacity/analysis.py:276 list_schedules (status_filter/skip/limit), :298 create_schedule, :324 get_schedule, :349 generate_schedule, :394 commit_schedule, over ORM backend/orm/capacity/schedule.py CapacitySchedule with DRAFT/COMMITTED ScheduleStatus lifecycle.

</details>

### Editing a saved simulation scenario in place. PUT /api/v2/simulation/scenarios/{scenario_id} accepts a SimulationScenarioUpdate (name, description, config_json, tags, is_active) and updates the stored record, including archiving via is_active.

**Slice:** capacity-simulation

**Backend:** backend/routes/simulation_scenarios.py:135-148 defines update_scenario_endpoint, guarded by get_current_active_supervisor plus _check_write_permission, calling crud.update_scenario(...) with payload.model_dump(exclude_unset=True) and committing. The list endpoint at simulation_scenarios.py:73 accepts include_inactive, which only means anything if something can set is_active=false.

**Why unreachable:** frontend/src/services/api/simulationScenarios.ts:91-99 exports updateScenario and it is re-exported in the default object at line 119, but grepping updateScenario across frontend/src/views, /components, /stores and /composables (excluding __tests__) returns zero call sites. The only scenario API calls in frontend/src/views/SimulationV2View.vue are createScenario (line 1743), listScenarios (1758), getScenario (1780), runScenario (1801), duplicateScenario (1827) and deleteScenario (1840). handleSaveScenario (SimulationV2View.vue:1725-1753) unconditionally builds a fresh payload and calls createScenario — there is no update branch and no notion of a currently-loaded scenario id to save back to. The scenario list dialog (SimulationV2View.vue:1094-1110) offers only load/run/duplicate/delete actions and never passes include_inactive.

**User impact:** Loading a saved scenario, tweaking the config, and clicking Save silently creates a second scenario rather than updating the one you opened, so the list accumulates near-duplicate entries. A scenario's name, description or tags can never be corrected after creation, and there is no way to archive one (is_active=false) — the only cleanup is permanent deletion.

<details><summary>verification</summary>

SEARCHED AND ABSENT (repo /Users/mcampos.cerda/Developer/Programming/kpi-operations):
1) `grep -rn updateScenario frontend/src` returns only the definition and re-export in frontend/src/services/api/simulationScenarios.ts:91 and :119, plus test-only hits in frontend/src/services/__tests__/simulationScenarios.spec.ts:17,114,116. Zero call sites in views/components/stores/composables.
2) Endpoint path: BASE = '/v2/simulation/scenarios' declared once at frontend/src/services/api/simulationScenarios.ts:60. No raw api.put() against any scenarios path exists anywhere in frontend/src.
3) Only importer of the service is frontend/src/views/SimulationV2View.vue:1355; its import block (lines 1347-1355) is exactly listScenarios, createScenario, getScenario, deleteScenario, duplicateScenario, runScenario — updateScenario is not imported.
4) Router: frontend/src/router/index.ts:144-151 maps /simulation to SimulationV2View.vue (+ /simulation-v2 redirect). The view is reachable; the update call is not made from it.
5) No store/composable path: `grep scenario frontend/src/stores/simulationV2Store.ts` returns nothing.
6) View state: no currentScenarioId / loadedScenarioId / editingScenario ref exists in the 2045-line SimulationV2View.vue. handleLoadScenario (1773+) pushes config_json into the store and records no id; handleSaveScenario (1725-1752) unconditionally calls createScenario.
7) Drawer template SimulationV2View.vue:1094-1135 renders four icon buttons only: mdi-download (load), mdi-play (run), mdi-content-copy (duplicate), mdi-delete (delete). refreshScenarios calls listScenarios({ limit: 200 }) — include_inactive is never passed.
8) i18n: dumped simulationV2.scenarios from frontend/src/i18n/locales/en.json — action keys are exactly load/run/duplicate/delete; no edit, rename, update or archive key in en or es.
9) Synonym / adjacent-surface check: frontend/src/views/CapacityPlanning/components/panels/ScenariosPanel.vue and frontend/src/services/api/capacityPlanning.ts:439-521 are a different backend family (/capacity/scenarios: get/create/compare/run/delete) and never touch /v2/simulation/scenarios. No e2e spec references the simulation scenarios endpoints (frontend/e2e/capacity-scenarios.spec.ts is the capacity feature).

CORRECTIONS TO THE CLAIM: backend/crud/simulation_scenario.py:160-169 delete_scenario sets scenario.is_active = False (soft delete), so "no way to archive" and "only cleanup is permanent deletion" are false, as is the inference that include_inactive is meaningless without PUT. The en.json confirmDelete string itself says the scenario is "soft-deleted and recoverable by an admin" — a promise no screen honors, since restoring requires the uncallable PUT.

</details>

### Alert configuration per client — list and create per-client alert settings (alert type, enabled flag, warning/critical thresholds, email/SMS notification flags, check frequency)

**Slice:** alerts-reports

**Backend:** backend/routes/alerts/config_history.py:45 `GET /api/alerts/config` (list, client-scoped via `verify_client_access`) and :61 `POST /api/alerts/config` (`get_current_active_supervisor`). Full stack behind it: ORM backend/orm/alert.py:69 `class AlertConfig` (ALERT_CONFIG table, columns enabled / warning_threshold / critical_threshold / notification_email / notification_sms / check_frequency_minutes), schemas backend/schemas/alert.py:188-211 (`AlertConfigBase`/`AlertConfigCreate`/`AlertConfigResponse`). The route file even carries a comment documenting a bug fixed on `/config`'s path spelling — it was exercised and repaired, then never wired up. The seeder populates it: backend/seed/emitters_alerts.py:39-50 defines 5 configs (otd, quality, efficiency, capacity, hold) and :170 emits one per client.

**Why unreachable:** `grep -rn "alerts/config" frontend/src` → 0 hits. The alerts UI (frontend/src/views/AlertsView.vue → frontend/src/components/alerts/AlertDashboard.vue) has only category/severity/status view filters and a 'Check Now' button; frontend/src/composables/useAlertDashboardData.ts:62,74 and useAlertDashboardActions.ts:27,40,59,81 call only `/alerts/`, `/alerts/summary`, `/alerts/generate/check-all`, and the acknowledge/resolve/dismiss actions. Neither admin screen touches it: `grep -i alert frontend/src/views/admin/ClientConfigView.vue` finds only `<v-alert>` UI banners.

**User impact:** Exactly the EQUIPMENT pattern: rows are seeded into a feature with no screen (5 per client). A supervisor cannot disable a noisy alert type, cannot set per-client warning/critical thresholds for alerts, and cannot choose email vs SMS notification per alert type. The generic KPI-threshold screen (AdminSettings) is a different table (KPI_THRESHOLD) and exposes none of enabled / notification_email / notification_sms / check_frequency_minutes.

<details><summary>verification</summary>

SEARCHES RUN (all negative):
1. `grep -rni "alerts/config|alert_config|alertconfig|ALERT_CONFIG" frontend --exclude-dir=node_modules --exclude-dir=dist` -> single hit, and it is a COMMENT not a call: frontend/e2e/alerts.spec.ts:10 "ALERT, ALERT_CONFIG and ALERT_HISTORY were empty in every demo".
2. Column-name search across all of frontend/src: `notification_email|notificationEmail|notification_sms|notificationSms` = 0 hits; `check_frequency|checkFrequency` = 0 hits. These four fields exist nowhere in the frontend.
3. `warning_threshold|critical_threshold` hits only frontend/src/composables/useKPIDashboardData.ts:23-24, fed by api.getKPIThresholds() -> frontend/src/services/api/admin.ts:22-24 `GET /kpi-thresholds` (+ :27 PUT, :30 DELETE). That is the KPI_THRESHOLD table, a different capability, and it carries none of enabled/notification_email/notification_sms/check_frequency_minutes. Confirms the auditor's "different table" point.
4. Complete inventory of /alerts call sites in the app: useAlertDashboardData.ts:62 `/alerts/?params`, :74 `/alerts/summary`; useAlertDashboardActions.ts:27 `/alerts/generate/check-all`, :40 `/alerts/{id}/acknowledge`, :59 `/alerts/{id}/resolve`, :81 `/alerts/{id}/dismiss`; services/api/kpi.ts:661 `/alerts/`. No dynamic path can resolve to /config (templated segments are always `/alerts/${alertId}/<action>`).
5. `ls frontend/src/services/api/` = 29 modules (admin, kpi, reports, workOrders, ...) and there is NO alerts service module at all.
6. frontend/src/router/index.ts: only alert-related route is :138-139 path '/alerts' name 'alerts' -> views/AlertsView.vue, which is a 10-line wrapper around components/alerts/AlertDashboard.vue. AlertDashboard's only controls are :28 help button, :31 generateAlerts, :40/:49/:56 category/severity/status view filters, :114 guide dialog. No config surface, no admin route for it.
7. i18n sweep of frontend/src/i18n/locales/{en,es}.json (190K/209K): no keys for alert enable / per-type threshold / SMS / check frequency.

THE ONE LEAD CHASED, WHICH AGGRAVATES RATHER THAN REFUTES:
en.json:1603 "alertOnThresholdBreach" is used at frontend/src/views/admin/AdminSettings.vue:170-171, in a "Notifications" v-card (:155-196) with switches emailNotifications (:163), alertOnThresholdBreach (:170), dailyReportEnabled (:176) and a Save button (:192 @click="saveNotificationSettings"). That handler is INERT:
  frontend/src/views/admin/AdminSettings.vue:465-475
    const saveNotificationSettings = async () => {
      saving.value = true
      try {
        await new Promise(resolve => setTimeout(resolve, 500))
        showSnackbar(t('admin.settings.notificationSettingsSaved'))
      } catch { showSnackbar(t('admin.settings.failedToSave'), 'error') }
      finally { saving.value = false }
    }
No API call. State lives in a local ref at :323-336 and is lost on navigation. Sibling handlers saveGeneralSettings (:453) and saveDataSettings (:477) are identical fakes; exportData (:489) only shows a snackbar. So the only notification UI in the product reports "Notification settings saved successfully" while persisting nothing, and still never touches ALERT_CONFIG.

NOT COVERED BY ANOTHER SURFACE: the admin ClientConfigView path uses useClientConfigData.ts:73 `/clients`, :86 `/client-config/defaults`, :102 `/client-config/{id}` -> backend/orm/client_config.py:27 ClientConfig, a different table whose only alert-adjacent field is wip_critical_threshold_days (useClientConfigForms.ts:24,102,238).

BACKEND IS REACHABLE AND EXERCISED: the route file even documents a path-spelling bug that was found and repaired (config_history.py:38-44, "/config/" never matched /api/alerts/config and GET /api/alerts/{alert_id} full-matched first, answering 404). And backend/seed/emitters_alerts.py:35-50 defines the 5 configs with the comment "a configuration screen where every row is on never shows what a disabled row looks like" -- seed data deliberately shaped for a configuration screen that was never built, emitted per client at :170.

</details>

### Domain-scoped KPI reports — production, quality, and attendance reports in both PDF and Excel, plus the report catalog that advertises them

**Slice:** alerts-reports

**Backend:** Six generating endpoints, each narrowing the KPI set: backend/routes/reports/production_reports.py:38 `GET /api/reports/production/pdf` (`production_kpis = ["efficiency","performance","availability","oee"]`) and :96 `/production/excel`; backend/routes/reports/kpi_reports.py:34 `/quality/pdf` (`quality_kpis = ["fpy","rty","ppm","dpmo"]`), :90 `/quality/excel`, :141 `/attendance/pdf` (`attendance_kpis = ["absenteeism"]`), :195 `/attendance/excel` (`sheets=["summary","attendance"]`). All stream real output from `PDFReportGenerator`/`ExcelReportGenerator` with per-type filenames and an `X-Report-Type` header. backend/routes/reports/comprehensive_reports.py:141 `GET /api/reports/available` returns a catalog naming all four report types and their endpoints.

**Why unreachable:** `grep -rn "reports/production|reports/quality|reports/attendance|reports/available" frontend/src` → 0 hits each. The only report calls in the app are the comprehensive pair and the email send: frontend/src/composables/useKPIReports.ts:55 `/reports/comprehensive/pdf`, :78 `/reports/comprehensive/excel`, :125 `/reports/send-manual`, and frontend/src/services/api/reports.ts:4 `/reports/comprehensive/excel`. The only report UI is the 3-item menu at frontend/src/views/KPIDashboard.vue:64-84 (Export PDF → downloadPDF, Export Excel → downloadExcel, Email) and the Excel button at frontend/src/views/DashboardView.vue:145-152 — no report-type picker anywhere. The `/export/*` CSV routes (frontend/src/services/api/csvExport.ts) are raw entity row dumps, not computed-KPI reports, so they do not cover this.

**User impact:** A quality manager who wants an FPY/RTY/PPM/DPMO-only report, or an HR lead who wants an absenteeism-only report, must take the everything-included comprehensive report instead. Six working report generators and a self-describing catalog endpoint are dead weight; the backend literally publishes a menu of reports at /api/reports/available that no screen ever reads.

<details><summary>verification</summary>

WHAT I SEARCHED (all negative for a reachable call):

1. Endpoint paths, whole frontend/src: `grep -rnE "reports/production|reports/quality|reports/attendance|reports/available"` -> 0 hits.
2. Dynamic path construction (the main way a grep for literals can be fooled): `grep -rnE '/reports/\$\{|reports/\$|report_type|reportType'` across *.ts/*.vue/*.js -> only useKPIReports.ts:55 `/reports/comprehensive/pdf` and :78 `/reports/comprehensive/excel`. Both templates hardcode "comprehensive"; no variable path segment exists anywhere.
3. All report calls in the app (grep -rn "reports/" frontend/src, excluding tests): useKPIReports.ts:55, :78, :125 (/reports/send-manual); services/api/reports.ts:4 (/reports/comprehensive/excel), :19/:31/:34 (/reports/email-config), :36 (email-config/test), :39 (send-manual). That is the complete set — comprehensive + email config only.
4. Router: `grep -i report frontend/src/router/index.ts` -> only /admin/variance-report (AssumptionVarianceReport.vue, unrelated). No reports route.
5. Views/components: `ls frontend/src/views | grep -i report` -> none. `find frontend/src/components -iname '*report*'` -> only dialogs/EmailReportsDialog.vue.
6. All download entry points: `grep -rniE "downloadPDF|downloadExcel|exportPDF|exportExcel"` -> KPIDashboard.vue:72/76 (the 3-item menu at lines 64-84, hardcoded to downloadPDF/downloadExcel), DashboardView.vue:150 -> api.exportExcel -> reports.ts:4 (comprehensive). No report-type picker exists.
7. i18n: `grep -rniE '"(production|quality|attendance)Report"|reportType|Production Efficiency Report|Quality Metrics Report|Absenteeism Report' frontend/src/i18n/locales/*.json` -> 0 hits.
8. Email path as an alternate route: backend/routes/reports/_models.py:43-49 `ManualReportRequest` has only client_id, start_date, end_date, recipient_emails — NO report_type field. So /reports/send-manual cannot select a domain report either. EmailReportsDialog.vue calls only getEmailReportConfig (:205), saveEmailReportConfig (:251), sendTestEmail (:274).

THE ONLY FRONTEND MENTION IS INERT DOCUMENTATION:
`grep` across all of frontend/ (including dist) found the endpoints in frontend/dist/assets/HelpCenter-*.js:2014-2016, 2150-2161. Source is docs/user-guide/08-reports.md, loaded by frontend/src/help/index.ts via `import.meta.glob('../../../docs/user-guide/*.md', {query:'?raw'})` and rendered at frontend/src/views/HelpCenter.vue:66 `v-html="renderedHtml"` (marked.parse, HelpCenter.vue:130-143), routed at router/index.ts:238-240 `/help/:id?`.

This is NOT reachability: the endpoint paths appear inside markdown backticks (`/api/reports/quality/pdf`), so marked renders them as <code> elements, never anchors. The only click handler (HelpCenter.vue:146-154) intercepts `a[href]` and acts solely on hrefs starting with '/help/'. There is no anchor, no fetch, no download — it is prose describing an API.

AGGRAVATING FINDING (makes the gap worse, not better):
docs/user-guide/08-reports.md:12 tells users "You access them via the **Email Reports Dialog** on the Home dashboard", and :36-45 gives explicit steps: "### From the UI / 1. Open Home (`/`) / 2. Click **Email Reports** (top-right) / 3. Choose: - Report type - Format (Excel / PDF) - Date range - Recipients / 4. **Send Now** OR **Schedule**".

None of that UI exists. EmailReportsDialog.vue contains only: an enable toggle (:39), a frequency v-select (:48-53, daily/weekly/monthly), a delivery-time field (:61), a recipients v-combobox (:73), and a test-email field (:103). Its buttons are Close (:8), Send Test (:110), Cancel (:129), Save Configuration (:131). There is no report-type selector, no format selector, and no "Send Now"/"Schedule" button. The shipped user guide documents a control that was never built.

CONCLUSION: The claim stands. Six working generators plus a self-describing catalog endpoint are unreachable — and the product ships user-facing documentation promising a report-type picker that does not exist, so a quality manager following the manual will hunt for a control that is absent rather than merely settling for the comprehensive report.

</details>

### Alert prediction accuracy history — how accurate the system's predictive alerts have actually been (accuracy rate %, average error %, per-category, over a configurable lookback)

**Slice:** alerts-reports

**Backend:** backend/routes/alerts/config_history.py:92-145 `GET /api/alerts/history/accuracy` — queries ALERT_HISTORY (backend/orm/alert.py, `class AlertHistory`) for rows with a recorded `actual_value`, joins Alert for the optional category filter, and returns `total_predictions`, `accurate_predictions`, `accuracy_rate_percent`, `average_error_percent` via `AlertsHistoryAccuracyResponse`. The seeder writes the history rows it reads (backend/seed/emitters_alerts.py:27,239 `AlertPredictionRecorded`).

**Why unreachable:** `grep -rn "alerts/history" frontend/src` → 0 hits. The only 'accuracy' surfaces in the frontend are `predictionData.model_accuracy` at frontend/src/views/kpi/Performance.vue:191 and frontend/src/views/kpi/Efficiency.vue:195, which come from the separate /api/predictions endpoints, not from alert history. frontend/src/views/AlertsView.vue renders only `<AlertDashboard />`, which has no history or accuracy panel.

**User impact:** Users are asked to act on predictive alerts but can never see whether those predictions have been right. The one endpoint that would build (or destroy) trust in the alert engine is invisible, and the seeded prediction-accuracy data it reads is never displayed.

<details><summary>verification</summary>

SEARCHES RUN (frontend/src unless noted), all via grep -rn:
- "alerts/history" -> 0 hits in frontend/src (2 hits only in frontend/dist/assets/HelpCenter-DHkIRkVj.js, which is the compiled copy of the markdown user guide, not a call)
- "history/accuracy" -> 0 hits in frontend/src
- "accuracy" case-insensitive -> 5 non-matching hits: i18n key kpi.modelAccuracy (en.json:398, es.json:398), en.json:591 hintText, en.json:1760/es.json:1760 admin.partGuide.accuracyWarning (rendered at views/admin/components/PartOpportunitiesGuide.vue:154), and views/kpi/Performance.vue:190-191 + views/kpi/Efficiency.vue:194-195
- "AlertHistory" / "alert_history" / "prediction_accuracy" / "predictionAccuracy" -> 0 hits
- "'/alerts | \"/alerts | `/alerts | /api/alerts" -> 8 hits, the complete call inventory (below)
- "accuracy|history" -i over frontend/src/components/alerts/*.vue -> 0 hits

COMPLETE FRONTEND /alerts CALL INVENTORY (8 hits, none is the accuracy endpoint):
- frontend/src/composables/useAlertDashboardData.ts:62  GET /alerts/?<filters>
- frontend/src/composables/useAlertDashboardData.ts:74  GET /alerts/summary
- frontend/src/composables/useAlertDashboardActions.ts:27  POST /alerts/generate/check-all
- frontend/src/composables/useAlertDashboardActions.ts:40  POST /alerts/{id}/acknowledge
- frontend/src/composables/useAlertDashboardActions.ts:59  POST /alerts/{id}/resolve
- frontend/src/composables/useAlertDashboardActions.ts:81  POST /alerts/{id}/dismiss
- frontend/src/services/api/kpi.ts:661  GET /alerts/ (per-KPI widget)
- frontend/src/App.vue:106 / router/index.ts:138  nav + route only

NAVIGATION TRACE PROVING ABSENCE:
- frontend/src/App.vue:106  <v-list-item prepend-icon="mdi-bell-alert" :title="$t('navigation.alerts')" value="alerts" to="/alerts" />  -- the ONLY alerts nav entry
- frontend/src/router/index.ts:138-142  path '/alerts' -> views/AlertsView.vue (no child routes, no other alert route)
- frontend/src/views/AlertsView.vue:8  template body is a header plus <AlertDashboard /> and nothing else
- frontend/src/components/alerts/AlertDashboard.vue  317 lines; imports only useAlertDashboardData (line 134, destructured line 148) and useAlertDashboardActions (line 135, line 161); zero occurrences of "accuracy" or "history". No accuracy panel/tab/dialog exists.

THE NEAR-MISS IS A DIFFERENT DATA SOURCE:
- frontend/src/views/kpi/Performance.vue:191 and Efficiency.vue:195 render predictionData.model_accuracy
- that field is produced at backend/routes/predictions.py:235  model_accuracy=float(forecast_result.accuracy_score)  (and backend/routes/analytics/predictions.py:137), i.e. a forecasting-model in-sample fit score over KPI series -- it never queries ALERT_HISTORY, so it cannot report whether alerts were right.

BACKEND CAPABILITY IS REAL AND REGISTERED:
- backend/routes/alerts/config_history.py:89-145  @config_history_router.get("/history/accuracy", response_model=AlertsHistoryAccuracyResponse); guard is Depends(get_current_user) (line 97) -- any authenticated user, not admin/cron; returns period_days, total_predictions, accurate_predictions, accuracy_rate_percent, average_error_percent, category, with a friendly "message" for the empty case
- backend/routes/alerts/__init__.py:20-29  router prefix "/api/alerts", config_history_router included FIRST
- backend/bootstrap/routers.py:184  app.include_router(alerts_router)

AGGRAVATING FINDING 1 -- in-app help promises a screen that does not exist:
- frontend/src/views/HelpCenter.vue renders docs/user-guide markdown in-app (sidebar doc list + rendered content)
- docs/user-guide/06-alerts.md:129  "The **alert accuracy** view (`/api/alerts/history/accuracy`) tracks how often dismissed alerts came back as real issues. If accuracy > 80%, the system is working; if < 50%, raise the thresholds."
- docs/user-guide/06-alerts.md:180  "| `GET /alerts/history/accuracy` | Triage accuracy KPI |"

AGGRAVATING FINDING 2 -- not seed-only data:
- backend/routes/alerts/crud.py:358-368  on resolve, "if alert.predicted_value and alert.current_value:" inserts AlertHistory(... actual_value=alert.current_value ...), so real user activity accumulates rows the endpoint counts
- backend/seed/emitters_alerts.py:238-250  AlertPredictionRecorded is the only writer of was_accurate/error_percent
- backend/schemas/workorder_contracts.py:214-217 documents that no runtime path sets error_percent/was_accurate, so on production data accuracy_rate_percent computes to 0.00 -- a backend defect that stays invisible precisely because no UI renders the value.

</details>


---

## LOW (8)

### Per-production-entry KPI drill-down (GET /api/kpi/calculate/{entry_id}) — efficiency, performance, quality rate, the ideal cycle time actually used, and whether it was inferred

**Slice:** kpi-analytics

**Backend:** backend/routes/kpi/calculations.py:31 GET /api/kpi/calculate/{entry_id} returns KPICalculationResponse with efficiency_percentage, performance_percentage, quality_rate, ideal_cycle_time_used, and was_inferred (the data-quality flag saying the cycle time was guessed rather than recorded), scoped through get_production_entry.

**Why unreachable:** frontend/src/services/api/kpi.ts:96 defines calculateKPIs(entryId) and grep across frontend/src finds no caller outside that line. frontend/src/views/ProductionEntry.vue renders only ProductionEntryGrid and the CSV upload dialog; frontend/src/views/DashboardView.vue:200-207 shows the stored efficiency_percentage column but nothing invokes the per-entry breakdown, so performance, quality rate, and was_inferred are never shown for a specific entry.

**User impact:** When a single production entry looks wrong, there is no way to open it and see how its KPIs were derived or whether the ideal cycle time behind them was inferred. The estimated-vs-measured distinction the backend tracks per entry never surfaces at the row level.

<details><summary>verification</summary>

BACKEND EXISTS AND IS WIRED: backend/routes/kpi/calculations.py:31 defines GET /api/kpi/calculate/{entry_id} with Depends(get_current_user) and scoping via get_production_entry; lines 47-58 compute calculate_efficiency/calculate_performance/calculate_quality_rate and return KPICalculationResponse. Schema at backend/schemas/production.py:213-219 (efficiency_percentage, performance_percentage, quality_rate, ideal_cycle_time_used, was_inferred). Registered at backend/routes/kpi/__init__.py:23 and :35, included at backend/bootstrap/routers.py:94. Requires a normal user JWT, so it is not internal/cron/admin-by-design.

SEARCHES PERFORMED, ALL NEGATIVE:
1. "calculateKPIs" repo-wide excluding node_modules: only frontend/src/services/api/kpi.ts:96 (the definition) and frontend/src/services/__tests__/kpi.spec.ts:22-28 (unit test of the definition). Third hit was the compiled frontend/dist/assets/index-2SqEULxF.js bundle, which merely embeds the unused export.
2. Path string "kpi/calculate" repo-wide: same two source locations only.
3. Symbols was_inferred / wasInferred / ideal_cycle_time_used / idealCycleTime across frontend/src: only frontend/src/stores/kpi.ts:467-470, inside the generic _extractInferenceFromResponse helper. Not a caller — and grep -rn "was_inferred" backend/routes backend/endpoints backend/schemas shows calculations.py:47,57 and schemas/production.py:219 are the ONLY places the field exists backend-side, so no endpoint the store actually calls ever populates that branch. idealCycleTime also hits components/WorkOrderDetailDrawer.vue:136, but that renders workOrder.ideal_cycle_time (a stored work-order column), not the per-entry ideal_cycle_time_used the calculator resolved.
4. frontend/src/router/index.ts: 38 path entries, none parameterized by a production-entry id; no entry-detail route. No files named EntryDetail/drilldown/kpiBreakdown anywhere in frontend/src.
5. frontend/src/components/grids/ProductionEntryGrid.vue: no row-click handler, no masterDetail, no detailCellRenderer (only @rows-pasted at :103 and AGGridBase row-editing hooks). Column defs at frontend/src/composables/useProductionGridData.ts:198-298 are raw inputs only (production_date, product_id, shift_id, work_order_id, units_produced, run_time_hours, employees_assigned, defect_count, scrap_count, actions) — no efficiency, quality or inferred column.
6. grep -rn "inferred|estimated|entry_id|entryId" frontend/src/views/kpi/*.vue across all 8 KPI detail views: ZERO matches.
7. InferenceIndicator.vue is referenced only at frontend/src/views/KPIDashboard.vue:120 and :332, bound to kpi.inference from the aggregate store keyed by KPI name — never per production entry.

PARTIAL-COVERAGE CHECK: frontend/src/views/DashboardView.vue:210-217 and :305 render stored efficiency_percentage and performance_percentage per entry row, so two of the five values are visible elsewhere as stored numbers. The drill-down's distinctive output — per-entry quality_rate, the ideal_cycle_time_used actually applied, and the was_inferred estimated-vs-measured flag — surfaces on no screen in the application.

</details>

### What-if dual-view calculation from user-supplied raw inputs (POST /api/metrics/calculate/oee, /otd, /fpy)

**Slice:** kpi-analytics

**Backend:** backend/routes/dual_view_calculate.py:44 mounts prefix "/api/metrics/calculate"; POST /oee (line 87), POST /otd (line 116), and POST /fpy (line 145) accept explicit raw-input payloads, run both standard and site_adjusted modes, persist a METRIC_CALCULATION_RESULT row, and return the result_id. These are separate from the /from-period/* variants (lines 201, 237, 273, 309) that aggregate inputs from stored production data.

**Why unreachable:** frontend/src/services/api/dualViewCalc.ts defines calculateOEE, calculateOTD, and calculateFPY for the raw-input variants, and grep across frontend/src finds no caller for any of the three (the only calculateFPY hits are an unrelated local helper in frontend/src/composables/useQualityData.ts:129). Every real consumer — frontend/src/components/dual_view/DualViewKPIPanel.vue:168-171 and frontend/src/composables/useDualViewInspector.ts:98-104 — uses only the *FromPeriod functions.

**User impact:** Low: the from-period path covers the normal case of calculating a metric over stored data, so nothing is lost for routine use. What is unreachable is the sandbox use — typing in hypothetical downtime or defect counts to see how the standard and site-adjusted numbers would move — which is what the raw-input endpoints exist for.

<details><summary>verification</summary>

WHAT I SEARCHED (all under /Users/mcampos.cerda/Developer/Programming/kpi-operations):

1. Endpoint path, full and partial — `grep -rn "metrics/calculate" frontend/src` returns only 7 hits, all inside frontend/src/services/api/dualViewCalc.ts itself (lines 4, 48, 68, 86 for the raw variants; 104, 107, 110 for from-period). No view, component, store, or composable contains the string.

2. Exported function names — `grep -rn "calculateOEE\|calculateOTD\|calculateFPY\|dualViewCalc" frontend/src frontend/tests frontend/e2e`:
   - frontend/src/services/api/dualViewCalc.ts:47,67,85 — the three definitions.
   - frontend/src/composables/useDualViewInspector.ts:22-25 imports ONLY calculateFPYFromPeriod / calculateOEEFromPeriod / calculateOTDFromPeriod, and calls them at lines 98/101/104.
   - frontend/src/components/dual_view/DualViewKPIPanel.vue:79-83 imports the same three FromPeriod functions; lines 168-171 call them.
   - frontend/src/composables/useQualityData.ts:129,138,254 and frontend/src/views/kpi/Quality.vue:491,575 — a local `calculateFPY(item)` helper that does arithmetic on a grid row, unrelated to the API (confirms the auditor's note).
   No other file imports from '@/services/api/dualViewCalc'.

3. Schema/payload names — `grep -rn "raw_inputs\|rawInputs\|RawInputs" frontend/src` returns 6 hits, ALL in dualViewCalc.ts (lines 25, 44, 56, 64, 72, 82 — the interface declarations). No component or store ever constructs a raw_inputs object, so nothing could call these even by a dynamically built path.

4. Dynamic path construction — every POST in frontend/src/services/api/*.ts touching /metrics/ is a hard-coded literal (verified by grep over the whole services/api directory); there is no `/metrics/calculate/${metric}` template anywhere.

5. Synonyms for the sandbox use case — `grep -rniEl "what.?if|sandbox|hypothetical|simulat|scenario" frontend/src` returns the Simulation V2 module (frontend/src/components/simulation/**, stores/simulationV2Store.ts) and the capacity-scenarios module (composables/useScenariosGridData.ts, stores/capacity/**). Neither touches /api/metrics/calculate — they drive the separate SimPy/capacity engines and produce no standard-vs-site-adjusted dual-view result, so they do not cover this capability.

6. i18n — the entire `dualView` block in frontend/src/i18n/locales/en.json (lines 4311-4338) contains only panel/toggle/inspector strings. There is no label, button, dialog title, or error message for entering raw inputs in either locale, i.e. no UI copy was ever written for this feature.

7. UI surface for the dual-view feature — frontend/src/components/dual_view/ contains exactly three files: DualViewKPIPanel.vue, DualViewToggle.vue, MetricInspector.vue. Grep for any POST, "recalc", "edit input", or "adjust input" inside that directory returns nothing; the inspector is read-only over a result_id produced by the from-period call.

8. Repo-wide (excluding node_modules/.git) `grep -rn "calculate/oee"` finds the endpoint referenced only by: backend/routes/dual_view_calculate.py:48, backend/tests/test_bootstrap/openapi_surface.json:1593, backend/tests/test_routes/test_dual_view_calculate_routes.py:107,128,136, and the frontend service file. Backend tests are the only callers in the repo.

CORROBORATING SIGNAL: frontend/coverage/services/api/dualViewCalc.ts.html:333/353/371 mark the three raw-variant `api.post(...)` statements "statement not covered" — no frontend unit test reaches them either. (Weak on its own, since lines 389/392/395 for the from-period variants are also uncovered in that report, but consistent.)

WHY IT LOOKS SUPERSEDED RATHER THAN MERELY UNWIRED: frontend/src/services/api/dualViewCalc.ts:96-99 documents the from-period variants as "Replaces the Phase 4c sample-input demo path with real aggregates" — so the raw-input functions read as leftovers from the earlier Phase 4c demo wiring, kept in the client after the real path landed. That makes them dead client code on top of a live, tested, registered backend route (registered at backend/bootstrap/routers.py:306), which is exactly the unreachable-capability pattern, not a deliberate internal endpoint.

</details>

### Production import history — GET /api/import-logs, the audit list of prior CSV/batch production imports (file, row counts, errors, timestamp).

**Slice:** operations

**Backend:** backend/routes/production.py:399 (import_logs_router = APIRouter(prefix='/api/import-logs')), :402-403 GET returning List[ImportLogEntry], schema at backend/schemas/import_log.py. Registered in backend/bootstrap/routers.py alongside production_router.

**Why unreachable:** No reference to import-logs anywhere in frontend/src. The upload surfaces that generate these rows — frontend/src/components/CSVUploadDialogProduction.vue:417 api.post('/production/upload/csv') and frontend/src/services/api/production.ts:26 api.post('/production/batch-import') — show only the immediate response and never link to or fetch the history. No router entry, no view.

**User impact:** After a CSV import dialog is closed, its outcome is gone. A user who imported yesterday's production and now suspects a bad file cannot see what was imported, when, by whom, how many rows landed or which were rejected — the log is written on every import and read by nobody.

<details><summary>verification</summary>

BACKEND EXISTS AND IS LIVE
- backend/routes/production.py:399 — import_logs_router = APIRouter(prefix="/api/import-logs", tags=["Production"])
- backend/routes/production.py:402-403 — @import_logs_router.get("", response_model=List[ImportLogEntry]); def get_import_logs(limit: int = 50, db=Depends(get_db), current_user: User = Depends(get_current_user)); filters ImportLog.user_id == current_user.user_id, orders by import_timestamp desc, returns log_id/user_id/import_timestamp/file_name/rows_attempted/rows_succeeded/rows_failed/error_details/import_type.
- backend/orm/import_log.py:16 — class ImportLog, __tablename__ = "import_log".
- backend/schemas/import_log.py — BatchImportRequest/BatchImportResponse/ImportLogResponse; ImportLogEntry in backend/schemas/reference_contracts.py.
- Registered: backend/bootstrap/routers.py:20 (import import_logs_router) and :89 (app.include_router(import_logs_router)).
- Not internal/cron/admin: guarded by get_current_user and scoped to the caller's own imports — an end-user audit feature by construction.

SEARCHES RUN OVER frontend/ (excluding node_modules and dist) — ALL ZERO HITS
- Path: "import-logs" — zero across all of frontend/, including e2e/, i18n JSON, and tests.
- Identifiers: import_logs, importLogs, ImportLog, ImportLogEntry, import_log — zero in frontend/src.
- Response field names (any grid/table rendering the payload would contain one): rows_attempted, rowsAttempted, rows_succeeded, import_timestamp, importTimestamp, import_type, importType — all zero.
- Synonyms: importHistory, "import history", uploadHistory, import_history, "historial de import" — zero.
- Generic "/import" produced only 7 files, every one a false positive: JS import-statement text, a comment in frontend/src/composables/useExportSheetOptions.ts:2 ("export/import sheet options"), a comment in frontend/e2e/clipboard-paste.spec.ts:9, package-lock.json, a coverage HTML artifact, and two spec files.

ROUTER — NO ENTRY
frontend/src/router/index.ts: all 38 path: entries enumerated. /login, /, /production-entry, /kpi-dashboard, /summaries, 8x /kpi/*, 4x /data-entry/*, /work-orders, /my-shift, /alerts, /simulation, /simulation-v2, /plan-vs-actual, /capacity-planning, /admin/settings, /admin/users, /admin/clients, /admin/defect-types, /admin/part-opportunities, /admin/client-config, /admin/floating-pool, /admin/employees, /admin/workflow-config, /admin/workflow-designer/:clientId?, /admin/database, /admin/variance-report, /help/:id?, and the :pathMatch(.*)* catch-all. No import/log/history route exists.

SERVICES — NO CALL
All 29 files in frontend/src/services/api/ listed. production.ts is the only production surface: createProductionEntry, getProductionEntries, getProductionEntry, updateProductionEntry, deleteProductionEntry, uploadCSV (:18, POST /production/upload/csv), batchImportProduction (:25-26, POST /production/batch-import). No GET of /import-logs anywhere in services or stores.

I18N — NO LABEL TO HANG A SCREEN OFF
frontend/src/i18n/locales/en.json grepped for "import": ~40 hits, all CSV-wizard strings (importTitleProduction, stepUploadDescProduction, rowsToImport, successfullyImported, importComplete, ...). No "import history" / "previous imports" / "recent imports" key in en.json.

NO ALTERNATIVE UI SURFACE COVERS IT
The natural fallback would be an audit-trail screen. backend/routes/audit.py:19 defines prefix /api/audit with GET "" (:99) and GET /{table_name}/{record_pk} (:137), and backend/routes/production.py:380-385 does log a BATCH_IMPORT audit action. But grepping frontend/src for '/audit, `/audit and "/audit returns zero — the audit API has no frontend caller either. So no second surface incidentally exposes import history.

CORRECTIONS THAT DEEPEN THE GAP
1. ImportLog rows are written ONLY in batch_import_production (backend/routes/production.py:306-396; insert at :360-370, import_log_id captured at :370, returned at :393). The CSV handler async def upload_csv at :189 writes none, and grep for ImportLog|import_log in backend/services/csv_upload_processor.py and backend/endpoints/csv_upload.py returns 0 matches. So CSVUploadDialogProduction.vue:417 is not a producer of these rows.
2. The producing endpoint is itself UI-unreachable: batchImportProduction is defined at frontend/src/services/api/production.ts:25-26 and wrapped by frontend/src/stores/productionDataStore.ts:304-312, but grep for batchImportProduction across frontend/src/views and frontend/src/components returns zero — no component calls it. Its only other references are frontend/src/stores/__tests__/productionDataStore.spec.ts:22 and frontend/src/services/__tests__/production.spec.ts:127-138.

NET: the import_log table is dead in both directions through the UI while both endpoints are registered and functional over HTTP. User impact: after a bulk production import, there is no screen showing what was imported, when, how many rows landed, or which were rejected; the CSV dialog's in-memory summary is the only feedback and is lost on close, so diagnosing a bad file requires direct DB access.

</details>

### Attendance statistics summary — GET /api/attendance/statistics/summary, Present/Late/Absent record counts plus total actual hours for a date range, optionally narrowed to one shift.

**Slice:** operations

**Backend:** backend/routes/attendance.py:195-196 (@router.get('/statistics/summary'), response_model AttendanceStatisticsSummaryResponse), body at :208-258 grouping by a Present/Late/Absent case expression and summing actual_hours, with a shift_id filter and full multi-tenant client filtering.

**Why unreachable:** No call to attendance/statistics anywhere in frontend/src. The attendance surfaces use only api.get('/attendance'), api.get('/attendance/kpi/absenteeism') and api.get('/attendance/kpi/absenteeism/trend') (frontend/src/composables/useDashboardOverviewData.ts:77 and frontend/src/services/api/kpi.ts). No view or component fetches the summary.

**User impact:** The absenteeism KPI gives a rate but not the composition behind it. Nobody can see the Present/Late/Absent record split or the total hours worked for a range, and the per-shift breakdown (shift_id filter) has no UI at all — so lateness, which this endpoint counts separately, is invisible in the product even though it is tracked in every attendance row.

<details><summary>verification</summary>

SEARCHED (frontend/, incl. coverage/ and docs/): (1) "statistics" and "statistics/summary" across the whole frontend tree — only hits are services/api/workflow.ts:71,74 (/workflow/statistics/...), plus prose comments and i18n "ariaStatsSummary" (work orders). Nothing attendance-related. (2) Every "attendance" reference in src/services/** and src/stores/** — the complete call set is services/api/dataEntry.ts:14-22 (POST/GET/PUT/DELETE /attendance, /attendance/bulk, /attendance/mark-all-present), services/api/kpi.ts:545 (/attendance/kpi/absenteeism), kpi.ts:651 (/attendance/kpi/absenteeism/trend), services/api/csvExport.ts:25 (/export/attendance). No /attendance/statistics/*. (3) Dynamic-path escape hatches: only dataEntry.ts:16-17 build `/attendance/${id}`; the sole generic builder is composables/useCSVExport.ts:70 (`/export/${entityType}`), which cannot reach /api/attendance/*. (4) Candidate consumers: components/AttendanceKPIs.vue:144 (the attendance_summary dashboard widget, wired at components/dashboard/WidgetGrid.vue:202) calls ONLY /attendance/kpi/absenteeism; composables/useDashboardOverviewData.ts:77 likewise; views/kpi/Absenteeism.vue + composables/useAbsenteeismData.ts:118 use raw GET /attendance plus the absenteeism KPI. (5) Schema/model synonyms AttendanceStatisticsSummaryResponse / AttendanceStatusStatistic (backend/schemas/attendance.py:312-323) — zero frontend hits. (6) is_late across frontend/src — only the write-path mapping in composables/useAttendanceGridData.ts:115-135,694 and unrelated work-order delay logic.

LATE IS GENUINELY INVISIBLE ON READ: composables/useAbsenteeismData.ts:123 collapses it (status: record.is_absent ? 'ABSENT' : 'PRESENT'); backend/schemas/attendance.py:191-231 (AttendanceRecordResponse) has no status field, so the data-entry grid Status column (useAttendanceGridData.ts:377-397, options Present/Absent/Late/...) is write-only — reloaded rows spread ...existing (useAttendanceGridData.ts:575-585) with no status key, leaving the cell blank; components/widgets/BradfordFactorWidget.vue:302 filters on r.status === 'Absent' || r.status === 'Late' against a payload that never carries status (inert); services/api/csvExport.ts:24 exportAttendance would expose is_late (backend/routes/export.py:355) but has NO caller in any view/component (only re-exported via services/api/index.ts:35,84).

PARTIAL COVERAGE FOUND (down-weights severity): total actual hours for a range IS reachable — Pivot Summaries Q1 renders the `actual` measure as "Attendance Hours" (composables/pivotPresets.ts:52), backed by backend/pivot/registry.py:185-198 (_LABOR, model AttendanceEntry) and backend/pivot/hooks.py:91-93 (c["actual"] += float(e.actual_hours or 0)); routed at frontend/src/router/index.ts:48-50 (/summaries) and nav-linked at frontend/src/App.vue:83. Absent count IS reachable — views/kpi/Absenteeism.vue:84 shows total_absences = SUM(case(is_absent==1,1,0)) from backend/routes/attendance.py:377; route /kpi/absenteeism at router/index.ts:90-91; the Present/Absent record list is on the same screen (Absenteeism.vue:162-176). shift_id is equally unexposed for /attendance/kpi/absenteeism (backend/routes/attendance.py:327; no shift control in views/kpi/Absenteeism.vue, no shift_id in services/api/kpi.ts:543-560), so that sub-claim is a shared filter gap, not evidence for this endpoint.

</details>

### Cross-referencing a capacity planning order to the shop-floor work orders executing it: GET /api/capacity/orders/{order_id}/work-orders.

**Slice:** capacity-simulation

**Backend:** backend/routes/capacity/work_order_bridge.py:19-32 defines get_capacity_order_work_orders, registered via backend/routes/capacity/__init__.py, with pagination, auth (get_current_user), a WorkOrderResponse response model, and a real service call to backend/services/work_order_service.list_orders_by_capacity_order.

**Why unreachable:** No wrapper for this path exists anywhere in the frontend API layer — frontend/src/services/api/capacityPlanning.ts has no work-order function, and frontend/src/services/api/workOrders.ts only targets the plain /work-orders router (lines 4-32), never /capacity/orders/{id}/work-orders. Grepping frontend/src for the substring 'work-orders' across services, stores, views, components and composables yields no match on the capacity-scoped path.

**User impact:** The Orders grid in Capacity Planning and the Work Order Management screen are disconnected. A planner looking at a capacity order cannot see which work orders were raised against it, and cannot tell whether a plan actually turned into execution, even though the backend link already exists.

<details><summary>verification</summary>

BACKEND EXISTS AND IS REAL
- /Users/mcampos.cerda/Developer/Programming/kpi-operations/backend/routes/capacity/work_order_bridge.py:19-32 — @work_order_bridge_router.get("/orders/{order_id}/work-orders", response_model=List[WorkOrderResponse]), with PaginationParams, get_current_user auth, and a real service call.
- Registered: backend/routes/capacity/__init__.py:41 (from .work_order_bridge import work_order_bridge_router) and :52 (router.include_router(work_order_bridge_router)) under prefix "/api/capacity". Final path: GET /api/capacity/orders/{order_id}/work-orders.
- Service chain is real: backend/services/work_order_service.py:85-89 list_orders_by_capacity_order -> get_work_orders_by_capacity_order. Covered by backend tests: backend/tests/test_crud/test_work_order_capacity_bridge.py:87 test_returns_linked_work_orders and backend/tests/test_routes/test_work_order_capacity_routes.py:217. So the backend is exercised and working — this is not dead code.

WHAT I SEARCHED (all negative for the capacity-scoped path)
1. Exact path substring "capacity/orders/" across the whole frontend/ tree (excluding node_modules, dist): only 3 files hit — frontend/src/services/api/capacityPlanning.ts, its spec, and a coverage HTML artifact. Enumerating every occurrence in capacityPlanning.ts gives exactly 6 capacity-order calls, lines 112, 125, 130, 137, 145, 153: GET /capacity/orders, GET /capacity/orders/scheduling, POST /capacity/orders, PUT /capacity/orders/{id}, PATCH /capacity/orders/{id}/status, DELETE /capacity/orders/{id}. There is no work-orders function. The spec file (services/__tests__/capacityPlanning.spec.ts:338-421) asserts the same six and nothing more.
2. Last path segment "work-orders" across all of frontend/src: 20+ hits, every one on a different router — /work-orders (services/api/workOrders.ts:4-35, useWorkOrderGridData.ts:234,253), /work-orders/{id}/jobs and /rty (components/JobLineItems.vue:228,244), /workflow/work-orders/{id}/* (services/api/workflow.ts:8,14,19,22,58,61), /clients/{id}/work-orders (services/api/workOrders.ts:35), /export/work-orders (services/api/csvExport.ts:13). None is capacity-scoped.
3. Model/schema/synonym names: "capacity_order", "capacityOrder", "capacity-order" across frontend/src — one single hit, views/PlanVsActualView.vue:123 item-value="capacity_order_id", used only as a v-data-table row key. Also searched linkedWorkOrder, relatedWorkOrder, orderWorkOrders, getOrderWorkOrders, workOrdersForOrder, fetchWorkOrdersFor — zero hits.
4. i18n: en.json/es.json:3804 "linkedWorkOrders" exists but is consumed only at views/PlanVsActualView.vue:187 (see below). No capacity-namespace work-order key.
5. The UI surface that owns these orders: frontend/src/views/CapacityPlanning/components/grids/OrdersGrid.vue has no drill-down, expand, row-click or detail handler at all — the only interactive control is @click="addRow" at line 7. Its column set (composables/useOrdersGridData.ts:161-214) is order_number, customer_name, style_model, order_quantity, required_date, priority, status, _actions — no work-order column and no link.
6. frontend/src/components/WorkOrderDetailDrawer.vue contains zero occurrences of "capacity"/"Capacity", so the reverse direction is not surfaced there either.

THE NEAR-MISS, AND WHY IT DOES NOT COVER THE CAPABILITY
views/PlanVsActualView.vue:187 renders {{ item.linked_work_orders }} under the label "Linked Work Orders". That data comes from getPlanVsActual -> api.get('/plan-vs-actual') (frontend/src/services/api/planVsActual.ts:11-13), a different endpoint, and the field is typed as a scalar count in backend/schemas/ops_contracts.py:464 (linked_work_orders: int). A planner sees a number, never the work order identities, statuses, or quantities that WorkOrderResponse would give them.

COLLATERAL FINDING (same bridge, also unreachable, worth reporting separately)
The reverse-direction bridge on the work-orders router is equally orphaned: backend/routes/work_orders.py:598 GET /{work_order_id}/capacity-order, :627 link_to_capacity_order, and :645 unlink_from_capacity_order (services at work_order_service.py:92-104). Grepping "capacity-order" across all of frontend/src returns zero matches. So the link/unlink WRITE capability has no UI control whatsoever — a user can never create or break the plan-to-execution link from the app; the links only exist because the seeder writes them.

</details>

### Server-side saved-filter history — recording ad-hoc filter configurations and reading back recent ones across sessions/devices (`GET /api/filters/history/recent`, `POST /api/filters/history`)

**Slice:** alerts-reports

**Backend:** backend/routes/filters.py:293 `GET /api/filters/history/recent` (per-user, limit 1-50) and :312 `POST /api/filters/history` (documented: 'Use this endpoint when applying ad-hoc filters that are not saved', capped at 50 entries/user), backed by a real FILTER_HISTORY table via `add_to_filter_history`/`get_filter_history`. `POST /api/filters/{id}/apply` (:194) also writes into it at :210.

**Why unreachable:** `getFilterHistory` is defined at frontend/src/services/api/preferences.ts:37 but has ZERO callers outside its own test file. The store never reads the server: frontend/src/stores/filtersStore.ts:89 `filterHistory = ref([])`, :132 persists it to `localStorage.setItem(HISTORY_KEY, ...)`, :148 hydrates it from localStorage, :255 `addToHistory` only mutates the local ref. The 'recent filters' the user sees (filtersStore.ts:125 `recentFilters`, consumed by frontend/src/composables/useFilterBarData.ts:268) is localStorage-only. Yet the UI DOES call the server delete — filtersStore.ts:338 `await api.clearFilterHistory()` → `DELETE /api/filters/history`, reached from FilterManager.vue:364. `POST /api/filters/history` is never called: grep for it returns nothing.

**User impact:** Filter history does not follow the user — clearing the browser or switching machines wipes their recent filters even though the server has been recording them all along. Worse, the 'Clear Filter History' button deletes a server-side history the user has never been shown, so it appears to work while acting on invisible data. Ad-hoc (unsaved) filters are never recorded server-side at all, so even the server copy is incomplete.

<details><summary>verification</summary>

BACKEND IS REAL AND MOUNTED: backend/routes/filters.py:293 `GET /history/recent` (limit 1-50, per-user) and :312 `POST /history` ("Use this endpoint when applying ad-hoc filters that are not saved"); router mounted at /api/filters by backend/bootstrap/routers.py:251. Persistence is a real table: backend/orm/saved_filter.py:58 `class FilterHistory` with `__tablename__ = "FILTER_HISTORY"` (:68); CRUD at backend/crud/saved_filter/history.py:47 `get_filter_history`, plus `add_to_filter_history` and `clear_filter_history` (50-entry trim at :27-42).

SEARCHES RUN (frontend/src, frontend/e2e, frontend/tests):
- `getFilterHistory` -> 4 hits total: definition at frontend/src/services/api/preferences.ts:37, and 3 lines in frontend/src/services/__tests__/preferences.spec.ts:199-205. ZERO production callers.
- `history/recent` -> identical 4 hits, nothing more.
- `filters/history` -> only preferences.ts:37 (GET) and preferences.ts:39 (DELETE).
- Exhaustive literal sweep `grep -rn "'/filters" --include=*.ts --include=*.vue` excluding tests returns EXACTLY four lines: `/filters` (GET), `/filters` (POST), `/filters/history/recent`, `/filters/history`. No `api.post('/filters/history', ...)` exists anywhere, so ad-hoc recording never fires. Template-literal filter paths were checked too and are only `/filters/${id}`, `/apply`, `/set-default`, `/duplicate`.
- `FilterHistory` / `filterHistory` / `filter_history` / `recentFilters` / `addToHistory` -> every production hit is local state.

READ PATH IS LOCALSTORAGE-ONLY: frontend/src/stores/filtersStore.ts:89 `filterHistory = ref([])`; :132 `localStorage.setItem(HISTORY_KEY, ...)`; :148 hydrates from `localStorage.getItem(HISTORY_KEY)`. The only server sync, `loadFromAPI()` at :158, calls `api.getSavedFilters()` and nothing else; `initializeFilters` (:180) awaits only that, and its two callers (composables/useFilterBarData.ts:325, composables/useKPIDashboardData.ts:179) therefore never fetch server history. `addToHistory` (:255) mutates only the local ref; `applyQuickFilter` (:293-301), the ad-hoc path, calls only `addToHistory` with no server write. What the user sees: filtersStore.ts:125 `recentFilters` -> useFilterBarData.ts:77/355 -> components/filters/FilterBar.vue:189-209 (`v-for item in recentFilters`, `@click="applyRecentFilter"`).

ASYMMETRY CONFIRMED: filtersStore.ts:334-338 `clearHistory()` clears the local ref then `await api.clearFilterHistory()` -> `DELETE /api/filters/history`, driven by the Clear History confirm dialog in components/filters/FilterManager.vue (~:359-380), whose count text is bound to the LOCAL `filterHistory.length`. The UI deletes server rows it has never displayed and mislabels how many.

ONE CORRECTION (strengthens the finding): the server history IS partially written by a reachable path -- filtersStore.ts:275 `applyFilter` -> `api.applyFilter(filter_id)` -> `POST /filters/{id}/apply`, which writes history at backend/routes/filters.py:210. So the server accumulates entries for saved-filter applies only; ad-hoc filters are never recorded, and nothing ever reads any of it back. No Vue route, view, component, nav/menu entry, i18n key, or e2e test reaches either history endpoint.

</details>

### Capacity alert generation — `POST /api/alerts/generate/capacity`, which raises a capacity alert from a load %, predicted idle days, overtime hours needed, and bottleneck station

**Slice:** alerts-reports

**Backend:** backend/routes/alerts/generate.py:132-177: supervisor-guarded, calls `generate_capacity_alert(...)` from backend/calculations/alerts.py and persists a real Alert row (category="capacity", kpi_key="load_percent", with metadata). It is NOT covered by check-all: backend/routes/alerts/generate.py:39-100 `generate_all_alerts` runs only `_check_efficiency_alerts`, `_check_otd_alerts`, `_check_quality_alerts`, `_check_hold_alerts` — capacity is absent from that list.

**Why unreachable:** `grep -rn "generate/capacity" frontend/src` → 0 hits. The only generation call in the app is frontend/src/composables/useAlertDashboardActions.ts:27 `await api.post('/alerts/generate/check-all')`, fired by the single 'Check Now' button at frontend/src/components/alerts/AlertDashboard.vue:31-34. Capacity Planning does not call it either: `grep -rn "alerts" frontend/src/views/CapacityPlanning/**` only matches a `<v-alert>` banner in components/panels/ComponentCheckPanel.vue.

**User impact:** The docstring says this is 'typically called from capacity planning simulation results', but the Capacity Planning screen never calls it. Capacity is one of the six categories offered in the alert board's category filter (AlertDashboard.vue:46), so users can filter for capacity alerts that the running app can never produce — the filter option is permanently empty unless the row was seeded.

<details><summary>verification</summary>

BACKEND CAPABILITY IS REAL: backend/routes/alerts/generate.py:132-177 defines POST /generate/capacity, guarded by get_current_active_supervisor, calling generate_capacity_alert(load_percent, predicted_idle_days, overtime_hours_needed, bottleneck_station) from backend/calculations/alerts.py, then constructing and persisting an Alert row at lines 160-176 (category="capacity", kpi_key="load_percent", current_value=float(load_percent), alert_metadata=result.metadata) with db.add/commit/refresh.

NOT COVERED BY ANOTHER SURFACE: generate_all_alerts (generate.py:39-100) runs exactly four checks -- _check_efficiency_alerts, _check_otd_alerts, _check_quality_alerts, _check_hold_alerts -- capacity is absent. `grep -rn 'category="capacity"' backend` returns exactly ONE hit: routes/alerts/generate.py:162. `grep -rn generate_capacity_alert backend` returns only that route plus tests (tests/test_calculations/test_alerts_comprehensive.py, test_additional_calc_coverage.py). No seeder, service, or scheduler creates a capacity alert.

NOT CRON/INTERNAL BY DESIGN: check-all's docstring explicitly says "should be called periodically (e.g., every hour)"; the capacity endpoint's docstring instead says "typically called from capacity planning simulation results" -- it expects an in-app caller, which does not exist.

SEARCHES RUN ACROSS FRONTEND (all negative):
1. Endpoint path: `grep -rn "generate/capacity" frontend/src` -> 0 hits; also run across frontend/e2e and frontend/tests -> 0 hits.
2. Parameter/schema names and synonyms: load_percent, loadPercent, bottleneck_station, bottleneckStation, overtime_hours_needed, overtimeHours, predicted_idle -> only i18n display labels in i18n/locales/en.json:2259,2353,2624,3008 and es.json (same lines). No API call.
3. Dynamic URL construction: grep for 'generate/${', '/generate', and '`/alerts' -> only /qr/generate/image (services/api/qr.ts:7) and /capacity/schedules/generate (services/api/capacityPlanning.ts:420, an unrelated schedules endpoint). No templated alerts-generate URL.
4. Exhaustive enumeration of EVERY alerts API touchpoint in the app: composables/useAlertDashboardActions.ts:27 POST /alerts/generate/check-all, :40 acknowledge, :59 resolve, :81 dismiss; composables/useAlertDashboardData.ts:62 GET /alerts/?, :74 GET /alerts/summary; services/api/kpi.ts:661 GET /alerts/ by kpi_key. That is the complete set. There is no services/api/alerts.ts file at all (ls services/api/ confirms).
5. Capacity Planning screen: no api.post to alerts anywhere under frontend/src/views/CapacityPlanning/** (only AG Grid params.api.getSelectedRows() at components/panels/ScenariosPanel.vue:128).

ONLY UI TRIGGER: the single "Check Now" button at components/alerts/AlertDashboard.vue:31-34 -> generateAlerts() -> useAlertDashboardActions.ts:27 -> check-all only.

AGGRAVATING EVIDENCE (UI promises the category): components/alerts/AlertDashboard.vue:45 renders <option value="capacity"> in the category filter, and components/alerts/AlertGuideDialog.vue:86-91 documents capacity alerts to the user with alerts.guide.capacityTitle, capacityDesc, capacityTrigger1, capacityTrigger2. components/alerts/AlertCard.vue:105 maps a capacity label. The route exists (router/index.ts:138-140 -> AlertsView.vue), so the screen is reachable -- the generation capability is not. A supervisor reads the in-app guide, filters for capacity, and gets a permanently empty list unless a row was seeded.

</details>

### Manual alert creation — `POST /api/alerts/` for a supervisor to raise an alert by hand

**Slice:** alerts-reports

**Backend:** backend/routes/alerts/crud.py:262-300 `create_alert`, status 201, accepting `AlertCreate` (category, severity, title, message, recommendation, client_id, kpi_key, work_order_id, current/threshold/predicted values, confidence, metadata) with `verify_client_access` and a persisted Alert row. Docstring: 'Typically alerts are generated automatically, but manual creation is supported.'

**Why unreachable:** The alert board has no create control at all — frontend/src/components/alerts/AlertDashboard.vue's only action buttons are 'How to use' (:29) and 'Check Now' (:31); the dialogs it mounts are AlertGuideDialog and AlertResolveDialog, neither of which creates. The composables cover only read + acknowledge/resolve/dismiss (frontend/src/composables/useAlertDashboardActions.ts:40,59,81). No POST to `/alerts/` (bare) exists anywhere in frontend/src.

**User impact:** A supervisor who spots a problem the automated checks miss cannot put it on the shared alert board for their shift to see and acknowledge. The board is read-and-close-only: the UI can acknowledge, resolve, and dismiss, but never create.

<details><summary>verification</summary>

BACKEND EXISTS AND DOES REAL WORK
- backend/routes/alerts/crud.py:262 `@crud_router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)`, `async def create_alert(alert_data: AlertCreate, ...)` at :263. Body (:275-296) constructs a real `Alert(...)` ORM row with generate_alert_id(), category, severity, status="active", title, message, recommendation, client_id, kpi_key, work_order_id, current/threshold/predicted values, confidence, alert_metadata, then db.add/commit/refresh. Tenant check at :273-274 `verify_client_access(current_user, alert_data.client_id)`.
- Schema behind it: backend/schemas/alert.py:61 `class AlertCreate(AlertBase)` with client_id, kpi_key, work_order_id, current_value, threshold_value, predicted_value, confidence (:64-71).
- Full CRUD siblings registered on the same router: crud.py:118 GET /, :160 GET /dashboard, :215 GET /summary, :245 GET /{alert_id}, :262 POST /, :301 acknowledge, :332 resolve, :376 dismiss.

WHAT I SEARCHED IN frontend/src (all negative for the bare POST)
1. Endpoint path — `grep -rn "'/alerts|\"/alerts|`/alerts|/api/alerts" frontend/src` returns exactly 10 hits, and every one is accounted for:
   - useAlertDashboardActions.ts:27 `api.post('/alerts/generate/check-all')`
   - useAlertDashboardActions.ts:40 `api.post(\`/alerts/${alertId}/acknowledge\`, {})`
   - useAlertDashboardActions.ts:59 `api.post(\`/alerts/${...}/resolve\`, {...})`
   - useAlertDashboardActions.ts:81 `api.post(\`/alerts/${alertId}/dismiss\`)`
   - useAlertDashboardData.ts:62 GET `/alerts/?...`, :74 GET `/alerts/summary`
   - services/api/kpi.ts:661 GET `/alerts/` (read, for KPI cards)
   - router/index.ts:138 the `/alerts` route, App.vue:106 the nav item, plus one test file.
   No bare `POST /alerts/` anywhere.
2. Every POST in the codebase mentioning "alert" — `grep -rn "post(" frontend/src | grep -i alert` returns only those same four action calls (generate/acknowledge/resolve/dismiss).
3. Identifier synonyms — `grep -rni "createalert|alertcreate|newalert|raisealert|addalert" frontend/src` → zero hits.
4. Raw HTTP escape hatches — `grep -rn "fetch\(|axios\." frontend/src | grep -i alert` → zero hits.
5. Service layer — `ls frontend/src/services/api/` has 28 modules (admin, kpi, workOrders, workflow, reports, …) and NO alerts module; alert traffic goes only through the two composables above.
6. Store layer — `grep -rln "alert" frontend/src/stores/` matches only kpi.ts, where every hit (lines 42, 282, 286, 309, 379, 390) is an `mdi-alert-*` icon name, not an API call.
7. UI controls — frontend/src/components/alerts/AlertDashboard.vue's entire `<div class="actions">` block is two buttons: :28 `@click="showGuide = true"` (How to use) and :31 `@click="generateAlerts"` (Check Now). The rest of the template is summary stat tiles (:5-25), three filter selects (:39-61), and AlertCard lists. The component directory is AbsenteeismAlert.vue (read-only, its single call is `api.get('/attendance/kpi/absenteeism')` at :223), AlertCard.vue (emits acknowledge/resolve/dismiss only), AlertGuideDialog.vue, AlertResolveDialog.vue — no create dialog exists.
8. i18n — dumping every key containing "alert" from frontend/src/i18n/locales/en.json yields ~60 keys (urgent, critical, checkNow, resolveAlert, acknowledge, dismiss, guide.*, category*) and not a single create/new/raise/add-alert label. A hidden or planned create control would have left a string here; there is none.
9. Router/nav — router/index.ts:137-142 exposes exactly one alerts route (`/alerts` → views/AlertsView.vue), and AlertsView.vue's entire template is `<h1>` + `<AlertDashboard />`. No child route, no admin alert-authoring screen.

NOT COVERED ELSEWHERE
`grep -rn "Alert(" backend/services backend/routes backend/endpoints` shows Alert rows are constructed in only two places: generate.py:160/255/339 (the automated threshold checks the Check Now button drives) and crud.py:276 (this endpoint). The generate endpoints (generate.py:39 check-all, :105 otd-risk, :118 quality, :132 capacity) take thresholds/client filters, not author-supplied content, so the Check Now button cannot stand in for a supervisor writing their own title/message/recommendation. The claim is specific, file-and-line anchored, and the endpoint is a normal user-facing supervisor action guarded by get_current_user + verify_client_access — not internal, cron, or admin-script by design.

Minor note found while verifying (not the gap): crud.py:274 calls `verify_client_access(current_user, alert_data.client_id)` without `db`, while the sibling read path at crud.py:258 passes `db`. backend/middleware/client_auth.py:125 declares `db: Optional[Session] = None`, so it does not crash, but the create path skips the junction-table client check the read path performs.

</details>
