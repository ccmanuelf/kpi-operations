@admin @critical
Feature: Admin Features
  As a system administrator
  I want to manage users, clients, and system settings
  So that I can control access and configure the platform

  Background:
    Given I am logged in as an admin

  # ============================================================
  # USER MANAGEMENT
  # ============================================================

  @user-management @smoke
  Feature: User Management
    Background:
      Given I am on the User Management page

    @user-management @display
    Scenario: User management page displays correctly
      Then I should see the "User Management" heading
      And I should see an "Add User" button
      And I should see filter controls for:
        | filter    |
        | Search    |
        | Role      |
        | Status    |
      And I should see a users data table with columns:
        | column    |
        | Username  |
        | Email     |
        | Full Name |
        | Role      |
        | Status    |
        | Created   |
        | Actions   |

    @user-management @table
    Scenario: Users table displays user data
      Given there are users in the system
      Then the table should display user information
      And active users should show a green "Active" chip
      And inactive users should show a red "Inactive" chip
      And roles should be color-coded:
        | role       | color  |
        | Admin      | red    |
        | Supervisor | orange |
        | Operator   | blue   |

    @user-management @search
    Scenario: Search users
      Given there are multiple users
      When I type "john" in the search field
      Then the table should filter to show only users matching "john"
      And the search should match username, email, or full name

    @user-management @filter-role
    Scenario: Filter users by role
      When I select "Operator" from the role filter
      Then only operators should be displayed in the table

    @user-management @filter-status
    Scenario: Filter users by status
      When I select "Active" from the status filter
      Then only active users should be displayed

    @user-management @add-user
    Scenario: Add new user
      When I click the "Add User" button
      Then I should see the create user dialog
      And the dialog should have fields:
        | field           | required |
        | Username        | yes      |
        | Email           | yes      |
        | Full Name       | yes      |
        | Password        | yes      |
        | Role            | yes      |
        | Assigned Client | no       |

    @user-management @add-user @validation
    Scenario: Add user validates required fields
      Given I have opened the create user dialog
      When I click "Create" without filling required fields
      Then I should see validation errors for:
        | field     | error                |
        | Username  | This field is required |
        | Email     | This field is required |
        | Full Name | This field is required |
        | Password  | This field is required |
        | Role      | This field is required |

    @user-management @add-user @email-validation
    Scenario: Add user validates email format
      Given I have opened the create user dialog
      When I enter email "invalid-email"
      And I try to submit
      Then I should see error "Invalid email address"

    @user-management @add-user @password-validation
    Scenario: Add user validates password length
      Given I have opened the create user dialog
      When I enter password "short"
      And I try to submit
      Then I should see error "Password must be at least 8 characters"

    @user-management @add-user @success
    Scenario: Successfully create new user
      Given I have opened the create user dialog
      When I fill in valid user details:
        | field           | value                |
        | Username        | newuser              |
        | Email           | newuser@factory.com  |
        | Full Name       | New User             |
        | Password        | SecurePass123!       |
        | Role            | Operator             |
      And I click "Create"
      Then I should see a success message "User created successfully"
      And the dialog should close
      And the new user should appear in the table

    @user-management @edit-user
    Scenario: Edit existing user
      Given there is a user "operator1" in the table
      When I click the edit button for "operator1"
      Then I should see the edit user dialog
      And the fields should be populated with user's data
      And the password field should be empty (not shown for edit)

    @user-management @edit-user @success
    Scenario: Successfully update user
      Given I am editing user "operator1"
      When I change the full name to "Updated Name"
      And I click "Update"
      Then I should see a success message "User updated successfully"
      And the table should show the updated name

    @user-management @toggle-status
    Scenario: Toggle user active status
      Given there is an active user "operator1"
      When I click the toggle status button for "operator1"
      Then the user should become inactive
      And I should see a success message "User deactivated successfully"

    @user-management @delete-user
    Scenario: Delete user requires confirmation
      Given there is a user "operator1"
      When I click the delete button for "operator1"
      Then I should see a confirmation dialog
      And it should ask "Are you sure you want to delete user operator1?"

    @user-management @delete-user @confirm
    Scenario: Confirm delete removes user
      Given I am viewing the delete confirmation for "operator1"
      When I click "Delete"
      Then the user should be removed from the table
      And I should see a success message "User deleted successfully"

    @user-management @delete-user @cancel
    Scenario: Cancel delete keeps user
      Given I am viewing the delete confirmation for "operator1"
      When I click "Cancel"
      Then the dialog should close
      And the user should remain in the table

    @user-management @roles
    Scenario: Role options are available
      When I open the create or edit user dialog
      And I click on the Role dropdown
      Then I should see roles:
        | role       | display    |
        | admin      | Admin      |
        | poweruser  | Supervisor |
        | operator   | Operator   |

    @user-management @refresh
    Scenario: Refresh users list
      When I click the refresh button
      Then the users list should reload from the server

  # ============================================================
  # CLIENT MANAGEMENT
  # ============================================================

  @client-management @smoke
  Feature: Client Management
    Background:
      Given I am on the Client Management page

    @client-management @display
    Scenario: Client management page displays correctly
      Then I should see the "Client Management" heading
      And I should see an "Add Client" button
      And I should see filter controls for:
        | filter |
        | Search |
        | Status |
      And I should see a clients data table with columns:
        | column       |
        | Client ID    |
        | Client Name  |
        | Contact      |
        | Email        |
        | Industry     |
        | Status       |
        | Created      |
        | Actions      |

    @client-management @add-client
    Scenario: Add new client
      When I click the "Add Client" button
      Then I should see the create client dialog
      And the dialog should have fields:
        | field         | required |
        | Client ID     | yes      |
        | Client Name   | yes      |
        | Contact Name  | no       |
        | Contact Email | no       |
        | Contact Phone | no       |
        | Industry      | no       |
        | Address       | no       |
        | Notes         | no       |

    @client-management @add-client @success
    Scenario: Successfully create new client
      Given I have opened the create client dialog
      When I fill in:
        | field         | value               |
        | Client ID     | ACME001             |
        | Client Name   | Acme Manufacturing  |
        | Contact Name  | John Smith          |
        | Contact Email | john@acme.com       |
        | Industry      | Automotive          |
      And I click "Create"
      Then I should see a success message "Client created successfully"
      And the new client should appear in the table

    @client-management @view-client
    Scenario: View client details
      Given there is a client "Acme Manufacturing"
      When I click the view button for that client
      Then I should see the client details dialog
      And it should show all client information

    @client-management @edit-client
    Scenario: Edit existing client
      Given there is a client "Acme Manufacturing"
      When I click the edit button for that client
      Then I should see the edit client dialog
      And the Client ID field should be disabled (not editable)
      And other fields should be populated with client data

    @client-management @toggle-status
    Scenario: Toggle client active status
      Given there is an active client
      When I click the toggle status button
      Then the client should become inactive
      And I should see a success message

    @client-management @delete-client
    Scenario: Delete client warns about associated data
      Given there is a client with associated data
      When I click the delete button for that client
      Then I should see a warning about deleting associated data
      And I should confirm before deletion

    @client-management @search
    Scenario: Search clients
      When I type "Acme" in the search field
      Then only clients matching "Acme" should be displayed

    @client-management @filter-status
    Scenario: Filter clients by status
      When I select "Active" from the status filter
      Then only active clients should be displayed

  # ============================================================
  # ADMIN SETTINGS
  # ============================================================

  @admin-settings
  Feature: Admin Settings
    Background:
      Given I am on the Admin Settings page

    @admin-settings @display
    Scenario: Settings page displays correctly
      Then I should see the "Settings" heading
      And I should see configuration options for the platform

  # ============================================================
  # DEFECT TYPES MANAGEMENT
  # ============================================================

  @defect-types
  Feature: Defect Types Management
    Background:
      Given I am on the Defect Types Management page

    @defect-types @display
    Scenario: Defect types page displays correctly
      Then I should see the "Defect Types" heading
      And I should be able to manage defect types per client

    @defect-types @add
    Scenario: Add new defect type
      When I click "Add Defect Type"
      Then I should see a form to create a defect type
      And I should be able to assign it to a client

    @defect-types @edit
    Scenario: Edit defect type
      Given there is an existing defect type
      When I click to edit it
      Then I should be able to modify its details

    @defect-types @delete
    Scenario: Delete defect type
      Given there is a defect type not in use
      When I click to delete it
      Then I should see a confirmation
      And upon confirming, it should be removed

  # ============================================================
  # AUTHORIZATION
  # ============================================================

  @authorization @admin-only
  Scenario Outline: Only admins can access admin pages
    Given I am logged in as "<role>"
    When I try to navigate to "<page>"
    Then I should be "<outcome>"

    Examples:
      | role       | page                  | outcome                      |
      | admin      | /admin/users          | on the user management page  |
      | admin      | /admin/clients        | on the client management page|
      | supervisor | /admin/users          | redirected to dashboard      |
      | supervisor | /admin/clients        | redirected to dashboard      |
      | operator   | /admin/users          | redirected to dashboard      |
      | operator   | /admin/clients        | redirected to dashboard      |

  @authorization @sidebar
  Scenario: Admin sidebar items only visible to admins
    Given I am logged in as an admin
    Then I should see Admin section in the sidebar
    When I logout and login as an operator
    Then I should NOT see Admin section in the sidebar

  # ============================================================
  # ERROR HANDLING
  # ============================================================

  @error-handling @user
  Scenario: Handle duplicate username error
    Given I am creating a new user
    And there is already a user with username "admin"
    When I try to create a user with username "admin"
    Then I should see an error indicating the username is taken

  @error-handling @client
  Scenario: Handle duplicate client ID error
    Given I am creating a new client
    And there is already a client with ID "ACME001"
    When I try to create a client with ID "ACME001"
    Then I should see an error indicating the client ID exists

  @error-handling @network
  Scenario: Handle network errors gracefully
    Given the server is unreachable
    When I try to save a user
    Then I should see an error message
    And I should be able to retry

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @tables
  Scenario: Admin tables are accessible
    Then data tables should have proper headers
    And action buttons should have aria-labels
    And dialogs should trap focus
    And success/error messages should be announced

  @accessibility @forms
  Scenario: Admin forms are accessible
    Then form fields should have associated labels
    And required fields should be marked
    And validation errors should be associated with fields
    And the forms should be keyboard navigable

  # ============================================================
  # BULK OPERATIONS
  # ============================================================

  @bulk @future
  Scenario: Bulk user import (future feature)
    Given I am on the user management page
    Then I should see an option to bulk import users
    When I upload a CSV of users
    Then they should be validated and imported

  @bulk @future
  Scenario: Bulk client import (future feature)
    Given I am on the client management page
    Then I should see an option to bulk import clients
    When I upload a CSV of clients
    Then they should be validated and imported
