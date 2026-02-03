# Production Line Simulation v2.0 - Task Breakdown

## Phase 1: Core Engine (Week 1-2)

### Backend Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| B1.1 | Create `backend/simulation_v2/__init__.py` | 0.5h | - |
| B1.2 | Create `backend/simulation_v2/models.py` - Input schemas | 4h | - |
| B1.3 | Create `backend/simulation_v2/models.py` - Output schemas (8 blocks) | 4h | B1.2 |
| B1.4 | Create `backend/simulation_v2/constants.py` | 1h | - |
| B1.5 | Create `backend/simulation_v2/engine.py` - SimPy simulator class | 8h | B1.2 |
| B1.6 | Create `backend/simulation_v2/engine.py` - Bundle process generator | 6h | B1.5 |
| B1.7 | Create `backend/simulation_v2/engine.py` - Metrics collection | 4h | B1.6 |
| B1.8 | Create `backend/simulation_v2/calculations.py` - Blocks 1, 2, 3 | 6h | B1.3, B1.7 |
| B1.9 | Create `backend/simulation_v2/calculations.py` - Blocks 6, 8 | 4h | B1.8 |
| B1.10 | Create `backend/routes/simulation_v2.py` - /run endpoint | 4h | B1.8 |
| B1.11 | Add router to `backend/main.py` | 0.5h | B1.10 |
| B1.12 | Create `backend/tests/test_simulation_v2/conftest.py` | 2h | B1.2 |
| B1.13 | Create `backend/tests/test_simulation_v2/test_models.py` | 4h | B1.2, B1.12 |
| B1.14 | Create `backend/tests/test_simulation_v2/test_engine.py` | 6h | B1.5, B1.12 |

**Phase 1 Backend Total: ~54h**

### Frontend Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| F1.1 | Add `xlsx` dependency to package.json | 0.5h | - |
| F1.2 | Update `vite.config.js` with xlsx chunking | 0.5h | F1.1 |
| F1.3 | Create `frontend/src/services/api/simulationV2.js` | 2h | - |
| F1.4 | Create `frontend/src/stores/simulationV2Store.js` | 6h | F1.3 |
| F1.5 | Create `frontend/src/components/simulation-v2/OperationsGrid.vue` | 8h | - |
| F1.6 | Create `frontend/src/components/simulation-v2/ScheduleForm.vue` | 4h | - |
| F1.7 | Create `frontend/src/components/simulation-v2/DemandGrid.vue` | 4h | - |
| F1.8 | Create `frontend/src/components/simulation-v2/ResultsBlock.vue` | 4h | - |
| F1.9 | Create `frontend/src/views/SimulationV2View.vue` - Input section | 8h | F1.4-F1.7 |
| F1.10 | Create `frontend/src/views/SimulationV2View.vue` - Results section | 6h | F1.8 |
| F1.11 | Add route to `frontend/src/router/index.js` | 0.5h | F1.9 |
| F1.12 | Create unit tests for store | 4h | F1.4 |

**Phase 1 Frontend Total: ~48h**

---

## Phase 2: Validation & Variability (Week 3)

### Backend Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| B2.1 | Create `backend/simulation_v2/validation.py` - Schema validation | 4h | B1.2 |
| B2.2 | Add sequence validation (gaps, duplicates) | 3h | B2.1 |
| B2.3 | Add product consistency validation | 2h | B2.1 |
| B2.4 | Add machine tool typo detection | 2h | B2.1 |
| B2.5 | Add demand mode validation | 2h | B2.1 |
| B2.6 | Add theoretical capacity check | 3h | B2.1 |
| B2.7 | Create `backend/routes/simulation_v2.py` - /validate endpoint | 2h | B2.1 |
| B2.8 | Add triangular distribution to engine | 2h | B1.5 |
| B2.9 | Create `backend/tests/test_simulation_v2/test_validation.py` | 6h | B2.1-B2.6 |

**Phase 2 Backend Total: ~26h**

### Frontend Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| F2.1 | Create `ValidationReport.vue` component | 4h | - |
| F2.2 | Add validation API call to store | 2h | B2.7 |
| F2.3 | Integrate validation flow in SimulationV2View | 4h | F2.1, F2.2 |
| F2.4 | Add error/warning styling | 2h | F2.1 |
| F2.5 | Add validation button and flow | 2h | F2.3 |

**Phase 2 Frontend Total: ~14h**

---

## Phase 3: Advanced Features (Week 4)

### Backend Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| B3.1 | Add rework logic to engine | 4h | B1.6 |
| B3.2 | Add breakdown logic to engine | 4h | B1.6 |
| B3.3 | Create calculations for Block 4 (Free Capacity) | 3h | B1.8 |
| B3.4 | Create calculations for Block 5 (Bundle Metrics) | 3h | B1.8 |
| B3.5 | Create calculations for Block 7 (Rebalancing) | 4h | B1.8 |
| B3.6 | Add defaults tracking for Block 8 | 2h | B1.9 |
| B3.7 | Integration tests for full workflow | 6h | B3.1-B3.6 |

**Phase 3 Backend Total: ~26h**

### Frontend Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| F3.1 | Create `BreakdownsGrid.vue` component | 3h | - |
| F3.2 | Create `ResultsDashboard.vue` with tabs | 6h | F1.8 |
| F3.3 | Create `StationPerformance.vue` specialized view | 4h | F3.2 |
| F3.4 | Create `RebalancingSuggestions.vue` view | 3h | F3.2 |
| F3.5 | Create `AssumptionLog.vue` collapsible view | 3h | F3.2 |
| F3.6 | Create `utils/excelExport.js` | 6h | F1.1 |
| F3.7 | Create `ExportDialog.vue` | 3h | F3.6 |
| F3.8 | Add Chart.js visualizations | 6h | F3.2 |
| F3.9 | Component integration tests | 4h | F3.1-F3.8 |

**Phase 3 Frontend Total: ~38h**

---

## Phase 4: Integration & Deployment (Week 5)

### Tasks

| ID | Task | Estimate | Dependencies |
|----|------|----------|--------------|
| D4.1 | Add role-based access control | 2h | B1.10 |
| D4.2 | Add deprecation headers to v1 routes | 2h | - |
| D4.3 | Add navigation menu item | 1h | F1.11 |
| D4.4 | E2E testing with Playwright | 8h | All |
| D4.5 | Performance testing (5 products × 50 ops) | 4h | All |
| D4.6 | Deploy to staging | 2h | D4.4 |
| D4.7 | QA testing on staging | 8h | D4.6 |
| D4.8 | Deploy to production | 2h | D4.7 |
| D4.9 | Monitor and hotfix | 4h | D4.8 |

**Phase 4 Total: ~33h**

---

## Summary

| Phase | Backend | Frontend | Other | Total |
|-------|---------|----------|-------|-------|
| Phase 1 | 54h | 48h | - | 102h |
| Phase 2 | 26h | 14h | - | 40h |
| Phase 3 | 26h | 38h | - | 64h |
| Phase 4 | 4h | 1h | 28h | 33h |
| **Total** | **110h** | **101h** | **28h** | **239h** |

**Estimated Duration**: 5-6 weeks (1 developer) or 3 weeks (2 developers)

---

## Critical Path

```
B1.2 → B1.5 → B1.6 → B1.7 → B1.8 → B1.10 → D4.4 → D4.8
 │                                    │
 └─────────────────────────────────────┘
                    ↓
              F1.4 → F1.9 → F3.2 → F3.6
```

The critical path runs through:
1. Pydantic models (foundation for everything)
2. SimPy engine (core simulation logic)
3. Output calculations (results generation)
4. API endpoint (backend complete)
5. Frontend store and view integration
6. E2E testing
7. Production deployment

---

## Definition of Done

### Per Task
- [ ] Code complete and follows project conventions
- [ ] Unit tests written and passing
- [ ] No new linting errors
- [ ] Code reviewed (if pair programming, self-review acceptable)

### Per Phase
- [ ] All tasks complete
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Demo to stakeholder

### Final Release
- [ ] All phases complete
- [ ] E2E tests passing
- [ ] Performance benchmarks met (<15s for typical simulation)
- [ ] Deployed to production
- [ ] Monitoring in place
- [ ] User documentation available
