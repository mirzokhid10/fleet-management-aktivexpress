@day-07
Feature: People register in the bot by phone, and staff sign in with Telegram
  A person shares their phone number in the bot. If it is in the company
  list, a manager confirms it is really them: dispatchers confirm drivers,
  the director confirms staff. Staff then sign in to the web through the
  bot, by tapping the number shown on their screen. No passwords.

  Scenario: A driver registers and the dispatcher confirms
    Given "Aliyev Vali" is in the driver list with phone "+998 90 123 45 67"
    When they open the bot, choose Uzbek and share their phone number
    Then the bot says "Rahmat! Rahbar tez orada ro'yxatdan o'tishingizni tasdiqlaydi."
    When a dispatcher confirms "Aliyev Vali" on the New users page
    Then the bot says "✅ Ro'yxatdan o'tishingiz tasdiqlandi. Xush kelibsiz, Aliyev!"
    And "Aliyev Vali" is linked to their Telegram account

  Scenario: A stranger cannot register
    When someone with phone "+998 99 000 00 00" opens the bot, chooses Uzbek and shares it
    Then the bot says "+998990000000 raqami kompaniya ro'yxatida yo'q."
    And nothing waits on the New users page

  Scenario: A dispatcher registers, the director confirms, and the dispatcher signs in
    Given dispatcher "Karimova Dilnoza" has phone "+998 93 765 43 21"
    When they open the bot, choose Uzbek and share their phone number
    And the director confirms "Karimova Dilnoza" on the New users page
    And they sign in on the website with Telegram
    Then they see the dashboard
