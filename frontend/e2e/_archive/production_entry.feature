@production-entry @data-entry @critical
Feature: Production Data Entry
  As a shop floor operator
  I want to enter production data quickly and accurately
  So that I can return to my work without delay and ensure KPIs are tracked

  Background:
    Given I am logged in as an operator
    And I am on the Production Entry page

  # ============================================================
  # PAGE LOADING
  # ============================================================

  @smoke @loading
  Scenario: Production entry page loads correctly
    Then I should see the "Production Entry" heading
    And I should see the "Import CSV" button
    And I should see the "Add Entry" button
    And I should see the production data table
    And reference data should be loaded

  @loading @skeleton
  Scenario: Page shows skeleton loader while initializing
    Given I am navigating to the Production Entry page
    Then I should see a skeleton loader
    When the data finishes loading
    Then the skeleton should be replaced with actual content

  # ============================================================
  # ADDING NEW ENTRIES
  # ============================================================

  @add-entry @happy-path
  Scenario: Add new production entry with all required fields
    When I click the "Add Entry" button
    Then a new editable row should appear at the top of the table
    And the date should default to today's date
    When I select product "Widget A"
    And I select shift "Day Shift"
    And I enter units produced "150"
    And I enter runtime hours "7.5"
    And I enter employees assigned "3"
    And I click the save button
    Then the entry should be saved successfully
    And I should see a success notification
    And the new entry should appear in the table

  @add-entry @defaults
  Scenario: New entry has sensible defaults
    When I click the "Add Entry" button
    Then the date should be set to today
    And the product should default to the first available product
    And the shift should default to the first available shift
    And units produced should be "0"
    And runtime hours should be "0"
    And employees assigned should be "1"

  @add-entry @cancel
  Scenario: Cancel new entry before saving
    When I click the "Add Entry" button
    And I start filling in the form
    And I click the cancel button on the row
    Then the new row should be removed
    And no data should be saved

  # ============================================================
  # EDITING EXISTING ENTRIES
  # ============================================================

  @edit @happy-path
  Scenario: Edit existing production entry
    Given there is an existing production entry
    When I click the edit button on that entry
    Then the row should become editable
    And I should see input fields for each column
    When I change units produced to "200"
    And I click the save button
    Then the entry should be updated
    And I should see the new value "200" displayed

  @edit @cancel
  Scenario: Cancel edit restores original values
    Given I am editing an existing entry
    And the original units produced is "150"
    When I change units produced to "999"
    And I click the cancel button
    Then the entry should show the original value "150"
    And the row should no longer be editable

  # ============================================================
  # VALIDATION
  # ============================================================

  @validation @required
  Scenario: Required fields are validated before save
    When I click the "Add Entry" button
    And I try to save without filling required fields
    Then I should see validation indicators on required fields
    And the entry should not be saved
    And focus should move to the first invalid field

  @validation @numeric
  Scenario: Numeric fields only accept numbers
    When I am editing an entry
    And I try to enter "abc" in the units produced field
    Then the field should only accept numeric input
    And the invalid input should be rejected

  @validation @positive
  Scenario: Units and runtime must be positive
    When I am editing an entry
    And I enter "-10" in the units produced field
    Then I should see a validation error
    And the entry should not save with negative values

  @validation @employees
  Scenario: Employees must be at least 1
    When I am editing an entry
    And I enter "0" in the employees assigned field
    Then I should see a validation error "Must be at least 1"

  # ============================================================
  # DELETING ENTRIES
  # ============================================================

  @delete @confirmation
  Scenario: Delete entry requires confirmation
    Given there is an existing production entry
    When I click the delete button on that entry
    Then I should see a confirmation dialog
    And the dialog should ask "Are you sure you want to delete this entry?"

  @delete @confirm
  Scenario: Confirm delete removes entry
    Given I am viewing the delete confirmation dialog
    When I click "OK" to confirm
    Then the entry should be removed from the table
    And the entry should be deleted from the database

  @delete @cancel
  Scenario: Cancel delete keeps entry
    Given I am viewing the delete confirmation dialog
    When I click "Cancel"
    Then the dialog should close
    And the entry should remain in the table

  # ============================================================
  # CSV IMPORT - 3-STEP WORKFLOW
  # ============================================================

  @csv-import @step1
  Scenario: Step 1 - Upload and validate CSV file
    When I click the "Import CSV" button
    Then I should see the CSV import dialog
    And I should see "Step 1: Upload & Validate"
    When I upload a valid CSV file with 10 rows
    Then I should see a validation summary showing:
      | metric       | value |
      | Total Rows   | 10    |
      | Valid Rows   | 10    |
      | Invalid Rows | 0     |
    And the "Next: Preview Data" button should be enabled

  @csv-import @step1 @validation
  Scenario: Step 1 - CSV missing required columns
    When I click the "Import CSV" button
    And I upload a CSV file missing the "product_id" column
    Then I should see an error "Missing required columns: product_id"
    And the "Next" button should be disabled

  @csv-import @step1 @validation
  Scenario: Step 1 - CSV with invalid data format
    When I upload a CSV with invalid date format in row 3
    Then I should see validation errors listed:
      | row | error                               |
      | 3   | Invalid date format (use YYYY-MM-DD) |
    And the validation summary should show 1 invalid row

  @csv-import @template
  Scenario: Download CSV template
    When I click the "Import CSV" button
    And I click "Download CSV Template"
    Then a CSV template file should be downloaded
    And the template should contain the required column headers

  @csv-import @step2
  Scenario: Step 2 - Preview and edit data
    Given I have uploaded a valid CSV in Step 1
    When I click "Next: Preview Data"
    Then I should see "Step 2: Preview & Edit"
    And I should see a data grid with the parsed data
    And valid rows should be highlighted in green
    And invalid rows should be highlighted in red
    And I should see the calculated efficiency for each row

  @csv-import @step2 @inline-edit
  Scenario: Step 2 - Fix errors by editing cells
    Given I am on Step 2 with some invalid rows
    When I click on an invalid cell
    And I correct the value
    Then the row should be re-validated
    And if valid, the row should turn green
    And the preview summary should update

  @csv-import @step3
  Scenario: Step 3 - Confirm and import
    Given I have previewed the data in Step 2
    When I click "Next: Confirm Import"
    Then I should see "Step 3: Final Confirmation"
    And I should see the count of rows to import
    And I should see the count of rows to skip
    And I should see the "Confirm & Import" button

  @csv-import @step3 @success
  Scenario: Step 3 - Successful import
    Given I am on Step 3 with 8 valid rows
    When I click "Confirm & Import 8 Rows"
    Then I should see a progress bar
    And I should see "Uploading data..."
    When the import completes
    Then I should see "Import completed successfully!"
    And I should see how many rows were imported
    And the dialog should close automatically
    And the production entries table should refresh

  @csv-import @step3 @partial
  Scenario: Step 3 - Import with skipped rows
    Given I am on Step 3 with 7 valid and 3 invalid rows
    Then I should see a warning about 3 rows being skipped
    When I click "Confirm & Import 7 Rows"
    Then only the 7 valid rows should be imported
    And I should see the import results

  @csv-import @cancel
  Scenario: Cancel CSV import at any step
    Given I am in the CSV import workflow
    When I click "Cancel"
    Then the dialog should close
    And no data should be imported
    And I should return to the production entry page

  # ============================================================
  # KEYBOARD SHORTCUTS
  # ============================================================

  @keyboard @shortcuts
  Scenario: Create new entry with keyboard shortcut
    When I press Ctrl+N
    Then a new editable row should be added
    And focus should be on the first editable field

  @keyboard @shortcuts
  Scenario: Save entry with keyboard shortcut
    Given I am editing an entry
    When I press Ctrl+S
    Then the entry should be saved
    And I should see a success notification

  @keyboard @navigation
  Scenario: Navigate cells with Tab key
    Given I am editing an entry
    When I press Tab
    Then focus should move to the next editable cell
    When I press Shift+Tab
    Then focus should move to the previous editable cell

  @keyboard @editing
  Scenario: Start editing with Enter key
    Given the table has focus on a row
    When I press Enter
    Then the row should become editable

  # ============================================================
  # PERFORMANCE
  # ============================================================

  @performance @large-dataset
  Scenario: Handle large number of entries efficiently
    Given there are 500 production entries
    Then the table should render without lag
    And scrolling should be smooth
    And pagination should work correctly

  @performance @csv-large
  Scenario: Import large CSV file
    Given I upload a CSV with 200 rows
    Then the validation should complete within 5 seconds
    And the preview grid should render smoothly
    And the import should complete within 30 seconds

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @a11y
  Scenario: Production entry meets accessibility standards
    Then the table should have proper ARIA roles
    And editable cells should be announced as editable
    And validation errors should be associated with fields
    And the CSV dialog should trap focus
    And escape key should close dialogs

  @accessibility @screen-reader
  Scenario: Screen reader announces table changes
    When I add a new entry
    Then the screen reader should announce "New row added"
    When I save an entry
    Then the screen reader should announce the result
    When I delete an entry
    Then the screen reader should announce "Entry deleted"
