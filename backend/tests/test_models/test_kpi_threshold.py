"""
Tests for KPI Threshold Pydantic models
Target: Cover all 6 models in backend/models/kpi_threshold.py
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.models.kpi_threshold import (
    KPIThresholdBase,
    KPIThresholdCreate,
    KPIThresholdUpdate,
    KPIThresholdResponse,
    KPIThresholdSet,
    KPIThresholdsBulkUpdate,
)


class TestKPIThresholdBase:
    def test_create_with_required_fields(self):
        t = KPIThresholdBase(kpi_key="efficiency", target_value=95.0)
        assert t.kpi_key == "efficiency"
        assert t.target_value == 95.0
        assert t.unit == "%"
        assert t.higher_is_better == "Y"
        assert t.warning_threshold is None
        assert t.critical_threshold is None

    def test_create_with_all_fields(self):
        t = KPIThresholdBase(
            kpi_key="quality",
            target_value=99.0,
            warning_threshold=95.0,
            critical_threshold=90.0,
            unit="ppm",
            higher_is_better="N",
        )
        assert t.warning_threshold == 95.0
        assert t.critical_threshold == 90.0
        assert t.unit == "ppm"
        assert t.higher_is_better == "N"

    def test_higher_is_better_pattern_valid(self):
        for val in ("Y", "N"):
            t = KPIThresholdBase(kpi_key="k", target_value=1.0, higher_is_better=val)
            assert t.higher_is_better == val

    def test_higher_is_better_pattern_invalid(self):
        with pytest.raises(ValidationError):
            KPIThresholdBase(kpi_key="k", target_value=1.0, higher_is_better="X")

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            KPIThresholdBase()


class TestKPIThresholdCreate:
    def test_inherits_base_fields(self):
        t = KPIThresholdCreate(kpi_key="oee", target_value=85.0)
        assert t.kpi_key == "oee"
        assert t.client_id is None

    def test_with_client_id(self):
        t = KPIThresholdCreate(kpi_key="oee", target_value=85.0, client_id="CLIENT-1")
        assert t.client_id == "CLIENT-1"


class TestKPIThresholdUpdate:
    def test_all_fields_optional(self):
        t = KPIThresholdUpdate()
        assert t.target_value is None
        assert t.warning_threshold is None
        assert t.critical_threshold is None
        assert t.unit is None
        assert t.higher_is_better is None

    def test_partial_update(self):
        t = KPIThresholdUpdate(target_value=90.0, unit="ppm")
        assert t.target_value == 90.0
        assert t.unit == "ppm"

    def test_higher_is_better_pattern_invalid(self):
        with pytest.raises(ValidationError):
            KPIThresholdUpdate(higher_is_better="MAYBE")


class TestKPIThresholdResponse:
    def test_from_attributes_config(self):
        assert KPIThresholdResponse.model_config.get("from_attributes") is True

    def test_create_response(self):
        t = KPIThresholdResponse(
            threshold_id="TH-001",
            kpi_key="efficiency",
            target_value=95.0,
            client_id="C1",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 2),
        )
        assert t.threshold_id == "TH-001"
        assert t.created_at == datetime(2026, 1, 1)


class TestKPIThresholdSet:
    def test_empty_set(self):
        s = KPIThresholdSet()
        assert s.client_id is None
        assert s.thresholds == []

    def test_populated_set(self):
        resp = KPIThresholdResponse(
            threshold_id="TH-1", kpi_key="quality", target_value=99.0
        )
        s = KPIThresholdSet(client_id="C1", client_name="Acme", thresholds=[resp])
        assert len(s.thresholds) == 1
        assert s.client_name == "Acme"


class TestKPIThresholdsBulkUpdate:
    def test_bulk_update(self):
        items = [
            KPIThresholdCreate(kpi_key="efficiency", target_value=95.0),
            KPIThresholdCreate(kpi_key="quality", target_value=99.0, client_id="C1"),
        ]
        bulk = KPIThresholdsBulkUpdate(client_id="C1", thresholds=items)
        assert len(bulk.thresholds) == 2
        assert bulk.client_id == "C1"
