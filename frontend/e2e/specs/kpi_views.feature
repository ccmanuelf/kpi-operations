@kpi-views @reports
Feature: KPI Views and Reports
  As a production manager
  I want to view detailed KPI reports with charts and analysis
  So that I can identify trends and make data-driven decisions

  Background:
    Given I am logged in as a supervisor

  # ============================================================
  # EFFICIENCY VIEW
  # ============================================================

  @efficiency @critical
  Feature: Efficiency KPI View
    Background:
      Given I am on the Efficiency KPI page

    @efficiency @smoke
    Scenario: Efficiency page displays all components
      Then I should see the "Operational Efficiency" heading
      And I should see the current efficiency percentage prominently displayed
      And I should see target indicator "Target: 85%"
      And I should see filters for client, start date, and end date
      And I should see summary cards for:
        | card             |
        | Current Efficiency |
        | Actual Output     |
        | Expected Output   |
        | Gap               |
      And I should see the efficiency trend chart
      And I should see historical data table

    @efficiency @tooltips
    Scenario: Efficiency cards show formula tooltips
      When I hover over the "Current Efficiency" card
      Then I should see a tooltip with:
        | content                                      |
        | Formula                                      |
        | Efficiency = (Actual Output / Expected Output) x 100 |
        | Meaning                                      |

    @efficiency @color-coding
    Scenario: Efficiency status is color-coded
      Then if efficiency >= 85%, the chip should be green (success)
      And if efficiency is 70-84%, the chip should be amber
      And if efficiency < 70%, the chip should be red (error)

    @efficiency @gap-color
    Scenario: Gap value is color-coded
      Then if gap is positive (exceeding target), it should be green
      And if gap is negative (below target), it should be red

    @efficiency @filtering
    Scenario: Filter efficiency data by client
      Given there is data for multiple clients
      When I select client "Acme Corp" from the filter
      Then the efficiency metrics should update for Acme only
      And the chart should show only Acme data

    @efficiency @date-range
    Scenario: Filter by date range
      When I set start date to "2026-01-01"
      And I set end date to "2026-01-15"
      And I click "Refresh"
      Then all data should be filtered to that date range
      And the chart should show the trend for those dates

    @efficiency @forecast
    Scenario: Toggle forecast display
      When I toggle "Show Forecast" on
      Then I should see forecast prediction lines on the chart
      And I should see prediction summary card with:
        | metric              |
        | Predicted Average   |
        | Current Value       |
        | Expected Change     |
        | Model Accuracy      |
        | Method              |

    @efficiency @forecast-days
    Scenario: Change forecast period
      Given forecast is enabled
      When I select "14" from the forecast days dropdown
      Then the forecast should extend 14 days into the future
      And prediction data should update

    @efficiency @health-assessment
    Scenario: View health assessment
      Given forecast is enabled
      Then I should see a Health Assessment card
      And it should display health score as a circular progress
      And it should show trend indicator (improving/declining/stable)
      And it should show recommendations

    @efficiency @breakdown
    Scenario: View efficiency by shift
      Then I should see "Efficiency by Shift" table
      And it should show each shift with:
        | column      |
        | Shift       |
        | Output      |
        | Expected    |
        | Efficiency  |

    @efficiency @by-product
    Scenario: View top products by efficiency
      Then I should see "Top Products by Efficiency" table
      And products should be ranked by efficiency

  # ============================================================
  # OEE VIEW
  # ============================================================

  @oee @critical
  Feature: OEE (Overall Equipment Effectiveness) View
    Background:
      Given I am on the OEE KPI page

    @oee @smoke
    Scenario: OEE page displays formula and components
      Then I should see the "Overall Equipment Effectiveness (OEE)" heading
      And I should see the OEE formula displayed:
        | formula                                     |
        | OEE = Availability x Performance x Quality  |
      And I should see the calculated OEE percentage
      And I should see target "Target: 85%" (World Class)

    @oee @components
    Scenario: OEE component cards are displayed
      Then I should see three component cards:
        | component    | description       |
        | Availability | Equipment uptime  |
        | Performance  | Speed efficiency  |
        | Quality      | First pass yield  |
      And each card should show the percentage
      And each card should be clickable for drill-down

    @oee @drill-down
    Scenario Outline: Clicking component navigates to detail view
      When I click on the "<component>" card
      Then I should be navigated to the <page> page

      Examples:
        | component    | page           |
        | Availability | /kpi/availability |
        | Performance  | /kpi/performance  |
        | Quality      | /kpi/quality      |

    @oee @tooltips
    Scenario: OEE components show formula tooltips
      When I hover over the "Availability" card
      Then I should see tooltip with:
        | content                                    |
        | Formula                                    |
        | Availability = (Uptime / Planned Time) x 100 |
        | Meaning                                    |
        | Target: 90%+                               |

    @oee @trend
    Scenario: OEE trend chart displays
      Then I should see an OEE trend chart
      And it should show the OEE line over time
      And it should show a "World Class (85%)" target line
      And the chart should be interactive (tooltips on hover)

    @oee @filtering
    Scenario: Filter OEE data by client and date
      When I select a client from the filter
      And I set a date range
      And I click "Refresh"
      Then OEE and all components should recalculate
      And the chart should update

    @oee @status-color
    Scenario: OEE status is color-coded
      Then if OEE >= 85%, it should show as green (World Class)
      And if OEE is 65-84%, it should show as amber
      And if OEE < 65%, it should show as red (needs improvement)

  # ============================================================
  # KPI DASHBOARD (SUMMARY VIEW)
  # ============================================================

  @kpi-dashboard
  Feature: KPI Dashboard Summary
    Background:
      Given I am on the KPI Dashboard page

    @kpi-dashboard @smoke
    Scenario: KPI dashboard shows all major KPIs
      Then I should see summary cards for all KPIs:
        | kpi              |
        | Efficiency       |
        | Performance      |
        | Quality (FPY)    |
        | Availability     |
        | OEE              |
        | On-Time Delivery |

    @kpi-dashboard @navigation
    Scenario: Each KPI card navigates to detail view
      When I click on the "Efficiency" KPI card
      Then I should be navigated to the Efficiency detail page

  # ============================================================
  # PERFORMANCE VIEW
  # ============================================================

  @performance
  Feature: Performance KPI View
    Background:
      Given I am on the Performance KPI page

    @performance @smoke
    Scenario: Performance page displays correctly
      Then I should see "Performance" heading
      And I should see current performance percentage
      And I should see formula tooltip explaining:
        | content                                       |
        | Performance = (Actual Rate / Ideal Rate) x 100 |

    @performance @trend
    Scenario: Performance trend chart
      Then I should see a performance trend chart
      And it should show target line at 95%

  # ============================================================
  # QUALITY VIEW
  # ============================================================

  @quality-kpi
  Feature: Quality KPI View
    Background:
      Given I am on the Quality KPI page

    @quality-kpi @smoke
    Scenario: Quality page displays metrics
      Then I should see "Quality" heading
      And I should see First Pass Yield (FPY) percentage
      And I should see defect rate
      And I should see PPM (Parts Per Million)

    @quality-kpi @defect-analysis
    Scenario: Defect breakdown by type
      Then I should see defect breakdown by type
      And I should see a chart showing defect distribution

    @quality-kpi @by-operator
    Scenario: Quality by operator widget
      Then I should see quality metrics by operator
      And I can identify top and bottom performers

  # ============================================================
  # AVAILABILITY VIEW
  # ============================================================

  @availability
  Feature: Availability KPI View
    Background:
      Given I am on the Availability KPI page

    @availability @smoke
    Scenario: Availability page displays correctly
      Then I should see "Availability" heading
      And I should see availability percentage
      And I should see planned vs actual uptime

    @availability @downtime-analysis
    Scenario: Downtime impact analysis
      Then I should see downtime impact widget
      And it should show downtime by category
      And it should show top reasons for downtime

  # ============================================================
  # ON-TIME DELIVERY VIEW
  # ============================================================

  @otd
  Feature: On-Time Delivery KPI View
    Background:
      Given I am on the On-Time Delivery KPI page

    @otd @smoke
    Scenario: OTD page displays correctly
      Then I should see "On-Time Delivery" heading
      And I should see OTD percentage
      And I should see orders delivered vs total orders

    @otd @breakdown
    Scenario: OTD breakdown by client
      Then I should see OTD by client breakdown
      And I can identify clients with delivery issues

  # ============================================================
  # ABSENTEEISM VIEW
  # ============================================================

  @absenteeism
  Feature: Absenteeism KPI View
    Background:
      Given I am on the Absenteeism KPI page

    @absenteeism @smoke
    Scenario: Absenteeism page displays correctly
      Then I should see "Absenteeism" heading
      And I should see absenteeism rate percentage
      And I should see trend over time

    @absenteeism @bradford
    Scenario: Bradford Factor widget
      Then I should see Bradford Factor widget
      And it should show employees with high Bradford scores
      And it should explain the Bradford Factor calculation

    @absenteeism @alerts
    Scenario: Absenteeism alerts
      Then I should see alerts for employees with concerning patterns
      And alerts should be prioritized by severity

  # ============================================================
  # WIP AGING VIEW
  # ============================================================

  @wip-aging
  Feature: WIP Aging View
    Background:
      Given I am on the WIP Aging KPI page

    @wip-aging @smoke
    Scenario: WIP Aging page displays correctly
      Then I should see "WIP Aging" heading
      And I should see work in progress items
      And items should be categorized by age buckets

    @wip-aging @buckets
    Scenario: WIP aging buckets
      Then I should see items grouped by age:
        | bucket     |
        | 0-7 days   |
        | 8-14 days  |
        | 15-30 days |
        | 30+ days   |

  # ============================================================
  # COMMON FEATURES
  # ============================================================

  @common @refresh
  Scenario Outline: All KPI views have refresh capability
    Given I am on the <view> page
    When I click the "Refresh" button
    Then the data should reload
    And I should see a loading indicator during refresh

    Examples:
      | view         |
      | Efficiency   |
      | OEE          |
      | Performance  |
      | Quality      |
      | Availability |

  @common @back-navigation
  Scenario Outline: All KPI views have back navigation
    Given I am on the <view> page
    Then I should see a back button
    When I click the back button
    Then I should return to the previous page

    Examples:
      | view         |
      | Efficiency   |
      | OEE          |
      | Performance  |

  @common @search
  Scenario: Historical data tables are searchable
    Given I am viewing a KPI page with historical data
    When I enter a search term in the search field
    Then the table should filter to matching rows

  @common @export
  Scenario: KPI data can be exported
    Given I am viewing KPI data
    Then I should have an option to export the data
    And exports should include the filtered data

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @charts
  Scenario: Charts have accessible alternatives
    Then all charts should have aria-labels
    And data should also be available in tabular format
    And color should not be the only indicator of status

  @accessibility @navigation
  Scenario: KPI views are keyboard navigable
    Then I should be able to tab through all interactive elements
    And charts should be focusable
    And tooltips should be accessible via keyboard
