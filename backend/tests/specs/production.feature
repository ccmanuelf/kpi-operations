# language: en
@production @crud
Feature: Production Entry Management
  As a shop floor operator
  I want to record and manage production data
  So that KPIs can be calculated accurately

  Background:
    Given the KPI Operations API is running
    And I am logged in as "operator@client1.com"
    And I have access to client "Manufacturing Co" with client_id "CLIENT-001"
    And the following products exist:
      | product_id | product_name | ideal_cycle_time |
      | 1          | Widget A     | 0.25             |
      | 2          | Widget B     | 0.30             |
    And the following shifts exist:
      | shift_id | shift_name | start_time | end_time |
      | 1        | Day Shift  | 07:00      | 15:00    |
      | 2        | Night Shift| 23:00      | 07:00    |

  # ============================================================================
  # CREATE PRODUCTION ENTRY
  # ============================================================================

  @create @happy-path
  Scenario: Create production entry with valid data
    When I submit a production entry with:
      | field              | value      |
      | product_id         | 1          |
      | shift_id           | 1          |
      | production_date    | 2026-01-25 |
      | units_produced     | 100        |
      | run_time_hours     | 7.5        |
      | employees_assigned | 5          |
    Then the response status should be 201
    And the entry should be created with a production_entry_id
    And the entry should have client_id "CLIENT-001"
    And efficiency should be calculated automatically

  @create @happy-path
  Scenario: Create production entry with all optional fields
    When I submit a production entry with:
      | field               | value             |
      | product_id          | 1                 |
      | shift_id            | 1                 |
      | production_date     | 2026-01-25        |
      | units_produced      | 100               |
      | run_time_hours      | 7.5               |
      | employees_assigned  | 5                 |
      | work_order_number   | WO-2026-001       |
      | job_id              | JOB-001           |
      | defect_count        | 3                 |
      | scrap_count         | 2                 |
      | rework_count        | 1                 |
      | setup_time_hours    | 0.5               |
      | downtime_hours      | 0.25              |
      | maintenance_hours   | 0.0               |
      | notes               | Test production   |
    Then the response status should be 201
    And all fields should be stored correctly

  @create @validation
  Scenario: Reject production entry with non-existent product
    When I submit a production entry with:
      | field       | value |
      | product_id  | 99999 |
      | shift_id    | 1     |
    Then the response status should be 404
    And the response should contain error "Product ID 99999 not found"

  @create @validation
  Scenario: Reject production entry with non-existent shift
    When I submit a production entry with:
      | field       | value |
      | product_id  | 1     |
      | shift_id    | 99999 |
    Then the response status should be 404
    And the response should contain error "Shift ID 99999 not found"

  @create @validation
  Scenario: Reject production entry with negative units_produced
    When I submit a production entry with:
      | field           | value |
      | product_id      | 1     |
      | shift_id        | 1     |
      | units_produced  | -10   |
    Then the response status should be 422
    And the response should contain validation error for "units_produced"

  @create @validation
  Scenario: Reject production entry with zero employees_assigned
    When I submit a production entry with:
      | field              | value |
      | product_id         | 1     |
      | shift_id           | 1     |
      | units_produced     | 100   |
      | employees_assigned | 0     |
    Then the response status should be 422 or the system uses inference

  # ============================================================================
  # READ PRODUCTION ENTRIES
  # ============================================================================

  @read @happy-path
  Scenario: List all production entries for authorized client
    Given there are 15 production entries for client "CLIENT-001"
    And there are 10 production entries for client "CLIENT-002"
    When I request GET "/api/production"
    Then the response status should be 200
    And I should receive only entries for client "CLIENT-001"
    And the response should contain at most 100 entries by default

  @read @pagination
  Scenario: List production entries with pagination
    Given there are 150 production entries for client "CLIENT-001"
    When I request GET "/api/production?skip=0&limit=50"
    Then the response status should be 200
    And I should receive 50 entries
    When I request GET "/api/production?skip=50&limit=50"
    Then I should receive the next 50 entries

  @read @filtering
  Scenario: Filter production entries by date range
    Given there are production entries from "2026-01-01" to "2026-01-31"
    When I request GET "/api/production?start_date=2026-01-10&end_date=2026-01-20"
    Then the response status should be 200
    And all entries should be within the date range

  @read @filtering
  Scenario: Filter production entries by product
    Given there are production entries for product_id 1 and product_id 2
    When I request GET "/api/production?product_id=1"
    Then the response status should be 200
    And all entries should have product_id 1

  @read @filtering
  Scenario: Filter production entries by shift
    Given there are production entries for shift_id 1 and shift_id 2
    When I request GET "/api/production?shift_id=1"
    Then the response status should be 200
    And all entries should have shift_id 1

  @read @happy-path
  Scenario: Get single production entry with KPI details
    Given a production entry exists with id 123 for client "CLIENT-001"
    When I request GET "/api/production/123"
    Then the response status should be 200
    And the response should include:
      | field                  |
      | production_entry_id    |
      | product_id             |
      | shift_id               |
      | units_produced         |
      | efficiency_percentage  |
      | performance_percentage |
      | quality_rate           |

  @read @not-found
  Scenario: Return 404 for non-existent production entry
    When I request GET "/api/production/99999"
    Then the response status should be 404
    And the response should contain error "Production entry 99999 not found"

  # ============================================================================
  # UPDATE PRODUCTION ENTRY
  # ============================================================================

  @update @happy-path
  Scenario: Update production entry fields
    Given a production entry exists with id 123 for client "CLIENT-001"
    When I submit a PUT request to "/api/production/123" with:
      | field          | value |
      | units_produced | 150   |
      | defect_count   | 5     |
    Then the response status should be 200
    And the units_produced should be 150
    And the defect_count should be 5
    And efficiency should be recalculated

  @update @validation
  Scenario: Reject update with invalid data
    Given a production entry exists with id 123 for client "CLIENT-001"
    When I submit a PUT request to "/api/production/123" with:
      | field          | value |
      | units_produced | -50   |
    Then the response status should be 422

  @update @not-found
  Scenario: Return 404 when updating non-existent entry
    When I submit a PUT request to "/api/production/99999" with:
      | field          | value |
      | units_produced | 100   |
    Then the response status should be 404

  # ============================================================================
  # DELETE PRODUCTION ENTRY
  # ============================================================================

  @delete @rbac
  Scenario: Supervisor can delete production entry
    Given I am logged in as "supervisor@client1.com" with role "SUPERVISOR"
    And a production entry exists with id 123 for client "CLIENT-001"
    When I submit a DELETE request to "/api/production/123"
    Then the response status should be 204
    And the entry should no longer exist

  @delete @rbac
  Scenario: Operator cannot delete production entry
    Given I am logged in as "operator@client1.com" with role "OPERATOR"
    And a production entry exists with id 123 for client "CLIENT-001"
    When I submit a DELETE request to "/api/production/123"
    Then the response status should be 403

  @delete @not-found
  Scenario: Return 404 when deleting non-existent entry
    Given I am logged in as "supervisor@client1.com" with role "SUPERVISOR"
    When I submit a DELETE request to "/api/production/99999"
    Then the response status should be 404

  # ============================================================================
  # CSV UPLOAD
  # ============================================================================

  @csv-upload @happy-path
  Scenario: Upload valid CSV with production entries
    When I upload a CSV file with valid production entries:
      | client_id  | product_id | shift_id | production_date | units_produced | run_time_hours | employees_assigned |
      | CLIENT-001 | 1          | 1        | 2026-01-25      | 100            | 7.5            | 5                  |
      | CLIENT-001 | 2          | 1        | 2026-01-25      | 80             | 7.0            | 4                  |
    Then the response status should be 200
    And the response should indicate 2 successful imports
    And the response should indicate 0 failed imports

  @csv-upload @validation
  Scenario: Upload CSV with some invalid rows
    When I upload a CSV file with mixed valid and invalid entries:
      | client_id  | product_id | shift_id | production_date | units_produced | run_time_hours | employees_assigned |
      | CLIENT-001 | 1          | 1        | 2026-01-25      | 100            | 7.5            | 5                  |
      | CLIENT-001 | 99999      | 1        | 2026-01-25      | 80             | 7.0            | 4                  |
    Then the response status should be 200
    And the response should indicate 1 successful imports
    And the response should indicate 1 failed imports
    And the errors array should contain details about row 2

  @csv-upload @validation
  Scenario: Reject non-CSV file
    When I upload a file named "data.txt" with content "not a csv"
    Then the response status should be 400
    And the response should contain error "File must be a CSV"

  @csv-upload @security
  Scenario: Reject CSV with unauthorized client_id
    When I upload a CSV file with client_id "CLIENT-999"
    Then the response status should be 403 or the row should fail
    And the response should indicate client access violation

  # ============================================================================
  # BATCH IMPORT
  # ============================================================================

  @batch-import @happy-path
  Scenario: Batch import validated production entries
    When I submit a batch import request with:
      | entries_count | 10    |
    Then the response status should be 200
    And all 10 entries should be created
    And an import_log entry should be created

  @batch-import @logging
  Scenario: Import log tracks batch import details
    Given I have completed a batch import with 8 successful and 2 failed entries
    When I request GET "/api/import-logs"
    Then the response should contain my import log with:
      | field           | value |
      | rows_attempted  | 10    |
      | rows_succeeded  | 8     |
      | rows_failed     | 2     |

  # ============================================================================
  # EFFICIENCY CALCULATION INFERENCE
  # ============================================================================

  @inference @happy-path
  Scenario: Calculate efficiency with provided ideal_cycle_time
    Given product_id 1 has ideal_cycle_time 0.25
    When I create a production entry with:
      | units_produced     | 100 |
      | employees_assigned | 5   |
      | shift_id           | 1   |
    Then efficiency should be calculated using ideal_cycle_time 0.25
    And the inference flag should be false

  @inference @fallback
  Scenario: Infer ideal_cycle_time from historical data
    Given product_id 3 has no ideal_cycle_time defined
    And there are historical production entries for product_id 3
    When I create a production entry for product_id 3
    Then ideal_cycle_time should be inferred from historical average
    And the inference flag should be true

  @inference @fallback
  Scenario: Use default ideal_cycle_time when no data available
    Given product_id 4 has no ideal_cycle_time defined
    And there are no historical production entries for product_id 4
    When I create a production entry for product_id 4
    Then efficiency should be calculated using default ideal_cycle_time 0.25
    And the inference flag should be true

  @inference @fallback
  Scenario: Infer employees count from fallback chain
    When I create a production entry with employees_assigned as 0:
      | field              | value |
      | employees_assigned | 0     |
      | employees_present  | 5     |
    Then employees count should be inferred as 5 from employees_present
    And the inference source should be "employees_present"

  # ============================================================================
  # EDGE CASES
  # ============================================================================

  @edge-case
  Scenario: Handle overnight shift calculations
    Given shift_id 2 has start_time "23:00" and end_time "07:00"
    When I create a production entry for shift_id 2
    Then scheduled_hours should be calculated as 8.0

  @edge-case
  Scenario: Handle maximum efficiency cap
    When I create a production entry that would result in 200% efficiency
    Then efficiency should be capped at 150%

  @edge-case
  Scenario: Handle zero run_time_hours
    When I create a production entry with run_time_hours 0
    Then the entry should be created
    And efficiency calculation should handle division safely
