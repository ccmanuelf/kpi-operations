# Frontend Dashboard Documentation

## Overview

The KPI Operations frontend is a production-ready Vue 3 + Vuetify dashboard built for tablet-optimized data entry and real-time KPI monitoring. It consumes 45+ API endpoints from the FastAPI backend and provides comprehensive visualization and data management capabilities.

## Technology Stack

- **Framework**: Vue 3 (Composition API)
- **UI Library**: Vuetify 3
- **State Management**: Pinia
- **Charts**: Chart.js with vue-chartjs
- **Routing**: Vue Router
- **Date Handling**: date-fns
- **HTTP Client**: Axios

## Architecture

```
frontend/
├── src/
│   ├── views/
│   │   ├── KPIDashboard.vue          # Main dashboard with all 10 KPIs
│   │   ├── kpi/
│   │   │   ├── Efficiency.vue        # Efficiency detail view
│   │   │   ├── WIPAging.vue          # WIP aging analysis
│   │   │   ├── OnTimeDelivery.vue    # Delivery performance
│   │   │   ├── Availability.vue      # Equipment availability
│   │   │   ├── Performance.vue       # Production performance
│   │   │   ├── Quality.vue           # Quality metrics (PPM/DPMO/FPY/RTY)
│   │   │   └── Absenteeism.vue       # Workforce absenteeism
│   ├── components/
│   │   ├── entries/
│   │   │   ├── DowntimeEntry.vue     # Downtime data entry
│   │   │   ├── AttendanceEntry.vue   # Attendance tracking
│   │   │   ├── QualityEntry.vue      # Quality inspection
│   │   │   └── HoldResumeEntry.vue   # Hold/resume management
│   ├── stores/
│   │   ├── kpi.js                    # KPI state management
│   │   └── authStore.js              # Authentication state
│   ├── services/
│   │   └── api.js                    # API integration (45+ endpoints)
│   └── router/
│       └── index.js                  # Route configuration
```

## Key Features

### 1. KPI Dashboard (`/kpi-dashboard`)

**10 Real-Time KPI Cards:**
- Efficiency
- WIP Aging
- On-Time Delivery
- Availability
- Performance
- Quality (FPY)
- OEE
- Absenteeism
- PPM
- Throughput Time

**Features:**
- Color-coded status indicators (green/yellow/red)
- Progress bars showing target achievement
- Click-through to detailed views
- Client selector for multi-tenant filtering
- Date range picker (7/30/90 days)
- Real-time trend charts
- Summary data table with sorting

**API Integration:**
- `/api/kpi/dashboard` - Dashboard summary
- `/api/kpi/{metric}` - Individual KPI data
- `/api/kpi/{metric}/trend` - Historical trends

### 2. Individual KPI Detail Views

Each KPI has a dedicated detail view with:
- **Summary Cards**: Key metrics at a glance
- **Trend Charts**: Historical performance visualization
- **Breakdown Tables**: Data by shift, product, department, etc.
- **Drill-Down Capability**: Click-through to granular data
- **Export Options**: PDF/Excel report generation

#### Efficiency (`/kpi/efficiency`)
- Current vs. target efficiency
- Actual vs. expected output
- Efficiency by shift and product
- Gap analysis

#### WIP Aging (`/kpi/wip-aging`)
- Average WIP age
- Age distribution (0-7d, 8-14d, 15+d)
- Critical aging items alert
- Top 10 aging items table

#### On-Time Delivery (`/kpi/on-time-delivery`)
- OTD percentage
- Performance by client
- Late deliveries tracking
- Average delay analysis

#### Quality (`/kpi/quality`)
- First Pass Yield (FPY)
- Rolled Throughput Yield (RTY)
- Parts Per Million (PPM)
- Defects Per Million Opportunities (DPMO)
- Top defect types analysis
- Quality by product breakdown

#### Availability (`/kpi/availability`)
- Uptime vs. downtime hours
- Mean Time Between Failures (MTBF)
- Top downtime reasons
- Availability by equipment

#### Performance (`/kpi/performance`)
- Actual vs. standard production rate
- Performance by shift and product
- Production hours tracking
- Throughput analysis

#### Absenteeism (`/kpi/absenteeism`)
- Absenteeism rate
- Absence reasons breakdown
- Department-wise analysis
- High absence alerts

### 3. Data Entry Forms

#### Downtime Entry (`/data-entry/downtime`)
**Fields:**
- Equipment selection
- Downtime reason
- Start/end time
- Duration (auto-calculated)
- Category
- Notes

**Features:**
- Inference engine suggestions
- Real-time duration calculation
- Read-back confirmation
- Validation rules

#### Attendance Entry (`/data-entry/attendance`)
**Fields:**
- Employee ID
- Date and shift
- Status (Present/Absent/Late)
- Absence reason (if absent)
- Clock in/out times
- Notes

**Features:**
- Status-based conditional fields
- Excused absence tracking
- Late minutes calculation

#### Quality Entry (`/data-entry/quality`)
**Fields:**
- Work order and product
- Inspected/defect/rejected quantities
- Defect type and severity
- Disposition
- Inspector ID
- Defect description
- Corrective action

**Features:**
- Real-time FPY calculation
- Defect rate and PPM display
- Pass quantity calculation
- Multi-field validation

#### Hold/Resume Entry (`/data-entry/hold-resume`)
**Tabs:**
1. **Create Hold**: Initiate production hold
2. **Resume Hold**: Release held items

**Hold Fields:**
- Work order and quantity
- Hold reason and severity
- Description and required action
- Customer notification flag

**Resume Fields:**
- Active hold selection
- Disposition
- Released quantity
- Resolution notes
- Approval tracking

## State Management (Pinia)

### KPI Store (`stores/kpi.js`)

**State:**
```javascript
{
  dashboard: null,
  selectedClient: null,
  dateRange: { start, end },
  efficiency: {},
  wipAging: {},
  onTimeDelivery: {},
  availability: {},
  performance: {},
  quality: {},
  oee: {},
  absenteeism: {},
  trends: {
    efficiency: [],
    wipAging: [],
    // ... other trends
  },
  loading: false,
  error: null
}
```

**Getters:**
- `kpiStatus(value, target, isHigherBetter)` - Color-coded status
- `kpiIcon(value, target, isHigherBetter)` - Status icon
- `allKPIs` - Combined KPI array with metadata

**Actions:**
- `fetchDashboard()` - Load dashboard data
- `fetchEfficiency()` - Load efficiency with trends
- `fetchWIPAging()` - Load WIP aging data
- `fetchAllKPIs()` - Parallel fetch all KPIs
- `setClient(clientId)` - Filter by client
- `setDateRange(start, end)` - Update date range

## API Service (`services/api.js`)

### Endpoints (45+)

**KPI Metrics:**
- `GET /api/kpi/dashboard`
- `GET /api/kpi/efficiency`
- `GET /api/kpi/wip-aging`
- `GET /api/kpi/on-time-delivery`
- `GET /api/kpi/availability`
- `GET /api/kpi/performance`
- `GET /api/kpi/quality`
- `GET /api/kpi/oee`
- `GET /api/kpi/absenteeism`
- `GET /api/kpi/defect-rates`
- `GET /api/kpi/throughput-time`

**KPI Trends:**
- `GET /api/kpi/{metric}/trend`

**Data Entry:**
- `POST /api/production`
- `POST /api/downtime`
- `POST /api/attendance`
- `POST /api/quality`
- `POST /api/holds`
- `POST /api/holds/{id}/resume`

**Reference Data:**
- `GET /api/products`
- `GET /api/shifts`
- `GET /api/clients`
- `GET /api/downtime-reasons`
- `GET /api/defect-types`

**Reports:**
- `GET /api/reports/daily/{date}`
- `GET /api/reports/weekly`
- `GET /api/reports/monthly`
- `GET /api/reports/excel`
- `GET /api/reports/pdf`

**CSV Upload:**
- `POST /api/production/upload/csv`

## Responsive Design

### Breakpoints
- **Mobile**: < 600px
- **Tablet**: 600px - 960px (primary target)
- **Desktop**: > 960px

### Grid Layout
```vue
<v-col cols="12" sm="6" md="4" lg="3">
  <!-- KPI Card -->
</v-col>
```

### Tablet Optimization
- Touch-friendly button sizes
- Large input fields for data entry
- Optimized spacing for landscape mode
- Horizontal scrolling for tables
- Collapsible navigation

## Charts Configuration

### Chart.js Setup
```javascript
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)
```

### Chart Options
```javascript
{
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: { display: true, position: 'top' },
    tooltip: { mode: 'index', intersect: false }
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      ticks: { callback: (value) => `${value}%` }
    }
  }
}
```

## Color Coding System

### Status Colors
- **Success** (Green): On target (≥95% for higher-better, ≤5% for lower-better)
- **Warning** (Yellow): At risk (80-94% or 6-20%)
- **Error** (Red): Critical (<80% or >20%)

### Chart Colors
- Efficiency: `#2e7d32` (green)
- Quality: `#1976d2` (blue)
- Availability: `#7b1fa2` (purple)
- OEE: `#d32f2f` (red)
- Target Line: `#f57c00` (orange, dashed)

## Data Entry Features

### Validation Rules
```javascript
const rules = {
  required: value => !!value || 'Field is required',
  positive: value => value > 0 || 'Must be greater than 0',
  email: value => /.+@.+\..+/.test(value) || 'Invalid email'
}
```

### Auto-Calculations
- **Downtime**: Duration from start/end times
- **Quality**: FPY, defect rate, PPM, pass quantity
- **Attendance**: Late minutes, hours worked

### Inference Engine Integration
- Real-time suggestions based on historical data
- Confidence scores displayed
- One-click application of suggestions
- Pattern learning from user corrections

### Read-Back Confirmation
```vue
<v-dialog v-model="confirmDialog">
  <v-card>
    <v-card-title>Confirm Entry</v-card-title>
    <v-card-text>
      <!-- Display entered values for verification -->
    </v-card-text>
    <v-card-actions>
      <v-btn @click="confirmSubmit">Confirm</v-btn>
      <v-btn @click="confirmDialog = false">Edit</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>
```

## Performance Optimization

### Code Splitting
```javascript
component: () => import('@/views/KPIDashboard.vue')
```

### Lazy Loading
- Route-based code splitting
- Component lazy loading
- Image lazy loading

### API Optimization
- Parallel requests with `Promise.all()`
- Request caching
- Debounced search inputs
- Pagination for large datasets

### State Management
- Selective component updates
- Computed properties for derived state
- Vuex/Pinia persistence

## Testing Recommendations

### Unit Tests
```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import KPIDashboard from '@/views/KPIDashboard.vue'

describe('KPIDashboard', () => {
  it('renders all 10 KPI cards', () => {
    const wrapper = mount(KPIDashboard)
    expect(wrapper.findAll('.kpi-card')).toHaveLength(10)
  })
})
```

### E2E Tests
```javascript
describe('Data Entry Flow', () => {
  it('submits downtime entry successfully', () => {
    cy.visit('/data-entry/downtime')
    cy.get('[data-test="equipment"]').select('Line 1')
    cy.get('[data-test="reason"]').select('Breakdown')
    cy.get('[data-test="submit"]').click()
    cy.contains('Entry created successfully')
  })
})
```

## Deployment

### Build Command
```bash
npm run build
```

### Environment Variables
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=KPI Operations Dashboard
```

### Production Optimization
- Minification enabled
- Tree shaking
- Asset optimization
- Gzip compression
- CDN for static assets

## Future Enhancements

1. **Real-Time Updates**: WebSocket integration for live KPI updates
2. **Offline Support**: PWA with service worker for offline data entry
3. **Advanced Analytics**: Predictive analytics and forecasting
4. **Mobile App**: Native mobile apps (iOS/Android)
5. **Notifications**: Push notifications for critical alerts
6. **Customization**: User-configurable dashboards and widgets
7. **Multi-Language**: i18n support for multiple languages
8. **Dark Mode**: Theme switching capability

## Troubleshooting

### Common Issues

**1. API Connection Failed**
- Check VITE_API_BASE_URL in .env
- Verify backend server is running
- Check CORS configuration

**2. Charts Not Rendering**
- Verify Chart.js registration
- Check data format matches chart expectations
- Ensure canvas element exists

**3. State Not Updating**
- Check Pinia store actions
- Verify API responses
- Check component reactivity

**4. Route Not Found**
- Verify route configuration in router/index.js
- Check component import paths
- Ensure lazy loading syntax is correct

## Support

For questions or issues:
- Check API documentation: `/docs` endpoint
- Review backend logs for API errors
- Inspect browser console for frontend errors
- Use Vue DevTools for state debugging
