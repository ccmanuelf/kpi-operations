# Advanced Analytics Dashboard Backend API

## Overview

Comprehensive analytics backend API with 5 specialized endpoints for KPI trend analysis, predictive forecasting, client benchmarking, performance heatmaps, and Pareto analysis.

## Architecture

### File Structure

```
backend/
├── routes/
│   └── analytics.py              # 5 analytics endpoints with OpenAPI docs
├── calculations/
│   ├── trend_analysis.py         # 9 trend calculation functions
│   └── predictions.py            # 7 forecasting algorithms
├── crud/
│   └── analytics.py              # 8 database query functions
└── schemas/
    └── analytics.py              # 15 Pydantic models

tests/
├── test_analytics_api.py         # 45+ endpoint integration tests
└── test_trend_analysis.py        # 30+ calculation unit tests
```

## Endpoints

### 1. GET /api/analytics/trends

**Purpose**: Analyze KPI trends over time with statistical analysis

**Features**:
- 7-day and 30-day moving averages
- Linear regression with R-squared
- Trend direction classification (increasing, decreasing, stable, volatile)
- Anomaly detection using 2-sigma method
- Statistical measures (mean, std dev, min, max)

**Parameters**:
- `client_id` (required): Client identifier
- `kpi_type` (required): efficiency | performance | quality | oee
- `time_range` (optional): 7d | 30d | 90d (default: 30d)
- `start_date` (optional): Custom start date (overrides time_range)
- `end_date` (optional): Custom end date

**Response Example**:
```json
{
  "client_id": "BOOT-LINE-A",
  "kpi_type": "efficiency",
  "time_range": "30d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-30",
  "data_points": [
    {
      "date": "2024-01-15",
      "value": 85.5,
      "moving_average_7": 84.2,
      "moving_average_30": 83.8
    }
  ],
  "trend_direction": "increasing",
  "trend_slope": 0.15,
  "average_value": 84.5,
  "std_deviation": 3.2,
  "min_value": 78.5,
  "max_value": 92.3,
  "anomalies_detected": 2,
  "anomaly_dates": ["2024-01-15", "2024-01-22"]
}
```

**Access Control**: Client-specific filtering enforced via `verify_client_access`

---

### 2. GET /api/analytics/predictions

**Purpose**: Forecast future KPI values using time series analysis

**Features**:
- Automatic method selection based on data characteristics
- Simple exponential smoothing (stable data)
- Double exponential smoothing / Holt's method (trending data)
- Linear trend extrapolation
- 95% confidence intervals
- Accuracy scoring (0-100)

**Parameters**:
- `client_id` (required): Client identifier
- `kpi_type` (required): efficiency | performance | quality
- `historical_days` (optional): 7-90 days (default: 30)
- `forecast_days` (optional): 1-30 days (default: 7)
- `method` (optional): auto | simple | double | linear (default: auto)

**Response Example**:
```json
{
  "client_id": "BOOT-LINE-A",
  "kpi_type": "efficiency",
  "prediction_method": "double_exponential_smoothing",
  "historical_start": "2024-01-01",
  "historical_end": "2024-01-30",
  "forecast_start": "2024-01-31",
  "forecast_end": "2024-02-07",
  "predictions": [
    {
      "date": "2024-02-01",
      "predicted_value": 86.5,
      "lower_bound": 82.1,
      "upper_bound": 90.9,
      "confidence": 85.0
    }
  ],
  "model_accuracy": 92.5,
  "historical_average": 84.5,
  "predicted_average": 86.2,
  "trend_continuation": true
}
```

**Algorithm Selection Logic**:
1. **Strong linear trend (R² > 0.7, |slope| > 0.1)**: Double exponential smoothing
2. **Moderate trend**: Linear extrapolation
3. **Weak trend or high variability**: Simple exponential smoothing

---

### 3. GET /api/analytics/comparisons

**Purpose**: Benchmark KPI performance across multiple clients

**Features**:
- Client performance ranking
- Percentile calculations (0-100)
- Industry benchmark comparison
- Performance ratings (Excellent, Good, Fair, Poor)
- Best and worst performer identification
- Multi-tenant aware (shows only accessible clients)

**Parameters**:
- `kpi_type` (required): efficiency | performance | quality
- `time_range` (optional): 7d | 30d | 90d (default: 30d)
- `start_date` (optional): Custom start date
- `end_date` (optional): Custom end date

**Response Example**:
```json
{
  "kpi_type": "efficiency",
  "time_range": "30d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-30",
  "clients": [
    {
      "client_id": "BOOT-LINE-A",
      "client_name": "Boot Production Line A",
      "average_value": 87.5,
      "percentile_rank": 82,
      "above_benchmark": true,
      "performance_rating": "Excellent",
      "total_data_points": 30
    }
  ],
  "overall_average": 84.5,
  "industry_benchmark": 85.0,
  "best_performer": "CLIENT-A",
  "worst_performer": "CLIENT-D",
  "performance_spread": 15.3
}
```

**Performance Rating Logic**:
- **Excellent**: ≥110% of benchmark
- **Good**: 95-110% of benchmark
- **Fair**: 85-95% of benchmark
- **Poor**: <85% of benchmark

---

### 4. GET /api/analytics/heatmap

**Purpose**: Visualize KPI performance by date and shift in matrix format

**Features**:
- Date × Shift matrix visualization
- Color-coded performance levels
- Missing data handling
- Suggested color scale for UI rendering
- All dates and shifts included (fills gaps)

**Parameters**:
- `client_id` (required): Client identifier
- `kpi_type` (required): efficiency | performance | quality
- `time_range` (optional): 7d | 30d | 90d (default: 30d)
- `start_date` (optional): Custom start date
- `end_date` (optional): Custom end date

**Response Example**:
```json
{
  "client_id": "BOOT-LINE-A",
  "kpi_type": "efficiency",
  "time_range": "30d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-30",
  "cells": [
    {
      "date": "2024-01-15",
      "shift_id": "SHIFT-001",
      "shift_name": "Day Shift",
      "value": 87.5,
      "performance_level": "Excellent",
      "color_code": "#22c55e"
    }
  ],
  "shifts": ["Day Shift", "Night Shift"],
  "dates": ["2024-01-01", "2024-01-02", "..."],
  "color_scale": {
    "Excellent": "#22c55e",
    "Good": "#84cc16",
    "Fair": "#eab308",
    "Poor": "#ef4444",
    "No Data": "#94a3b8"
  }
}
```

**Color Mapping**:
- **Excellent** (#22c55e): >110% of benchmark
- **Good** (#84cc16): 100-110% of benchmark
- **Fair** (#eab308): 90-100% of benchmark
- **Poor** (#ef4444): <90% of benchmark
- **No Data** (#94a3b8): Missing data

---

### 5. GET /api/analytics/pareto

**Purpose**: Identify vital few defect categories using Pareto principle (80/20 rule)

**Features**:
- Defects sorted by frequency (descending)
- Cumulative percentage calculation
- Vital few identification (configurable threshold)
- Quality improvement prioritization

**Parameters**:
- `client_id` (required): Client identifier
- `time_range` (optional): 7d | 30d | 90d (default: 30d)
- `start_date` (optional): Custom start date
- `end_date` (optional): Custom end date
- `pareto_threshold` (optional): 50-95 (default: 80.0)

**Response Example**:
```json
{
  "client_id": "BOOT-LINE-A",
  "time_range": "30d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-30",
  "items": [
    {
      "defect_type": "Stitching",
      "count": 145,
      "percentage": 45.2,
      "cumulative_percentage": 45.2,
      "is_vital_few": true
    }
  ],
  "total_defects": 320,
  "vital_few_count": 3,
  "vital_few_percentage": 82.5,
  "pareto_threshold": 80.0
}
```

**Use Cases**:
- Quality improvement prioritization
- Root cause analysis focus
- Resource allocation for defect reduction
- Six Sigma DMAIC projects

---

## Calculation Modules

### Trend Analysis Functions

1. **`calculate_moving_average(values, window)`**
   - Simple moving average with configurable window
   - Returns None for insufficient data points

2. **`calculate_exponential_moving_average(values, alpha)`**
   - EMA with smoothing factor (0 < alpha ≤ 1)
   - Default alpha: 0.2

3. **`linear_regression(x_values, y_values)`**
   - Least squares regression
   - Returns (slope, intercept, r_squared)

4. **`determine_trend_direction(slope, r_squared, std_dev, mean)`**
   - Classifies trend as: increasing, decreasing, stable, volatile
   - Uses R² and coefficient of variation

5. **`detect_anomalies(values, threshold_std)`**
   - Standard deviation method (default: 2-sigma)
   - Returns list of anomaly indices

6. **`calculate_seasonal_decomposition(values, period)`**
   - Additive model: Trend + Seasonal + Residual
   - Default period: 7 (weekly patterns)

7. **`analyze_trend(dates, values)`**
   - Comprehensive trend analysis
   - Returns TrendResult with slope, R², and direction

### Prediction Functions

1. **`simple_exponential_smoothing(values, alpha, forecast_periods)`**
   - Best for: Stable data without trend
   - Constant level forecast

2. **`double_exponential_smoothing(values, alpha, beta, forecast_periods)`**
   - Best for: Data with linear trend
   - Holt's two-parameter method

3. **`linear_trend_extrapolation(values, forecast_periods)`**
   - Best for: Strong linear patterns
   - Least squares projection

4. **`auto_forecast(values, forecast_periods)`**
   - Automatic method selection
   - Analyzes data characteristics and selects best algorithm

5. **`calculate_forecast_accuracy(actual, predicted)`**
   - Returns MAE, RMSE, MAPE metrics

---

## Multi-Tenant Security

All endpoints enforce client access control:

1. **Client Filtering**:
   - `verify_client_access(user, client_id)` validates access
   - Raises `ClientAccessError` (403) if denied

2. **Role-Based Access**:
   - **ADMIN/POWERUSER**: Access all clients
   - **LEADER/OPERATOR**: Access only assigned clients (comma-separated list)

3. **Database Queries**:
   - All queries use `get_user_client_filter(user)`
   - Automatic WHERE clause injection for client isolation

4. **Comparison Endpoint**:
   - Shows only clients user has access to
   - No data leakage across tenants

---

## Testing

### API Tests (`test_analytics_api.py`)

- **45+ integration tests** covering:
  - Success scenarios for all 5 endpoints
  - Custom date ranges
  - Invalid parameters (validation errors)
  - Authentication failures (401)
  - Authorization failures (403)
  - Multi-KPI workflows
  - Full analytics workflow integration

### Calculation Tests (`test_trend_analysis.py`)

- **30+ unit tests** covering:
  - Moving averages (simple & exponential)
  - Linear regression (increasing, decreasing, stable)
  - Trend direction classification
  - Anomaly detection
  - Seasonal decomposition
  - All forecasting methods
  - Accuracy metrics
  - Edge cases and error handling

---

## OpenAPI/Swagger Documentation

All endpoints include:
- Comprehensive descriptions
- Parameter documentation with constraints
- Response schemas with examples
- HTTP status code documentation (200, 400, 403, 404)
- Usage examples in description
- Access control notes

**Access Swagger UI**: `http://localhost:8000/docs`

---

## Performance Considerations

1. **Database Queries**:
   - Aggregation at database level (AVG, SUM)
   - Indexed date and client_id columns
   - JOINs optimized with proper foreign keys

2. **Calculation Efficiency**:
   - O(n) moving averages
   - O(n) linear regression
   - O(n log n) sorting for Pareto
   - Minimal memory allocation

3. **Response Size**:
   - Heatmap: ~1KB per cell (30 days × 2 shifts = ~60KB)
   - Trends: ~100 bytes per data point
   - Predictions: ~150 bytes per forecast point

4. **Caching Opportunities** (future):
   - Cache trend analysis for unchanged date ranges
   - Cache client comparisons (TTL: 1 hour)
   - Invalidate on new production data

---

## Usage Examples

### 1. Dashboard Overview

```javascript
// Fetch 30-day trends for main KPIs
const efficiency = await fetch('/api/analytics/trends?client_id=BOOT-LINE-A&kpi_type=efficiency&time_range=30d');
const performance = await fetch('/api/analytics/trends?client_id=BOOT-LINE-A&kpi_type=performance&time_range=30d');
const quality = await fetch('/api/analytics/trends?client_id=BOOT-LINE-A&kpi_type=quality&time_range=30d');
```

### 2. Predictive Analytics

```javascript
// Forecast next 7 days
const forecast = await fetch('/api/analytics/predictions?client_id=BOOT-LINE-A&kpi_type=efficiency&forecast_days=7');
```

### 3. Benchmarking

```javascript
// Compare performance across all accessible clients
const comparison = await fetch('/api/analytics/comparisons?kpi_type=efficiency&time_range=30d');
```

### 4. Shift Analysis

```javascript
// Heatmap for identifying problematic shifts/dates
const heatmap = await fetch('/api/analytics/heatmap?client_id=BOOT-LINE-A&kpi_type=efficiency&time_range=30d');
```

### 5. Quality Focus

```javascript
// Identify top defect types for improvement
const pareto = await fetch('/api/analytics/pareto?client_id=BOOT-LINE-A&time_range=30d');
```

---

## Future Enhancements

1. **Advanced Forecasting**:
   - ARIMA/SARIMA models (requires scipy)
   - Prophet (Facebook's forecasting library)
   - Neural network predictions

2. **Statistical Tests**:
   - Shapiro-Wilk normality test
   - Mann-Kendall trend test
   - Granger causality

3. **Additional Visualizations**:
   - Correlation matrix
   - Box plots by shift
   - Control charts (SPC)

4. **Real-Time Analytics**:
   - WebSocket streaming for live updates
   - Incremental calculations
   - Alert generation

5. **Machine Learning**:
   - Anomaly detection (Isolation Forest)
   - Clustering similar clients
   - Predictive maintenance

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK**: Successful response
- **400 Bad Request**: Invalid parameters or insufficient data
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Access denied to client data
- **404 Not Found**: No data found for specified parameters
- **422 Unprocessable Entity**: Validation errors (Pydantic)
- **500 Internal Server Error**: Unexpected server errors

Error responses include descriptive messages:
```json
{
  "detail": "Insufficient historical data for forecasting. Need at least 7 days, found 3"
}
```

---

## Dependencies

Required Python packages:
```txt
fastapi>=0.104.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
python-dateutil>=2.8.0
```

No external dependencies for calculations (pure Python implementation).

---

## Deployment Notes

1. **Database Indexes**:
   ```sql
   CREATE INDEX idx_production_date_client ON production_entries(production_date, client_id);
   CREATE INDEX idx_quality_date_client ON quality_entries(inspection_date, client_id);
   ```

2. **Environment Variables**:
   - No additional env vars required
   - Uses existing `DATABASE_URL` and authentication

3. **API Rate Limiting** (recommended):
   - Trends: 100 requests/minute
   - Predictions: 50 requests/minute (computationally expensive)
   - Comparisons: 50 requests/minute
   - Heatmap: 100 requests/minute
   - Pareto: 100 requests/minute

---

## License

Part of KPI Operations Dashboard platform. See project README for licensing information.
