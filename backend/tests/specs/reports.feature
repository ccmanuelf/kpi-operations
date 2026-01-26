# language: en
@reports @export
Feature: Report Generation
  As a production manager
  I want to generate PDF and Excel reports
  So that I can share KPI data with stakeholders

  Background:
    Given the KPI Operations API is running
    And I am logged in as "manager@client1.com"
    And I have access to client "Manufacturing Co" with client_id "CLIENT-001"

  # ============================================================================
  # PRODUCTION REPORTS
  # ============================================================================

  @production @pdf @happy-path
  Scenario: Generate production efficiency PDF report
    When I request GET "/api/reports/production/pdf?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/pdf"
    And the Content-Disposition header should contain "production_report"
    And the X-Report-Type header should be "production"
    And the X-Generated-By header should contain my username

  @production @excel @happy-path
  Scenario: Generate production efficiency Excel report
    When I request GET "/api/reports/production/excel?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    And the Content-Disposition header should contain ".xlsx"

  @production @client-filter
  Scenario: Generate production report for specific client
    Given I am logged in as an admin
    When I request GET "/api/reports/production/pdf?client_id=CLIENT-001&start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the report should only contain "CLIENT-001" data

  # ============================================================================
  # QUALITY REPORTS
  # ============================================================================

  @quality @pdf @happy-path
  Scenario: Generate quality metrics PDF report
    When I request GET "/api/reports/quality/pdf?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/pdf"
    And the report should include:
      | metric |
      | FPY    |
      | RTY    |
      | PPM    |
      | DPMO   |

  @quality @excel @happy-path
  Scenario: Generate quality metrics Excel report
    When I request GET "/api/reports/quality/excel?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

  # ============================================================================
  # ATTENDANCE REPORTS
  # ============================================================================

  @attendance @pdf @happy-path
  Scenario: Generate attendance and absenteeism PDF report
    When I request GET "/api/reports/attendance/pdf?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/pdf"
    And the report should include absenteeism rates

  @attendance @excel @happy-path
  Scenario: Generate attendance Excel report
    When I request GET "/api/reports/attendance/excel?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

  # ============================================================================
  # COMPREHENSIVE REPORTS
  # ============================================================================

  @comprehensive @pdf @happy-path
  Scenario: Generate comprehensive KPI PDF report
    When I request GET "/api/reports/comprehensive/pdf?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the content-type should be "application/pdf"
    And the report should include all KPI categories:
      | category    |
      | Production  |
      | Quality     |
      | Attendance  |
      | Downtime    |
      | OTD         |

  @comprehensive @excel @happy-path
  Scenario: Generate comprehensive KPI Excel report
    When I request GET "/api/reports/comprehensive/excel?start_date=2026-01-01&end_date=2026-01-31"
    Then the response status should be 200
    And the Excel workbook should contain multiple sheets:
      | sheet_name       |
      | Executive Summary|
      | Production       |
      | Quality          |
      | Downtime         |
      | Attendance       |

  # ============================================================================
  # DATE HANDLING
  # ============================================================================

  @date @defaults
  Scenario: Reports default to last 30 days when no dates specified
    When I request GET "/api/reports/production/pdf" without date parameters
    Then the response status should be 200
    And the report should cover the last 30 days

  @date @validation
  Scenario: Reject report with invalid date format
    When I request GET "/api/reports/production/pdf?start_date=01-25-2026"
    Then the response status should be 400
    And the error should mention "Invalid date format"

  @date @validation
  Scenario: Reject report with start_date after end_date
    When I request GET "/api/reports/production/pdf?start_date=2026-02-01&end_date=2026-01-01"
    Then the response status should be 400
    And the error should mention "Start date must be before end date"

  @date @edge-case
  Scenario: Handle single day report
    When I request GET "/api/reports/production/pdf?start_date=2026-01-15&end_date=2026-01-15"
    Then the response status should be 200
    And the report should be generated for that single day

  # ============================================================================
  # MULTI-TENANT SECURITY
  # ============================================================================

  @security @client-isolation
  Scenario: Operator cannot generate report for other client
    Given I am logged in as "operator@client1.com" assigned to "CLIENT-001"
    When I request GET "/api/reports/production/pdf?client_id=CLIENT-002"
    Then the response status should be 403

  @security @client-isolation
  Scenario: Report data is filtered by user's client
    Given I am logged in as "operator@client1.com" assigned to "CLIENT-001"
    When I request GET "/api/reports/production/pdf"
    Then the response status should be 200
    And the report should only contain "CLIENT-001" data

  @security @admin-access
  Scenario: Admin can generate reports for any client
    Given I am logged in as "admin@kpi-ops.com" with role "ADMIN"
    When I request GET "/api/reports/comprehensive/pdf?client_id=CLIENT-002"
    Then the response status should be 200
    And the report should contain "CLIENT-002" data

  # ============================================================================
  # AVAILABLE REPORTS METADATA
  # ============================================================================

  @metadata @happy-path
  Scenario: Get list of available report types
    When I request GET "/api/reports/available"
    Then the response status should be 200
    And the response should contain report types:
      | type         |
      | production   |
      | quality      |
      | attendance   |
      | comprehensive|
    And each report type should have:
      | field       |
      | name        |
      | description |
      | formats     |
      | endpoints   |

  # ============================================================================
  # EMAIL REPORT CONFIGURATION
  # ============================================================================

  @email @config @get
  Scenario: Get email report configuration
    When I request GET "/api/reports/email-config"
    Then the response status should be 200
    And the response should contain:
      | field     |
      | enabled   |
      | frequency |
      | report_time |
      | recipients  |

  @email @config @get @client-specific
  Scenario: Get client-specific email configuration
    When I request GET "/api/reports/email-config?client_id=CLIENT-001"
    Then the response status should be 200
    And client_id should be "CLIENT-001"

  @email @config @create @happy-path
  Scenario: Create email report configuration
    When I submit POST "/api/reports/email-config" with:
      | field                    | value                        |
      | enabled                  | true                         |
      | frequency                | daily                        |
      | report_time              | 06:00                        |
      | recipients               | ["manager@client1.com"]      |
      | include_executive_summary| true                         |
      | include_efficiency       | true                         |
      | include_quality          | true                         |
    Then the response status should be 200
    And the configuration should be saved

  @email @config @validation
  Scenario: Reject email config without recipients when enabled
    When I submit POST "/api/reports/email-config" with:
      | field      | value |
      | enabled    | true  |
      | recipients | []    |
    Then the response status should be 400
    And the error should mention "At least one recipient email is required"

  @email @config @validation
  Scenario: Reject email config with invalid frequency
    When I submit POST "/api/reports/email-config" with:
      | field     | value   |
      | enabled   | true    |
      | frequency | hourly  |
    Then the response status should be 400
    And the error should mention "Frequency must be 'daily', 'weekly', or 'monthly'"

  @email @config @update @happy-path
  Scenario: Update existing email configuration
    Given an email configuration exists for my user
    When I submit PUT "/api/reports/email-config" with:
      | field     | value  |
      | frequency | weekly |
    Then the response status should be 200
    And frequency should be updated to "weekly"

  @email @config @update @not-found
  Scenario: Return 404 when updating non-existent config
    Given no email configuration exists for my user
    When I submit PUT "/api/reports/email-config"
    Then the response status should be 404
    And the error should mention "Email configuration not found"

  @email @test @happy-path
  Scenario: Send test email
    When I submit POST "/api/reports/email-config/test" with:
      | field | value               |
      | email | test@client1.com    |
    Then the response status should be 200
    And the response should indicate success

  # ============================================================================
  # MANUAL REPORT SENDING
  # ============================================================================

  @email @manual @happy-path
  Scenario: Manually send report via email
    When I submit POST "/api/reports/send-manual" with:
      | field            | value                     |
      | client_id        | CLIENT-001                |
      | start_date       | 2026-01-01                |
      | end_date         | 2026-01-31                |
      | recipient_emails | ["manager@client1.com"]   |
    Then the response status should be 200
    And the response should indicate report was sent

  @email @manual @security
  Scenario: Cannot send manual report for unauthorized client
    Given I am logged in as "operator@client1.com" assigned to "CLIENT-001"
    When I submit POST "/api/reports/send-manual" with:
      | field     | value      |
      | client_id | CLIENT-002 |
    Then the response status should be 403

  @email @manual @validation
  Scenario: Reject manual report with invalid date range
    When I submit POST "/api/reports/send-manual" with:
      | field      | value      |
      | client_id  | CLIENT-001 |
      | start_date | 2026-02-01 |
      | end_date   | 2026-01-01 |
    Then the response status should be 400
    And the error should mention "Start date must be before end date"

  # ============================================================================
  # ERROR HANDLING
  # ============================================================================

  @error @generation-failure
  Scenario: Handle report generation failure gracefully
    Given report generation will fail due to internal error
    When I request GET "/api/reports/production/pdf"
    Then the response status should be 500
    And the error should mention "Error generating PDF report"

  @error @no-data
  Scenario: Handle report with no data
    Given there is no production data for the date range
    When I request GET "/api/reports/production/pdf?start_date=2099-01-01&end_date=2099-01-31"
    Then the response status should be 200
    And the report should indicate no data available

  # ============================================================================
  # PERFORMANCE
  # ============================================================================

  @performance @large-dataset
  Scenario: Generate report for large date range
    Given there is extensive production data
    When I request GET "/api/reports/comprehensive/excel?start_date=2025-01-01&end_date=2025-12-31"
    Then the response should complete within acceptable time
    And the response status should be 200

  @performance @concurrent
  Scenario: Handle concurrent report requests
    Given multiple users request reports simultaneously
    Then all requests should be processed correctly
    And there should be no resource conflicts
