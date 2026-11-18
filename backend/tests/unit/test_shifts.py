"""Unit tests for starting and ending shifts (Day 8)."""

import datetime as dt

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bot.shift_handlers import span, when
from apps.fleet import shifts
from apps.fleet.models import Shift
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_driver_of_needs_a_linked_active_driver():
    person = f.user(role="driver")
    assert shifts.driver_of(None) is None
    assert shifts.driver_of(person.pk) is None
    d = f.driver(user=person)
    assert shifts.driver_of(person.pk) == d
    d.is_active = False
    d.save()
    assert shifts.driver_of(person.pk) is None


def test_free_vehicles_puts_own_vehicle_first_and_hides_busy_and_inactive():
    a, b, own = (f.vehicle(plate=p) for p in ("01A001AA", "01A002AA", "01A003AA"))
    f.vehicle(plate="01A004AA", is_active=False)
    busy = f.vehicle(plate="01A005AA")
    f.shift(vehicle=busy)
    d = f.driver(default_vehicle=own)
    assert shifts.free_vehicles(d) == [own, a, b]


def test_ended_shift_frees_the_vehicle():
    v = f.vehicle()
    f.shift(vehicle=v, ended_at=timezone.now())
    assert shifts.free_vehicles(f.driver()) == [v]


@pytest.mark.parametrize("typed", ["002", "2aa", " 0 0 2 ", "01A002AA"])
def test_free_vehicles_search_ignores_spaces_and_case(typed):
    f.vehicle(plate="01A001AA")
    v = f.vehicle(plate="01A002AA")
    assert shifts.free_vehicles(f.driver(), typed) == [v]


def test_start_opens_a_shift_and_writes_the_audit_log():
    person = f.user(role="driver")
    d, v = f.driver(user=person), f.vehicle()
    out = shifts.start(d, v.pk, person)
    assert out.result == shifts.STARTED
    assert out.shift.is_open and out.shift.vehicle == v
    row = AuditLog.objects.get()
    assert (row.action, row.source, row.actor) == ("create", "bot", person)


def test_start_twice_returns_the_open_shift():
    d = f.driver()
    first = shifts.start(d, f.vehicle().pk).shift
    out = shifts.start(d, f.vehicle().pk)
    assert (out.result, out.shift) == (shifts.ALREADY_ON_SHIFT, first)
    assert Shift.objects.count() == 1


def test_start_on_a_busy_vehicle_names_who_has_it():
    v = f.vehicle()
    theirs = f.shift(vehicle=v, driver=f.driver(full_name="Karimov Ali"))
    out = shifts.start(f.driver(), v.pk)
    assert (out.result, out.shift) == (shifts.VEHICLE_BUSY, theirs)


@pytest.mark.parametrize("make", [lambda: f.vehicle(is_active=False).pk, lambda: 999_999])
def test_start_on_an_inactive_or_missing_vehicle(make):
    assert shifts.start(f.driver(), make()).result == shifts.VEHICLE_UNAVAILABLE


def test_database_still_refuses_two_open_shifts_on_one_vehicle():
    v = f.vehicle()
    f.shift(vehicle=v)
    with pytest.raises(IntegrityError):
        f.shift(vehicle=v)


def test_end_closes_once_and_logs_who():
    sh = f.shift()
    boss = f.user(role="dispatcher")
    assert shifts.end(sh, actor=boss, source="web", reason="forgot") is True
    sh.refresh_from_db()
    assert sh.ended_at is not None
    assert shifts.end(sh) is False  # already ended: nothing changes
    row = AuditLog.objects.get()
    assert (row.action, row.source, row.actor, row.reason) == ("update", "web", boss, "forgot")
    assert row.changes["ended_at"][0] is None


def test_end_of_a_stale_copy_does_not_move_the_end_time():
    sh = f.shift()
    stale = Shift.objects.get(pk=sh.pk)
    shifts.end(sh)
    first_end = Shift.objects.get(pk=sh.pk).ended_at
    assert shifts.end(stale) is False
    assert Shift.objects.get(pk=sh.pk).ended_at == first_end


def test_duration_and_hours_minutes():
    start = timezone.now() - dt.timedelta(hours=9, minutes=28, seconds=30)
    sh = f.shift(started_at=start)
    assert shifts.hours_minutes(shifts.duration(sh)) == (9, 28)
    assert shifts.hours_minutes(dt.timedelta(seconds=-5)) == (0, 0)


def test_wording_of_times_and_spans():
    from django.utils import translation

    now = timezone.localtime()
    assert when(now) == f"{now:%H:%M}"
    assert when(now - dt.timedelta(days=2)) == f"{now - dt.timedelta(days=2):%d.%m %H:%M}"
    with translation.override("uz"):
        assert span(dt.timedelta(hours=2, minutes=5)) == "2 soat 5 daqiqa"
        assert span(dt.timedelta(minutes=40)) == "40 daqiqa"
    with translation.override("ru"):
        assert span(dt.timedelta(hours=1)) == "1 ч 0 мин"
