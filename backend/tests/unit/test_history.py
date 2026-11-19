"""Unit tests for route history data (Day 15)."""

import datetime as dt

import pytest
from django.utils import timezone, translation

from apps.tracking import history, trips
from apps.tracking.history import Choice
from tests import factories as f
from tests.unit.test_trips import LON, Route, at, north, store

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

DAY = timezone.localtime(at(0)).date()  # T0 = 18 Nov 2026 05:00 UTC = 10:00 in Tashkent


@pytest.fixture
def day_drive(db):
    shift = f.shift(started_at=at(-60), ended_at=at(3600))
    store(shift, Route().drive(2000, 4).stand(6).drive(3000, 5))
    trips.rebuild(shift)
    return shift


def build(vehicle, day=DAY, days=1):
    with translation.override("uz"):
        return history.build(Choice(vehicle, day, days), now=at(7200))


def test_route_trips_and_stops_of_the_day(day_drive):
    data = build(day_drive.vehicle)
    [s] = data["shifts"]
    assert s["id"] == day_drive.pk and len(s["points"]) == 31
    t0, lon, lat, speed = s["points"][0]
    assert (t0, lon, lat) == (history.ms(at(0)), LON, pytest.approx(north(0)))
    a, b = data["trips"]
    assert (a["start"], a["end"]) == (history.ms(at(0)), history.ms(at(240)))
    assert s["points"][a["i0"]][0] == history.ms(at(0))
    assert s["points"][a["i1"]][0] == history.ms(at(240))
    assert s["points"][b["i0"]][0] == history.ms(at(600))
    assert (a["start_label"], a["end_label"], a["km"]) == ("10:00", "10:04", "2,0")
    stop, parked = data["stops"]
    assert (stop["start"], stop["end"], stop["minutes"]) == (
        history.ms(at(240)), history.ms(at(600)), 6)
    assert stop["lat"] == pytest.approx(north(2000))
    # after the last point it stood until the shift ended
    assert (parked["start"], parked["end"], parked["minutes"]) == (
        history.ms(at(900)), history.ms(at(3600)), 45)
    assert data["summary"] == {"km": "5,0", "trips": 2, "driving": "9 daqiqa"}
    assert data["tz_offset_min"] == 300 and data["multi_day"] is False


def test_a_trip_after_a_silent_stop_starts_at_the_parked_point(db):
    shift = f.shift(started_at=at(-60), ended_at=at(7200))
    store(shift, Route().drive(2000, 4).silent(20, meters=300).drive(3000, 5))
    trips.rebuild(shift)
    data = build(shift.vehicle)
    points, second = data["shifts"][0]["points"], data["trips"][1]
    assert second["start"] == history.ms(at(1440))
    assert points[second["i0"]][0] == history.ms(at(240))  # where it stood


def test_only_this_vehicle_good_points_and_days(day_drive):
    other = f.shift(started_at=at(-60), ended_at=at(3600))
    store(other, Route().drive(1000, 2))
    bad = day_drive.points.order_by("recorded_at")[5]
    bad.is_valid = False
    bad.save()
    data = build(day_drive.vehicle)
    assert len(data["shifts"][0]["points"]) == 30
    assert build(day_drive.vehicle, DAY + dt.timedelta(days=1))["shifts"] == []
    assert build(day_drive.vehicle, DAY - dt.timedelta(days=1))["shifts"] == []


def test_several_days_show_dates_and_reach_at_most_a_week(day_drive):
    data = build(day_drive.vehicle, DAY - dt.timedelta(days=1), days=2)
    assert data["multi_day"] and data["trips"][0]["start_label"] == "18.11 10:00"
    start, end = history.window(DAY, 30)
    assert end - start == dt.timedelta(days=history.MAX_DAYS)


def test_recent_days_are_newest_first(day_drive):
    later = f.shift(vehicle=day_drive.vehicle, started_at=at(86_400 * 2),
                    ended_at=at(86_400 * 2 + 3600))
    store(later, Route().drive(2000, 4))
    for st in later.points.order_by("recorded_at"):
        st.recorded_at += dt.timedelta(days=2)
        st.save()
    trips.rebuild(later)
    assert history.recent_days(day_drive.vehicle) == [DAY + dt.timedelta(days=2), DAY]


@pytest.mark.parametrize("minutes, text", [(9, "9 daqiqa"), (75, "1 soat 15 daqiqa")])
def test_duration_words(minutes, text):
    with translation.override("uz"):
        assert history.duration(dt.timedelta(minutes=minutes)) == text
