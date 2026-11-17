@day-01
Feature: Company data templates
  So that the fleet can be loaded on Day 5 without guesswork,
  the company receives one Excel template, fills it in,
  and gets back either "OK" or a list of exact cells to fix.

  Scenario: The company receives a template covering everything we need
    Given the blank data template
    Then it has a sheet for each of these lists
      | sheet             |
      | Vehicles          |
      | Drivers           |
      | Last service      |
      | Service intervals |
      | Documents         |
      | Store stock       |
      | Places            |
      | Who confirms what |
      | Settings          |
    And every column header is in Uzbek and Russian

  Scenario: A correctly filled template is accepted
    Given the blank data template
    When the company fills it with complete, correct data
    Then the check says OK
    And it counts 2 vehicles and 2 drivers

  Scenario: Mistakes are pointed out cell by cell
    Given the blank data template
    When the company fills it with complete, correct data
    But vehicle row 3 has the plate "01 AB 12"
    And driver row 4 has the phone "+7 900 123 45 67"
    Then the check fails
    And the problems include "Vehicles, row 3, Davlat raqami / Госномер"
    And the problems include "Drivers, row 4, Telegram telefon raqami / Телефон в Telegram"

  Scenario: A document for an unknown vehicle is refused
    Given the blank data template
    When the company fills it with complete, correct data
    But document row 3 belongs to vehicle "40 X 000 XX"
    Then the check fails
    And the problems include "vehicle 40 X 000 XX is not in the Vehicles sheet"
