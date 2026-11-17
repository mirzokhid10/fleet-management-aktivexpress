@day-03
Feature: Database design covers the signed-off scope
  The schema stores everything the company sends us on Day 1
  and enforces the approval rules, before any screen is built.

  Scenario: Every column of the company data template has a place in the database
    Given the company data template
    Then every column maps to a real model field

  Scenario: A driver cannot be on two vehicles at once
    Given driver "Aliyev Vali" is on shift with vehicle "01 A 123 BC"
    When the driver tries to start a shift with vehicle "01 777 AAA"
    Then the database refuses it

  Scenario: A refuel waits for a dispatcher and keeps its photos
    Given driver "Aliyev Vali" is on shift with vehicle "01 A 123 BC"
    When the driver sends a refuel of 60 litres of Dizel with an odometer photo and a receipt photo
    Then the refuel is waiting in the approvals inbox
    And the refuel has 2 photos attached
    And it cannot be marked confirmed without saying who confirmed it

  Scenario: History cannot be rewritten
    Given an audit log entry exists
    When someone tries to change it
    Then the database refuses it
