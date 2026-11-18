@day-04 @day-07
Feature: Users log in by role
  Staff sign in to the web app by confirming in the company Telegram bot
  (Day 7) and see only what their role may use. Drivers work in the bot only.
  The interface is in Uzbek or Russian, as each user prefers.

  Scenario Outline: Staff see the pages of their role
    Given a <role> account
    When they sign in with Telegram
    Then they land on the dashboard
    And the menu shows "<shown>"
    And the menu does not show "<hidden>"

    Examples:
      | role        | shown                         | hidden                   |
      | director    | Sozlamalar, Jonli xarita      | -                        |
      | dispatcher  | Jonli xarita, Tasdiqlash      | Sozlamalar               |
      | storekeeper | Ombor, Texnik xizmat          | Jonli xarita, Sozlamalar |

  Scenario: A driver is sent to the Telegram bot
    Given a driver account
    When they sign in with Telegram
    Then they stay on the sign-in page
    And the bot tells them "Haydovchilar faqat shu botda ishlaydi."

  Scenario: A Russian-speaking storekeeper gets a Russian interface
    Given a storekeeper account that prefers Russian
    When they sign in with Telegram
    Then the menu shows "Склад, Техобслуживание"

  Scenario: Switching language is remembered for next time
    Given a dispatcher account
    When they sign in with Telegram
    And they switch the language to Russian
    And they log out and sign in again
    Then the menu shows "Карта онлайн, Подтверждения"

  Scenario: Pages need a login
    When someone opens the dashboard without signing in
    Then they are sent to the sign-in page
