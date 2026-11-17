"""Vehicle and driver lists, the Excel import pages and the admin panel (Day 5)."""

import datetime as dt
import html
import io

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from openpyxl import load_workbook

from apps.audit.models import AuditLog
from apps.fleet.models import Driver, Vehicle
from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def text(response) -> str:
    return html.unescape(response.content.decode())


def upload(client, path):
    with open(path, "rb") as fh:
        return client.post("/vehicles/import/", {"file": fh})


# --- lists -----------------------------------------------------------------

@pytest.mark.parametrize("url", ["/vehicles/", "/drivers/", "/vehicles/import/"])
def test_storekeeper_cannot_open_fleet_pages(login_as, url):
    assert login_as("storekeeper").get(url).status_code == 403


def test_vehicle_list_shows_plates_as_people_write_them(login_as):
    f.vehicle(plate="01A123BC", brand="Isuzu", model="NPR 82")
    page = text(login_as("dispatcher").get("/vehicles/"))
    assert "01 A 123 BC" in page and "Isuzu NPR 82" in page
    assert 'data-menu="vehicles"' in page


def test_vehicle_search_ignores_spaces_in_the_plate(login_as):
    f.vehicle(plate="01A123BC")
    f.vehicle(plate="10B555CC")
    page = text(login_as("director").get("/vehicles/?q=01 a 123"))
    assert 'data-plate="01A123BC"' in page and 'data-plate="10B555CC"' not in page
    assert "1 / 2" not in page  # the count line, not pagination
    assert "2 tadan 1" in page


def test_empty_lists_point_to_the_import(login_as):
    client = login_as("director")
    assert "import qiling" in text(client.get("/vehicles/"))
    assert "import qiling" in text(client.get("/drivers/"))


def test_driver_list_warns_about_licences(login_as):
    today = timezone.localdate()
    f.driver(full_name="Old", licence_expiry=today - dt.timedelta(days=1))
    f.driver(full_name="Soon", licence_expiry=today + dt.timedelta(days=10))
    f.driver(full_name="Fine", licence_expiry=today + dt.timedelta(days=400))
    page = text(login_as("dispatcher", language="ru").get("/drivers/"))
    assert page.count('data-licence="expired"') == 1
    assert page.count('data-licence="soon"') == 1
    assert "Просрочены" in page and "В течение 30 дней" in page


# --- import ----------------------------------------------------------------

def test_upload_shows_a_preview_and_saves_nothing(login_as, filled, valid_data):
    client = login_as("dispatcher")
    page = text(upload(client, filled(valid_data)))
    assert 'data-testid="preview"' in page and 'data-testid="confirm"' in page
    assert page.count('data-action="create"') == 4
    assert Vehicle.objects.count() == 0


def test_confirm_imports_and_lands_on_the_vehicle_list(login_as, filled, valid_data, media):
    client = login_as("dispatcher")
    page = upload(client, filled(valid_data))
    token = page.context["token"]

    response = client.post("/vehicles/import/confirm/", {"token": token}, follow=True)
    assert response.redirect_chain[-1][0] == "/vehicles/"
    assert "avtomobillar — 2 yangi" in text(response)
    assert Vehicle.objects.count() == 2 and Driver.objects.count() == 2
    assert AuditLog.objects.filter(source="import", actor=client.user).count() == 4
    assert list((media / "imports").iterdir()) == []  # the upload is not kept


def test_a_preview_can_be_imported_only_once(login_as, filled, valid_data):
    client = login_as("dispatcher")
    token = upload(client, filled(valid_data)).context["token"]
    client.post("/vehicles/import/confirm/", {"token": token})
    response = client.post("/vehicles/import/confirm/", {"token": token}, follow=True)
    assert "muddati tugadi" in text(response)


def test_another_users_preview_cannot_be_confirmed(login_as, filled, valid_data, client):
    token = upload(login_as("dispatcher"), filled(valid_data)).context["token"]
    client.logout()
    login_as("director")  # a different user in a fresh session
    client.post("/vehicles/import/confirm/", {"token": token})
    assert Vehicle.objects.count() == 0


def test_problems_are_listed_by_row_and_there_is_no_confirm(login_as, filled, valid_data):
    valid_data["vehicles"][1]["vin"] = "SHORT"
    page = text(upload(login_as("dispatcher"), filled(valid_data)))
    assert "Topilgan xatolar: 1" in page
    assert 'data-testid="issues"' in page and "VIN / VIN" in page
    assert 'data-testid="confirm"' not in page


def test_a_non_excel_file_is_refused(login_as, tmp_path):
    fake = tmp_path / "list.xlsx"
    fake.write_text("plate,brand\n")
    page = text(upload(login_as("dispatcher"), fake))
    assert "Bu yaroqli Excel fayli emas." in page


def test_only_xlsx_files_are_accepted(login_as, tmp_path):
    csv = tmp_path / "list.csv"
    csv.write_text("plate,brand\n")
    response = upload(login_as("dispatcher"), csv)
    assert response.context["form"].errors["file"]


def test_blank_template_downloads_as_excel(login_as):
    response = login_as("dispatcher").get("/vehicles/import/template.xlsx")
    assert response.status_code == 200
    assert 'filename="fleet-data-template.xlsx"' in response["Content-Disposition"]
    wb = load_workbook(io.BytesIO(b"".join(response.streaming_content)))
    assert {"Vehicles", "Drivers"} <= set(wb.sheetnames)


# --- command line ----------------------------------------------------------

def test_command_dry_run_then_import(filled, valid_data):
    path = filled(valid_data)
    out = io.StringIO()
    call_command("import_fleet", str(path), "--dry-run", stdout=out)
    assert "vehicles: 2 new" in out.getvalue() and Vehicle.objects.count() == 0
    call_command("import_fleet", str(path), stdout=out)
    assert Vehicle.objects.count() == 2


def test_command_refuses_a_bad_file(filled, valid_data):
    valid_data["drivers"][0]["default_plate"] = "99 Z 999 ZZ"
    with pytest.raises(CommandError):
        call_command("import_fleet", str(filled(valid_data)), stdout=io.StringIO())


# --- admin panel -----------------------------------------------------------

def test_admin_link_is_shown_only_to_admins(login_as, client):
    assert 'data-testid="admin-link"' not in text(login_as("dispatcher").get("/"))
    client.logout()
    assert 'data-testid="admin-link"' in text(
        login_as("director", is_staff=True, is_superuser=True).get("/"))


@pytest.mark.parametrize("url", ["/admin/fleet/vehicle/", "/admin/fleet/driver/",
                                 "/admin/accounts/user/", "/admin/audit/auditlog/",
                                 "/admin/tracking/geofence/", "/admin/entries/entry/",
                                 "/admin/store/storeitem/", "/admin/documents/document/",
                                 "/admin/maintenance/servicerecord/",
                                 "/admin/core/companysettings/"])
def test_admin_pages_open(login_as, url):
    client = login_as("director", is_staff=True, is_superuser=True)
    assert client.get(url).status_code == 200


def test_admin_edit_is_written_to_the_audit_log(login_as):
    client = login_as("director", is_staff=True, is_superuser=True)
    v = f.vehicle(odometer_km=100)
    form = {"plate": v.plate, "brand": v.brand, "model": v.model, "year": v.year, "vin": v.vin,
            "fuel_type": v.fuel_type, "fuel_norm": "14.5", "second_fuel_type": "",
            "second_fuel_norm": "", "odometer_km": 200, "is_active": "on", "notes": ""}
    response = client.post(f"/admin/fleet/vehicle/{v.pk}/change/", form)
    assert response.status_code == 302, response.context["adminform"].form.errors
    log = AuditLog.objects.get(action="update", source="web")
    assert log.actor == client.user and log.changes == {"odometer_km": [100, 200]}


def test_audit_log_cannot_be_edited_in_the_admin(login_as):
    client = login_as("director", is_staff=True, is_superuser=True)
    assert client.get("/admin/audit/auditlog/add/").status_code == 403
