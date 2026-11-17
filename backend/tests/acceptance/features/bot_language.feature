@day-06
Feature: The bot answers in Uzbek or Russian
  Drivers open the company bot, pick their language once, and from then on
  the bot speaks to them in it. They can change it any time with /language.

  Scenario: A new driver picks Russian
    Given a driver who has never used the bot
    When they send "/start"
    Then the bot asks "Tilni tanlang · Выберите язык"
    And offers the buttons "🇺🇿 O'zbekcha, 🇷🇺 Русский"
    When they tap "🇷🇺 Русский"
    Then the bot says "Здравствуйте, Vali! Это бот Aktiv Fleet."
    When they send "/start"
    Then the bot says "Здравствуйте, Vali! Это бот Aktiv Fleet."

  Scenario Outline: Help comes in the chosen language
    Given a driver who chose <language>
    When they send "/help"
    Then the bot says "<first line>"

    Examples:
      | language | first line              |
      | Uzbek    | Bot nimalar qila oladi: |
      | Russian  | Что умеет бот:          |

  Scenario: Changing the language later
    Given a driver who chose Russian
    When they send "/language"
    And they tap "🇺🇿 O'zbekcha"
    Then the bot says "✅ Til: O'zbekcha"
