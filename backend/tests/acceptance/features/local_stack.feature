@day-02
Feature: The web app runs locally
  So that both developers build on the same base,
  the Django app runs on Docker Compose with PostGIS and Redis
  and shows the TailAdmin layout with the fleet menu.

  Scenario: A developer opens the web app
    When I open the home page
    Then I see the page title "Dashboard"
    And the sidebar lists these pages in order
      | page        |
      | Dashboard   |
      | Live map    |
      | Trips       |
      | Approvals   |
      | Vehicles    |
      | Drivers     |
      | Fuel        |
      | Maintenance |
      | Store       |
      | Documents   |
      | Reports     |
      | Settings    |
    And "Live map" is marked as coming on day 12

  Scenario: The services the app needs are up
    When I open the health check
    Then the database answers with PostGIS
    And the cache answers
