import pytest
from openpyxl import load_workbook
from pytest_bdd import given, parsers, scenarios, then, when

from fleet_import.schema import ALL_SHEETS
from fleet_import.validate import validate_workbook
from fleet_import.workbook import HEADER_ROW
from tests.conftest import fill_template

pytestmark = pytest.mark.acceptance

scenarios("data_templates.feature")


@pytest.fixture
def ctx():
    return {}


@given("the blank data template", target_fixture="ctx")
def blank_template(template_path):
    return {"path": template_path, "data": None}


@when("the company fills it with complete, correct data")
def fill_correct(ctx, valid_data):
    ctx["data"] = valid_data


@when(parsers.parse('vehicle row {row:d} has the plate "{plate}"'))
def bad_plate(ctx, row, plate):
    ctx["data"]["vehicles"][row - 3]["plate"] = plate


@when(parsers.parse('driver row {row:d} has the phone "{phone}"'))
def bad_phone(ctx, row, phone):
    ctx["data"]["drivers"][row - 3]["phone"] = phone


@when(parsers.parse('document row {row:d} belongs to vehicle "{plate}"'))
def unknown_vehicle_document(ctx, row, plate):
    ctx["data"]["documents"][row - 3].update(owner_type="Vehicle", owner=plate)


def _report(ctx):
    if "report" not in ctx:
        if ctx["data"] is not None:
            fill_template(ctx["path"], ctx["data"])
        ctx["report"] = validate_workbook(ctx["path"])
    return ctx["report"]


@then("it has a sheet for each of these lists")
def has_sheets(ctx, datatable):
    expected = [row[0] for row in datatable[1:]]
    assert load_workbook(ctx["path"]).sheetnames[1:] == expected


@then("every column header is in Uzbek and Russian")
def bilingual_headers(ctx):
    wb = load_workbook(ctx["path"])
    for sheet in ALL_SHEETS:
        ws = wb[sheet.title]
        for col in range(1, len(sheet.fields) + 1):
            assert " / " in ws.cell(HEADER_ROW, col).value


@then("the check says OK")
def check_ok(ctx):
    report = _report(ctx)
    assert report.ok, report.summary()


@then(parsers.parse("it counts {vehicles:d} vehicles and {drivers:d} drivers"))
def counts(ctx, vehicles, drivers):
    report = _report(ctx)
    assert len(report.rows["vehicles"]) == vehicles
    assert len(report.rows["drivers"]) == drivers


@then("the check fails")
def check_fails(ctx):
    assert not _report(ctx).ok


@then(parsers.parse('the problems include "{text}"'))
def problem_listed(ctx, text):
    summary = _report(ctx).summary()
    assert text in summary, summary
