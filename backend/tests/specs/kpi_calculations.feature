# language: en
@kpi @calculations
Feature: KPI Calculations
  As a production manager
  I want accurate KPI calculations
  So that I can monitor and improve manufacturing performance

  Background:
    Given the KPI Operations API is running
    And I am logged in as "manager@client1.com"
    And I have access to client "Manufacturing Co" with client_id "CLIENT-001"

  # ============================================================================
  # EFFICIENCY CALCULATION
  # ============================================================================

  @efficiency @happy-path
  Scenario: Calculate efficiency for production entry
    Given a production entry exists with:
      | field              | value |
      | entry_id           | 123   |
      | units_produced     | 100   |
      | employees_assigned | 5     |
      | shift_id           | 1     |
    And the product has ideal_cycle_time 0.25 hours
    And the shift has scheduled_hours 8.0
    When I request GET "/api/kpi/calculate/123"
    Then the response status should be 200
    And the response should contain:
      | field                 | value |
      | entry_id              | 123   |
      | efficiency_percentage | 62.5  |
    # Formula: (100 * 0.25) / (5 * 8) * 100 = 62.5%

  @efficiency @formula-verification
  Scenario Outline: Verify efficiency formula across different scenarios
    Given a production entry with:
      | units_produced | <units> |
      | employees      | <emps>  |
      | shift_hours    | <hours> |
      | cycle_time     | <cycle> |
    When efficiency is calculated
    Then the result should be <expected_efficiency>%

    Examples:
      | units | emps | hours | cycle | expected_efficiency |
      | 100   | 5    | 8     | 0.25  | 62.5               |
      | 200   | 4    | 8     | 0.20  | 125.0              |
      | 50    | 2    | 8     | 0.50  | 156.25 (capped 150)|
      | 80    | 10   | 8     | 0.25  | 25.0               |

  @efficiency @trend
  Scenario: Get efficiency trend over date range
    Given there are daily production entries from "2026-01-01" to "2026-01-30"
    When I request GET "/api/kpi/efficiency/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain 30 data points
    And each data point should have "date" and "value" fields

  @efficiency @by-shift
  Scenario: Get efficiency aggregated by shift
    Given there are production entries for multiple shifts
    When I request GET "/api/kpi/efficiency/by-shift"
    Then the response status should be 200
    And the response should contain efficiency data for each shift
    And each shift should have:
      | field           |
      | shift_id        |
      | shift_name      |
      | actual_output   |
      | expected_output |
      | efficiency      |

  @efficiency @by-product
  Scenario: Get efficiency aggregated by product
    Given there are production entries for multiple products
    When I request GET "/api/kpi/efficiency/by-product?limit=10"
    Then the response status should be 200
    And the response should contain top 10 products by efficiency

  # ============================================================================
  # PERFORMANCE CALCULATION
  # ============================================================================

  @performance @happy-path
  Scenario: Calculate performance rate
    Given a production entry exists with:
      | units_produced  | 100  |
      | ideal_run_rate  | 12   |
      | actual_run_time | 10.0 |
    When performance is calculated
    Then performance_percentage should be (100 / (12 * 10)) * 100 = 83.3%

  @performance @trend
  Scenario: Get performance trend over date range
    When I request GET "/api/kpi/performance/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily performance values

  @performance @by-shift
  Scenario: Get performance aggregated by shift
    When I request GET "/api/kpi/performance/by-shift"
    Then the response status should be 200
    And the response should contain:
      | field       |
      | shift_id    |
      | shift_name  |
      | units       |
      | rate        |
      | performance |

  # ============================================================================
  # QUALITY METRICS (FPY, RTY, PPM, DPMO)
  # ============================================================================

  @quality @fpy @happy-path
  Scenario: Calculate First Pass Yield (FPY)
    Given quality inspection entries exist with:
      | units_inspected | units_passed | units_defective |
      | 100             | 95           | 5               |
    When I request GET "/api/quality/kpi/fpy-rty"
    Then the response status should be 200
    And fpy_percentage should be 95.0
    # FPY = (95 / 100) * 100 = 95%

  @quality @rty @happy-path
  Scenario: Calculate Rolled Throughput Yield (RTY)
    Given quality inspection entries exist for multiple stages:
      | inspection_stage | units_inspected | units_passed |
      | Incoming         | 1000            | 980          |
      | In-Process       | 980             | 960          |
      | Final            | 960             | 950          |
    When I request GET "/api/quality/kpi/fpy-rty"
    Then the response status should be 200
    And rty_percentage should be approximately 95.0
    # RTY = 0.98 * 0.98 * 0.99 * 100 = 95.06%

  @quality @ppm @happy-path
  Scenario: Calculate Parts Per Million (PPM) defect rate
    Given quality entries exist with:
      | total_inspected | total_defects |
      | 1000000         | 500           |
    When I request GET "/api/quality/kpi/ppm"
    Then the response status should be 200
    And the response should contain:
      | field            | value   |
      | ppm              | 500.0   |
      | total_units_inspected | 1000000 |
      | total_defects    | 500     |
    # PPM = (500 / 1000000) * 1000000 = 500

  @quality @ppm @inference
  Scenario: PPM calculation indicates estimation when no data
    Given no quality entries exist for the date range
    When I request GET "/api/quality/kpi/ppm?start_date=2026-02-01&end_date=2026-02-28"
    Then the response status should be 200
    And the inference.is_estimated should be true
    And the inference.confidence_score should be 0.3

  @quality @dpmo @happy-path
  Scenario: Calculate Defects Per Million Opportunities (DPMO)
    Given production data with:
      | total_units | defects | opportunities_per_unit |
      | 10000       | 50      | 10                     |
    When I request GET "/api/quality/kpi/dpmo?product_id=1&shift_id=1&start_date=2026-01-01&end_date=2026-01-31&opportunities_per_unit=10"
    Then the response status should be 200
    And dpmo should be 500
    And sigma_level should be approximately 4.79
    # DPMO = (50 / (10000 * 10)) * 1000000 = 500

  @quality @trend
  Scenario: Get quality trend over date range
    When I request GET "/api/kpi/quality/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily FPY values

  @quality @top-defects
  Scenario: Get top defects for Pareto analysis
    When I request GET "/api/quality/kpi/top-defects?limit=10"
    Then the response status should be 200
    And defects should be sorted by frequency descending

  @quality @by-product
  Scenario: Get quality metrics by product
    When I request GET "/api/quality/kpi/by-product"
    Then the response status should be 200
    And each product should have:
      | field         |
      | product_name  |
      | inspected     |
      | defects       |
      | fpy           |

  # ============================================================================
  # AVAILABILITY CALCULATION
  # ============================================================================

  @availability @happy-path
  Scenario: Calculate availability from scheduled and downtime
    Given the scheduled hours for shift 1 is 8.0
    And downtime events total 1.5 hours
    When I request GET "/api/kpi/availability?product_id=1&shift_id=1&production_date=2026-01-25"
    Then the response status should be 200
    And availability_percentage should be 81.25
    # Availability = ((8 - 1.5) / 8) * 100 = 81.25%

  @availability @trend
  Scenario: Get availability trend over date range
    When I request GET "/api/kpi/availability/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily availability percentages

  # ============================================================================
  # OEE (OVERALL EQUIPMENT EFFECTIVENESS)
  # ============================================================================

  @oee @happy-path
  Scenario: Calculate OEE from component metrics
    Given for a production period:
      | availability | performance | quality |
      | 90%          | 95%         | 99%     |
    When OEE is calculated
    Then OEE should be 84.65%
    # OEE = 0.90 * 0.95 * 0.99 * 100 = 84.65%

  @oee @trend
  Scenario: Get OEE trend over date range
    When I request GET "/api/kpi/oee/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily OEE values
    And each value should be between 0 and 100

  @oee @world-class
  Scenario Outline: Classify OEE performance level
    Given OEE is calculated as <oee_value>%
    Then the performance classification should be "<classification>"

    Examples:
      | oee_value | classification |
      | 85        | World Class    |
      | 75        | Good           |
      | 65        | Typical        |
      | 50        | Needs Improvement |

  # ============================================================================
  # ON-TIME DELIVERY (OTD)
  # ============================================================================

  @otd @happy-path
  Scenario: Calculate On-Time Delivery percentage
    Given work orders exist with:
      | total_orders | on_time_deliveries |
      | 100          | 92                 |
    When I request GET "/api/kpi/otd"
    Then the response status should be 200
    And otd_percentage should be 92.0
    And on_time_count should be 92
    And total_orders should be 100

  @otd @on-time-definition
  Scenario: Order is considered on-time if delivered by required_date
    Given a work order with:
      | required_date        | actual_delivery_date |
      | 2026-01-25           | 2026-01-24           |
    Then the order should be counted as on-time

  @otd @open-orders
  Scenario: Open orders before due date count as on-time
    Given a work order with:
      | required_date        | actual_delivery_date | status |
      | 2026-02-01           | NULL                 | Open   |
    And today is 2026-01-25
    Then the order should be counted as on-time

  @otd @late-definition
  Scenario: Order is considered late if delivered after required_date
    Given a work order with:
      | required_date        | actual_delivery_date |
      | 2026-01-20           | 2026-01-22           |
    Then the order should be counted as late

  @otd @trend
  Scenario: Get OTD trend over date range
    When I request GET "/api/kpi/on-time-delivery/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily OTD percentages

  @otd @late-orders
  Scenario: Get list of late orders
    When I request GET "/api/kpi/late-orders"
    Then the response status should be 200
    And the response should contain work orders past their due date

  @otd @by-client
  Scenario: Get OTD metrics by client
    Given I am logged in as an admin
    When I request GET "/api/kpi/otd/by-client"
    Then the response status should be 200
    And each client should have OTD metrics

  # ============================================================================
  # ABSENTEEISM
  # ============================================================================

  @absenteeism @happy-path
  Scenario: Calculate absenteeism rate
    Given attendance entries exist with:
      | total_scheduled_hours | total_absent_hours |
      | 1000                  | 50                 |
    When I request GET "/api/attendance/kpi/absenteeism"
    Then the response status should be 200
    And absenteeism_rate should be 5.0
    # Absenteeism = (50 / 1000) * 100 = 5%

  @absenteeism @trend
  Scenario: Get absenteeism trend over date range
    When I request GET "/api/kpi/absenteeism/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily absenteeism rates

  @absenteeism @by-reason
  Scenario: Get absenteeism breakdown by reason
    When I request GET "/api/attendance/kpi/absenteeism"
    Then the response should contain by_reason array with:
      | field      |
      | reason     |
      | count      |
      | percentage |

  @absenteeism @by-department
  Scenario: Get absenteeism by department
    When I request GET "/api/attendance/kpi/absenteeism"
    Then the response should contain by_department array

  @absenteeism @high-absence
  Scenario: Identify employees with high absence
    When I request GET "/api/attendance/kpi/absenteeism"
    Then the response should contain high_absence_employees array
    And employees with 2+ absences should be flagged

  @bradford-factor @happy-path
  Scenario: Calculate Bradford Factor for employee
    Given employee 123 has:
      | absence_spells | total_days_absent |
      | 5              | 10                |
    When I request GET "/api/attendance/kpi/bradford-factor/123?start_date=2026-01-01&end_date=2026-12-31"
    Then the response status should be 200
    And bradford_score should be 250
    # Bradford = 5^2 * 10 = 250
    And interpretation should be "High risk - Formal action required"

  @bradford-factor @interpretation
  Scenario Outline: Bradford Factor risk interpretation
    Given employee has bradford_score <score>
    Then the interpretation should be "<risk_level>"

    Examples:
      | score | risk_level                          |
      | 25    | Low risk                            |
      | 75    | Medium risk - Monitor closely       |
      | 150   | High risk - Formal action required  |
      | 300   | Critical - Final warning/termination|

  # ============================================================================
  # KPI DASHBOARD
  # ============================================================================

  @dashboard @happy-path
  Scenario: Get KPI dashboard summary
    When I request GET "/api/kpi/dashboard?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the response should contain aggregated KPI metrics
    And client filtering should be applied based on user authorization

  @dashboard @default-dates
  Scenario: Dashboard defaults to last 30 days
    When I request GET "/api/kpi/dashboard" without date parameters
    Then the response status should be 200
    And the date range should default to the last 30 days

  # ============================================================================
  # KPI THRESHOLDS
  # ============================================================================

  @thresholds @happy-path
  Scenario: Get KPI thresholds for client
    When I request GET "/api/kpi-thresholds?client_id=CLIENT-001"
    Then the response status should be 200
    And the response should contain thresholds for:
      | kpi_key     |
      | efficiency  |
      | performance |
      | quality     |
      | oee         |
      | absenteeism |

  @thresholds @global-defaults
  Scenario: Get global default thresholds
    When I request GET "/api/kpi-thresholds" without client_id
    Then the response status should be 200
    And all thresholds should have is_global true

  @thresholds @update @rbac
  Scenario: Admin can update KPI thresholds
    Given I am logged in as an admin
    When I submit a PUT request to "/api/kpi-thresholds" with:
      | client_id  | CLIENT-001                          |
      | thresholds | {"efficiency": {"target_value": 85}}|
    Then the response status should be 200
    And the efficiency target should be updated to 85

  @thresholds @update @rbac
  Scenario: Non-admin cannot update thresholds
    Given I am logged in as "operator@client1.com" with role "OPERATOR"
    When I submit a PUT request to "/api/kpi-thresholds"
    Then the response status should be 403

  # ============================================================================
  # WIP AGING
  # ============================================================================

  @wip-aging @happy-path
  Scenario: Calculate WIP aging metrics
    Given there are active holds with various ages
    When I request GET "/api/kpi/wip-aging"
    Then the response status should be 200
    And the response should contain:
      | field               |
      | total_held_quantity |
      | average_aging_days  |
      | aging_0_7_days      |
      | aging_8_14_days     |
      | aging_15_30_days    |
      | aging_over_30_days  |

  @wip-aging @trend
  Scenario: Get WIP aging trend
    When I request GET "/api/kpi/wip-aging/trend?start_date=2026-01-01&end_date=2026-01-30"
    Then the response status should be 200
    And the response should contain daily average aging values

  @wip-aging @top-items
  Scenario: Get top aging WIP items
    When I request GET "/api/kpi/wip-aging/top?limit=10"
    Then the response status should be 200
    And items should be sorted by age descending

  @chronic-holds @happy-path
  Scenario: Identify chronic WIP holds
    Given holds exist older than 30 days
    When I request GET "/api/kpi/chronic-holds?threshold_days=30"
    Then the response status should be 200
    And the response should contain holds older than 30 days
