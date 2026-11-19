"""The demo_drives command: test trips for local development (Day 14)."""

import datetime as dt

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.fleet.models import Shift
from apps.tracking.models import Geofence, LiveSession, Trip
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def demo(settings):
    settings.DEBUG = True
    v1, v2 = f.vehicle(plate="01D001AA"), f.vehicle(plate="01D002AA")
    return (f.driver(full_name="Demo Haydovchi Bir", default_vehicle=v1),
            f.driver(full_name="Demo Haydovchi Ikki", default_vehicle=v2))


def test_makes_working_days_with_trips_at_demo_places(demo):
    f.driver(full_name="Real Driver")
    call_command("demo_drives", "--days", "2", "--offline")
    made = Shift.objects.order_by("started_at")
    assert made.count() == 4
    assert {s.driver.full_name for s in made} == {"Demo Haydovchi Bir", "Demo Haydovchi Ikki"}
    assert all(s.vehicle == s.driver.default_vehicle for s in made)
    assert all(s.ended_at < timezone.now() for s in made)
    # loading, 3–4 clients and back: a trip to each place and one home
    assert all(4 <= s.trips.count() <= 5 for s in made)
    assert Geofence.objects.filter(name__startswith="Demo · ").count() == 7
    assert not Trip.objects.filter(ended_at__isnull=True).exists()


def test_a_day_with_a_real_shift_is_skipped(demo):
    bir, _ = demo
    yesterday = timezone.localdate() - dt.timedelta(days=1)
    noon = timezone.make_aware(dt.datetime.combine(yesterday, dt.time(12, 0)))
    f.shift(driver=bir, vehicle=bir.default_vehicle, started_at=noon,
            ended_at=noon + dt.timedelta(hours=1))
    call_command("demo_drives", "--days", "1", "--offline")
    assert Shift.objects.filter(driver=bir).count() == 1  # only the real one


def test_remove_keeps_real_phone_shifts(demo):
    bir, _ = demo
    call_command("demo_drives", "--days", "1", "--offline")
    real = f.shift(driver=bir, started_at=timezone.now() - dt.timedelta(days=9),
                   ended_at=timezone.now() - dt.timedelta(days=9) + dt.timedelta(hours=1))
    LiveSession.objects.create(shift=real, chat_id=1, message_id=1, live_period_s=900,
                               started_at=real.started_at, last_update_at=real.started_at)
    f.point(real, 69.2, 41.3, real.started_at)
    call_command("demo_drives", "--remove")
    assert list(Shift.objects.all()) == [real]
    assert not Geofence.objects.exists()


def test_refuses_without_debug(demo, settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("demo_drives", "--offline")
