@day-02
Feature: The web app runs locally
  So that both developers build on the same base,
  the Django app runs on Docker Compose with PostGIS and Redis
  and shows the TailAdmin layout with the fleet menu.

  Scenario: A developer opens the web app as the director
    Given I am logged in as the director
    When I open the home page
    Then I see the page title "Bosh sahifa"
    And the sidebar lists these pages in order
      | page          |
      | Bosh sahifa   |
      | Jonli xarita  |
      | Reyslar       |
      | Tasdiqlash    |
      | Avtomobillar  |
      | Haydovchilar  |
      | Yoqilg'i      |
      | Texnik xizmat |
      | Ombor         |
      | Hujjatlar     |
      | Hisobotlar    |
      | Sozlamalar    |
    And "Jonli xarita" is marked as coming on day 12

  Scenario: The services the app needs are up
    When I open the health check
    Then the database answers with PostGIS
    And the cache answers
