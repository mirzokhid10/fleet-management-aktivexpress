@day-12
Feature: Managers see every vehicle on the live map
  The web map shows each vehicle where its driver's phone last was, with a
  status: moving, stopped, no signal (on shift but no location) or off shift
  (parked at its last known place). Real phones send Telegram live location.

  Background:
    Given driver "Aliyev Vali" is registered in the bot
    And vehicle "01 777 AAA" is parked and has never been tracked

  Scenario: The map follows a driver through the shift
    When "Aliyev Vali" starts a shift with "01 A 123 BC"
    Then the map shows "01 A 123 BC" as "Signal yo'q" with no position
    When they share their live location and drive north at 40 km/h for 2 minutes
    Then the map shows "01 A 123 BC" as "Harakatda" with driver "Aliyev Vali" at the last place
    When they stand still for 2 minutes
    Then the map shows "01 A 123 BC" as "To'xtagan"
    When they stop sharing
    Then the map shows "01 A 123 BC" as "Signal yo'q" at the last place
    When they end the shift
    Then the map shows "01 A 123 BC" as "Smenada emas" at the last place
    And the map shows "01 777 AAA" as "Smenada emas" with no position

  Scenario: A share that goes silent turns into no signal after 10 minutes
    Given "Aliyev Vali" is on shift with "01 A 123 BC" and driving
    When nothing arrives from their phone for 9 minutes
    Then the map shows "01 A 123 BC" as "To'xtagan"
    When nothing arrives from their phone for 11 minutes
    Then the map shows "01 A 123 BC" as "Signal yo'q" at the last place
