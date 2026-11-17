"""The blank template: structure the company sees when they open it."""

import re

import pytest
from openpyxl import load_workbook

from fleet_import.schema import ALL_SHEETS, VEHICLES
from fleet_import.workbook import FIRST_DATA_ROW, HEADER_ROW, HINT_ROW

pytestmark = pytest.mark.functional


def test_template_has_instructions_then_one_sheet_per_list(template_path):
    wb = load_workbook(template_path)
    assert wb.sheetnames == ["Instructions"] + [s.title for s in ALL_SHEETS]


def test_every_sheet_title_fits_excel_limit():
    assert all(len(s.title) <= 31 for s in ALL_SHEETS)


@pytest.mark.parametrize("sheet", ALL_SHEETS, ids=lambda s: s.key)
def test_headers_are_bilingual_and_mark_required(template_path, sheet):
    ws = load_workbook(template_path)[sheet.title]
    headers = [ws.cell(HEADER_ROW, c).value for c in range(1, len(sheet.fields) + 1)]
    for header, fld in zip(headers, sheet.fields):
        assert header.startswith(f"{fld.label_uz} / {fld.label_ru}")
        assert header.endswith(" *") == fld.required


@pytest.mark.parametrize("sheet", ALL_SHEETS, ids=lambda s: s.key)
def test_choice_columns_have_dropdowns(template_path, sheet):
    ws = load_workbook(template_path)[sheet.title]
    lists = {}
    for dv in ws.data_validations.dataValidation:
        letter = re.match(r"[A-Z]+", str(dv.sqref)).group()
        assert str(dv.sqref).startswith(f"{letter}{FIRST_DATA_ROW}:")
        lists[letter] = dv.formula1
    for col, fld in enumerate(sheet.fields, start=1):
        letter = ws.cell(1, col).column_letter
        if fld.choices:
            assert lists[letter] == '"' + ",".join(fld.choices) + '"'
        else:
            assert letter not in lists


def test_hint_row_shows_examples_and_panes_are_frozen(template_path):
    ws = load_workbook(template_path)[VEHICLES.title]
    assert "01 A 123 BC" in ws.cell(HINT_ROW, 1).value
    assert ws.freeze_panes == f"A{FIRST_DATA_ROW}"


def test_blank_template_reports_missing_single_row_settings(template_path):
    from fleet_import.validate import validate_workbook

    report = validate_workbook(template_path)
    assert [str(i) for i in report.issues] == ["Settings: fill exactly one row (found 0)"]
