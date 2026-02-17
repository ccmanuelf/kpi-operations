@navigation @accessibility
Feature: Application Navigation
  As a factory floor user
  I want intuitive navigation with keyboard shortcuts
  So that I can quickly access different parts of the application

  Background:
    Given I am logged in as an operator
    And I am on any authenticated page

  # ============================================================
  # SIDEBAR NAVIGATION
  # ============================================================

  @sidebar @smoke
  Scenario: Navigation sidebar displays all sections
    Then I should see the navigation sidebar
    And the sidebar should contain the following sections:
      | section     | items                                         |
      | Main        | Dashboard, Production Entry, KPI Dashboard    |
      | Data Entry  | Downtime, Attendance, Quality, Hold/Resume    |
      | KPI Reports | Efficiency, WIP Aging, OTD, Availability, Performance, Quality, Absenteeism, OEE |
      | Admin       | Settings, Users, Clients, Defect Types        |

  @sidebar @navigation
  Scenario Outline: Navigate to pages via sidebar
    When I click on "<item>" in the sidebar
    Then I should be navigated to "<path>"
    And the "<item>" menu item should be highlighted as active

    Examples:
      | item             | path                   |
      | Dashboard        | /                      |
      | Production Entry | /production-entry      |
      | KPI Dashboard    | /kpi-dashboard         |
      | Downtime         | /data-entry/downtime   |
      | Attendance       | /data-entry/attendance |
      | Quality          | /data-entry/quality    |
      | Hold/Resume      | /data-entry/hold-resume|
      | Efficiency       | /kpi/efficiency        |
      | OEE              | /kpi/oee               |

  @sidebar @collapse
  Scenario: Collapse and expand sidebar
    Given the sidebar is expanded
    When I click the collapse button
    Then the sidebar should collapse to rail mode
    And only icons should be visible
    And I should still be able to navigate via icons

  @sidebar @expand
  Scenario: Expand collapsed sidebar
    Given the sidebar is in rail (collapsed) mode
    When I click the expand button
    Then the sidebar should expand to full width
    And menu item text should be visible

  @sidebar @hover
  Scenario: Hover reveals labels in rail mode
    Given the sidebar is in rail mode
    When I hover over a menu icon
    Then I should see a tooltip with the menu item name

  @sidebar @persistent
  Scenario: Sidebar state persists across navigation
    Given I have collapsed the sidebar
    When I navigate to a different page
    Then the sidebar should remain collapsed

  # ============================================================
  # APP BAR
  # ============================================================

  @appbar @display
  Scenario: App bar displays controls
    Then I should see the app bar at the top
    And the app bar should show "KPI Platform" title
    And I should see a hamburger menu button
    And I should see a keyboard shortcuts button
    And I should see a logout button

  @appbar @hamburger
  Scenario: Hamburger menu toggles sidebar on mobile
    Given I am on a mobile viewport
    When I click the hamburger menu
    Then the sidebar should toggle visibility

  # ============================================================
  # KEYBOARD SHORTCUTS
  # ============================================================

  @keyboard @help
  Scenario: Open keyboard shortcuts help
    When I click the keyboard icon in the app bar
    Then I should see the keyboard shortcuts help modal
    And it should display all available shortcuts by category

  @keyboard @help-shortcut
  Scenario: Open help with keyboard shortcut
    When I press Ctrl+/
    Then the keyboard shortcuts help modal should open

  @keyboard @close-help
  Scenario: Close help modal with Escape
    Given the keyboard shortcuts help modal is open
    When I press Escape
    Then the modal should close

  @keyboard @global-shortcuts
  Scenario Outline: Global keyboard shortcuts work
    When I press "<shortcut>"
    Then "<action>" should occur

    Examples:
      | shortcut | action                           |
      | Ctrl+S   | Save current form/grid           |
      | Ctrl+N   | Create new entry                 |
      | Ctrl+F   | Focus search field               |
      | Ctrl+K   | Open command palette             |
      | Ctrl+/   | Show keyboard shortcuts help     |
      | Escape   | Close modals/cancel editing      |
      | Ctrl+R   | Refresh current data             |

  @keyboard @navigation-shortcuts
  Scenario Outline: Navigation shortcuts work
    When I press "<shortcut>"
    Then I should be navigated to "<destination>"

    Examples:
      | shortcut | destination          |
      | Ctrl+D   | Dashboard (/)        |
      | Ctrl+P   | Production Entry     |
      | Ctrl+Q   | Quality Entry        |
      | Ctrl+A   | Attendance Entry     |
      | Ctrl+T   | Downtime Entry       |

  @keyboard @grid-shortcuts
  Scenario: Grid navigation shortcuts
    Given I am editing a data grid
    Then the following shortcuts should work:
      | shortcut       | action                      |
      | Tab            | Move to next editable cell  |
      | Shift+Tab      | Move to previous cell       |
      | Ctrl+Home      | Go to first cell            |
      | Ctrl+End       | Go to last cell             |
      | Enter          | Edit cell / Confirm edit    |
      | Escape         | Cancel cell edit            |
      | Ctrl+Z         | Undo last action            |
      | Ctrl+Y         | Redo last undone action     |
      | Ctrl+C         | Copy selected cells         |
      | Ctrl+V         | Paste data                  |

  @keyboard @form-shortcuts
  Scenario: Form shortcuts work
    Given I am on a data entry form
    Then the following shortcuts should work:
      | shortcut       | action                      |
      | Ctrl+S         | Save form                   |
      | Ctrl+Enter     | Save form (alternative)     |
      | Escape         | Cancel form editing         |
      | Ctrl+Shift+R   | Reset form to initial values|
      | Ctrl+Down      | Move to next form field     |
      | Ctrl+Up        | Move to previous form field |
      | Ctrl+E         | Focus first invalid field   |

  @keyboard @notification
  Scenario: Shortcut notifications appear
    Given keyboard notifications are enabled
    When I use a keyboard shortcut
    Then I should see a notification briefly showing what action was triggered

  @keyboard @preferences
  Scenario: Keyboard shortcut notifications can be disabled
    Given I am in the preferences
    When I disable "Show shortcut notifications"
    And I use a keyboard shortcut
    Then no notification should appear

  # ============================================================
  # MOBILE NAVIGATION
  # ============================================================

  @mobile @navigation
  Scenario: Mobile navigation drawer
    Given I am on a mobile viewport (< 768px)
    Then the sidebar should be hidden by default
    When I tap the hamburger menu
    Then the navigation drawer should slide in
    And I should see all navigation options

  @mobile @close-drawer
  Scenario: Close mobile drawer on navigation
    Given the mobile navigation drawer is open
    When I tap on a menu item
    Then I should navigate to that page
    And the drawer should close automatically

  @mobile @swipe
  Scenario: Swipe to close mobile drawer
    Given the mobile navigation drawer is open
    When I swipe left on the drawer
    Then the drawer should close

  @mobile @bottom-nav
  Scenario: Bottom navigation on mobile
    Given I am on a mobile viewport
    Then I should see a bottom navigation bar
    And it should contain quick access to:
      | item             |
      | Dashboard        |
      | Production       |
      | Data Entry       |
      | Reports          |

  # ============================================================
  # SKIP TO CONTENT
  # ============================================================

  @accessibility @skip-link
  Scenario: Skip to main content link
    When I press Tab as the first action on the page
    Then I should see a "Skip to main content" link
    When I press Enter on the skip link
    Then focus should move to the main content area

  @accessibility @skip-link-hidden
  Scenario: Skip link is visually hidden until focused
    Then the skip link should be visually hidden
    When I focus on the skip link
    Then it should become visible

  # ============================================================
  # BREADCRUMBS / PAGE CONTEXT
  # ============================================================

  @context @page-title
  Scenario: Page titles reflect current location
    When I navigate to the Efficiency page
    Then the page title should include "Efficiency"
    And the browser tab should show "Efficiency - KPI Platform"

  @context @back-button
  Scenario: Back button navigates to previous page
    Given I navigated from Dashboard to Efficiency
    When I click the back button
    Then I should return to the Dashboard

  # ============================================================
  # ERROR HANDLING
  # ============================================================

  @error @404
  Scenario: Handle invalid routes gracefully
    When I navigate to a non-existent route "/invalid-page"
    Then I should see a 404 error page
    And I should have a link to return to the dashboard

  @error @network
  Scenario: Handle network errors during navigation
    Given the network is unavailable
    When I try to navigate to a page
    Then I should see an appropriate error message
    And I should be able to retry the navigation

  # ============================================================
  # ACCESSIBILITY
  # ============================================================

  @accessibility @focus
  Scenario: Focus indicators are always visible
    When I tab through the application
    Then every focusable element should have a visible focus indicator
    And the focus order should be logical and sequential

  @accessibility @aria
  Scenario: ARIA landmarks are present
    Then the page should have the following ARIA landmarks:
      | role       | element            |
      | banner     | App bar            |
      | navigation | Sidebar            |
      | main       | Main content       |

  @accessibility @screen-reader
  Scenario: Navigation changes are announced
    When I navigate to a new page
    Then the new page title should be announced to screen readers
    And the main content area should receive focus

  @accessibility @reduced-motion
  Scenario: Respects reduced motion preference
    Given the user prefers reduced motion
    Then page transitions should be instant
    And no animations should play during navigation

  # ============================================================
  # ADMIN NAVIGATION RESTRICTIONS
  # ============================================================

  @admin @restricted
  Scenario: Admin section hidden from operators
    Given I am logged in as an operator
    Then I should not see the "Admin" section in the sidebar
    And admin routes should not be accessible

  @admin @visible
  Scenario: Admin section visible to admins
    Given I am logged in as an admin
    Then I should see the "Admin" section in the sidebar
    And I should be able to navigate to admin pages

  @admin @guard
  Scenario: Admin routes are protected
    Given I am logged in as an operator
    When I try to navigate directly to "/admin/users"
    Then I should be redirected to the dashboard
    And I should not see admin content
