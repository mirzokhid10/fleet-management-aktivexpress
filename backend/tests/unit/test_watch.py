"""Unit tests for noticing stopped location sharing (Day 11)."""

import datetime as dt

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.core.models import CompanySettings
from apps.tracking import watch
from apps.tracking.models import LiveSession, LocationPoint, SharingGap
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

NOW = timezone.now().replace(microsecond=0)


def ago(minutes: float) -> dt.datetime:
    return NOW - dt.timedelta(minutes=minutes)


def sharing(sh, last_minutes_ago: float, ended_reason: str = "", started: float = 60):
    kw = {"ended_at": ago(last_minutes_ago), "end_reason": ended_reason} if ended_reason else {}
    s = LiveSession.objects.create(shift=sh, chat_id=1, message_id=LiveSession.objects.count()
                                   + 1, live_period_s=0x7FFFFFFF, started_at=ago(started),
                                   last_update_at=ago(last_minutes_ago), **kw)
    LocationPoint.objects.create(shift=sh, vehicle=sh.vehicle, session=s,
                                 recorded_at=ago(last_minutes_ago), point=Point(69.2, 41.3))
    return s


def test_sharing_driver_is_fine():
    sh = f.shift(started_at=ago(60))
    sharing(sh, 0.5)
    assert watch.check(NOW) == []


def test_silent_share_is_noticed_after_the_limit():
    sh = f.shift(started_at=ago(60))
    s = sharing(sh, 9.5)
    assert watch.check(NOW) == []  # 9.5 min < 10
    [event] = watch.check(NOW + dt.timedelta(minutes=1))
    assert (event.kind, event.shift, event.since, event.minutes) == ("gap", sh, ago(9.5), 10)
    s.refresh_from_db()
    assert (s.end_reason, s.ended_at) == ("silent", ago(9.5))
    assert event.last_point.recorded_at == ago(9.5)


def test_stopped_share_counts_from_when_it_stopped():
    sh = f.shift(started_at=ago(60))
    sharing(sh, 12, ended_reason="stopped")
    [event] = watch.check(NOW)
    assert (event.since, event.minutes) == (ago(12), 12)


def test_never_shared_counts_from_the_shift_start():
    sh = f.shift(started_at=ago(5))
    assert watch.check(NOW) == []
    sh.started_at = ago(11)
    sh.save()
    [event] = watch.check(NOW)
    assert (event.since, event.last_point) == (ago(11), None)


def test_the_alert_goes_out_once_per_gap():
    sh = f.shift(started_at=ago(60))
    sharing(sh, 15, ended_reason="stopped")
    assert len(watch.check(NOW)) == 1
    assert watch.check(NOW + dt.timedelta(minutes=5)) == []
    assert SharingGap.objects.get().resolved_at is None


def test_location_back_closes_the_gap_and_says_how_long():
    sh = f.shift(started_at=ago(60))
    sharing(sh, 15, ended_reason="stopped")
    watch.check(NOW)
    sharing(sh, 0, started=0)  # shared again just now
    [event] = watch.check(NOW)
    assert (event.kind, event.minutes) == ("back", 15)
    assert SharingGap.objects.get().resolved_at == NOW
    assert watch.check(NOW) == []


def test_a_second_gap_is_a_new_alert():
    sh = f.shift(started_at=ago(120))
    sharing(sh, 60, ended_reason="stopped", started=120)
    watch.check(NOW - dt.timedelta(minutes=40))
    # Back for a while, then off again, all between two checks.
    sharing(sh, 30, ended_reason="stopped", started=40)
    back, gap = watch.check(NOW)
    assert (back.kind, back.minutes) == ("back", 20)  # off from 60 to 40 min ago
    assert (gap.kind, gap.since) == ("gap", ago(30))
    assert SharingGap.objects.filter(resolved_at__isnull=True).count() == 1


def test_ended_shift_closes_its_gap_silently():
    sh = f.shift(started_at=ago(60))
    sharing(sh, 15, ended_reason="stopped")
    watch.check(NOW)
    sh.ended_at = NOW
    sh.save()
    assert watch.check(NOW + dt.timedelta(minutes=1)) == []
    assert SharingGap.objects.get().resolved_at is not None


def test_limit_comes_from_company_settings():
    cs = CompanySettings.load()
    cs.stop_alert_minutes = 5
    cs.save()
    sh = f.shift(started_at=ago(60))
    sharing(sh, 6, ended_reason="stopped")
    assert len(watch.check(NOW)) == 1


def test_event_knows_where_to_remind_the_driver():
    person = f.user(role="driver", telegram_id=555, language="ru")
    sh = f.shift(driver=f.driver(user=person), started_at=ago(30))
    [event] = watch.check(NOW)
    assert (event.driver_chat_id, event.driver_language) == (555, "ru")
