@day-10
Feature: The track of a shift is clean: distance and speed without bad points
  Each point gets the distance and speed from the last good point. Points
  Telegram is unsure about (accuracy worse than 100 m) and GPS jumps
  (faster than 150 km/h) are kept for checking but left out of the track.

  Scenario: A drive with a GPS jump and a vague point
    Given "Aliyev Vali" is on shift and sharing live location
    When their location moves like this
      | after s | metres north | accuracy m |
      | 30      | 400          | 10         |
      | 60      | 6000         | 10         |
      | 90      | 800          | 10         |
      | 120     | 820          | 400        |
      | 150     | 1200         | 10         |
    Then 2 of the 6 points are marked bad
    And the clean track is 1.2 km with top speed 48 km/h
    When they end the shift
    Then the bot says "Masofa: 1,2 km."
    And the dispatcher sees 1,2 km for the shift
