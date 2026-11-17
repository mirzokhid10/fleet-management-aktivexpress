@day-05
Feature: The real fleet list is imported from Excel
  The company fills the data template sent on Day 1. A manager uploads it,
  sees exactly what will change, and only then imports it. Problems are
  listed by sheet, row and column, and a file with problems imports nothing.

  Scenario: A dispatcher imports the filled template
    Given a dispatcher is signed in
    And the company filled the template with 2 vehicles and 2 drivers
    When they upload the file
    Then they see 2 new vehicles and 2 new drivers
    And nothing is saved yet
    When they confirm the import
    Then the vehicle list shows "01 A 123 BC, 01 777 AAA"
    And the driver list shows "Aliyev Vali, Karimov Ali"
    And driver "Aliyev Vali" drives "01 A 123 BC" by default

  Scenario: A file with mistakes imports nothing
    Given a dispatcher is signed in
    And the company filled the template with a wrong phone on row 4 of Drivers
    When they upload the file
    Then they see a problem on sheet "Drivers", row 4
    And they cannot confirm the import

  Scenario: The corrected file is imported again later
    Given a dispatcher is signed in
    And the fleet was imported before
    And the company changed the odometer of "01 A 123 BC" to 160000
    When they upload the file
    Then they see 1 changed vehicle
    When they confirm the import
    Then "01 A 123 BC" shows 160000 km
