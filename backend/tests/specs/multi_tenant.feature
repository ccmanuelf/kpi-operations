# language: en
@multi-tenant @security
Feature: Multi-Tenant Security and Client Isolation
  As a platform administrator
  I want strict client data isolation
  So that tenants cannot access each other's data

  Background:
    Given the KPI Operations API is running
    And the following clients exist:
      | client_id   | client_name       |
      | CLIENT-001  | Manufacturing Co  |
      | CLIENT-002  | Production Inc    |
      | CLIENT-003  | Factory Ltd       |
    And the following users exist:
      | username        | role       | client_id_assigned |
      | operator1       | OPERATOR   | CLIENT-001         |
      | operator2       | OPERATOR   | CLIENT-002         |
      | supervisor1     | SUPERVISOR | CLIENT-001         |
      | poweruser1      | POWERUSER  | CLIENT-001,CLIENT-002 |
      | admin           | ADMIN      | NULL               |

  # ============================================================================
  # PRODUCTION ENTRY ISOLATION
  # ============================================================================

  @production @isolation @happy-path
  Scenario: Operator sees only their client's production entries
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And there are 20 production entries for "CLIENT-001"
    And there are 15 production entries for "CLIENT-002"
    When I request GET "/api/production"
    Then the response status should be 200
    And all entries should have client_id "CLIENT-001"
    And I should see 20 entries

  @production @isolation @forbidden
  Scenario: Operator cannot access other client's production entry
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And a production entry exists with id 999 for "CLIENT-002"
    When I request GET "/api/production/999"
    Then the response status should be 403 or 404
    And the response should not contain entry details

  @production @isolation @forbidden
  Scenario: Operator cannot create production entry for other client
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I submit a production entry with client_id "CLIENT-002"
    Then the response status should be 403
    And the entry should not be created

  @production @isolation @forbidden
  Scenario: Operator cannot update other client's production entry
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And a production entry exists with id 999 for "CLIENT-002"
    When I submit a PUT request to "/api/production/999"
    Then the response status should be 403 or 404

  @production @isolation @forbidden
  Scenario: Supervisor cannot delete other client's production entry
    Given I am logged in as "supervisor1" assigned to "CLIENT-001"
    And a production entry exists with id 999 for "CLIENT-002"
    When I submit a DELETE request to "/api/production/999"
    Then the response status should be 403 or 404

  # ============================================================================
  # QUALITY INSPECTION ISOLATION
  # ============================================================================

  @quality @isolation @happy-path
  Scenario: Operator sees only their client's quality inspections
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And there are 10 quality inspections for "CLIENT-001"
    And there are 8 quality inspections for "CLIENT-002"
    When I request GET "/api/quality"
    Then the response status should be 200
    And all inspections should have client_id "CLIENT-001"

  @quality @isolation @forbidden
  Scenario: Operator cannot access other client's quality inspection
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And a quality inspection exists with id "QI-999" for "CLIENT-002"
    When I request GET "/api/quality/QI-999"
    Then the response status should be 403 or 404

  @quality @isolation @statistics
  Scenario: Quality statistics are filtered by client
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/quality/statistics/summary?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And statistics should only include "CLIENT-001" data

  # ============================================================================
  # ATTENDANCE ISOLATION
  # ============================================================================

  @attendance @isolation @happy-path
  Scenario: Operator sees only their client's attendance records
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/attendance"
    Then all records should belong to "CLIENT-001"

  @attendance @isolation @statistics
  Scenario: Attendance statistics are filtered by client
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/attendance/statistics/summary?start_date=2026-01-01&end_date=2026-01-31"
    Then statistics should only include "CLIENT-001" employees

  # ============================================================================
  # DOWNTIME ISOLATION
  # ============================================================================

  @downtime @isolation @happy-path
  Scenario: Operator sees only their client's downtime events
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/downtime"
    Then all events should belong to "CLIENT-001"

  @downtime @isolation @forbidden
  Scenario: Operator cannot access other client's downtime event
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And a downtime event exists with id "DT-999" for "CLIENT-002"
    When I request GET "/api/downtime/DT-999"
    Then the response status should be 403 or 404

  # ============================================================================
  # WIP HOLDS ISOLATION
  # ============================================================================

  @holds @isolation @happy-path
  Scenario: Operator sees only their client's WIP holds
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/holds"
    Then all holds should belong to "CLIENT-001"

  # ============================================================================
  # WORK ORDER ISOLATION
  # ============================================================================

  @work-orders @isolation @happy-path
  Scenario: Operator sees only their client's work orders
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And there are 25 work orders for "CLIENT-001"
    And there are 20 work orders for "CLIENT-002"
    When I request GET "/api/work-orders"
    Then the response status should be 200
    And all work orders should have client_id "CLIENT-001"

  @work-orders @isolation @forbidden
  Scenario: Operator cannot access other client's work order
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    And a work order exists with id "WO-999" for "CLIENT-002"
    When I request GET "/api/work-orders/WO-999"
    Then the response status should be 404
    And the response should contain "not found or access denied"

  # ============================================================================
  # KPI CALCULATIONS ISOLATION
  # ============================================================================

  @kpi @isolation @efficiency
  Scenario: Efficiency calculations are client-scoped
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/kpi/efficiency/trend"
    Then the data should only include "CLIENT-001" production

  @kpi @isolation @quality
  Scenario: Quality KPIs are client-scoped
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/quality/kpi/ppm"
    Then PPM should be calculated from "CLIENT-001" data only

  @kpi @isolation @absenteeism
  Scenario: Absenteeism KPIs are client-scoped
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/attendance/kpi/absenteeism"
    Then absenteeism should be calculated from "CLIENT-001" attendance only

  @kpi @isolation @otd
  Scenario: OTD KPIs are client-scoped
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/kpi/otd"
    Then OTD should be calculated from "CLIENT-001" work orders only

  @kpi @isolation @wip-aging
  Scenario: WIP aging KPIs are client-scoped
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/kpi/wip-aging"
    Then aging data should only include "CLIENT-001" holds

  # ============================================================================
  # REPORT GENERATION ISOLATION
  # ============================================================================

  @reports @isolation @happy-path
  Scenario: Reports are filtered by authorized client
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/reports/production/pdf"
    Then the report should only contain "CLIENT-001" data

  @reports @isolation @forbidden
  Scenario: Operator cannot generate report for other client
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/reports/production/pdf?client_id=CLIENT-002"
    Then the response status should be 403

  # ============================================================================
  # MULTI-CLIENT ACCESS (POWERUSER)
  # ============================================================================

  @poweruser @multi-client @happy-path
  Scenario: Poweruser can access multiple assigned clients
    Given I am logged in as "poweruser1" assigned to "CLIENT-001,CLIENT-002"
    When I request GET "/api/production?client_id=CLIENT-001"
    Then the response status should be 200
    And entries should be from "CLIENT-001"
    When I request GET "/api/production?client_id=CLIENT-002"
    Then the response status should be 200
    And entries should be from "CLIENT-002"

  @poweruser @multi-client @forbidden
  Scenario: Poweruser cannot access unassigned client
    Given I am logged in as "poweruser1" assigned to "CLIENT-001,CLIENT-002"
    When I request GET "/api/production?client_id=CLIENT-003"
    Then the response status should be 403

  @poweruser @multi-client @aggregation
  Scenario: Poweruser can see aggregated data across assigned clients
    Given I am logged in as "poweruser1" assigned to "CLIENT-001,CLIENT-002"
    When I request GET "/api/production" without client filter
    Then entries from both "CLIENT-001" and "CLIENT-002" should be returned

  # ============================================================================
  # ADMIN ACCESS
  # ============================================================================

  @admin @all-access @happy-path
  Scenario: Admin can access all client data
    Given I am logged in as "admin" with role "ADMIN"
    When I request GET "/api/production?client_id=CLIENT-001"
    Then the response status should be 200
    When I request GET "/api/production?client_id=CLIENT-002"
    Then the response status should be 200
    When I request GET "/api/production?client_id=CLIENT-003"
    Then the response status should be 200

  @admin @all-access @reports
  Scenario: Admin can generate reports for any client
    Given I am logged in as "admin" with role "ADMIN"
    When I request GET "/api/reports/comprehensive/pdf?client_id=CLIENT-002"
    Then the response status should be 200
    And the report should contain "CLIENT-002" data

  @admin @all-access @cross-client-kpi
  Scenario: Admin can view cross-client KPI aggregations
    Given I am logged in as "admin" with role "ADMIN"
    When I request GET "/api/kpi/otd/by-client"
    Then the response status should be 200
    And the response should contain OTD metrics for all clients

  # ============================================================================
  # JWT TOKEN SECURITY
  # ============================================================================

  @jwt @client-in-token
  Scenario: JWT token contains client_id for stateless validation
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I decode my access token
    Then the payload should contain client_ids "CLIENT-001"

  @jwt @multi-client-token
  Scenario: Poweruser token contains multiple client_ids
    Given I am logged in as "poweruser1" assigned to "CLIENT-001,CLIENT-002"
    When I decode my access token
    Then the payload should contain client_ids "CLIENT-001,CLIENT-002"

  @jwt @admin-token
  Scenario: Admin token has no client restriction
    Given I am logged in as "admin" with role "ADMIN"
    When I decode my access token
    Then the client_ids should be null or empty

  # ============================================================================
  # EXPLICIT CLIENT_ID PARAMETER VALIDATION
  # ============================================================================

  @client-filter @explicit @happy-path
  Scenario: Explicit client_id parameter filters results
    Given I am logged in as "poweruser1" assigned to "CLIENT-001,CLIENT-002"
    When I request GET "/api/production?client_id=CLIENT-001"
    Then only "CLIENT-001" entries should be returned

  @client-filter @explicit @forbidden
  Scenario: Explicit client_id for unauthorized client is rejected
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/production?client_id=CLIENT-002"
    Then the response status should be 403

  @client-filter @explicit @verified
  Scenario: Client access is verified before processing
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I request GET "/api/quality/statistics/summary?client_id=CLIENT-002&start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 403
    And the request should be rejected before any data processing

  # ============================================================================
  # CSV UPLOAD CLIENT VALIDATION
  # ============================================================================

  @csv @client-validation @required
  Scenario: CSV upload requires client_id column
    When I upload a CSV without client_id column
    Then all rows should fail with "client_id is required"

  @csv @client-validation @forbidden
  Scenario: CSV upload rejects unauthorized client_id
    Given I am logged in as "operator1" assigned to "CLIENT-001"
    When I upload a CSV with rows having client_id "CLIENT-002"
    Then those rows should fail with client access violation

  # ============================================================================
  # EDGE CASES
  # ============================================================================

  @edge-case @no-client
  Scenario: Handle user with no client assignment
    Given a user exists with no client_id_assigned
    When the user logs in and requests GET "/api/production"
    Then the response should handle the edge case appropriately

  @edge-case @deleted-client
  Scenario: Handle deleted client references
    Given a production entry references a deleted client
    When an admin requests GET "/api/production"
    Then the response should handle orphaned data appropriately

  @edge-case @concurrent-access
  Scenario: Handle concurrent requests across tenants
    Given multiple users from different clients make concurrent requests
    Then each user should only see their own client's data
    And there should be no data leakage between tenants
