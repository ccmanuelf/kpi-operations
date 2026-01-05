"""
Analytics Pydantic schemas for request/response validation
Comprehensive analytics API models with OpenAPI documentation
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
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
    """Available KPI types for analytics"""
    EFFICIENCY = "efficiency"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    OEE = "oee"
    DEFECT_RATE = "defect_rate"
    ATTENDANCE = "attendance"


# ===== TREND ANALYSIS SCHEMAS =====

class TrendDataPoint(BaseModel):
    """Single data point in trend analysis"""
    date: date = Field(..., description="Date of the data point")
    value: Decimal = Field(..., description="KPI value")
    moving_average_7: Optional[Decimal] = Field(None, description="7-day moving average")
    moving_average_30: Optional[Decimal] = Field(None, description="30-day moving average")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "value": 85.5,
                "moving_average_7": 84.2,
                "moving_average_30": 83.8
            }
        }


class TrendAnalysisResponse(BaseModel):
    """Response for KPI trend analysis endpoint"""
    client_id: str = Field(..., description="Client ID")
    kpi_type: KPIType = Field(..., description="Type of KPI analyzed")
    time_range: str = Field(..., description="Time range analyzed (e.g., '30d')")
    start_date: date = Field(..., description="Analysis start date")
    end_date: date = Field(..., description="Analysis end date")
    data_points: List[TrendDataPoint] = Field(..., description="Time series data points")
    trend_direction: TrendDirection = Field(..., description="Overall trend direction")
    trend_slope: Decimal = Field(..., description="Linear regression slope (change per day)")
    average_value: Decimal = Field(..., description="Mean value over period")
    std_deviation: Decimal = Field(..., description="Standard deviation")
    min_value: Decimal = Field(..., description="Minimum value")
    max_value: Decimal = Field(..., description="Maximum value")
    anomalies_detected: int = Field(..., description="Number of anomalies detected")
    anomaly_dates: List[date] = Field(default=[], description="Dates with anomalies")

    class Config:
        json_schema_extra = {
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


# ===== PREDICTION SCHEMAS =====

class PredictionDataPoint(BaseModel):
    """Single prediction data point"""
    date: date = Field(..., description="Predicted date")
    predicted_value: Decimal = Field(..., description="Predicted KPI value")
    lower_bound: Decimal = Field(..., description="95% confidence interval lower bound")
    upper_bound: Decimal = Field(..., description="95% confidence interval upper bound")
    confidence: Decimal = Field(..., description="Prediction confidence (0-100)")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-02-01",
                "predicted_value": 86.5,
                "lower_bound": 82.1,
                "upper_bound": 90.9,
                "confidence": 85.0
            }
        }


class PredictionResponse(BaseModel):
    """Response for KPI prediction/forecasting endpoint"""
    client_id: str = Field(..., description="Client ID")
    kpi_type: KPIType = Field(..., description="Type of KPI predicted")
    prediction_method: str = Field(..., description="Forecasting method used (exponential_smoothing, arima, linear)")
    historical_start: date = Field(..., description="Start of historical data used")
    historical_end: date = Field(..., description="End of historical data used")
    forecast_start: date = Field(..., description="Start of forecast period")
    forecast_end: date = Field(..., description="End of forecast period")
    predictions: List[PredictionDataPoint] = Field(..., description="Forecasted data points")
    model_accuracy: Decimal = Field(..., description="Model accuracy score (0-100)")
    historical_average: Decimal = Field(..., description="Historical average for reference")
    predicted_average: Decimal = Field(..., description="Average of predictions")
    trend_continuation: bool = Field(..., description="Whether current trend is expected to continue")

    class Config:
        json_schema_extra = {
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


# ===== COMPARISON SCHEMAS =====

class ClientComparisonData(BaseModel):
    """Comparison data for a single client"""
    client_id: str = Field(..., description="Client ID")
    client_name: str = Field(..., description="Client name")
    average_value: Decimal = Field(..., description="Average KPI value")
    percentile_rank: int = Field(..., description="Percentile rank (0-100)")
    above_benchmark: bool = Field(..., description="Whether above industry benchmark")
    performance_rating: str = Field(..., description="Performance rating (Excellent, Good, Fair, Poor)")
    total_data_points: int = Field(..., description="Number of data points")

    class Config:
        json_schema_extra = {
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


class ComparisonResponse(BaseModel):
    """Response for client-to-client benchmarking endpoint"""
    kpi_type: KPIType = Field(..., description="Type of KPI compared")
    time_range: str = Field(..., description="Time range for comparison")
    start_date: date = Field(..., description="Comparison start date")
    end_date: date = Field(..., description="Comparison end date")
    clients: List[ClientComparisonData] = Field(..., description="Client comparison data")
    overall_average: Decimal = Field(..., description="Overall average across all clients")
    industry_benchmark: Decimal = Field(..., description="Industry benchmark value")
    best_performer: str = Field(..., description="Best performing client ID")
    worst_performer: str = Field(..., description="Worst performing client ID")
    performance_spread: Decimal = Field(..., description="Difference between best and worst")

    class Config:
        json_schema_extra = {
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


# ===== HEATMAP SCHEMAS =====

class HeatmapCell(BaseModel):
    """Single cell in performance heatmap"""
    date: date = Field(..., description="Date")
    shift_id: str = Field(..., description="Shift identifier")
    shift_name: str = Field(..., description="Shift name (e.g., 'Day Shift')")
    value: Optional[Decimal] = Field(None, description="KPI value (null if no data)")
    performance_level: str = Field(..., description="Performance level (Excellent, Good, Fair, Poor, No Data)")
    color_code: str = Field(..., description="Suggested color code for visualization")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "shift_id": "SHIFT-001",
                "shift_name": "Day Shift",
                "value": 87.5,
                "performance_level": "Excellent",
                "color_code": "#22c55e"
            }
        }


class HeatmapResponse(BaseModel):
    """Response for performance heatmap endpoint"""
    client_id: str = Field(..., description="Client ID")
    kpi_type: KPIType = Field(..., description="Type of KPI visualized")
    time_range: str = Field(..., description="Time range displayed")
    start_date: date = Field(..., description="Heatmap start date")
    end_date: date = Field(..., description="Heatmap end date")
    cells: List[HeatmapCell] = Field(..., description="Heatmap cells (date x shift matrix)")
    shifts: List[str] = Field(..., description="List of shift names")
    dates: List[date] = Field(..., description="List of dates")
    color_scale: Dict[str, str] = Field(..., description="Color scale mapping")

    class Config:
        json_schema_extra = {
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


# ===== PARETO ANALYSIS SCHEMAS =====

class ParetoItem(BaseModel):
    """Single item in Pareto analysis"""
    defect_type: str = Field(..., description="Defect type/category")
    count: int = Field(..., description="Defect count")
    percentage: Decimal = Field(..., description="Percentage of total")
    cumulative_percentage: Decimal = Field(..., description="Cumulative percentage")
    is_vital_few: bool = Field(..., description="Part of vital few (80% rule)")

    class Config:
        json_schema_extra = {
            "example": {
                "defect_type": "Stitching",
                "count": 145,
                "percentage": 45.2,
                "cumulative_percentage": 45.2,
                "is_vital_few": True
            }
        }


class ParetoResponse(BaseModel):
    """Response for defect Pareto analysis endpoint"""
    client_id: str = Field(..., description="Client ID")
    time_range: str = Field(..., description="Time range analyzed")
    start_date: date = Field(..., description="Analysis start date")
    end_date: date = Field(..., description="Analysis end date")
    items: List[ParetoItem] = Field(..., description="Pareto items (sorted by count descending)")
    total_defects: int = Field(..., description="Total defect count")
    vital_few_count: int = Field(..., description="Number of vital few categories")
    vital_few_percentage: Decimal = Field(..., description="Percentage covered by vital few")
    pareto_threshold: Decimal = Field(default=Decimal("80.0"), description="Pareto threshold used")

    class Config:
        json_schema_extra = {
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
