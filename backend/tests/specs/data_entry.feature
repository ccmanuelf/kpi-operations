# language: en
@data-entry @crud
Feature: Data Entry Management
  As a shop floor operator or supervisor
  I want to record various operational data
  So that comprehensive KPIs can be calculated

  Background:
    Given the KPI Operations API is running
    And I am logged in as "operator@client1.com"
    And I have access to client "Manufacturing Co" with client_id "CLIENT-001"

  # ============================================================================
  # DOWNTIME ENTRY
  # ============================================================================

  @downtime @create @happy-path
  Scenario: Create downtime event with valid data
    When I submit a downtime event with:
      | field                     | value             |
      | shift_date                | 2026-01-25        |
      | shift_id                  | 1                 |
      | work_order_id             | WO-2026-001       |
      | downtime_reason           | Machine breakdown |
      | downtime_duration_minutes | 45                |
      | downtime_category         | Unplanned         |
      | notes                     | Hydraulic leak    |
    Then the response status should be 201
    And the downtime event should be created with a downtime_entry_id
    And the event should have client_id "CLIENT-001"

  @downtime @read @happy-path
  Scenario: List downtime events with filters
    Given there are 20 downtime events for client "CLIENT-001"
    When I request GET "/api/downtime?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And all events should be within the date range
    And all events should belong to "CLIENT-001"

  @downtime @read @by-reason
  Scenario: Filter downtime events by reason
    Given there are downtime events with various reasons
    When I request GET "/api/downtime?downtime_reason=Machine breakdown"
    Then all returned events should have downtime_reason "Machine breakdown"

  @downtime @update @happy-path
  Scenario: Update downtime event
    Given a downtime event exists with id "DT-001" for client "CLIENT-001"
    When I submit a PUT request to "/api/downtime/DT-001" with:
      | field                     | value |
      | downtime_duration_minutes | 60    |
    Then the response status should be 200
    And the duration should be updated to 60

  @downtime @delete @rbac
  Scenario: Only supervisor can delete downtime event
    Given I am logged in as "operator@client1.com" with role "OPERATOR"
    And a downtime event exists with id "DT-001"
    When I submit a DELETE request to "/api/downtime/DT-001"
    Then the response status should be 403

  @downtime @delete @happy-path
  Scenario: Supervisor deletes downtime event
    Given I am logged in as "supervisor@client1.com" with role "SUPERVISOR"
    And a downtime event exists with id "DT-001" for client "CLIENT-001"
    When I submit a DELETE request to "/api/downtime/DT-001"
    Then the response status should be 204

  # ============================================================================
  # ATTENDANCE ENTRY
  # ============================================================================

  @attendance @create @happy-path
  Scenario: Create attendance record with valid data
    When I submit an attendance record with:
      | field           | value      |
      | employee_id     | EMP-001    |
      | shift_date      | 2026-01-25 |
      | shift_id        | 1          |
      | scheduled_hours | 8.0        |
      | actual_hours    | 8.0        |
      | is_absent       | 0          |
      | is_late         | 0          |
    Then the response status should be 201
    And the attendance record should be created
    And is_absent should be 0

  @attendance @create @absent
  Scenario: Create attendance record for absent employee
    When I submit an attendance record with:
      | field           | value      |
      | employee_id     | EMP-002    |
      | shift_date      | 2026-01-25 |
      | shift_id        | 1          |
      | scheduled_hours | 8.0        |
      | actual_hours    | 0.0        |
      | is_absent       | 1          |
      | absence_type    | Sick       |
      | absence_hours   | 8.0        |
    Then the response status should be 201
    And is_absent should be 1
    And absence_type should be "Sick"

  @attendance @create @late
  Scenario: Create attendance record for late employee
    When I submit an attendance record with:
      | field           | value      |
      | employee_id     | EMP-003    |
      | shift_date      | 2026-01-25 |
      | shift_id        | 1          |
      | scheduled_hours | 8.0        |
      | actual_hours    | 7.5        |
      | is_absent       | 0          |
      | is_late         | 1          |
    Then the response status should be 201
    And is_late should be 1

  @attendance @read @happy-path
  Scenario: List attendance records with filters
    When I request GET "/api/attendance?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And all records should be within the date range

  @attendance @read @by-employee
  Scenario: Get attendance by employee
    Given employee "EMP-001" has 20 attendance records
    When I request GET "/api/attendance/by-employee/EMP-001"
    Then the response status should be 200
    And all records should be for employee "EMP-001"

  @attendance @read @by-date-range
  Scenario: Get attendance by date range
    When I request GET "/api/attendance/by-date-range?start_date=2026-01-15&end_date=2026-01-20"
    Then the response status should be 200
    And all records should be between 2026-01-15 and 2026-01-20

  @attendance @read @statistics
  Scenario: Get attendance statistics summary
    When I request GET "/api/attendance/statistics/summary?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the response should contain:
      | field      |
      | statistics |
    And statistics should be grouped by status

  @attendance @update @happy-path
  Scenario: Update attendance record
    Given an attendance record exists with id 123
    When I submit a PUT request to "/api/attendance/123" with:
      | field        | value |
      | actual_hours | 7.0   |
    Then the response status should be 200
    And actual_hours should be updated to 7.0

  @attendance @delete @rbac
  Scenario: Only supervisor can delete attendance record
    Given I am logged in as "operator@client1.com" with role "OPERATOR"
    When I submit a DELETE request to "/api/attendance/123"
    Then the response status should be 403

  # ============================================================================
  # QUALITY INSPECTION ENTRY
  # ============================================================================

  @quality @create @happy-path
  Scenario: Create quality inspection with valid data
    When I submit a quality inspection with:
      | field            | value       |
      | shift_date       | 2026-01-25  |
      | shift_id         | 1           |
      | work_order_id    | WO-2026-001 |
      | inspection_stage | In-Process  |
      | units_inspected  | 100         |
      | units_passed     | 95          |
      | units_defective  | 5           |
      | units_reworked   | 3           |
      | units_scrapped   | 2           |
    Then the response status should be 201
    And the inspection should be created
    And PPM should be calculated automatically

  @quality @create @defect-types
  Scenario: Create quality inspection with defect details
    When I submit a quality inspection with defect breakdown:
      | defect_type    | count |
      | Stitching      | 2     |
      | Color mismatch | 1     |
      | Sizing         | 2     |
    Then the defect details should be stored separately
    And total defects should sum to 5

  @quality @read @happy-path
  Scenario: List quality inspections with filters
    When I request GET "/api/quality?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And all inspections should be within the date range

  @quality @read @by-work-order
  Scenario: Get quality inspections by work order
    Given work order "WO-2026-001" has 5 quality inspections
    When I request GET "/api/quality/by-work-order/WO-2026-001"
    Then the response status should be 200
    And all inspections should be for work order "WO-2026-001"

  @quality @read @by-stage
  Scenario: Filter quality inspections by stage
    When I request GET "/api/quality?inspection_stage=Final"
    Then all returned inspections should have inspection_stage "Final"

  @quality @update @happy-path
  Scenario: Update quality inspection
    Given a quality inspection exists with id 456
    When I submit a PUT request to "/api/quality/456" with:
      | field           | value |
      | units_defective | 3     |
    Then the response status should be 200
    And units_defective should be updated to 3

  # ============================================================================
  # WIP HOLD/RESUME ENTRY
  # ============================================================================

  @holds @create @happy-path
  Scenario: Create WIP hold record
    When I submit a WIP hold with:
      | field                | value                |
      | work_order_id        | WO-2026-001          |
      | hold_date            | 2026-01-25           |
      | hold_reason_category | Quality Issue        |
      | hold_reason_detail   | Failed fabric test   |
      | held_by              | operator@client1.com |
    Then the response status should be 201
    And the hold should be created with status "ON_HOLD"

  @holds @read @happy-path
  Scenario: List WIP holds with filters
    When I request GET "/api/holds?released=false"
    Then the response status should be 200
    And all holds should be unreleased (still on hold)

  @holds @read @by-reason
  Scenario: Filter holds by reason category
    When I request GET "/api/holds?hold_reason_category=Quality Issue"
    Then all returned holds should have hold_reason_category "Quality Issue"

  @holds @update @release
  Scenario: Release a WIP hold
    Given a WIP hold exists with id 789 in "ON_HOLD" status
    When I submit a PUT request to "/api/holds/789" with:
      | field       | value                |
      | hold_status | RELEASED             |
      | resume_date | 2026-01-26           |
      | released_by | supervisor@client1.com|
    Then the response status should be 200
    And hold_status should be "RELEASED"
    And resume_date should be set

  @holds @update @escalate
  Scenario: Escalate a WIP hold
    Given a WIP hold exists with id 789 in "ON_HOLD" status
    When I submit a PUT request to "/api/holds/789" with:
      | field       | value     |
      | hold_status | ESCALATED |
    Then the response status should be 200
    And hold_status should be "ESCALATED"

  @holds @delete @rbac
  Scenario: Only supervisor can delete WIP hold
    Given I am logged in as "operator@client1.com" with role "OPERATOR"
    When I submit a DELETE request to "/api/holds/789"
    Then the response status should be 403

  # ============================================================================
  # WORK ORDER ENTRY
  # ============================================================================

  @work-orders @create @happy-path
  Scenario: Create work order with valid data
    When I submit a work order with:
      | field           | value       |
      | work_order_id   | WO-2026-100 |
      | client_id       | CLIENT-001  |
      | style_model     | Style-A     |
      | quantity        | 1000        |
      | required_date   | 2026-02-15  |
      | status          | Open        |
    Then the response status should be 201
    And the work order should be created

  @work-orders @read @happy-path
  Scenario: List work orders with filters
    When I request GET "/api/work-orders?status_filter=Open"
    Then the response status should be 200
    And all work orders should have status "Open"

  @work-orders @read @by-status
  Scenario: Get work orders by status
    When I request GET "/api/work-orders/status/In Progress"
    Then the response status should be 200
    And all work orders should have status "In Progress"

  @work-orders @read @by-date-range
  Scenario: Get work orders by date range
    When I request GET "/api/work-orders/date-range?start_date=2026-01-01&end_date=2026-03-31"
    Then the response status should be 200
    And work orders should be within the date range

  @work-orders @update @happy-path
  Scenario: Update work order status
    Given a work order exists with id "WO-2026-001"
    When I submit a PUT request to "/api/work-orders/WO-2026-001" with:
      | field  | value       |
      | status | In Progress |
    Then the response status should be 200
    And status should be "In Progress"

  @work-orders @update @delivery
  Scenario: Mark work order as delivered
    Given a work order exists with id "WO-2026-001"
    When I submit a PUT request to "/api/work-orders/WO-2026-001" with:
      | field                | value      |
      | status               | Completed  |
      | actual_delivery_date | 2026-02-10 |
    Then the response status should be 200
    And actual_delivery_date should be set

  @work-orders @delete @rbac
  Scenario: Only supervisor can delete work order
    Given I am logged in as "supervisor@client1.com" with role "SUPERVISOR"
    And a work order exists with id "WO-2026-001"
    When I submit a DELETE request to "/api/work-orders/WO-2026-001"
    Then the response status should be 204

  # ============================================================================
  # VALIDATION RULES
  # ============================================================================

  @validation @required-fields
  Scenario: Reject entry with missing required fields
    When I submit a production entry without product_id
    Then the response status should be 422
    And the error should indicate "product_id" is required

  @validation @date-format
  Scenario: Reject entry with invalid date format
    When I submit a production entry with:
      | field           | value      |
      | production_date | 25-01-2026 |
    Then the response status should be 422
    And the error should indicate invalid date format

  @validation @numeric-range
  Scenario: Reject entry with negative numeric values
    When I submit a quality inspection with:
      | field           | value |
      | units_inspected | -10   |
    Then the response status should be 422
    And the error should indicate value must be positive

  @validation @consistency
  Scenario: Reject entry with inconsistent data
    When I submit a quality inspection with:
      | field           | value |
      | units_inspected | 100   |
      | units_passed    | 60    |
      | units_defective | 50    |
    Then the response status should be 422 or accepted with warning
    # units_passed + units_defective > units_inspected

  @validation @future-date
  Scenario: Reject entry with future production date
    When I submit a production entry with:
      | field           | value      |
      | production_date | 2027-01-01 |
    Then the response may be rejected or flagged

  # ============================================================================
  # ERROR HANDLING
  # ============================================================================

  @error @not-found
  Scenario: Return 404 for non-existent resource
    When I request GET "/api/production/99999"
    Then the response status should be 404
    And the response should contain "not found"

  @error @unauthorized
  Scenario: Return 401 for unauthenticated request
    When I request GET "/api/production" without authentication
    Then the response status should be 401

  @error @forbidden
  Scenario: Return 403 for unauthorized access
    Given I am logged in as "operator@client1.com"
    And a production entry exists for "CLIENT-002"
    When I try to access that entry
    Then the response status should be 403 or 404

  @error @method-not-allowed
  Scenario: Return 405 for unsupported HTTP method
    When I request PATCH "/api/production/123"
    Then the response status should be 405

  @error @server-error
  Scenario: Handle server errors gracefully
    Given the database is temporarily unavailable
    When I request GET "/api/production"
    Then the response status should be 500
    And the error should not expose sensitive information
