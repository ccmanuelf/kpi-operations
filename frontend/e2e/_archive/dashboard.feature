@dashboard @critical
Feature: Production Dashboard
  As a shop floor supervisor
  I want to view production KPIs at a glance
  So that I can monitor factory performance and make informed decisions

  Background:
    Given I am logged in as a supervisor
    And I am on the Production Dashboard page

  # ============================================================
  # DASHBOARD OVERVIEW
  # ============================================================

  @smoke @overview
  Scenario: Dashboard displays key production metrics
    Then I should see the "Production Dashboard" heading
    And I should see a KPI card for "Today's Units"
    And I should see a KPI card for "Avg Efficiency"
    And I should see a KPI card for "Avg Performance"
    And I should see a KPI card for "Total Entries"
    And each card should display a numeric value

  @overview @tooltips
  Scenario: KPI cards show explanatory tooltips on hover
    When I hover over the "Avg Efficiency" card
    Then I should see a tooltip containing:
      | content               |
      | Formula               |
      | Efficiency = (Actual Output / Expected Output) x 100 |
      | Meaning               |
    And the tooltip should have high contrast for readability

  @overview @loading
  Scenario: Dashboard shows loading state while fetching data
    Given data is being fetched
    Then I should see loading indicators on KPI cards
    And the data table should show a loading spinner
    And interactive elements should be temporarily disabled

  # ============================================================
  # CLIENT FILTERING
  # ============================================================

  @filtering @client
  Scenario: Filter dashboard by client
    Given there are multiple clients with production data
    When I select "Acme Manufacturing" from the client filter
    Then the KPI cards should update to show Acme data only
    And the production entries table should show only Acme entries
    And the client filter should display "Acme Manufacturing"

  @filtering @client
  Scenario: Clear client filter shows all data
    Given I have filtered by a specific client
    When I click the clear button on the client filter
    Then the dashboard should show data for all clients
    And the KPI values should be recalculated

  @filtering @loading
  Scenario: Filter change shows loading state
    When I change the client filter
    Then the dashboard should show a loading indicator
    And the data should refresh with the new filter applied

  # ============================================================
  # PRODUCTION ENTRIES TABLE
  # ============================================================

  @table @display
  Scenario: Production entries table displays correctly
    Then I should see a data table with columns:
      | column      |
      | Date        |
      | Reference   |
      | Product     |
      | Shift       |
      | Units       |
      | Efficiency  |
      | Performance |
    And entries should be sorted by date descending by default
    And each row should have efficiency and performance color-coded chips

  @table @sorting
  Scenario: Sort production entries by column
    When I click on the "Date" column header
    Then entries should be sorted by date ascending
    When I click on the "Date" column header again
    Then entries should be sorted by date descending

  @table @pagination
  Scenario: Paginate through production entries
    Given there are more than 10 production entries
    Then I should see pagination controls
    And I should see "10 items per page" by default
    When I click the next page button
    Then I should see the next set of entries

  @table @pagination
  Scenario: Change items per page
    When I select "25" from the items per page dropdown
    Then I should see up to 25 entries on the page
    And the pagination should update accordingly

  @table @color-coding
  Scenario: Efficiency values are color-coded
    Then entries with efficiency >= 85% should have green chips
    And entries with efficiency between 70-84% should have orange chips
    And entries with efficiency < 70% should have red chips

  @table @color-coding
  Scenario: Performance values are color-coded
    Then entries with performance >= 90% should have green chips
    And entries with performance between 75-89% should have orange chips
    And entries with performance < 75% should have red chips

  # ============================================================
  # EXPORT FUNCTIONALITY
  # ============================================================

  @export @csv
  Scenario: Export production data to CSV
    Given there are production entries in the table
    When I click the "Export CSV" button
    Then a CSV file should be downloaded
    And the file name should contain "production_entries" and today's date
    And the CSV should contain all visible columns
    And the CSV data should match the table data

  @export @excel
  Scenario: Export production data to Excel
    Given there are production entries in the table
    When I click the "Export Excel" button
    Then an Excel file should be downloaded
    And the file should have .xlsx extension
    And the data should be properly formatted

  @export @disabled
  Scenario: Export buttons disabled when no data
    Given there are no production entries
    Then the "Export CSV" button should be disabled
    And the "Export Excel" button should be disabled

  # ============================================================
  # EMAIL REPORTS
  # ============================================================

  @email @dialog
  Scenario: Open email reports dialog
    When I click the "Email Reports" button
    Then I should see the email reports dialog
    And I should see options to configure report delivery

  @email @configuration
  Scenario: Configure email report schedule
    Given I have opened the email reports dialog
    When I select "Daily" frequency
    And I enter recipient "manager@factory.com"
    And I select report type "Production Summary"
    And I click "Save"
    Then I should see a success notification
    And the email configuration should be saved

  # ============================================================
  # DATE FILTERING
  # ============================================================

  @filtering @date
  Scenario: Filter dashboard by date range
    When I set the start date to "2026-01-01"
    And I set the end date to "2026-01-15"
    Then the dashboard should show data only from that date range
    And the KPI calculations should reflect the filtered period

  @filtering @date
  Scenario: Default date range is last 30 days
    Then the start date should be 30 days ago
    And the end date should be today
    And data should be filtered to this default range

  # ============================================================
  # RESPONSIVE DESIGN
  # ============================================================

  @responsive @mobile
  Scenario: Dashboard is usable on mobile devices
    Given I am viewing on a mobile viewport (375px wide)
    Then the KPI cards should stack vertically
    And the data table should be horizontally scrollable
    And the client filter should be full width
    And all touch targets should be at least 44px

  @responsive @tablet
  Scenario: Dashboard adapts to tablet layout
    Given I am viewing on a tablet viewport (768px wide)
    Then the KPI cards should display in a 2x2 grid
    And the navigation should be accessible via hamburger menu

  # ============================================================
  # REAL-TIME UPDATES
  # ============================================================

  @realtime @refresh
  Scenario: Manual refresh updates dashboard data
    When I click the refresh button
    Then I should see a loading indicator
    And the data should be fetched from the server
    And the KPI values should update if changed

  @realtime @keyboard
  Scenario: Keyboard shortcut refreshes data
    When I press Ctrl+R
    Then a notification should appear "Refreshing data..."
    And the dashboard should refresh

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @a11y
  Scenario: Dashboard meets accessibility standards
    Then all data tables should have proper headers
    And KPI values should be readable by screen readers
    And charts should have accessible alternatives
    And color is not the only means of conveying information
    And focus indicators should be visible

  @accessibility @navigation
  Scenario: Keyboard navigation through dashboard
    Then I should be able to tab through all KPI cards
    And I should be able to navigate the data table with arrow keys
    And filter controls should be keyboard accessible
    And export buttons should be in the tab order
