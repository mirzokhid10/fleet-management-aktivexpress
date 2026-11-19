@day-14
Feature: Trips: the day of a vehicle as drives from A to B
  A stop of 5 minutes or more ends one trip and starts the next. The trips
  page shows each trip from place to place, with time and kilometres.

  Background:
    Given the company places
      | name          | metres north |
      | Asosiy ombor  | 0            |
      | Mijoz Chorsu  | 2000         |

  Scenario: Warehouse to a client and back
    Given "Aliyev Vali" is on shift at "Asosiy ombor" sharing live location
    When they drive 2000 metres north in 4 minutes
    And they stand still for 6 minutes
    And they drive 2000 metres south in 4 minutes
    And they end the shift
    Then the dispatcher sees these trips
      | route                         | distance |
      | Mijoz Chorsu → Asosiy ombor   | 2,0 km   |
      | Asosiy ombor → Mijoz Chorsu   | 2,0 km   |
    And the trips total 4,0 km

  Scenario: A driver still driving is on the way
    Given "Aliyev Vali" is on shift at "Asosiy ombor" sharing live location
    When they drive 1000 metres north in 2 minutes
    Then the dispatcher sees 1 trip on the way

  Scenario: A parked phone that went quiet has arrived
    Given "Aliyev Vali" is on shift at "Asosiy ombor" sharing live location
    When they drive 2000 metres north in 4 minutes
    And nothing comes from the phone for 10 minutes
    Then the dispatcher sees 0 trips on the way
    And the dispatcher sees these trips
      | route                         | distance |
      | Asosiy ombor → Mijoz Chorsu   | 2,0 km   |
