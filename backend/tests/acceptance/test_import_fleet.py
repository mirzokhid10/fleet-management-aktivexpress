import html

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from apps.fleet.importer import apply_import
from apps.fleet.models import Driver, Vehicle
from tests import factories as f

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("import_fleet.feature")


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def ctx(client, valid_data, filled):
    return {"client": client, "data": valid_data, "fill": filled}


def _page(response) -> str:
    return html.unescape(response.content.decode())


@given("a dispatcher is signed in")
def signed_in(ctx):
    ctx["client"].force_login(f.user(role="dispatcher"))


@given("the company filled the template with 2 vehicles and 2 drivers")
def filled_ok(ctx):
    assert len(ctx["data"]["vehicles"]) == len(ctx["data"]["drivers"]) == 2


@given("the company filled the template with a wrong phone on row 4 of Drivers")
def filled_wrong_phone(ctx):
    ctx["data"]["drivers"][1]["phone"] = "90 12"  # row 4 = second data row


@given("the fleet was imported before")
def imported_before(ctx):
    apply_import(ctx["fill"](ctx["data"]))


@given(parsers.parse('the company changed the odometer of "{plate}" to {km:d}'))
def change_odometer(ctx, plate, km):
    row = next(v for v in ctx["data"]["vehicles"] if v["plate"] == plate)
    row["odometer_km"] = km


@when("they upload the file")
def upload(ctx):
    path = ctx["fill"](ctx["data"])
    with open(path, "rb") as fh:
        ctx["response"] = ctx["client"].post("/vehicles/import/", {"file": fh})


@when("they confirm the import")
def confirm(ctx):
    token = ctx["response"].context["token"]
    ctx["response"] = ctx["client"].post("/vehicles/import/confirm/", {"token": token},
                                         follow=True)


def _count(ctx, label):
    return dict((str(k), v) for k, v in ctx["response"].context["counts"])[label]


@then(parsers.parse("they see {nv:d} new vehicles and {nd:d} new drivers"))
def see_new(ctx, nv, nd):
    assert _count(ctx, "Yangi avtomobillar") == nv
    assert _count(ctx, "Yangi haydovchilar") == nd


@then(parsers.parse("they see {n:d} changed vehicle"))
def see_changed(ctx, n):
    assert _count(ctx, "O'zgargan avtomobillar") == n


@then("nothing is saved yet")
def nothing_saved(ctx):
    assert Vehicle.objects.count() == 0 and Driver.objects.count() == 0


@then(parsers.parse('the vehicle list shows "{items}"'))
def vehicle_list(ctx, items):
    page = _page(ctx["client"].get("/vehicles/"))
    for item in items.split(", "):
        assert item in page


@then(parsers.parse('the driver list shows "{items}"'))
def driver_list(ctx, items):
    page = _page(ctx["client"].get("/drivers/"))
    for item in items.split(", "):
        assert item in page


@then(parsers.parse('driver "{name}" drives "{plate}" by default'))
def drives(ctx, name, plate):
    assert Driver.objects.get(full_name=name).default_vehicle.plate_display == plate


@then(parsers.parse('they see a problem on sheet "{sheet}", row {row:d}'))
def problem(ctx, sheet, row):
    issues = ctx["response"].context["plan"].issues
    assert [(i.sheet, i.row) for i in issues] == [(sheet, row)]


@then("they cannot confirm the import")
def cannot_confirm(ctx):
    assert 'data-testid="confirm"' not in _page(ctx["response"])
    assert Vehicle.objects.count() == 0


@then(parsers.parse('"{plate}" shows {km:d} km'))
def shows_km(ctx, plate, km):
    assert Vehicle.objects.get(plate=plate.replace(" ", "")).odometer_km == km
