@day-11
Feature: Managers learn within 10 minutes when a driver stops sharing location
  The bot checks every 30 seconds. When a driver on shift has had no
  location for the time set in Company settings (10 minutes), the managers'
  Telegram group gets an alert with the last known place, and the driver
  gets a reminder. When location comes back, the group hears that too.

  Background:
    Given the bot was added to the group "Aktiv dispetcherlar"
    And the director chose that group for alerts
    And "Aliyev Vali" is on shift with "01 A 123 BC" and sharing live location

  Scenario: Location stops and comes back
    When they stop sharing at 10:00
    Then at 10:09 nobody has been alerted
    And by 10:10:30 the group got "⚠️ Aliyev Vali · 01 A 123 BC: joylashuv 10 daqiqadan beri o'chiq (10:00 dan)."
    And the driver got "⚠️ Joylashuvingiz 10 daqiqadan beri o'chiq. Dispetcherga xabar berildi."
    And at 10:15 nobody is alerted again
    When they share again at 10:20
    Then by 10:20:30 the group got "✅ Aliyev Vali · 01 A 123 BC: joylashuv yana yoqildi (20 daqiqa o'chiq edi)."

  Scenario: The driver ends the shift instead
    When they stop sharing at 10:00
    And they end the shift at 10:05
    Then at 10:30 nobody has been alerted
