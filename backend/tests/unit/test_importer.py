"""Excel import of vehicles and drivers (Day 5): plan, apply, re-import."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.fleet.importer import CREATE, SAME, UPDATE, ImportBlocked, apply_import, plan_import
from apps.fleet.models import Driver, Vehicle
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_plan_writes_nothing(filled, valid_data):
    plan = plan_import(filled(valid_data))
    assert plan.ok, plan.summary()
    assert [r.action for r in plan.vehicles + plan.drivers] == [CREATE] * 4
    assert Vehicle.objects.count() == Driver.objects.count() == 0


def test_apply_stores_clean_values_and_links_the_main_vehicle(filled, valid_data):
    apply_import(filled(valid_data))

    isuzu = Vehicle.objects.get(plate="01A123BC")
    assert (isuzu.brand, isuzu.vin, isuzu.fuel_norm, isuzu.second_fuel_type) == \
        ("Isuzu", "JALC4B16507000001", Decimal("14.50"), "")
    damas = Vehicle.objects.get(plate="01777AAA")
    assert (damas.second_fuel_type, damas.second_fuel_norm) == ("Metan", Decimal("8.00"))

    vali = Driver.objects.get(phone="+998901234567")
    assert vali.default_vehicle == isuzu
    assert vali.licence_expiry == dt.date(2028, 12, 31)
    assert Driver.objects.get(phone="+998937654321").default_vehicle is None


def test_every_new_row_is_in_the_audit_log(filled, valid_data, django_user_model):
    actor = f.user(role="director")
    apply_import(filled(valid_data), actor=actor)
    rows = AuditLog.objects.filter(source="import", action="create", actor=actor)
    assert rows.count() == 4
    assert rows.filter(object_repr__startswith="01 A 123 BC").get().changes["vin"] == \
        [None, "JALC4B16507000001"]


def test_importing_the_same_file_again_changes_nothing(filled, valid_data):
    path = filled(valid_data)
    apply_import(path)
    before = AuditLog.objects.count()
    plan = apply_import(path)
    assert {r.action for r in plan.vehicles + plan.drivers} == {SAME}
    assert AuditLog.objects.count() == before


def test_changed_row_is_updated_and_the_change_is_shown(filled, valid_data, template_path):
    apply_import(filled(valid_data))
    valid_data["vehicles"][0]["odometer_km"] = 160000
    valid_data["drivers"][1]["default_plate"] = "01 777 AAA"
    plan = apply_import(filled(valid_data))

    assert plan.vehicles[0].action == UPDATE
    assert plan.vehicles[0].changes == {"odometer_km": [154300, 160000]}
    assert plan.drivers[1].changes == {"default_vehicle": [None, "01 777 AAA"]}
    assert Vehicle.objects.get(plate="01A123BC").odometer_km == 160000
    log = AuditLog.objects.get(source="import", action="update", object_repr__startswith="01 A")
    assert log.changes == {"odometer_km": [154300, 160000]}


def test_odometer_cannot_go_back(filled, valid_data):
    apply_import(filled(valid_data))
    valid_data["vehicles"][0]["odometer_km"] = 1000
    plan = plan_import(filled(valid_data))
    assert not plan.ok
    assert "cannot go back" in plan.issues[0].message
    assert plan.issues[0].column.startswith("Hozirgi probeg")


def test_vin_of_another_vehicle_in_the_system_is_refused(filled, valid_data):
    f.vehicle(plate="10B555CC", vin="JALC4B16507000001")
    plan = plan_import(filled(valid_data))
    assert [(i.sheet, i.row, i.column) for i in plan.issues] == [("Vehicles", 3, "VIN / VIN")]


def test_licence_of_another_driver_in_the_system_is_refused(filled, valid_data):
    f.driver(phone="+998991112233", licence_number="AF1234567")
    plan = plan_import(filled(valid_data))
    assert [(i.sheet, i.row) for i in plan.issues] == [("Drivers", 3)]
    assert plan.issues[0].column.startswith("Guvohnoma raqami")


def test_a_problem_blocks_the_whole_file(filled, valid_data):
    valid_data["drivers"][1]["phone"] = "12345"
    path = filled(valid_data)
    with pytest.raises(ImportBlocked):
        apply_import(path)
    assert Vehicle.objects.count() == 0  # the valid vehicles were not imported either


def test_other_sheets_do_not_block_today(filled, valid_data):
    valid_data["store_opening"][0]["quantity"] = "a lot"
    del valid_data["settings"]
    assert plan_import(filled(valid_data)).ok


def test_second_fuel_needs_its_norm(filled, valid_data):
    del valid_data["vehicles"][1]["second_fuel_norm"]
    plan = plan_import(filled(valid_data))
    assert [i.message for i in plan.issues] == ["is required when there is a second fuel"]


def test_existing_driver_keeps_their_bot_link(filled, valid_data):
    user = f.user(role="driver")
    f.driver(phone="+998901234567", licence_number="AF1234567", user=user)
    apply_import(filled(valid_data))
    assert Driver.objects.get(phone="+998901234567").user == user


def test_summary_reads_well(filled, valid_data):
    assert plan_import(filled(valid_data)).summary() == (
        "vehicles: 2 new, 0 changed, 0 unchanged; drivers: 2 new, 0 changed, 0 unchanged")
