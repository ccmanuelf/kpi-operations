# language: en
@authentication @security
Feature: Authentication and Authorization
  As a user of the KPI Operations platform
  I want to securely authenticate and manage my credentials
  So that my account and data remain protected

  Background:
    Given the KPI Operations API is running
    And the database is available

  # ============================================================================
  # USER REGISTRATION
  # ============================================================================

  @registration @happy-path
  Scenario: Register new user with valid credentials
    When I submit a registration request with:
      | field     | value                    |
      | username  | newoperator              |
      | email     | newoperator@client1.com  |
      | password  | SecurePass123!           |
      | full_name | New Operator             |
      | role      | OPERATOR                 |
    Then the response status should be 201
    And the response should contain a user_id matching pattern "USR-[A-Z0-9]{8}"
    And the response should contain the username "newoperator"
    And the password should not be included in the response

  @registration @validation
  Scenario: Reject registration with existing username
    Given a user exists with username "existinguser"
    When I submit a registration request with:
      | field    | value                |
      | username | existinguser         |
      | email    | new@client1.com      |
      | password | SecurePass123!       |
    Then the response status should be 400
    And the response should contain error "Username already registered"

  @registration @validation
  Scenario: Reject registration with existing email
    Given a user exists with email "existing@client1.com"
    When I submit a registration request with:
      | field    | value                |
      | username | newuser              |
      | email    | existing@client1.com |
      | password | SecurePass123!       |
    Then the response status should be 400
    And the response should contain error "Email already registered"

  @registration @rate-limiting
  Scenario: Enforce rate limiting on registration endpoint
    Given I have made 10 registration requests within 1 minute
    When I submit another registration request
    Then the response status should be 429
    And the response should contain error "Rate limit exceeded"

  # ============================================================================
  # USER LOGIN
  # ============================================================================

  @login @happy-path
  Scenario: Successful login with valid credentials
    Given a user exists with username "operator1" and password "ValidPass123!"
    When I submit a login request with:
      | field    | value         |
      | username | operator1     |
      | password | ValidPass123! |
    Then the response status should be 200
    And the response should contain an access_token
    And the response should contain token_type "bearer"
    And the response should contain user information

  @login @validation
  Scenario: Reject login with incorrect password
    Given a user exists with username "operator1" and password "ValidPass123!"
    When I submit a login request with:
      | field    | value         |
      | username | operator1     |
      | password | WrongPass123! |
    Then the response status should be 401
    And the response should contain error "Incorrect username or password"
    And the response header should contain "WWW-Authenticate: Bearer"

  @login @validation
  Scenario: Reject login with non-existent username
    When I submit a login request with:
      | field    | value           |
      | username | nonexistentuser |
      | password | AnyPassword123! |
    Then the response status should be 401
    And the response should contain error "Incorrect username or password"

  @login @security
  Scenario: Reject login for inactive user
    Given a user exists with username "inactiveuser" and is_active false
    When I submit a login request with:
      | field    | value         |
      | username | inactiveuser  |
      | password | ValidPass123! |
    Then the response status should be 403
    And the response should contain error "User account is inactive"

  @login @rate-limiting
  Scenario: Enforce rate limiting on login endpoint
    Given I have made 10 login requests within 1 minute
    When I submit another login request
    Then the response status should be 429
    And the response should contain error "Rate limit exceeded"

  # ============================================================================
  # JWT TOKEN HANDLING
  # ============================================================================

  @jwt @happy-path
  Scenario: Access protected endpoint with valid token
    Given I am logged in as "operator@client1.com"
    When I request GET "/api/auth/me"
    Then the response status should be 200
    And the response should contain my user information

  @jwt @validation
  Scenario: Reject request without authentication token
    When I request GET "/api/auth/me" without authentication
    Then the response status should be 401
    And the response should contain error "Not authenticated"

  @jwt @validation
  Scenario: Reject request with expired token
    Given I have an expired JWT token
    When I request GET "/api/auth/me" with the expired token
    Then the response status should be 401
    And the response should contain error "Token has expired"

  @jwt @validation
  Scenario: Reject request with malformed token
    Given I have a malformed JWT token "invalid.token.here"
    When I request GET "/api/auth/me" with the malformed token
    Then the response status should be 401
    And the response should contain error "Could not validate credentials"

  @jwt @security
  Scenario: Token contains client_id for multi-tenant validation
    Given I am logged in as "operator@client1.com" assigned to client "CLIENT-001"
    When I decode my access token
    Then the token payload should contain "client_ids" with value "CLIENT-001"
    And the token payload should contain "role" with value "OPERATOR"

  # ============================================================================
  # LOGOUT
  # ============================================================================

  @logout @happy-path
  Scenario: Successfully logout and invalidate token
    Given I am logged in as "operator@client1.com"
    And I have noted my current access_token
    When I request POST "/api/auth/logout"
    Then the response status should be 200
    And the response should contain message "Successfully logged out"
    When I use the previous token to request GET "/api/auth/me"
    Then the response status should be 401

  # ============================================================================
  # PASSWORD MANAGEMENT
  # ============================================================================

  @password @happy-path
  Scenario: Request password reset for existing email
    Given a user exists with email "user@client1.com"
    When I request a password reset for email "user@client1.com"
    Then the response status should be 200
    And the response should contain message "If your email is registered, you will receive a password reset link"

  @password @security
  Scenario: Password reset does not reveal email existence
    When I request a password reset for email "nonexistent@client1.com"
    Then the response status should be 200
    And the response should contain message "If your email is registered, you will receive a password reset link"

  @password @happy-path
  Scenario: Reset password with valid token
    Given I have a valid password reset token for user "resetuser"
    When I submit a password reset with:
      | field        | value          |
      | token        | <reset_token>  |
      | new_password | NewSecure123!  |
    Then the response status should be 200
    And the response should contain message "Password has been reset successfully"
    And I can login with the new password

  @password @validation
  Scenario: Reject password reset with invalid token
    When I submit a password reset with:
      | field        | value           |
      | token        | invalid.token   |
      | new_password | NewSecure123!   |
    Then the response status should be 400
    And the response should contain error "Invalid or expired reset token"

  @password @validation
  Scenario: Reject password reset with expired token
    Given I have an expired password reset token
    When I submit a password reset with the expired token
    Then the response status should be 400
    And the response should contain error "Invalid or expired reset token"

  @password @happy-path
  Scenario: Change password for authenticated user
    Given I am logged in as "operator@client1.com" with password "CurrentPass123!"
    When I submit a password change with:
      | field            | value           |
      | current_password | CurrentPass123! |
      | new_password     | NewSecure456!   |
    Then the response status should be 200
    And the response should contain message "Password changed successfully"

  @password @validation
  Scenario: Reject password change with incorrect current password
    Given I am logged in as "operator@client1.com" with password "CurrentPass123!"
    When I submit a password change with:
      | field            | value           |
      | current_password | WrongPassword!  |
      | new_password     | NewSecure456!   |
    Then the response status should be 400
    And the response should contain error "Current password is incorrect"

  # ============================================================================
  # ROLE-BASED ACCESS CONTROL
  # ============================================================================

  @rbac @security
  Scenario: Operator cannot access admin-only endpoints
    Given I am logged in as "operator@client1.com" with role "OPERATOR"
    When I request DELETE "/api/production/123"
    Then the response status should be 403
    And the response should contain error "Supervisor access required"

  @rbac @security
  Scenario: Supervisor can access supervisor-only endpoints
    Given I am logged in as "supervisor@client1.com" with role "SUPERVISOR"
    When I request DELETE "/api/production/123"
    Then the response status should not be 403

  @rbac @security
  Scenario: Admin has access to all endpoints
    Given I am logged in as "admin@kpi-ops.com" with role "ADMIN"
    When I request any protected endpoint
    Then I should not receive a 403 Forbidden response

  # ============================================================================
  # EDGE CASES AND ERROR HANDLING
  # ============================================================================

  @edge-case
  Scenario: Handle special characters in username
    When I submit a registration request with:
      | field    | value                  |
      | username | user_with-special.char |
      | email    | special@client1.com    |
      | password | SecurePass123!         |
    Then the response status should be 201 or 400 depending on validation rules

  @edge-case
  Scenario: Handle Unicode characters in full_name
    When I submit a registration request with:
      | field     | value              |
      | username  | unicodeuser        |
      | email     | unicode@client1.com|
      | password  | SecurePass123!     |
      | full_name | Jose Garcia Munoz  |
    Then the response status should be 201
    And the full_name should be stored correctly

  @edge-case
  Scenario: Handle maximum length inputs
    When I submit a registration request with username of 255 characters
    Then the response should handle the request appropriately

  @security
  Scenario: Prevent SQL injection in login
    When I submit a login request with:
      | field    | value                        |
      | username | admin'; DROP TABLE users; -- |
      | password | anything                     |
    Then the response status should be 401
    And the database should not be affected
