# Operations Health Dashboard - Design Document

## 1. Dashboard Purpose

The Operations Health Dashboard provides **real-time operational health overview** for plant managers and supervisors. It serves as the central command center for monitoring manufacturing operations at a glance.

### Target Users
- **Plant Managers**: Need high-level KPI summary and trend alerts
- **Supervisors**: Need shift-level metrics and quick access to issues
- **Operations Staff**: Need status of active work orders and downtime events

### Key Goals
- Provide instant visibility into plant health (OEE as primary metric)
- Surface critical alerts and issues requiring immediate attention
- Enable quick navigation to detailed views for investigation
- Support mobile access for floor walks

---

## 2. Key Metrics Display

### 2.1 Hero Section - Overall Equipment Effectiveness (OEE)

```
+--------------------------------------------------+
|          OVERALL EQUIPMENT EFFECTIVENESS          |
|                                                  |
|              [===GAUGE CHART===]                 |
|                    78.5%                         |
|                                                  |
|   Availability: 92.1%  |  Performance: 89.3%    |
|   Quality: 95.4%                                 |
|                                                  |
|   Target: 85% | Status: AT RISK (Yellow)        |
+--------------------------------------------------+
```

**Visual Specifications:**
- Large circular gauge (200px diameter)
- OEE value in text-h2 font inside gauge
- Three sub-metrics below with progress bars
- Color-coded status chip

### 2.2 Metric Cards Grid (6 Cards)

| Card | Metric | Icon | Sparkline | Color Logic |
|------|--------|------|-----------|-------------|
| 1 | Production Today | mdi-factory | 7-day trend | Green: >= target, Yellow: 80-99%, Red: <80% |
| 2 | Active Downtime | mdi-clock-alert | None (count) | Green: 0, Yellow: 1-2, Red: 3+ |
| 3 | Quality Alerts | mdi-alert-octagon | 7-day defect trend | Green: 0, Yellow: 1-3, Red: 4+ |
| 4 | Attendance Coverage | mdi-account-group | None | Green: >=95%, Yellow: 85-95%, Red: <85% |
| 5 | Work Orders Active | mdi-clipboard-list | Aging distribution | Green: <=10, Yellow: 11-20, Red: >20 |
| 6 | On-Time Delivery | mdi-truck-check | 30-day trend | Green: >=95%, Yellow: 90-95%, Red: <90% |

**Card Layout:**
```
+---------------------------+
| [Icon]        [Sparkline] |
|                           |
|   42 / 50                 |
|   Production Today        |
|                           |
| [===Progress Bar======]   |
| Target: 50 | Status: OK   |
+---------------------------+
```

### 2.3 Critical Alerts Section

```
+--------------------------------------------------+
| CRITICAL ALERTS                          [Clear] |
+--------------------------------------------------+
| [!] Machine M-007 down for 2h 15m - Mechanical   |
| [!] Quality hold: WO-2024-1547 - Inspection req  |
| [!] Absenteeism spike: 3 unplanned absences      |
+--------------------------------------------------+
```

**Alert Types:**
- Downtime > 1 hour
- Quality holds pending
- Absenteeism > 5%
- OEE dropping below 70%

---

## 3. Layout Specification

### 3.1 Desktop Layout (>= 1280px)

```
+------------------------------------------------------------------+
| HEADER: Operations Health Dashboard              [Refresh] [Date] |
+------------------------------------------------------------------+
|                                                                   |
|  +---------------------------+  +------------------------------+  |
|  |                           |  |    CRITICAL ALERTS (3)       |  |
|  |    OEE GAUGE              |  |                              |  |
|  |    78.5%                  |  |  [Alert 1]                   |  |
|  |                           |  |  [Alert 2]                   |  |
|  |  A: 92.1% P: 89.3% Q:95.4 |  |  [Alert 3]                   |  |
|  +---------------------------+  +------------------------------+  |
|                                                                   |
|  +--------+  +--------+  +--------+  +--------+  +--------+  +--+ |
|  | PROD   |  | DOWN   |  | QUAL   |  | ATTEND |  | WO     |  |OTD||
|  | TODAY  |  | TIME   |  | ALERTS |  | COVER  |  | ACTIVE |  |   ||
|  | 42/50  |  |   2    |  |   1    |  | 94.2%  |  |   15   |  |97%||
|  +--------+  +--------+  +--------+  +--------+  +--------+  +--+ |
|                                                                   |
|  +---------------------------+  +------------------------------+  |
|  |   RECENT ACTIVITY         |  |   QUICK ACTIONS              |  |
|  |   ----------------------  |  |                              |  |
|  |   09:45 Production logged |  |  [+ Log Production]          |  |
|  |   09:32 Downtime started  |  |  [+ Report Downtime]         |  |
|  |   09:15 Quality check     |  |  [+ Quality Entry]           |  |
|  |   08:50 Shift started     |  |  [View All KPIs]             |  |
|  +---------------------------+  +------------------------------+  |
+------------------------------------------------------------------+
```

### 3.2 Tablet Layout (768px - 1279px)

- OEE gauge and alerts stack vertically
- Metric cards: 3 per row
- Activity feed and quick actions stack

### 3.3 Mobile Layout (< 768px)

- OEE gauge: full width, smaller (150px)
- Alerts: horizontal scroll
- Metric cards: 2 per row, compact
- Activity feed: collapsible
- Quick actions: floating action button (FAB)

---

## 4. Component Structure

### 4.1 Vue Component Hierarchy

```
OperationsHealthDashboard.vue
├── OEEGaugeWidget.vue
│   └── v-progress-circular (Vuetify)
├── CriticalAlertsPanel.vue
│   └── v-alert items
├── MetricCardGrid.vue
│   ├── MetricCard.vue (x6)
│   │   ├── v-card
│   │   ├── v-sparkline
│   │   └── v-progress-linear
├── RecentActivityFeed.vue
│   └── v-list with v-timeline
└── QuickActionsPanel.vue
    └── v-btn-group
```

### 4.2 Vuetify Components Used

| Component | Usage |
|-----------|-------|
| `v-container` | Main layout container |
| `v-row` / `v-col` | Responsive grid |
| `v-card` | Metric cards, panels |
| `v-progress-circular` | OEE gauge |
| `v-progress-linear` | Metric progress bars |
| `v-sparkline` | Mini trend charts |
| `v-alert` | Critical alerts |
| `v-list` / `v-list-item` | Activity feed |
| `v-chip` | Status indicators |
| `v-btn` | Actions |
| `v-tooltip` | Metric explanations |
| `v-skeleton-loader` | Loading states |

### 4.3 Props and Data Requirements

```typescript
// Main Dashboard Data Interface
interface OperationsHealthData {
  oee: {
    overall: number;          // 0-100
    availability: number;     // 0-100
    performance: number;      // 0-100
    quality: number;          // 0-100
    target: number;           // 0-100
    trend: TrendPoint[];      // Last 7 days
  };
  production: {
    today: number;
    target: number;
    trend: TrendPoint[];
  };
  downtime: {
    activeCount: number;
    activeEvents: DowntimeEvent[];
  };
  quality: {
    alertCount: number;
    holdCount: number;
    defectTrend: TrendPoint[];
  };
  attendance: {
    coveragePercent: number;
    scheduled: number;
    present: number;
    absent: number;
  };
  workOrders: {
    activeCount: number;
    agingDistribution: AgingBucket[];
  };
  otd: {
    percentage: number;
    trend: TrendPoint[];
  };
  alerts: CriticalAlert[];
  recentActivity: ActivityItem[];
}

interface TrendPoint {
  date: string;
  value: number;
}

interface CriticalAlert {
  id: string;
  type: 'downtime' | 'quality' | 'attendance' | 'oee';
  severity: 'critical' | 'warning';
  message: string;
  timestamp: string;
  actionUrl?: string;
}

interface ActivityItem {
  id: string;
  type: 'production' | 'downtime' | 'quality' | 'attendance';
  description: string;
  timestamp: string;
  user?: string;
}
```

---

## 5. Color Coding System

### 5.1 Status Colors

| Status | Color | Vuetify Class | Condition |
|--------|-------|---------------|-----------|
| On Target | Green | `success` | Value >= 90% of target |
| Warning | Yellow | `warning` | Value 70-89% of target |
| Critical | Red | `error` | Value < 70% of target |

### 5.2 Specific Metric Thresholds

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| OEE | >= 85% | 70-84% | < 70% |
| Availability | >= 90% | 80-89% | < 80% |
| Performance | >= 95% | 85-94% | < 85% |
| Quality | >= 99% | 95-98% | < 95% |
| OTD | >= 95% | 90-94% | < 90% |
| Attendance | >= 95% | 85-94% | < 85% |

### 5.3 Implementation

```typescript
function getStatusColor(value: number, thresholds: { green: number; yellow: number }): string {
  if (value >= thresholds.green) return 'success';
  if (value >= thresholds.yellow) return 'warning';
  return 'error';
}

function getOEEStatus(oee: number): string {
  return getStatusColor(oee, { green: 85, yellow: 70 });
}
```

---

## 6. API Endpoints Required

### 6.1 Primary Data Endpoint

```
GET /api/v1/dashboard/operations-health
Query Params:
  - client_id?: string
  - shift_id?: string

Response: OperationsHealthData
```

### 6.2 Supporting Endpoints (Existing)

| Endpoint | Data Used |
|----------|-----------|
| `GET /api/v1/kpi/oee` | OEE components |
| `GET /api/v1/kpi/efficiency` | Production efficiency |
| `GET /api/v1/downtime/active` | Active downtime events |
| `GET /api/v1/quality/alerts` | Quality holds/alerts |
| `GET /api/v1/attendance/coverage` | Attendance coverage |
| `GET /api/v1/work-orders/active` | Active work orders |
| `GET /api/v1/kpi/on-time-delivery` | OTD percentage |

---

## 7. Accessibility Requirements

### 7.1 ARIA Labels

- OEE gauge: `aria-label="Overall Equipment Effectiveness: 78.5 percent"`
- Metric cards: `role="article"` with `aria-labelledby`
- Alerts: `role="alert"` with `aria-live="polite"`
- Activity feed: `role="log"` with timestamps

### 7.2 Keyboard Navigation

- Tab through all metric cards
- Enter/Space to expand card details
- Arrow keys to navigate activity feed
- Escape to close expanded views

### 7.3 Color Contrast

- All text meets WCAG AA (4.5:1)
- Status colors supplemented with icons
- High-contrast mode support

---

## 8. Performance Considerations

### 8.1 Data Refresh Strategy

- Initial load: All data in parallel
- Auto-refresh: Every 60 seconds (configurable)
- Websocket for critical alerts (optional enhancement)

### 8.2 Caching

- Store last known values for offline display
- Show stale data indicator when offline
- Optimistic updates for user actions

### 8.3 Lazy Loading

- Sparklines: Load after main metrics
- Activity feed: Paginated (10 items initial)
- Alerts: Show latest 5, "View all" for more

---

## 9. Implementation Phases

### Phase 1: Core Dashboard (MVP)
- [ ] OEE gauge with breakdown
- [ ] 6 metric cards (static data)
- [ ] Critical alerts panel
- [ ] Basic responsive layout

### Phase 2: Interactivity
- [ ] Sparkline trends
- [ ] Click-through to detail views
- [ ] Quick action buttons
- [ ] Activity feed

### Phase 3: Enhancements
- [ ] Real-time updates
- [ ] Custom alert thresholds
- [ ] Shift comparison toggle
- [ ] Export/print view

---

## 10. Related Documents

- [KPI Dashboard View](/frontend/src/views/KPIDashboard.vue)
- [Dashboard Overview Component](/frontend/src/components/DashboardOverview.vue)
- [Widget Pattern](/frontend/src/components/widgets/DowntimeImpactWidget.vue)
- [API Documentation](/docs/API_DOCUMENTATION.md)
