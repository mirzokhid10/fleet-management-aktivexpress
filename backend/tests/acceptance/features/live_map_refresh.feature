@day-13
Feature: The live map keeps itself up to date
  The dispatcher leaves the map open; it asks for new positions every 10
  seconds, so vehicles move on the screen without reloading the page.
  Clicking a vehicle shows its driver, phone, speed, last update and
  distance on the shift.

  Background:
    Given driver "Aliyev Vali" is registered in the bot

  Scenario: A vehicle moves on the open map
    Given "Aliyev Vali" is on shift with "01 A 123 BC" and driving
    And the dispatcher has the live map open
    When they drive north at 40 km/h for 1 minute
    Then the next refresh, at most 10 seconds later, shows "01 A 123 BC" at the new place
    And the vehicle panel of "01 A 123 BC" shows driver "Aliyev Vali", 40 km/h and 2,0 km on this shift

  Scenario: The open map notices the driver stopped sharing
    Given "Aliyev Vali" is on shift with "01 A 123 BC" and driving
    And the dispatcher has the live map open
    When they stop sharing
    Then the next refresh, at most 10 seconds later, shows "01 A 123 BC" as "Signal yo'q"
