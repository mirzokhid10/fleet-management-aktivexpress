from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, transaction
from django.utils import timezone
from pytest_bdd import given, parsers, scenarios, then, when

from apps.audit.models import AuditLog
from apps.entries.models import Entry, Photo, Refuel
from fleet_import.fields import parse_plate
from fleet_import.mapping import TEMPLATE_TO_MODEL
from fleet_import.schema import ALL_SHEETS
from tests import factories as f

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("schema.feature")


@pytest.fixture
def ctx():
    return {}


def _attempt(ctx, fn):
    try:
        with transaction.atomic():
            fn()
        ctx["refused"] = False
    except DatabaseError:
        ctx["refused"] = True


# --- template coverage -----------------------------------------------------

@given("the company data template")
def template():
    pass


@then("every column maps to a real model field")
def every_column_mapped():
    missing = []
    for sheet in ALL_SHEETS:
        mapped = TEMPLATE_TO_MODEL.get(sheet.key, {})
        for fld in sheet.fields:
            target = mapped.get(fld.key)
            if not target:
                missing.append(f"{sheet.title}.{fld.key}: not mapped")
                continue
            app_label, model_name, field_name = target.split(".")
            model = apps.get_model(app_label, model_name)
            try:
                model._meta.get_field(field_name)
            except Exception:
                missing.append(f"{sheet.title}.{fld.key}: {target} does not exist")
    assert not missing, "\n".join(missing)


# --- shifts ----------------------------------------------------------------

@given(parsers.parse('driver "{name}" is on shift with vehicle "{plate}"'))
def on_shift(ctx, name, plate):
    ctx["shift"] = f.shift(driver=f.driver(full_name=name),
                           vehicle=f.vehicle(plate=parse_plate(plate)))


@when(parsers.parse('the driver tries to start a shift with vehicle "{plate}"'))
def second_shift(ctx, plate):
    other = f.vehicle(plate=parse_plate(plate))
    _attempt(ctx, lambda: f.shift(driver=ctx["shift"].driver, vehicle=other))


@then("the database refuses it")
def refused(ctx):
    assert ctx["refused"] is True


# --- refuel ----------------------------------------------------------------

@when(parsers.parse("the driver sends a refuel of {litres:d} litres of {fuel} "
                    "with an odometer photo and a receipt photo"))
def send_refuel(ctx, litres, fuel):
    s = ctx["shift"]
    driver_user = f.user(role="driver")
    e = f.entry(kind=Entry.Kind.REFUEL, driver=s.driver, vehicle=s.vehicle, shift=s,
                odometer_km=s.vehicle.odometer_km + 420)
    Refuel.objects.create(entry=e, fuel_type=fuel, quantity=Decimal(litres),
                          price_per_unit_uzs=Decimal(12500), total_uzs=Decimal(12500 * litres))
    for kind in Entry.REQUIRED_PHOTOS[Entry.Kind.REFUEL]:
        Photo.objects.create(entry=e, kind=kind, taken_at=timezone.now(),
                             telegram_file_id=f"file-{kind}", uploaded_by=driver_user)
    ctx["entry"] = e


@then("the refuel is waiting in the approvals inbox")
def in_inbox(ctx):
    inbox = Entry.objects.filter(status=Entry.Status.PENDING).order_by("submitted_at")
    assert list(inbox) == [ctx["entry"]]


@then(parsers.parse("the refuel has {count:d} photos attached"))
def photos_attached(ctx, count):
    assert sorted(ctx["entry"].photos.values_list("kind", flat=True)) == ["odometer", "receipt"]
    assert ctx["entry"].photos.count() == count


@then("it cannot be marked confirmed without saying who confirmed it")
def confirm_needs_decider(ctx):
    _attempt(ctx, lambda: Entry.objects.filter(pk=ctx["entry"].pk).update(
        status=Entry.Status.CONFIRMED, decided_at=timezone.now()))
    assert ctx["refused"] is True


# --- audit -----------------------------------------------------------------

@given("an audit log entry exists")
def audit_entry(ctx):
    v = f.vehicle()
    ctx["log"] = AuditLog.objects.create(source="web", action="update", object_id=str(v.pk),
                                         object_repr=str(v), changes={"odometer_km": [1, 2]},
                                         content_type=ContentType.objects.get_for_model(v))


@when("someone tries to change it")
def change_audit(ctx):
    _attempt(ctx, lambda: AuditLog.objects.filter(pk=ctx["log"].pk)
             .update(changes={"odometer_km": [1, 999]}))
