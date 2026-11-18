"""Unit tests for storing live location (Day 9)."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.fleet import shifts
from apps.tracking import live
from apps.tracking.models import LiveSession, LocationPoint
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

CHAT = 7001
LIVE = 0x7FFFFFFF


@pytest.fixture
def on_shift():
    """A driver on shift: (user_id, shift)."""
    person = f.user(role="driver")
    sh = f.shift(driver=f.driver(user=person))
    return person.pk, sh


def fix(message_id=1, lat=41.3, lon=69.2, at=None, live_period=LIVE, **kw):
    return live.Fix(chat_id=CHAT, message_id=message_id, latitude=lat, longitude=lon,
                    at=at or timezone.now(), live_period=live_period, **kw)


def test_first_share_starts_a_session_and_stores_the_point(on_shift):
    user_id, sh = on_shift
    assert live.receive(user_id, fix(accuracy_m=12.5, heading=90), edited=False) == live.STARTED
    session = LiveSession.objects.get()
    assert (session.shift, session.chat_id, session.message_id, session.live_period_s) == \
        (sh, CHAT, 1, LIVE)
    p = LocationPoint.objects.get()
    assert (p.shift, p.vehicle, p.session) == (sh, sh.vehicle, session)
    assert (p.point.x, p.point.y, p.point.srid) == (69.2, 41.3, 4326)  # lon, lat
    assert (p.accuracy_m, p.heading, p.is_valid) == (12.5, 90, True)


def test_updates_add_points_to_the_same_session(on_shift):
    user_id, sh = on_shift
    t = timezone.now()
    live.receive(user_id, fix(at=t), edited=False)
    for n in range(1, 4):
        assert live.receive(user_id, fix(at=t + dt.timedelta(seconds=30 * n),
                                         lat=41.3 + n / 1000), edited=True) == live.POINT
    assert sh.points.count() == 4
    session = LiveSession.objects.get()
    assert session.last_update_at == t + dt.timedelta(seconds=90)
    assert [round(p.point.y, 3) for p in sh.points.all()] == [41.3, 41.301, 41.302, 41.303]


def test_the_same_update_twice_is_stored_once(on_shift):
    user_id, sh = on_shift
    t = timezone.now()
    live.receive(user_id, fix(at=t), edited=False)
    live.receive(user_id, fix(at=t + dt.timedelta(seconds=30)), edited=True)
    live.receive(user_id, fix(at=t + dt.timedelta(seconds=30)), edited=True)
    assert sh.points.count() == 2


def test_stopping_keeps_the_last_point_and_ends_the_session(on_shift):
    user_id, sh = on_shift
    t = timezone.now()
    live.receive(user_id, fix(at=t), edited=False)
    stop = t + dt.timedelta(minutes=5)
    assert live.receive(user_id, fix(at=stop, live_period=None), edited=True) == live.STOPPED
    session = LiveSession.objects.get()
    assert (session.ended_at, session.end_reason) == (stop, "stopped")
    assert sh.points.count() == 2
    # anything after that for the same message is ignored
    assert live.receive(user_id, fix(at=stop + dt.timedelta(seconds=5)), edited=True) == \
        live.IGNORED
    assert sh.points.count() == 2


def test_a_new_share_replaces_the_old_one(on_shift):
    user_id, sh = on_shift
    live.receive(user_id, fix(message_id=1), edited=False)
    live.receive(user_id, fix(message_id=2), edited=False)
    old, new = LiveSession.objects.order_by("message_id")
    assert (old.end_reason, new.ended_at) == ("stopped", None)


def test_updates_after_the_live_period_are_ignored(on_shift):
    user_id, sh = on_shift
    t = timezone.now()
    live.receive(user_id, fix(at=t, live_period=900), edited=False)  # 15 minutes
    late = t + dt.timedelta(minutes=16)
    assert live.receive(user_id, fix(at=late, live_period=900), edited=True) == live.IGNORED
    assert LiveSession.objects.get().end_reason == "expired"
    assert sh.points.count() == 1


def test_ending_the_shift_ends_the_share_and_later_points_are_dropped(on_shift):
    user_id, sh = on_shift
    live.receive(user_id, fix(), edited=False)
    shifts.end(sh)
    session = LiveSession.objects.get()
    assert session.end_reason == "shift_ended"
    assert live.receive(user_id, fix(at=timezone.now() + dt.timedelta(seconds=30)),
                        edited=True) == live.IGNORED
    assert sh.points.count() == 1


def test_share_started_before_the_shift_is_adopted_on_its_next_update():
    person = f.user(role="driver")
    d = f.driver(user=person)
    assert live.receive(person.pk, fix(), edited=False) == live.NO_SHIFT
    assert not LocationPoint.objects.exists()
    sh = shifts.start(d, f.vehicle().pk).shift
    later = timezone.now() + dt.timedelta(seconds=30)
    assert live.receive(person.pk, fix(at=later), edited=True) == live.STARTED
    assert LiveSession.objects.get().shift == sh
    assert sh.points.count() == 1


@pytest.mark.parametrize("edited, expected", [(False, live.NOT_LIVE), (True, live.IGNORED)])
def test_one_time_location_is_not_stored(on_shift, edited, expected):
    user_id, _ = on_shift
    assert live.receive(user_id, fix(live_period=None), edited=edited) == expected
    assert not LocationPoint.objects.exists()


@pytest.mark.parametrize("make_user", [lambda: None, lambda: f.user(role="dispatcher").pk])
def test_people_who_are_not_drivers(make_user):
    assert live.receive(make_user(), fix(), edited=False) == live.NOT_DRIVER
    assert live.receive(make_user(), fix(message_id=9), edited=True) == live.IGNORED
    assert not LocationPoint.objects.exists()


def test_is_sharing(on_shift):
    user_id, sh = on_shift
    assert live.is_sharing(sh) is False
    live.receive(user_id, fix(), edited=False)
    assert live.is_sharing(sh) is True
