"""The database itself enforces the Day 1 rules, whatever code writes to it."""

import datetime as dt
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.models import CompanySettings
from apps.documents.models import Document
from apps.entries.models import Entry, Photo, Refuel
from apps.maintenance.models import ServiceRecord
from apps.store.models import StockMovement
from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

NOW = timezone.now()


def refused(fn):
    """True when the database refuses the write."""
    try:
        with transaction.atomic():
            fn()
    except DatabaseError:
        return True
    return False


# --- people and vehicles ---------------------------------------------------

def test_plate_and_vin_are_unique():
    v = f.vehicle()
    assert refused(lambda: f.vehicle(plate=v.plate))
    assert refused(lambda: f.vehicle(vin=v.vin))


def test_second_fuel_needs_its_own_norm_and_must_differ():
    assert refused(lambda: f.vehicle(second_fuel_type="Metan"))
    assert refused(lambda: f.vehicle(second_fuel_type="Dizel", second_fuel_norm=Decimal(9)))
    f.vehicle(fuel_type="AI-92", second_fuel_type="Metan", second_fuel_norm=Decimal(8))


def test_drivers_cannot_be_approvers_and_role_must_be_known():
    assert refused(lambda: f.user(role=User.Role.DRIVER, approves_fuel=True))
    assert refused(lambda: f.user(role="boss"))
    f.user(role=User.Role.DISPATCHER, approves_fuel=True)


def test_full_clean_runs_the_template_validators():
    from django.core.exceptions import ValidationError

    v = f.vehicle()
    v.plate = "01 a 123 bc"
    with pytest.raises(ValidationError, match="plate"):
        v.full_clean()


# --- shifts and tracking ---------------------------------------------------

def test_one_open_shift_per_driver_and_per_vehicle():
    s = f.shift()
    assert refused(lambda: f.shift(driver=s.driver))
    assert refused(lambda: f.shift(vehicle=s.vehicle))

    s.ended_at = NOW
    s.save()
    f.shift(driver=s.driver, vehicle=s.vehicle, started_at=NOW)


def test_shift_cannot_end_before_it_starts():
    assert refused(lambda: f.shift(started_at=NOW, ended_at=NOW - dt.timedelta(minutes=1)))


def test_postgis_measures_a_track_in_metres():
    s = f.shift()
    # Three points along Amir Temur avenue, Tashkent, ~1.1 km apart in total.
    for i, (lon, lat) in enumerate([(69.2797, 41.3111), (69.2810, 41.3160), (69.2822, 41.3210)]):
        f.point(s, lon, lat, NOW - dt.timedelta(minutes=10 - i))

    with connection.cursor() as cur:
        cur.execute("""
            SELECT ST_Length(ST_MakeLine(point ORDER BY recorded_at)::geography)
            FROM tracking_locationpoint WHERE shift_id = %s
        """, [s.id])
        metres = cur.fetchone()[0]
    assert 1050 < metres < 1200


def test_live_session_end_needs_a_reason():
    from apps.tracking.models import LiveSession

    s = f.shift()
    base = dict(shift=s, chat_id=1, live_period_s=28800, started_at=NOW, last_update_at=NOW)
    assert refused(lambda: LiveSession.objects.create(message_id=1, ended_at=NOW, **base))
    LiveSession.objects.create(message_id=2, ended_at=NOW, end_reason="stopped", **base)


# --- entries and approval --------------------------------------------------

def test_entry_status_and_decision_must_agree():
    boss = f.user()
    assert refused(lambda: f.entry(status="confirmed"))
    assert refused(lambda: f.entry(status="rejected", decided_by=boss, decided_at=NOW))
    assert refused(lambda: f.entry(decided_by=boss, decided_at=NOW))  # pending but decided
    f.entry(status="confirmed", decided_by=boss, decided_at=NOW)
    f.entry(status="rejected", decided_by=boss, decided_at=NOW, reject_reason="unclear_photo")


def test_odometer_required_except_for_part_requests():
    assert refused(lambda: f.entry(kind="refuel", odometer_km=None))
    f.entry(kind="part")


def test_refuel_detail_lives_one_to_one_with_its_entry():
    e = f.entry(kind="refuel")
    Refuel.objects.create(entry=e, fuel_type="Dizel", quantity=Decimal(60),
                          price_per_unit_uzs=Decimal(12500), total_uzs=Decimal(750000))
    assert Entry.objects.get(pk=e.pk).refuel.quantity == 60
    assert refused(lambda: Refuel.objects.create(entry=e, fuel_type="Dizel", quantity=1,
                                                 price_per_unit_uzs=1, total_uzs=1))


def test_photo_belongs_to_exactly_one_record_and_has_a_source():
    e, u = f.entry(), f.user(role="driver")
    doc = Document.objects.create(doc_type="Insurance", vehicle=e.vehicle,
                                  expires_on=dt.date(2027, 3, 1))
    base = dict(kind="odometer", taken_at=NOW, uploaded_by=u)
    assert refused(lambda: Photo.objects.create(telegram_file_id="x", **base))  # no owner
    assert refused(lambda: Photo.objects.create(entry=e, document=doc,
                                                telegram_file_id="x", **base))
    assert refused(lambda: Photo.objects.create(entry=e, **base))  # no file, no telegram id
    Photo.objects.create(entry=e, telegram_file_id="AgAC1", telegram_file_unique_id="u1", **base)
    assert refused(lambda: Photo.objects.create(entry=e, telegram_file_id="AgAC2",
                                                telegram_file_unique_id="u1", **base))


# --- documents, store, maintenance, settings -------------------------------

def test_document_owner_matches_its_type():
    v, d = f.vehicle(), f.driver()
    exp = dt.date(2027, 1, 1)
    assert refused(lambda: Document.objects.create(doc_type="Insurance", driver=d, expires_on=exp))
    assert refused(lambda: Document.objects.create(doc_type="Driving licence", vehicle=v,
                                                   expires_on=exp))
    assert refused(lambda: Document.objects.create(doc_type="Insurance", vehicle=v, driver=d,
                                                   expires_on=exp))
    Document.objects.create(doc_type="Power of attorney", driver=d, expires_on=exp)


def test_stock_is_the_sum_of_movements_with_correct_signs():
    item, v, keeper = f.store_item(), f.vehicle(), f.user(role="storekeeper")
    move = dict(item=item, created_by=keeper)
    StockMovement.objects.create(kind="opening", quantity=Decimal(120), **move)
    StockMovement.objects.create(kind="issue", quantity=Decimal(-8), vehicle=v, **move)
    assert item.stock() == Decimal(112)

    assert refused(lambda: StockMovement.objects.create(kind="issue", quantity=-1, **move))
    assert refused(lambda: StockMovement.objects.create(kind="purchase", quantity=-5, **move))
    assert refused(lambda: StockMovement.objects.create(kind="issue", quantity=5, vehicle=v,
                                                        **move))


def test_service_record_from_entry_must_link_the_entry():
    v = f.vehicle()
    rec = dict(vehicle=v, service="Oil", done_on=dt.date(2026, 10, 15), odometer_km=150000)
    assert refused(lambda: ServiceRecord.objects.create(source="entry", **rec))
    ServiceRecord.objects.create(source="import", **rec)


def test_company_settings_is_a_single_row():
    s = CompanySettings.load()
    assert s.pk == 1 and s.retention_months == 3
    CompanySettings(retention_months=1).save()  # overwrites row 1
    assert CompanySettings.objects.count() == 1
    assert refused(lambda: CompanySettings.objects.filter(pk=1).update(retention_months=2))


# --- audit -----------------------------------------------------------------

def test_audit_log_is_append_only():
    from django.contrib.contenttypes.models import ContentType

    v = f.vehicle()
    log = AuditLog.objects.create(source="web", action="create", object_id=str(v.pk),
                                  object_repr=str(v),
                                  content_type=ContentType.objects.get_for_model(v))
    assert refused(lambda: AuditLog.objects.filter(pk=log.pk).update(reason="edited"))
    assert refused(lambda: AuditLog.objects.filter(pk=log.pk).delete())
    assert AuditLog.objects.get(pk=log.pk).reason == ""
