"""
Tests for Workflow API Routes
Phase 10.4: Workflow Foundation - API Routes

Tests cover:
- Status transitions endpoints
- Transition history endpoints
- Workflow configuration endpoints
- Bulk operations endpoints
- Elapsed time analytics endpoints
- Statistics endpoints
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
import json


# Mock user for authentication
def create_mock_user(role="operator", client_id="CLIENT-001"):
    """Create a mock authenticated user"""
    user = Mock()
    user.user_id = 1
    user.username = "test_user"
    user.role = role
    user.client_id = client_id
    user.allowed_clients = [client_id] if client_id else []
    return user


def create_mock_admin_user(client_id="CLIENT-001"):
    """Create a mock admin user"""
    return create_mock_user(role="admin", client_id=client_id)


def create_mock_supervisor_user(client_id="CLIENT-001"):
    """Create a mock supervisor user"""
    return create_mock_user(role="supervisor", client_id=client_id)


class TestTransitionWorkOrder:
    """Test POST /api/workflow/work-orders/{id}/transition"""

    def test_transition_work_order_success(self):
        """Test successful work order transition"""
        from backend.routes.workflow import transition_work_order_status
        from backend.models.workflow import WorkflowTransitionCreate, WorkflowStatusEnum

        mock_db = Mock()
        mock_user = create_mock_user()

        transition = Mock()
        transition.to_status = WorkflowStatusEnum.RELEASED
        transition.notes = "Test transition"

        with patch("backend.routes.workflow.transition_work_order") as mock_func:
            mock_func.return_value = {"work_order": Mock(), "transition": Mock(), "success": True}

            result = transition_work_order_status(
                work_order_id="WO-001", transition=transition, db=mock_db, current_user=mock_user
            )

            assert result["success"] is True
            mock_func.assert_called_once()


class TestValidateTransition:
    """Test POST /api/workflow/work-orders/{id}/validate"""

    def test_validate_transition_endpoint(self):
        """Test transition validation endpoint"""
        from backend.routes.workflow import validate_work_order_transition

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.validate_transition") as mock_func:
            mock_func.return_value = {
                "is_valid": True,
                "from_status": "RECEIVED",
                "to_status": "RELEASED",
                "reason": None,
                "allowed_transitions": ["RELEASED", "ON_HOLD"],
            }

            result = validate_work_order_transition(
                work_order_id="WO-001", to_status="RELEASED", db=mock_db, current_user=mock_user
            )

            assert result["is_valid"] is True
            assert result["allowed_transitions"] is not None


class TestGetAllowedTransitions:
    """Test GET /api/workflow/work-orders/{id}/allowed-transitions"""

    def test_get_allowed_transitions_endpoint(self):
        """Test getting allowed transitions for work order"""
        from backend.routes.workflow import get_work_order_allowed_transitions

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.get_allowed_transitions_for_work_order") as mock_func:
            mock_func.return_value = {
                "work_order_id": "WO-001",
                "current_status": "RECEIVED",
                "allowed_next_statuses": ["RELEASED", "ON_HOLD", "CANCELLED"],
                "client_id": "CLIENT-001",
            }

            result = get_work_order_allowed_transitions(work_order_id="WO-001", db=mock_db, current_user=mock_user)

            assert result["current_status"] == "RECEIVED"
            assert "RELEASED" in result["allowed_next_statuses"]


class TestGetTransitionHistory:
    """Test GET /api/workflow/work-orders/{id}/history"""

    def test_get_transition_history_endpoint(self):
        """Test getting transition history for work order"""
        from backend.routes.workflow import get_work_order_transition_history

        mock_db = Mock()
        mock_user = create_mock_user()

        mock_transitions = [
            Mock(
                transition_id=1,
                from_status=None,
                to_status="RECEIVED",
                transitioned_at=datetime.utcnow(),
                notes="Initial",
            ),
            Mock(
                transition_id=2,
                from_status="RECEIVED",
                to_status="RELEASED",
                transitioned_at=datetime.utcnow(),
                notes=None,
            ),
        ]

        with patch("backend.routes.workflow.get_work_order_transitions") as mock_func:
            mock_func.return_value = mock_transitions

            result = get_work_order_transition_history(work_order_id="WO-001", db=mock_db, current_user=mock_user)

            assert len(result) == 2


class TestBulkTransition:
    """Test POST /api/workflow/bulk-transition"""

    def test_bulk_transition_success(self):
        """Test bulk transition endpoint"""
        from backend.routes.workflow import bulk_transition_work_orders_endpoint
        from backend.models.workflow import BulkTransitionRequest, WorkflowStatusEnum

        mock_db = Mock()
        mock_user = create_mock_supervisor_user()

        request = Mock()
        request.work_order_ids = ["WO-001", "WO-002", "WO-003"]
        request.to_status = WorkflowStatusEnum.RELEASED
        request.notes = "Bulk test"

        with patch("backend.routes.workflow.bulk_transition_work_orders") as mock_func:
            mock_func.return_value = {"total_requested": 3, "successful": 2, "failed": 1, "results": []}

            result = bulk_transition_work_orders_endpoint(
                request=request, client_id="CLIENT-001", db=mock_db, current_user=mock_user
            )

            assert result["total_requested"] == 3
            assert result["successful"] == 2


class TestWorkflowConfiguration:
    """Test workflow configuration endpoints"""

    def test_get_workflow_config(self):
        """Test GET /api/workflow/config/{client_id}"""
        from backend.routes.workflow import get_client_workflow_config

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.get_workflow_configuration") as mock_func:
            mock_func.return_value = {
                "client_id": "CLIENT-001",
                "workflow_statuses": ["RECEIVED", "RELEASED", "COMPLETED"],
                "workflow_transitions": {},
                "workflow_closure_trigger": "at_shipment",
            }

            result = get_client_workflow_config(client_id="CLIENT-001", db=mock_db, current_user=mock_user)

            assert result["client_id"] == "CLIENT-001"
            assert "workflow_statuses" in result

    def test_update_workflow_config(self):
        """Test PUT /api/workflow/config/{client_id}"""
        from backend.routes.workflow import update_client_workflow_config

        mock_db = Mock()
        mock_user = create_mock_supervisor_user()

        config = Mock()
        config.model_dump.return_value = {
            "workflow_statuses": ["RECEIVED", "COMPLETED"],
            "workflow_closure_trigger": "at_completion",
        }

        with patch("backend.routes.workflow.update_workflow_configuration") as mock_func:
            mock_func.return_value = {
                "client_id": "CLIENT-001",
                "workflow_statuses": ["RECEIVED", "COMPLETED"],
                "workflow_closure_trigger": "at_completion",
            }

            result = update_client_workflow_config(
                client_id="CLIENT-001", config=config, db=mock_db, current_user=mock_user
            )

            assert result["workflow_closure_trigger"] == "at_completion"


class TestApplyTemplate:
    """Test POST /api/workflow/config/{client_id}/apply-template"""

    def test_apply_template_endpoint(self):
        """Test applying workflow template"""
        from backend.routes.workflow import apply_workflow_template_endpoint

        mock_db = Mock()
        mock_user = create_mock_supervisor_user()

        with patch("backend.routes.workflow.apply_workflow_template") as mock_func:
            mock_func.return_value = {
                "client_id": "CLIENT-001",
                "workflow_statuses": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
                "template_applied": "standard",
            }

            result = apply_workflow_template_endpoint(
                client_id="CLIENT-001", template_id="standard", db=mock_db, current_user=mock_user
            )

            assert "workflow_statuses" in result


class TestListTemplates:
    """Test GET /api/workflow/templates"""

    def test_list_templates(self):
        """Test listing workflow templates"""
        from backend.routes.workflow import list_workflow_templates

        mock_user = create_mock_user()

        result = list_workflow_templates(current_user=mock_user)

        assert "templates" in result
        assert "count" in result
        assert result["count"] > 0

        # Verify template structure
        for template in result["templates"]:
            assert "template_id" in template
            assert "name" in template
            assert "workflow_statuses" in template


class TestElapsedTimeEndpoints:
    """Test elapsed time analytics endpoints"""

    def test_get_work_order_elapsed_time(self):
        """Test GET /api/workflow/work-orders/{id}/elapsed-time"""
        from backend.routes.workflow import get_work_order_elapsed_time

        mock_db = Mock()
        mock_user = create_mock_user()

        # Mock work order
        mock_wo = Mock()
        mock_wo.work_order_id = "WO-001"
        mock_wo.client_id = "CLIENT-001"
        mock_wo.status = "IN_PROGRESS"
        mock_wo.received_date = datetime.utcnow() - timedelta(hours=24)
        mock_wo.dispatch_date = datetime.utcnow() - timedelta(hours=12)
        mock_wo.closure_date = None
        mock_wo.shipped_date = None
        mock_wo.expected_date = datetime.utcnow() + timedelta(days=1)
        mock_wo.actual_delivery_date = None
        mock_wo.updated_at = datetime.utcnow()

        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_wo

        with patch("backend.middleware.client_auth.verify_client_access"):
            with patch("backend.routes.workflow.calculate_work_order_elapsed_times") as mock_func:
                mock_func.return_value = {"work_order_id": "WO-001", "lifecycle": {"total_hours": 24}, "stages": {}}

                result = get_work_order_elapsed_time(work_order_id="WO-001", db=mock_db, current_user=mock_user)

                assert result["work_order_id"] == "WO-001"

    def test_get_work_order_elapsed_time_not_found(self):
        """Test 404 when work order not found"""
        from backend.routes.workflow import get_work_order_elapsed_time
        from fastapi import HTTPException

        mock_db = Mock()
        mock_user = create_mock_user()

        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_work_order_elapsed_time(work_order_id="WO-NOTFOUND", db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404

    def test_get_transition_times_endpoint(self):
        """Test GET /api/workflow/work-orders/{id}/transition-times"""
        from backend.routes.workflow import get_work_order_transition_times

        mock_db = Mock()
        mock_user = create_mock_user()

        mock_wo = Mock()
        mock_wo.work_order_id = "WO-001"
        mock_wo.client_id = "CLIENT-001"

        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_wo

        with patch("backend.middleware.client_auth.verify_client_access"):
            with patch("backend.routes.workflow.get_transition_elapsed_times") as mock_func:
                mock_func.return_value = [
                    {"from_status": None, "to_status": "RECEIVED", "elapsed_from_previous_hours": None},
                    {"from_status": "RECEIVED", "to_status": "RELEASED", "elapsed_from_previous_hours": 4},
                ]

                result = get_work_order_transition_times(work_order_id="WO-001", db=mock_db, current_user=mock_user)

                assert len(result) == 2

    def test_get_client_average_times_endpoint(self):
        """Test GET /api/workflow/analytics/{client_id}/average-times"""
        from backend.routes.workflow import get_client_average_elapsed_times

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.middleware.client_auth.verify_client_access"):
            with patch("backend.routes.workflow.calculate_client_average_times") as mock_func:
                mock_func.return_value = {
                    "client_id": "CLIENT-001",
                    "count": 50,
                    "averages": {"lifecycle_hours": 72, "lead_time_hours": 8},
                }

                result = get_client_average_elapsed_times(client_id="CLIENT-001", db=mock_db, current_user=mock_user)

                assert result["count"] == 50
                assert result["averages"]["lifecycle_hours"] == 72

    def test_get_stage_durations_endpoint(self):
        """Test GET /api/workflow/analytics/{client_id}/stage-durations"""
        from backend.routes.workflow import get_client_stage_durations

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.middleware.client_auth.verify_client_access"):
            with patch("backend.routes.workflow.calculate_stage_duration_summary") as mock_func:
                mock_func.return_value = {
                    "client_id": "CLIENT-001",
                    "stage_durations": [{"from_status": "RECEIVED", "to_status": "RELEASED", "avg_hours": 4.5}],
                }

                result = get_client_stage_durations(client_id="CLIENT-001", db=mock_db, current_user=mock_user)

                assert len(result["stage_durations"]) == 1


class TestStatisticsEndpoints:
    """Test statistics and reporting endpoints"""

    def test_get_transition_statistics(self):
        """Test GET /api/workflow/statistics/{client_id}/transitions"""
        from backend.routes.workflow import get_client_transition_statistics

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.get_transition_statistics") as mock_func:
            mock_func.return_value = {
                "client_id": "CLIENT-001",
                "total_transitions": 150,
                "by_transition": [],
                "by_source": [],
            }

            result = get_client_transition_statistics(client_id="CLIENT-001", db=mock_db, current_user=mock_user)

            assert result["total_transitions"] == 150

    def test_get_status_distribution(self):
        """Test GET /api/workflow/statistics/{client_id}/status-distribution"""
        from backend.routes.workflow import get_client_status_distribution

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.get_status_distribution") as mock_func:
            mock_func.return_value = {
                "client_id": "CLIENT-001",
                "total_work_orders": 100,
                "by_status": [
                    {"status": "IN_PROGRESS", "count": 30, "percentage": 30.0},
                    {"status": "COMPLETED", "count": 70, "percentage": 70.0},
                ],
            }

            result = get_client_status_distribution(client_id="CLIENT-001", db=mock_db, current_user=mock_user)

            assert result["total_work_orders"] == 100
            assert len(result["by_status"]) == 2

    def test_get_client_all_transitions(self):
        """Test GET /api/workflow/transitions/{client_id}"""
        from backend.routes.workflow import get_client_all_transitions

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.get_client_transitions") as mock_func:
            mock_transitions = [Mock() for _ in range(5)]
            mock_func.return_value = mock_transitions

            result = get_client_all_transitions(client_id="CLIENT-001", db=mock_db, current_user=mock_user)

            assert len(result) == 5

    def test_get_client_transitions_with_filters(self):
        """Test transitions endpoint with filters"""
        from backend.routes.workflow import get_client_all_transitions

        mock_db = Mock()
        mock_user = create_mock_user()

        with patch("backend.routes.workflow.get_client_transitions") as mock_func:
            mock_func.return_value = []

            result = get_client_all_transitions(
                client_id="CLIENT-001",
                skip=10,
                limit=50,
                from_status="RECEIVED",
                to_status="RELEASED",
                trigger_source="manual",
                db=mock_db,
                current_user=mock_user,
            )

            # Verify filters were passed
            mock_func.assert_called_once()
            call_args = mock_func.call_args
            assert call_args.kwargs.get("skip") == 10
            assert call_args.kwargs.get("limit") == 50
            assert call_args.kwargs.get("from_status") == "RECEIVED"


class TestWorkflowTemplatesContent:
    """Test workflow templates content"""

    def test_templates_have_required_fields(self):
        """Test all templates have required fields"""
        from backend.models.workflow import WORKFLOW_TEMPLATES

        required_fields = [
            "template_id",
            "name",
            "description",
            "workflow_statuses",
            "workflow_transitions",
            "workflow_optional_statuses",
            "workflow_closure_trigger",
        ]

        for template_id, template in WORKFLOW_TEMPLATES.items():
            for field in required_fields:
                assert hasattr(template, field), f"Template {template_id} missing {field}"

    def test_standard_template_has_full_flow(self):
        """Test standard template has complete workflow"""
        from backend.models.workflow import WORKFLOW_TEMPLATES

        standard = WORKFLOW_TEMPLATES.get("standard")
        assert standard is not None

        # Should have standard statuses
        assert "RECEIVED" in standard.workflow_statuses
        assert "RELEASED" in standard.workflow_statuses
        assert "COMPLETED" in standard.workflow_statuses

    def test_simple_template_is_simplified(self):
        """Test simple template has fewer statuses"""
        from backend.models.workflow import WORKFLOW_TEMPLATES

        simple = WORKFLOW_TEMPLATES.get("simple")
        if simple:
            # Simple should have fewer steps than standard
            standard = WORKFLOW_TEMPLATES.get("standard")
            assert len(simple.workflow_statuses) <= len(standard.workflow_statuses)

    def test_express_template_closure_trigger(self):
        """Test express template closes at completion"""
        from backend.models.workflow import WORKFLOW_TEMPLATES

        express = WORKFLOW_TEMPLATES.get("express")
        if express:
            # Express typically auto-closes at completion
            assert express.workflow_closure_trigger in ["at_completion", "at_shipment"]
