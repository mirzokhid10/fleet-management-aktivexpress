@day-15
Feature: Route history: see where a vehicle went and play it back
  A manager picks a vehicle and a day (or opens a trip from the Trips page)
  and sees the roads driven, each trip and the stops between them, and can
  play the day back.

  Background:
    Given the company places
      | name          | metres north |
      | Asosiy ombor  | 0            |
      | Mijoz Chorsu  | 2000         |

  Scenario: Open a trip from the Trips page
    Given "Aliyev Vali" is on shift at "Asosiy ombor" sharing live location
    When they drive 2000 metres north in 4 minutes
    And they stand still for 6 minutes
    And they drive 2000 metres south in 4 minutes
    And they end the shift
    And the dispatcher opens the first trip on the map
    Then route history shows the day of that vehicle
    And the timeline is
      | kind | text                         |
      | trip | Asosiy ombor → Mijoz Chorsu  |
      | stop | 6 daqiqa · Mijoz Chorsu      |
      | trip | Mijoz Chorsu → Asosiy ombor  |
    And playback runs from the first point to the last
