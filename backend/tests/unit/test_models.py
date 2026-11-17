"""Model behaviour that needs no database."""

import datetime as dt
import re
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.core.choices import DocumentType, FuelType, ServiceItem
from apps.core.validators import validate_phone, validate_plate, validate_vin
from apps.documents.models import DRIVER_DOCUMENTS, VEHICLE_DOCUMENTS
from apps.entries.models import Entry, Photo
from apps.fleet.models import Shift, Vehicle
from fleet_import import schema

pytestmark = pytest.mark.unit


def test_choices_match_the_company_template():
    assert tuple(FuelType.values) == schema.FUEL_TYPES
    assert tuple(ServiceItem.values) == schema.SERVICE_ITEMS
    assert tuple(DocumentType.values) == schema.DOCUMENT_TYPES


def test_every_document_type_belongs_to_exactly_one_owner_kind():
    assert sorted(VEHICLE_DOCUMENTS + DRIVER_DOCUMENTS) == sorted(DocumentType.values)


@pytest.mark.parametrize("fuel, unit", [("Metan", "m3"), ("Dizel", "l"), ("Propan", "l")])
def test_fuel_unit(fuel, unit):
    assert FuelType.unit(fuel) == unit


def test_validators_accept_normalised_values():
    validate_plate("01A123BC")
    validate_phone("+998901234567")
    validate_vin("JALC4B16507000001")


@pytest.mark.parametrize("validator, raw, message", [
    (validate_plate, "01 A 123 BC", "Write it as 01A123BC"),
    (validate_plate, "ABC", "Uzbek plate"),
    (validate_phone, "90 123 45 67", "Write it as +998901234567"),
    (validate_vin, "short", "17 letters"),
])
def test_validators_reject_with_helpful_message(validator, raw, message):
    with pytest.raises(ValidationError, match=re.escape(message)):
        validator(raw)


def test_vehicle_display():
    v = Vehicle(plate="01123ABC", brand="Chevrolet", model="Damas", fuel_type="AI-80",
                second_fuel_type="Metan", fuel_norm=Decimal(9))
    assert str(v) == "01 123 ABC · Chevrolet Damas"
    assert v.fuel_types == ["AI-80", "Metan"]


def test_shift_is_open_until_ended():
    s = Shift(started_at=dt.datetime(2026, 11, 17, 8, tzinfo=dt.UTC))
    assert s.is_open
    s.ended_at = s.started_at + dt.timedelta(hours=9)
    assert not s.is_open


def test_every_entry_kind_has_an_approver_and_photo_rule():
    kinds = set(Entry.Kind.values)
    assert set(Entry.APPROVER_FLAG) == kinds
    assert set(Entry.REQUIRED_PHOTOS) == kinds
    for photo_kinds in Entry.REQUIRED_PHOTOS.values():
        assert set(photo_kinds) <= set(Photo.Kind.values)


def test_required_photos_follow_the_signed_off_rules():
    assert Entry.REQUIRED_PHOTOS[Entry.Kind.REFUEL] == ["odometer", "receipt"]
    assert Entry.REQUIRED_PHOTOS[Entry.Kind.DAILY] == ["odometer"]


def test_approver_flags_exist_on_user():
    from apps.accounts.models import User

    for flag in set(Entry.APPROVER_FLAG.values()):
        assert User._meta.get_field(flag).default is False
