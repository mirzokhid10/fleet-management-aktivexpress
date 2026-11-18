Feature: The superuser sees the fleet at a glance in the admin
  The Django admin (Unfold theme) opens on a summary: how many vehicles
  and drivers are active, who is on shift, open location alerts, and the
  latest changes. Until the managers' alert group is chosen it warns.

  Scenario: First look, then the alert group is chosen
    Given 3 active vehicles and 1 retired vehicle
    And "Aliyev Vali" is on shift
    And the bot was added to the Telegram group "Dispetcherlar"
    When the director opens the admin
    Then they see 4 active vehicles and 1 on shift now
    And they are warned that the alert group is not set
    When they choose "Dispetcherlar" as the alert group in Company settings
    Then the warning is gone
    And the change to Company settings is listed under recent changes
