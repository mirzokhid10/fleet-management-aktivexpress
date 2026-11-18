"""Unit tests for vehicle statuses on the live map (Day 12)."""

import datetime as dt

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.models import CompanySettings
from apps.tracking import livemap
from apps.tracking.livemap import MOVING, NO_SIGNAL, OFF_SHIFT, STOPPED
from apps.tracking.models import LiveSession
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

NOW = dt.datetime(2026, 11, 19, 6, 0, tzinfo=dt.UTC)  # 11:00 in Tashkent
_ids = iter(range(1, 10_000))


def ago(minutes: float) -> dt.datetime:
    return NOW - dt.timedelta(minutes=minutes)


def sharing(sh, last_update_min=0.5, ended=False):
    return LiveSession.objects.create(
        shift=sh, chat_id=1, message_id=next(_ids), live_period_s=0x7FFFFFFF,
        started_at=ago(60), last_update_at=ago(last_update_min),
        ended_at=ago(last_update_min) if ended else None, end_reason="stopped" if ended else "")


def on_shift(plate="01A123BC", name="Aliyev Vali", **kw):
    return f.shift(driver=f.driver(full_name=name), vehicle=f.vehicle(plate=plate, **kw),
                   started_at=ago(120))


def one(plate="01 A 123 BC"):
    return next(v for v in livemap.fleet(NOW) if v.plate == plate)


def test_moving_vehicle_with_its_driver_and_place():
    sh = on_shift()
    sharing(sh)
    f.point(sh, 69.20, 41.30, ago(0.5), speed_kmh=42.4, heading=90)
    v = one()
    assert (v.status, v.driver, v.shift_id) == (MOVING, "Aliyev Vali", sh.pk)
    assert (v.lat, v.lon, v.speed_kmh, v.heading, v.at) == (41.30, 69.20, 42.4, 90, ago(0.5))
    assert v.model == "Isuzu NPR 82" and v.on_map


@pytest.mark.parametrize("speed, status", [(None, STOPPED), (0, STOPPED), (4.9, STOPPED),
                                           (5, MOVING), (90, MOVING)])
def test_five_km_h_makes_it_moving(speed, status):
    sh = on_shift()
    sharing(sh)
    f.point(sh, 69.2, 41.3, ago(0.5), speed_kmh=speed)
    assert one().status == status


def test_updates_coming_but_no_good_point_lately_is_stopped():
    sh = on_shift()
    sharing(sh, last_update_min=0.5)
    f.point(sh, 69.2, 41.3, ago(15), speed_kmh=60)  # the last good point is old
    f.point(sh, 70.9, 41.3, ago(0.5), speed_kmh=None, is_valid=False)  # a jump
    v = one()
    assert v.status == STOPPED
    assert (v.lat, v.lon) == (41.3, 69.2)  # bad points never move the marker


@pytest.mark.parametrize("minutes, status", [(9.9, STOPPED), (10.1, NO_SIGNAL)])
def test_silent_share_is_no_signal_after_the_alert_minutes(minutes, status):
    sh = on_shift()
    sharing(sh, last_update_min=minutes)
    f.point(sh, 69.2, 41.3, ago(minutes), speed_kmh=40)
    assert one().status == status


@pytest.mark.parametrize("minutes, status", [(1.9, MOVING), (2.1, STOPPED)])
def test_moving_only_while_the_last_point_is_recent(minutes, status):
    sh = on_shift()
    sharing(sh, last_update_min=minutes)
    f.point(sh, 69.2, 41.3, ago(minutes), speed_kmh=40)
    assert one().status == status


def test_alert_minutes_come_from_company_settings():
    cs = CompanySettings.load()
    cs.stop_alert_minutes = 5
    cs.save()
    sh = on_shift()
    sharing(sh, last_update_min=6)
    assert one().status == NO_SIGNAL


def test_stopped_sharing_is_no_signal_at_once_at_the_last_place():
    sh = on_shift()
    sharing(sh, last_update_min=1, ended=True)
    f.point(sh, 69.2, 41.3, ago(1), speed_kmh=30)
    v = one()
    assert v.status == NO_SIGNAL and (v.lat, v.lon) == (41.3, 69.2)


def test_on_shift_but_never_shared():
    on_shift()
    v = one()
    assert (v.status, v.lat, v.on_map) == (NO_SIGNAL, None, False)


def test_off_shift_vehicle_stays_at_its_last_known_place():
    old = on_shift()
    old.started_at = ago(700)
    f.point(old, 69.21, 41.31, ago(600), speed_kmh=50)
    old.ended_at = ago(590)
    old.save()
    v = one()
    assert (v.status, v.driver, v.shift_id) == (OFF_SHIFT, "", None)
    assert (v.lat, v.lon, v.at) == (41.31, 69.21, ago(600))


def test_vehicle_never_seen():
    f.vehicle(plate="01777AAA")
    v = one("01 777 AAA")
    assert (v.status, v.on_map) == (OFF_SHIFT, False)


def test_retired_vehicles_are_left_out_unless_on_shift():
    f.vehicle(plate="01777AAA", is_active=False)
    on_shift(plate="01555AAA", is_active=False)
    plates = [v.plate for v in livemap.fleet(NOW)]
    assert plates == ["01 555 AAA"]


def test_order_moving_stopped_no_signal_off_shift_then_plate():
    f.vehicle(plate="01001AAA")  # off shift
    on_shift(plate="01002AAA")  # no signal
    for plate, speed in [("01004AAA", 0), ("01003AAA", 30), ("01005AAA", 30)]:
        sh = on_shift(plate=plate)
        sharing(sh)
        f.point(sh, 69.2, 41.3, ago(0.5), speed_kmh=speed)
    items = livemap.fleet(NOW)
    assert [(v.plate, v.status) for v in items] == [
        ("01 003 AAA", MOVING), ("01 005 AAA", MOVING), ("01 004 AAA", STOPPED),
        ("01 002 AAA", NO_SIGNAL), ("01 001 AAA", OFF_SHIFT)]
    assert livemap.counts(items) == {MOVING: 2, STOPPED: 1, NO_SIGNAL: 1, OFF_SHIFT: 1}


def _queries() -> int:
    with CaptureQueriesContext(connection) as q:
        livemap.fleet(NOW)
    return len(q)


def test_same_number_of_queries_for_any_fleet_size():
    CompanySettings.load()  # created once, on first use
    sh = on_shift(plate="01001AAA")
    sharing(sh)
    f.point(sh, 69.2, 41.3, ago(1))
    small = _queries()
    for n in range(2, 12):
        sh = on_shift(plate=f"01{n:03d}AAA", name=f"Driver {n}")
        sharing(sh)
        f.point(sh, 69.2, 41.3, ago(1))
        f.point(sh, 69.2, 41.3, ago(2))
    assert _queries() == small
