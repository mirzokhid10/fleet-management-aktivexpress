@day-09
Feature: Drivers on shift share live location, and the points are stored per shift
  After /start_shift the bot asks for Telegram live location. Every update
  is stored as a point of that shift. The bot speaks up only when something
  changes: sharing started, sharing stopped, or a location it cannot use.

  Background:
    Given driver "Aliyev Vali" is registered in the bot

  Scenario: A shift with live location
    When "Aliyev Vali" starts a shift with "01 A 123 BC"
    Then the bot asks them to share their live location
    When they share their live location and it moves 5 times
    Then the shift has 6 points
    And the dispatcher sees the shift sharing location with 6 points
    When they end the shift
    Then the bot says they can stop sharing their location
    And further updates are not stored

  Scenario: The driver turns location off during the shift
    Given "Aliyev Vali" is on shift with "01 A 123 BC" and sharing live location
    When they stop sharing
    Then the bot asks them to share it again
    And the dispatcher sees the shift is not sharing location

  Scenario: Location before the shift is not stored
    When "Aliyev Vali" shares their live location without a shift
    Then the bot tells them to start a shift first
    And no points are stored
