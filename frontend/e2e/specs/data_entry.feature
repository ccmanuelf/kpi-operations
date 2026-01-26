@data-entry
Feature: Data Entry Forms
  As a shop floor operator
  I want to record downtime, attendance, quality, and hold events
  So that the factory has accurate data for KPI tracking

  # ============================================================
  # DOWNTIME ENTRY
  # ============================================================

  @downtime @critical
  Feature: Downtime Entry
    Background:
      Given I am logged in as an operator
      And I am on the Downtime Entry page

    @downtime @smoke
    Scenario: Downtime entry page loads correctly
      Then I should see the "Downtime Entry" heading
      And I should see the CSV import button
      And I should see a form with fields:
        | field           | type     |
        | Equipment       | select   |
        | Downtime Reason | select   |
        | Start Time      | datetime |
        | End Time        | datetime |
        | Duration        | readonly |
        | Category        | select   |
        | Notes           | textarea |

    @downtime @skeleton
    Scenario: Downtime page shows loading skeleton
      Given reference data is being loaded
      Then I should see a skeleton loader
      When data finishes loading
      Then the form should be displayed

    @downtime @happy-path
    Scenario: Submit downtime entry with valid data
      When I select equipment "CNC Machine 1"
      And I select downtime reason "Mechanical Failure"
      And I set start time to "2026-01-25 08:00"
      And I set end time to "2026-01-25 09:30"
      Then the duration should automatically calculate to "90 minutes"
      When I select category "Unplanned Breakdown"
      And I enter notes "Spindle bearing replacement"
      And I click "Submit Downtime Entry"
      Then I should see a success message
      And the form should be reset for the next entry

    @downtime @duration-calc
    Scenario: Duration calculates automatically
      When I set start time to "2026-01-25 10:00"
      And I set end time to "2026-01-25 11:45"
      Then the duration field should show "105" minutes
      And the duration field should be readonly

    @downtime @validation
    Scenario: Downtime entry validates required fields
      When I click "Submit Downtime Entry" without filling required fields
      Then I should see validation errors on:
        | field           |
        | Equipment       |
        | Downtime Reason |
        | Start Time      |

    @downtime @inference
    Scenario: Inference engine suggests category
      When I select downtime reason "Mechanical Failure"
      Then I should see an inference suggestion panel
      And it should recommend category "Unplanned Breakdown"
      And it should show confidence percentage
      When I click "Apply Suggestion"
      Then the category field should be set to "Unplanned Breakdown"

    @downtime @categories
    Scenario: Downtime categories are available
      When I click on the Category dropdown
      Then I should see options:
        | category             |
        | Planned Maintenance  |
        | Unplanned Breakdown  |
        | Changeover           |
        | Material Shortage    |
        | Quality Issue        |
        | Operator Absence     |
        | Other                |

  # ============================================================
  # ATTENDANCE ENTRY
  # ============================================================

  @attendance @critical
  Feature: Attendance Entry
    Background:
      Given I am logged in as an operator
      And I am on the Attendance Entry page

    @attendance @smoke
    Scenario: Attendance entry page loads correctly
      Then I should see the "Attendance Entry" heading
      And I should see a form with fields:
        | field          | type     |
        | Employee ID    | text     |
        | Date           | date     |
        | Shift          | select   |
        | Status         | select   |
        | Clock In Time  | time     |
        | Clock Out Time | time     |
        | Notes          | textarea |

    @attendance @status-present
    Scenario: Submit attendance for present employee
      When I enter employee ID "EMP001"
      And the date defaults to today
      And I select shift "Day Shift"
      And I select status "Present"
      And I enter clock in time "07:00"
      And I enter clock out time "15:30"
      And I click "Submit Attendance"
      Then I should see a success message
      And the form should be reset

    @attendance @status-absent
    Scenario: Absent status shows additional fields
      When I select status "Absent"
      Then I should see an "Absence Reason" dropdown
      And I should see an "Excused Absence" checkbox
      When I select absence reason "Sick Leave"
      And I check "Excused Absence"
      And I submit the form
      Then the absence should be recorded with the reason

    @attendance @status-late
    Scenario: Late status shows minutes late field
      When I select status "Late"
      Then I should see a "Minutes Late" field
      When I enter minutes late "15"
      And I submit the form
      Then the late arrival should be recorded

    @attendance @absence-reasons
    Scenario: Absence reasons are available
      When I select status "Absent"
      And I click on the Absence Reason dropdown
      Then I should see options:
        | reason              |
        | Sick Leave          |
        | Personal Leave      |
        | Family Emergency    |
        | Medical Appointment |
        | No Show             |
        | Unauthorized        |
        | Other               |

    @attendance @validation
    Scenario: Attendance validates required fields
      When I click "Submit Attendance" without filling required fields
      Then I should see validation errors on:
        | field       |
        | Employee ID |
        | Date        |
        | Shift       |
        | Status      |

    @attendance @default-date
    Scenario: Date defaults to today
      Then the date field should show today's date
      And I should be able to change it to a past date

  # ============================================================
  # QUALITY ENTRY
  # ============================================================

  @quality @critical
  Feature: Quality Inspection Entry
    Background:
      Given I am logged in as a quality inspector
      And I am on the Quality Entry page

    @quality @smoke
    Scenario: Quality entry page loads correctly
      Then I should see the "Quality Inspection Entry" heading
      And I should see a form with fields:
        | field               | type     |
        | Client              | select   |
        | Work Order          | select   |
        | Product             | select   |
        | Inspected Quantity  | number   |
        | Defect Quantity     | number   |
        | Rejected Quantity   | number   |
        | Primary Defect Type | select   |
        | Severity            | select   |
        | Disposition         | select   |
        | Inspector ID        | text     |
        | Defect Description  | textarea |
        | Corrective Action   | textarea |

    @quality @happy-path
    Scenario: Submit quality inspection entry
      When I select client "Acme Corp"
      And I select work order "WO-2026-001"
      And I select product "Widget A"
      And I enter inspected quantity "100"
      And I enter defect quantity "3"
      And I enter rejected quantity "2"
      And I select defect type "Dimensional"
      And I select severity "Minor"
      And I select disposition "Rework"
      And I click "Submit Quality Entry"
      Then I should see a success message
      And the form should be reset

    @quality @calculated-metrics
    Scenario: Quality metrics calculate automatically
      When I enter inspected quantity "100"
      And I enter defect quantity "5"
      Then I should see calculated metrics panel showing:
        | metric       | value    |
        | FPY          | 95.00%   |
        | Defect Rate  | 5.00%    |
        | PPM          | 50000    |
        | Pass Qty     | 95       |

    @quality @fpy-calculation
    Scenario: FPY updates in real-time
      When I enter inspected quantity "200"
      And I enter defect quantity "4"
      Then FPY should show "98.00%"
      When I change defect quantity to "10"
      Then FPY should update to "95.00%"

    @quality @defect-types
    Scenario: Defect types filter by client
      Given client "Acme Corp" has custom defect types
      When I select client "Acme Corp"
      Then the defect type dropdown should show Acme's defect types
      And the hint should say "Select a client first" if no client selected

    @quality @severities
    Scenario: Severity levels are available
      When I click on the Severity dropdown
      Then I should see options:
        | severity  |
        | Critical  |
        | Major     |
        | Minor     |
        | Cosmetic  |

    @quality @dispositions
    Scenario: Disposition options are available
      When I click on the Disposition dropdown
      Then I should see options:
        | disposition         |
        | Accept              |
        | Reject              |
        | Rework              |
        | Use As Is           |
        | Return to Supplier  |

    @quality @validation
    Scenario: Quality entry validates required fields
      When I click "Submit Quality Entry" without filling required fields
      Then I should see validation errors on:
        | field              |
        | Client             |
        | Work Order         |
        | Product            |
        | Inspected Quantity |
        | Disposition        |

    @quality @positive-validation
    Scenario: Inspected quantity must be positive
      When I enter inspected quantity "0"
      And I try to submit
      Then I should see error "Must be greater than 0"

  # ============================================================
  # HOLD/RESUME ENTRY
  # ============================================================

  @hold-resume @critical
  Feature: Hold/Resume Entry
    Background:
      Given I am logged in as an operator
      And I am on the Hold/Resume Entry page

    @hold-resume @smoke
    Scenario: Hold/Resume page loads with tabs
      Then I should see the "Hold/Resume Management" heading
      And I should see two tabs:
        | tab           |
        | Create Hold   |
        | Resume Hold   |
      And the "Create Hold" tab should be active by default

    @hold @happy-path
    Scenario: Create a new hold
      Given I am on the "Create Hold" tab
      When I select work order "WO-2026-001"
      And I enter quantity to hold "50"
      And I select hold reason "Quality Issue"
      And I select severity "High"
      And I enter hold description "Out of spec dimensions"
      And I enter required action "Inspection required"
      And I enter initiated by "John Smith"
      And I check "Customer Notification Required"
      And I click "Create Hold"
      Then I should see a success message "Hold created successfully!"
      And the form should be reset

    @hold @reasons
    Scenario: Hold reasons are available
      When I click on the Hold Reason dropdown
      Then I should see options:
        | reason                  |
        | Quality Issue           |
        | Material Defect         |
        | Process Non-Conformance |
        | Customer Request        |
        | Engineering Change      |
        | Inspection Failure      |
        | Supplier Issue          |
        | Other                   |

    @hold @severities
    Scenario: Hold severity levels are available
      When I click on the Severity dropdown
      Then I should see options:
        | severity |
        | Critical |
        | High     |
        | Medium   |
        | Low      |

    @hold @validation
    Scenario: Hold creation validates required fields
      Given I am on the "Create Hold" tab
      When I click "Create Hold" without filling required fields
      Then I should see validation errors on:
        | field            |
        | Work Order       |
        | Quantity to Hold |
        | Hold Reason      |
        | Severity         |
        | Hold Description |

    @resume @tab-switch
    Scenario: Switch to Resume Hold tab
      When I click on the "Resume Hold" tab
      Then I should see a dropdown to select an active hold
      And I should see resume form fields

    @resume @select-hold
    Scenario: Select active hold to resume
      Given I am on the "Resume Hold" tab
      And there are active holds in the system
      When I select an active hold from the dropdown
      Then I should see the hold information displayed:
        | info          |
        | Work Order    |
        | Quantity      |
        | Reason        |
        | Description   |
        | Hold Date     |
      And the released quantity should default to the hold quantity

    @resume @happy-path
    Scenario: Resume a hold
      Given I have selected an active hold to resume
      When I select disposition "Release"
      And I enter released quantity "50"
      And I enter resolution notes "Inspection passed"
      And I enter approved by "Jane Doe"
      And I check "Customer Notified"
      And I click "Resume Hold"
      Then I should see a success message "Hold resumed successfully!"
      And the form should be reset
      And the hold should be removed from active holds

    @resume @dispositions
    Scenario: Resume dispositions are available
      When I am on the Resume Hold tab
      And I click on the Disposition dropdown
      Then I should see options:
        | disposition         |
        | Release             |
        | Rework              |
        | Scrap               |
        | Return to Supplier  |
        | Use As Is           |

    @resume @validation
    Scenario: Resume hold validates required fields
      Given I have selected an active hold
      When I click "Resume Hold" without filling required fields
      Then I should see validation errors on:
        | field            |
        | Disposition      |
        | Resolution Notes |
        | Approved By      |

  # ============================================================
  # CSV IMPORT (ALL FORMS)
  # ============================================================

  @csv-import @all-forms
  Scenario Outline: CSV import available on all data entry forms
    Given I am on the <form> Entry page
    Then I should see a CSV import button
    When I click the CSV import button
    Then I should see the CSV upload dialog

    Examples:
      | form       |
      | Downtime   |
      | Attendance |
      | Quality    |
      | Hold       |

  @csv-import @refresh
  Scenario: CSV import refreshes data on success
    Given I am on the Downtime Entry page
    When I successfully import data via CSV
    Then a "submitted" event should be emitted
    And the page data should refresh

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @forms
  Scenario: All data entry forms meet accessibility standards
    Then all form fields should have visible labels
    And required fields should be marked with asterisks
    And error messages should be associated with fields via aria-describedby
    And form validation should announce errors to screen readers
    And dropdowns should be keyboard navigable

  @accessibility @focus
  Scenario: Focus management after form submission
    When I submit a valid form entry
    Then focus should return to the first form field
    And the success message should be announced
