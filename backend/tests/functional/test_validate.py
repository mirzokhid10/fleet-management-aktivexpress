"""Validating a filled template end to end."""

import datetime as dt

import pytest
from openpyxl import load_workbook

from fleet_import.__main__ import main
from fleet_import.validate import validate_workbook

pytestmark = pytest.mark.functional


def messages(report):
    return [str(i) for i in report.issues]


def test_complete_valid_data_passes_and_is_cleaned(filled, valid_data):
    report = validate_workbook(filled(valid_data))

    assert report.ok, report.summary()
    vehicle = report.rows["vehicles"][0]
    assert vehicle["plate"] == "01A123BC"
    assert vehicle["fuel_norm"] == 14.5
    assert report.rows["drivers"][1]["phone"] == "+998937654321"
    assert report.rows["drivers"][0]["licence_expiry"] == dt.date(2028, 12, 31)
    assert report.rows["approvers"][0]["fuel"] is True
    assert report.rows["settings"][0]["retention_months"] == 3
    assert report.rows["settings"][0]["work_start"] == dt.time(8, 0)


def test_blank_rows_between_data_are_ignored(filled, valid_data):
    valid_data["vehicles"].insert(1, {})
    report = validate_workbook(filled(valid_data))
    assert report.ok, report.summary()
    assert len(report.rows["vehicles"]) == 2


def test_each_bad_cell_is_reported_with_sheet_row_and_column(filled, valid_data):
    valid_data["vehicles"][0]["plate"] = "ABC"
    valid_data["vehicles"][1]["fuel_type"] = "Benzin"
    del valid_data["drivers"][0]["phone"]

    report = validate_workbook(filled(valid_data))

    assert not report.ok
    msgs = messages(report)
    assert any(m.startswith("Vehicles, row 3, Davlat raqami / Госномер: must be an Uzbek plate")
               for m in msgs)
    assert any(m.startswith("Vehicles, row 4, Yoqilg'i turi / Тип топлива: must be one of")
               for m in msgs)
    assert "Drivers, row 3, Telegram telefon raqami / Телефон в Telegram: is required (got None)" \
        in msgs


def test_duplicates_are_found_even_when_written_differently(filled, valid_data):
    valid_data["vehicles"][1]["plate"] = "01a123bc"
    report = validate_workbook(filled(valid_data))
    assert "Vehicles, row 4, Davlat raqami / Госномер: duplicate of row 3" in messages(report)


def test_cross_sheet_references_must_exist(filled, valid_data):
    valid_data["last_service"][0]["plate"] = "10 B 999 CC"
    valid_data["documents"][1]["owner"] = "+998 99 999 99 99"
    valid_data["service_intervals"][0]["model"] = "Gazel"
    valid_data["drivers"][0]["default_plate"] = "10 B 999 CC"

    msgs = messages(validate_workbook(filled(valid_data)))

    assert any("Last service, row 3" in m and "not in the Vehicles sheet" in m for m in msgs)
    assert any("Documents, row 4" in m and "not in the Drivers sheet" in m for m in msgs)
    assert any("Service intervals, row 3" in m and "not used by any vehicle" in m for m in msgs)
    assert any("Drivers, row 3" in m and "not in the Vehicles sheet" in m for m in msgs)


def test_last_service_cannot_be_ahead_of_current_odometer(filled, valid_data):
    valid_data["last_service"][0]["odometer_km"] = 160000
    msgs = messages(validate_workbook(filled(valid_data)))
    assert any("higher than the vehicle's current odometer" in m for m in msgs)


def test_settings_rules(filled, valid_data):
    valid_data["settings"][0].update(work_start="19:00", work_end="08:00", retention_months=2)
    msgs = messages(validate_workbook(filled(valid_data)))
    assert any("later than the start of work" in m for m in msgs)
    assert any("Marshrut tarixi" in m and "one of: 1, 3" in m for m in msgs)


def test_geofence_needs_both_coordinates(filled, valid_data):
    del valid_data["geofences"][0]["longitude"]
    msgs = messages(validate_workbook(filled(valid_data)))
    assert "Places, row 3: give both latitude and longitude, or neither" in msgs


def test_missing_sheet_is_reported(filled, valid_data):
    path = filled(valid_data)
    wb = load_workbook(path)
    del wb["Store stock"]
    wb.save(path)
    assert "Store stock: sheet is missing" in messages(validate_workbook(path))


def test_cli_writes_template_and_checks_it(tmp_path, capsys, valid_data):
    from tests.conftest import fill_template

    path = tmp_path / "t.xlsx"
    assert main(["template", str(path)]) == 0
    assert main(["check", str(path)]) == 1
    assert "fill exactly one row" in capsys.readouterr().out

    fill_template(path, valid_data)
    assert main(["check", str(path)]) == 0
    assert capsys.readouterr().out.startswith("OK — vehicles: 2, drivers: 2")
