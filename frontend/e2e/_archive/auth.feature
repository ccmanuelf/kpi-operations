@auth @critical
Feature: User Authentication
  As a shop floor worker
  I want to securely log in and out of the KPI platform
  So that I can access my production data and protect sensitive information

  Background:
    Given the KPI Platform application is running
    And I am on the login page

  # ============================================================
  # LOGIN SCENARIOS
  # ============================================================

  @smoke @login
  Scenario: Successful login with valid credentials
    Given I see the "Manufacturing KPI" title
    When I enter username "operator1"
    And I enter password "ValidPassword123!"
    And I click the "Login" button
    Then I should be redirected to the dashboard
    And I should see the "Production Dashboard" heading
    And I should see the navigation sidebar
    And my session should be persisted in local storage

  @login @validation
  Scenario: Login fails with invalid username
    When I enter username "nonexistent_user"
    And I enter password "SomePassword123!"
    And I click the "Login" button
    Then I should see an error alert with message "Login failed"
    And I should remain on the login page
    And the password field should be cleared

  @login @validation
  Scenario: Login fails with invalid password
    When I enter username "operator1"
    And I enter password "WrongPassword123!"
    And I click the "Login" button
    Then I should see an error alert with message "Login failed"
    And I should remain on the login page

  @login @validation
  Scenario: Login shows validation error for empty username
    When I leave the username field empty
    And I enter password "SomePassword123!"
    And I click the "Login" button
    Then I should see validation error "Username is required"
    And the form should not be submitted

  @login @validation
  Scenario: Login shows validation error for empty password
    When I enter username "operator1"
    And I leave the password field empty
    And I click the "Login" button
    Then I should see validation error "Password is required"
    And the form should not be submitted

  @login @accessibility
  Scenario: Login form is accessible via keyboard
    When I focus on the username field
    And I type "operator1"
    And I press Tab
    Then the password field should be focused
    When I type "ValidPassword123!"
    And I press Enter
    Then the login should be attempted

  @login @loading
  Scenario: Login button shows loading state during authentication
    When I enter valid credentials
    And I click the "Login" button
    Then the "Login" button should show a loading spinner
    And the "Login" button should be disabled
    And the form fields should be disabled

  # ============================================================
  # LOGOUT SCENARIOS
  # ============================================================

  @logout
  Scenario: Successful logout clears session
    Given I am logged in as an operator
    When I click the logout button in the app bar
    Then I should be redirected to the login page
    And my access token should be removed from local storage
    And my user data should be removed from local storage

  @logout @confirmation
  Scenario: Navigation guard redirects unauthenticated users
    Given I am not logged in
    When I try to navigate to the dashboard URL directly
    Then I should be redirected to the login page
    And I should not see any dashboard content

  # ============================================================
  # SESSION PERSISTENCE
  # ============================================================

  @session @persistence
  Scenario: Session persists across page refreshes
    Given I am logged in as an operator
    When I refresh the page
    Then I should remain logged in
    And I should still see the dashboard
    And my user information should be displayed correctly

  @session @persistence
  Scenario: Expired token redirects to login
    Given I am logged in as an operator
    And my access token has expired
    When I try to access a protected resource
    Then I should be redirected to the login page
    And I should see a message indicating session expired

  # ============================================================
  # REGISTRATION SCENARIOS
  # ============================================================

  @registration
  Scenario: Open registration dialog
    When I click the "Create Account" link
    Then I should see the registration dialog
    And the dialog should have title "Create Account"
    And I should see fields for:
      | field            |
      | Username         |
      | Email            |
      | Full Name        |
      | Password         |
      | Confirm Password |

  @registration @validation
  Scenario: Registration requires all fields
    Given I have opened the registration dialog
    When I click the "Create Account" button
    Then I should see validation errors for required fields
    And the registration should not be submitted

  @registration @validation
  Scenario: Registration validates password requirements
    Given I have opened the registration dialog
    When I enter password "short"
    Then I should see error "Password must be at least 8 characters"

  @registration @validation
  Scenario: Registration validates password confirmation
    Given I have opened the registration dialog
    When I enter password "ValidPassword123!"
    And I enter confirm password "DifferentPassword123!"
    And I click the "Create Account" button
    Then I should see error "Passwords do not match"

  @registration @success
  Scenario: Successful registration shows confirmation
    Given I have opened the registration dialog
    When I fill in valid registration details:
      | field            | value                    |
      | Username         | newoperator              |
      | Email            | newop@factory.com        |
      | Full Name        | New Operator             |
      | Password         | SecurePassword123!       |
      | Confirm Password | SecurePassword123!       |
    And I click the "Create Account" button
    Then I should see a success message "Account created successfully"
    And the dialog should close automatically
    And I should be able to log in with my new credentials

  # ============================================================
  # FORGOT PASSWORD SCENARIOS
  # ============================================================

  @forgot-password
  Scenario: Open forgot password dialog
    When I click the "Forgot Password?" link
    Then I should see the forgot password dialog
    And the dialog should have title "Reset Password"
    And I should see an email input field

  @forgot-password @validation
  Scenario: Forgot password requires email
    Given I have opened the forgot password dialog
    When I click the "Send Reset Link" button without entering email
    Then I should see error "Email is required"

  @forgot-password @success
  Scenario: Forgot password sends reset link
    Given I have opened the forgot password dialog
    When I enter email "operator@factory.com"
    And I click the "Send Reset Link" button
    Then I should see message "If your email is registered, you will receive a password reset link"
    And the dialog should close automatically after a few seconds

  # ============================================================
  # ROLE-BASED ACCESS
  # ============================================================

  @authorization @admin
  Scenario: Admin user can access admin settings
    Given I am logged in as an admin
    When I navigate to the admin settings
    Then I should see the admin settings page
    And I should see user management options
    And I should see client management options

  @authorization @operator
  Scenario: Operator cannot access admin pages
    Given I am logged in as an operator
    When I try to navigate to "/admin/settings" directly
    Then I should be redirected to the dashboard
    And I should not see the admin settings page

  @authorization @supervisor
  Scenario: Supervisor has intermediate access
    Given I am logged in as a supervisor
    When I check my available navigation options
    Then I should see data entry options
    And I should see KPI report options
    And I should not see admin options

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @a11y
  Scenario: Login page meets accessibility requirements
    Then the page should have proper ARIA labels
    And all form fields should be associated with labels
    And error messages should be announced to screen readers
    And the page should have a skip-to-main link
    And color contrast should meet WCAG 2.1 AA standards

  @accessibility @focus
  Scenario: Focus management on login errors
    When I submit invalid credentials
    Then focus should move to the error alert
    And the error should be announced by screen readers
    And I should be able to navigate back to the form

  @accessibility @keyboard
  Scenario: All actions accessible via keyboard
    Then I should be able to tab through all interactive elements
    And the tab order should be logical
    And I should be able to activate buttons with Enter or Space
    And I should be able to close dialogs with Escape
