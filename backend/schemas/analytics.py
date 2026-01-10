"""
Analytics Pydantic schemas for request/response validation
Comprehensive analytics API models with OpenAPI documentation
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import datetime
from decimal import Decimal
from enum import Enum


class TimeRange(str, Enum):
    """Time range options for analytics queries"""
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    CUSTOM = "custom"


class TrendDirection(str, Enum):
    """Trend direction indicators"""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class KPIType(str, Enum):
    """
    All 10 KPI types for Phase 5 comprehensive analytics

    Production KPIs:
    - EFFICIENCY: Production efficiency percentage
    - PERFORMANCE: Production performance percentage
    - AVAILABILITY: Equipment availability percentage
    - OEE: Overall Equipment Effectiveness

    Quality KPIs:
    - PPM: Parts Per Million defects
    - DPMO: Defects Per Million Opportunities
    - FPY: First Pass Yield percentage
    - RTY: Rolled Throughput Yield percentage
    - QUALITY: General quality rate

    Workforce & Delivery KPIs:
    - ABSENTEEISM: Absenteeism rate percentage
    - OTD: On-Time Delivery percentage
    - ATTENDANCE: Attendance rate (inverse of absenteeism)
    - DEFECT_RATE: Overall defect rate
    """
    # Production KPIs
    EFFICIENCY = "efficiency"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    OEE = "oee"

    # Quality KPIs
    PPM = "ppm"
    DPMO = "dpmo"
    FPY = "fpy"
    RTY = "rty"
    QUALITY = "quality"
    DEFECT_RATE = "defect_rate"

    # Workforce & Delivery KPIs
    ABSENTEEISM = "absenteeism"
    OTD = "otd"
    ATTENDANCE = "attendance"


# ===== TREND ANALYSIS SCHEMAS =====

class TrendDataPoint(BaseModel):
    """Single data point in trend analysis"""
    date: datetime.date = Field(..., description="Date of the data point")
    value: float = Field(..., description="KPI value")
    moving_average_7: Optional[float] = Field(None, description="7-day moving average")
    moving_average_30: Optional[float] = Field(None, description="30-day moving average")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "value": 85.5,
                "moving_average_7": 84.2,
                "moving_average_30": 83.8
            }
        }
    )


class TrendAnalysisResponse(BaseModel):
    """Response for KPI trend analysis endpoint"""
    client_id: str = Field(..., description="Client ID")
    kpi_type: KPIType = Field(..., description="Type of KPI analyzed")
    time_range: str = Field(..., description="Time range analyzed (e.g., '30d')")
    start_date: datetime.date = Field(..., description="Analysis start date")
    end_date: datetime.date = Field(..., description="Analysis end date")
    data_points: List[TrendDataPoint] = Field(..., description="Time series data points")
    trend_direction: TrendDirection = Field(..., description="Overall trend direction")
    trend_slope: float = Field(..., description="Linear regression slope (change per day)")
    average_value: float = Field(..., description="Mean value over period")
    std_deviation: float = Field(..., description="Standard deviation")
    min_value: float = Field(..., description="Minimum value")
    max_value: float = Field(..., description="Maximum value")
    anomalies_detected: int = Field(..., description="Number of anomalies detected")
    anomaly_dates: List[datetime.date] = Field(default=[], description="Dates with anomalies")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "30d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-30",
                "data_points": [],
                "trend_direction": "increasing",
                "trend_slope": 0.15,
                "average_value": 84.5,
                "std_deviation": 3.2,
                "min_value": 78.5,
                "max_value": 92.3,
                "anomalies_detected": 2,
                "anomaly_dates": ["2024-01-15", "2024-01-22"]
            }
        }
    )


# ===== PREDICTION SCHEMAS =====

class PredictionDataPoint(BaseModel):
    """Single prediction data point"""
    date: datetime.date = Field(..., description="Predicted date")
    predicted_value: float = Field(..., description="Predicted KPI value")
    lower_bound: float = Field(..., description="95% confidence interval lower bound")
    upper_bound: float = Field(..., description="95% confidence interval upper bound")
    confidence: float = Field(..., description="Prediction confidence (0-100)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-02-01",
                "predicted_value": 86.5,
                "lower_bound": 82.1,
                "upper_bound": 90.9,
                "confidence": 85.0
            }
        }
    )


class PredictionResponse(BaseModel):
    """Response for KPI prediction/forecasting endpoint"""
    client_id: str = Field(..., description="Client ID")
    kpi_type: KPIType = Field(..., description="Type of KPI predicted")
    prediction_method: str = Field(..., description="Forecasting method used (exponential_smoothing, arima, linear)")
    historical_start: datetime.date = Field(..., description="Start of historical data used")
    historical_end: datetime.date = Field(..., description="End of historical data used")
    forecast_start: datetime.date = Field(..., description="Start of forecast period")
    forecast_end: datetime.date = Field(..., description="End of forecast period")
    predictions: List[PredictionDataPoint] = Field(..., description="Forecasted data points")
    model_accuracy: float = Field(..., description="Model accuracy score (0-100)")
    historical_average: float = Field(..., description="Historical average for reference")
    predicted_average: float = Field(..., description="Average of predictions")
    trend_continuation: bool = Field(..., description="Whether current trend is expected to continue")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "prediction_method": "exponential_smoothing",
                "historical_start": "2024-01-01",
                "historical_end": "2024-01-30",
                "forecast_start": "2024-01-31",
                "forecast_end": "2024-02-07",
                "predictions": [],
                "model_accuracy": 92.5,
                "historical_average": 84.5,
                "predicted_average": 86.2,
                "trend_continuation": True
            }
        }
    )


# ===== COMPARISON SCHEMAS =====

class ClientComparisonData(BaseModel):
    """Comparison data for a single client"""
    client_id: str = Field(..., description="Client ID")
    client_name: str = Field(..., description="Client name")
    average_value: float = Field(..., description="Average KPI value")
    percentile_rank: int = Field(..., description="Percentile rank (0-100)")
    above_benchmark: bool = Field(..., description="Whether above industry benchmark")
    performance_rating: str = Field(..., description="Performance rating (Excellent, Good, Fair, Poor)")
    total_data_points: int = Field(..., description="Number of data points")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "client_name": "Boot Production Line A",
                "average_value": 87.5,
                "percentile_rank": 82,
                "above_benchmark": True,
                "performance_rating": "Excellent",
                "total_data_points": 30
            }
        }
    )


class ComparisonResponse(BaseModel):
    """Response for client-to-client benchmarking endpoint"""
    kpi_type: KPIType = Field(..., description="Type of KPI compared")
    time_range: str = Field(..., description="Time range for comparison")
    start_date: datetime.date = Field(..., description="Comparison start date")
    end_date: datetime.date = Field(..., description="Comparison end date")
    clients: List[ClientComparisonData] = Field(..., description="Client comparison data")
    overall_average: float = Field(..., description="Overall average across all clients")
    industry_benchmark: float = Field(..., description="Industry benchmark value")
    best_performer: str = Field(..., description="Best performing client ID")
    worst_performer: str = Field(..., description="Worst performing client ID")
    performance_spread: float = Field(..., description="Difference between best and worst")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kpi_type": "efficiency",
                "time_range": "30d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-30",
                "clients": [],
                "overall_average": 84.5,
                "industry_benchmark": 85.0,
                "best_performer": "CLIENT-A",
                "worst_performer": "CLIENT-D",
                "performance_spread": 15.3
            }
        }
    )


# ===== HEATMAP SCHEMAS =====

class HeatmapCell(BaseModel):
    """Single cell in performance heatmap"""
    date: datetime.date = Field(..., description="Date")
    shift_id: str = Field(..., description="Shift identifier")
    shift_name: str = Field(..., description="Shift name (e.g., 'Day Shift')")
    value: Optional[float] = Field(None, description="KPI value (null if no data)")
    performance_level: str = Field(..., description="Performance level (Excellent, Good, Fair, Poor, No Data)")
    color_code: str = Field(..., description="Suggested color code for visualization")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "shift_id": "SHIFT-001",
                "shift_name": "Day Shift",
                "value": 87.5,
                "performance_level": "Excellent",
                "color_code": "#22c55e"
            }
        }
    )


class HeatmapResponse(BaseModel):
    """Response for performance heatmap endpoint"""
    client_id: str = Field(..., description="Client ID")
    kpi_type: KPIType = Field(..., description="Type of KPI visualized")
    time_range: str = Field(..., description="Time range displayed")
    start_date: datetime.date = Field(..., description="Heatmap start date")
    end_date: datetime.date = Field(..., description="Heatmap end date")
    cells: List[HeatmapCell] = Field(..., description="Heatmap cells (date x shift matrix)")
    shifts: List[str] = Field(..., description="List of shift names")
    dates: List[datetime.date] = Field(..., description="List of dates")
    color_scale: Dict[str, str] = Field(..., description="Color scale mapping")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "time_range": "30d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-30",
                "cells": [],
                "shifts": ["Day Shift", "Night Shift"],
                "dates": [],
                "color_scale": {
                    "Excellent": "#22c55e",
                    "Good": "#84cc16",
                    "Fair": "#eab308",
                    "Poor": "#ef4444",
                    "No Data": "#94a3b8"
                }
            }
        }
    )


# ===== PARETO ANALYSIS SCHEMAS =====

class ParetoItem(BaseModel):
    """Single item in Pareto analysis"""
    defect_type: str = Field(..., description="Defect type/category")
    count: int = Field(..., description="Defect count")
    percentage: float = Field(..., description="Percentage of total")
    cumulative_percentage: float = Field(..., description="Cumulative percentage")
    is_vital_few: bool = Field(..., description="Part of vital few (80% rule)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "defect_type": "Stitching",
                "count": 145,
                "percentage": 45.2,
                "cumulative_percentage": 45.2,
                "is_vital_few": True
            }
        }
    )


class ParetoResponse(BaseModel):
    """Response for defect Pareto analysis endpoint"""
    client_id: str = Field(..., description="Client ID")
    time_range: str = Field(..., description="Time range analyzed")
    start_date: datetime.date = Field(..., description="Analysis start date")
    end_date: datetime.date = Field(..., description="Analysis end date")
    items: List[ParetoItem] = Field(..., description="Pareto items (sorted by count descending)")
    total_defects: int = Field(..., description="Total defect count")
    vital_few_count: int = Field(..., description="Number of vital few categories")
    vital_few_percentage: float = Field(..., description="Percentage covered by vital few")
    pareto_threshold: float = Field(default=80.0, description="Pareto threshold used")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "time_range": "30d",
                "start_date": "2024-01-01",
                "end_date": "2024-01-30",
                "items": [],
                "total_defects": 320,
                "vital_few_count": 3,
                "vital_few_percentage": 82.5,
                "pareto_threshold": 80.0
            }
        }
    )


# ===== PHASE 5: ENHANCED PREDICTION SCHEMAS =====

class KPIBenchmark(BaseModel):
    """Industry benchmark data for a KPI"""
    target: float = Field(..., description="Target value")
    excellent: float = Field(..., description="Excellent threshold")
    good: float = Field(..., description="Good threshold")
    fair: float = Field(..., description="Fair threshold")
    unit: str = Field(..., description="Unit of measurement")
    description: str = Field(..., description="KPI description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target": 85.0,
                "excellent": 92.0,
                "good": 85.0,
                "fair": 75.0,
                "unit": "%",
                "description": "Production efficiency - actual vs. expected output"
            }
        }
    )


class KPIHealthAssessment(BaseModel):
    """Health assessment for a KPI based on current and predicted values"""
    health_score: float = Field(..., ge=0, le=100, description="Overall health score (0-100)")
    trend: str = Field(..., description="Trend direction (improving, declining, stable)")
    current_vs_target: float = Field(..., description="Difference from target value")
    recommendations: List[str] = Field(default=[], description="Action recommendations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "health_score": 82.5,
                "trend": "improving",
                "current_vs_target": -2.5,
                "recommendations": ["Monitor for continued improvement"]
            }
        }
    )


class EnhancedPredictionDataPoint(BaseModel):
    """Enhanced prediction data point with additional analytics"""
    date: datetime.date = Field(..., description="Predicted date")
    predicted_value: float = Field(..., description="Predicted KPI value")
    lower_bound: float = Field(..., description="95% confidence interval lower bound")
    upper_bound: float = Field(..., description="95% confidence interval upper bound")
    confidence: float = Field(..., description="Prediction confidence (0-100)")
    day_of_week: str = Field(..., description="Day of week name")
    is_weekend: bool = Field(default=False, description="Whether this is a weekend day")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-02-01",
                "predicted_value": 86.5,
                "lower_bound": 82.1,
                "upper_bound": 90.9,
                "confidence": 85.0,
                "day_of_week": "Thursday",
                "is_weekend": False
            }
        }
    )


class KPIHistoryPoint(BaseModel):
    """Historical KPI data point"""
    date: datetime.date = Field(..., description="Date of measurement")
    value: float = Field(..., description="KPI value")
    is_anomaly: bool = Field(default=False, description="Whether this is an anomaly")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "value": 85.5,
                "is_anomaly": False
            }
        }
    )


class ComprehensivePredictionResponse(BaseModel):
    """
    Comprehensive KPI prediction response with full analytics

    This enhanced response includes:
    - Historical data points
    - Forecasted predictions with confidence intervals
    - Health assessment and recommendations
    - Industry benchmarks
    - Method and accuracy details
    """
    client_id: str = Field(..., description="Client ID")
    kpi_type: str = Field(..., description="Type of KPI predicted")
    kpi_display_name: str = Field(..., description="Human-readable KPI name")

    # Historical data
    historical_start: datetime.date = Field(..., description="Start of historical data")
    historical_end: datetime.date = Field(..., description="End of historical data")
    historical_data: List[KPIHistoryPoint] = Field(..., description="Historical data points")
    historical_average: float = Field(..., description="Historical average value")
    current_value: float = Field(..., description="Most recent actual value")

    # Forecast data
    forecast_start: datetime.date = Field(..., description="Start of forecast period")
    forecast_end: datetime.date = Field(..., description="End of forecast period")
    predictions: List[EnhancedPredictionDataPoint] = Field(..., description="Forecasted values")
    predicted_average: float = Field(..., description="Average of predictions")

    # Model information
    prediction_method: str = Field(..., description="Forecasting method used")
    model_accuracy: float = Field(..., description="Model accuracy score (0-100)")

    # Health assessment
    health_assessment: KPIHealthAssessment = Field(..., description="KPI health evaluation")

    # Benchmarks
    benchmark: KPIBenchmark = Field(..., description="Industry benchmark data")

    # Trend analysis
    trend_continuation: bool = Field(..., description="Whether current trend continues")
    expected_change_percent: float = Field(..., description="Expected % change from current")

    # Metadata
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow, description="Response generation timestamp")
    data_quality_score: float = Field(default=100.0, description="Quality score of input data (0-100)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "kpi_type": "efficiency",
                "kpi_display_name": "Production Efficiency",
                "historical_start": "2024-01-01",
                "historical_end": "2024-01-30",
                "historical_data": [],
                "historical_average": 84.5,
                "current_value": 86.0,
                "forecast_start": "2024-01-31",
                "forecast_end": "2024-02-07",
                "predictions": [],
                "predicted_average": 87.2,
                "prediction_method": "double_exponential_smoothing",
                "model_accuracy": 92.5,
                "health_assessment": {
                    "health_score": 85.0,
                    "trend": "improving",
                    "current_vs_target": 1.0,
                    "recommendations": []
                },
                "benchmark": {
                    "target": 85.0,
                    "excellent": 92.0,
                    "good": 85.0,
                    "fair": 75.0,
                    "unit": "%",
                    "description": "Production efficiency"
                },
                "trend_continuation": True,
                "expected_change_percent": 1.4,
                "generated_at": "2024-01-30T12:00:00Z",
                "data_quality_score": 98.5
            }
        }
    )


class AllKPIPredictionsResponse(BaseModel):
    """Response containing predictions for all 10 KPIs"""
    client_id: str = Field(..., description="Client ID")
    forecast_days: int = Field(..., description="Number of days forecasted")
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Individual KPI predictions
    efficiency: Optional[ComprehensivePredictionResponse] = None
    performance: Optional[ComprehensivePredictionResponse] = None
    availability: Optional[ComprehensivePredictionResponse] = None
    oee: Optional[ComprehensivePredictionResponse] = None
    ppm: Optional[ComprehensivePredictionResponse] = None
    dpmo: Optional[ComprehensivePredictionResponse] = None
    fpy: Optional[ComprehensivePredictionResponse] = None
    rty: Optional[ComprehensivePredictionResponse] = None
    absenteeism: Optional[ComprehensivePredictionResponse] = None
    otd: Optional[ComprehensivePredictionResponse] = None

    # Summary metrics
    overall_health_score: float = Field(..., description="Average health score across all KPIs")
    kpis_improving: int = Field(default=0, description="Count of improving KPIs")
    kpis_declining: int = Field(default=0, description="Count of declining KPIs")
    kpis_stable: int = Field(default=0, description="Count of stable KPIs")
    priority_actions: List[str] = Field(default=[], description="Priority action items")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "BOOT-LINE-A",
                "forecast_days": 7,
                "generated_at": "2024-01-30T12:00:00Z",
                "overall_health_score": 82.5,
                "kpis_improving": 6,
                "kpis_declining": 2,
                "kpis_stable": 2,
                "priority_actions": [
                    "Review PPM trending upward",
                    "Monitor absenteeism rate"
                ]
            }
        }
    )
