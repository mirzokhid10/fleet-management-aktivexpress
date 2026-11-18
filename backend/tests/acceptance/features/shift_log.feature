@day-08
Feature: Drivers start and end shifts in the bot, and the shift log fills
  A registered driver sends /start_shift and taps the vehicle they take;
  their own vehicle is offered first. /end_shift ends it after a yes.
  Managers see every shift on the Shifts page. A vehicle can have only one
  driver at a time: if someone forgot /end_shift, the dispatcher ends it.

  Background:
    Given vehicle "01 A 123 BC" is the main vehicle of driver "Aliyev Vali"
    And vehicle "01 777 AAA" is also in the fleet

  Scenario: A day's shift from start to end
    When "Aliyev Vali" sends /start_shift
    Then the bot offers "⭐ 01 A 123 BC · Isuzu NPR 82" first
    When they tap "01 A 123 BC"
    Then the bot says the shift started on "01 A 123 BC"
    And the dispatcher sees "Aliyev Vali" on shift with "01 A 123 BC"
    When "Aliyev Vali" sends /end_shift and confirms
    Then the bot says the shift ended on "01 A 123 BC"
    And the shift log shows the shift of "Aliyev Vali" as ended

  Scenario: A vehicle someone forgot to hand back
    Given driver "Karimov Ali" is on shift with "01 A 123 BC"
    When "Aliyev Vali" sends /start_shift
    Then the bot does not offer "01 A 123 BC"
    When the dispatcher ends the shift of "Karimov Ali"
    Then "Karimov Ali" gets a message in the bot that the dispatcher ended it
    And "Aliyev Vali" can take "01 A 123 BC"
