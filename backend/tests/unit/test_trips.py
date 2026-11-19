"""Unit tests for trip detection (Day 14)."""

from __future__ import annotations

import datetime as dt

import pytest
from django.contrib.gis.geos import Point, Polygon

from apps.fleet import shifts
from apps.tracking import track, trips
from apps.tracking.models import Geofence, LocationPoint, Trip
from apps.tracking.trips import Pt, detect
from tests import factories as f

T0 = dt.datetime(2026, 11, 18, 5, 0, tzinfo=dt.UTC)
LAT, LON = 41.3, 69.2
M_PER_DEG_LAT = 111_195


def at(seconds: float) -> dt.datetime:
    return T0 + dt.timedelta(seconds=seconds)


def north(meters: float) -> float:
    return LAT + meters / M_PER_DEG_LAT


class Route:
    """A drive along one street, written as steps; a point every 30 s while sharing."""

    def __init__(self):
        self.t, self.m = 0, 0.0
        self.steps: list[tuple[int, float]] = [(0, 0.0)]

    def drive(self, meters: float, minutes: float) -> Route:
        n = int(minutes * 2)
        self.steps += [(self.t + 30 * k, self.m + meters * k / n) for k in range(1, n + 1)]
        self.t, self.m = self.t + 30 * n, self.m + meters
        return self

    def stand(self, minutes: float) -> Route:
        n = int(minutes * 2)
        self.steps += [(self.t + 30 * k, self.m) for k in range(1, n + 1)]
        self.t += 30 * n
        return self

    def silent(self, minutes: float, meters: float = 0) -> Route:
        """No points for a while (phone still, or sharing off), then one."""
        self.t, self.m = self.t + int(minutes * 60), self.m + meters
        self.steps.append((self.t, self.m))
        return self

    def points(self) -> list[Pt]:
        out, prev = [], None
        for sec, m in self.steps:
            d = v = 0.0
            if prev is not None:
                d = track.distance_m(LON, north(prev[1]), LON, north(m))
                d = 0.0 if d < track.JITTER_M else d
                v = d / (sec - prev[0]) * 3.6
            out.append(Pt(at(sec), LON, north(m), d, v))
            prev = (sec, m)
        return out

    @property
    def end(self) -> dt.datetime:
        return at(self.t)


def found(route: Route, is_open: bool = False, until: dt.datetime | None = None):
    return detect(route.points(), until or route.end, is_open)


# --- pure rules --------------------------------------------------------------

@pytest.mark.unit
def test_no_points_no_trips():
    assert detect([], T0, False) == []


@pytest.mark.unit
def test_one_drive_without_stopping_is_one_trip():
    [trip] = found(Route().drive(2000, 4))
    assert (trip.started_at, trip.ended_at) == (T0, at(240))
    assert trip.distance_m == pytest.approx(2000, rel=0.005)
    assert trip.max_speed_kmh == pytest.approx(30, rel=0.005)


@pytest.mark.unit
def test_a_stop_of_5_minutes_splits_the_trip():
    a, b = found(Route().drive(2000, 4).stand(6).drive(3000, 5))
    assert (a.started_at, a.ended_at) == (T0, at(240))  # arrived
    assert (b.started_at, b.ended_at) == (at(600), at(900))  # left after 6 min
    assert a.distance_m == pytest.approx(2000, rel=0.005)
    assert b.distance_m == pytest.approx(3000, rel=0.005)


@pytest.mark.unit
def test_a_shorter_stop_does_not():
    [trip] = found(Route().drive(2000, 4).stand(4).drive(3000, 5))
    assert trip.distance_m == pytest.approx(5000, rel=0.005)


@pytest.mark.unit
def test_a_silent_parked_phone_is_a_stop():
    # Telegram sends nothing for 20 min; the next point is 300 m on: walking pace.
    a, b = found(Route().drive(2000, 4).silent(20, meters=300).drive(3000, 5))
    assert a.ended_at == at(240)
    assert b.started_at == at(240 + 1200)  # first point that shows it moving again
    assert b.distance_m == pytest.approx(3300, rel=0.005)  # from the place it stood


@pytest.mark.unit
def test_driving_with_sharing_off_stays_one_trip():
    # 8 km in 10 min without points: it drove, it did not stop.
    [trip] = found(Route().drive(2000, 4).silent(10, meters=8000).drive(3000, 5))
    assert trip.distance_m == pytest.approx(13_000, rel=0.005)


@pytest.mark.unit
def test_waiting_at_the_depot_first_is_not_a_trip():
    [trip] = found(Route().stand(30).drive(2000, 4))
    assert trip.started_at == at(1800)


@pytest.mark.unit
def test_moving_around_the_yard_is_not_a_trip():
    trips_found = found(Route().drive(2000, 4).stand(6).drive(150, 1).stand(6).drive(3000, 5))
    assert len(trips_found) == 2


@pytest.mark.unit
def test_on_an_open_shift_the_last_trip_is_on_the_way():
    route = Route().drive(2000, 4)
    [trip] = found(route, is_open=True)
    assert trip.ended_at is None


@pytest.mark.unit
def test_it_arrives_once_it_has_stood_for_5_minutes():
    route = Route().drive(2000, 4).stand(2)
    [trip] = found(route, is_open=True, until=route.end + dt.timedelta(minutes=2))
    assert trip.ended_at is None  # 4 min standing so far
    [trip] = found(route, is_open=True, until=route.end + dt.timedelta(minutes=3))
    assert trip.ended_at == at(240)


# --- database --------------------------------------------------------------

def store(shift, route: Route) -> None:
    """Save the route's points the way the bot does (Day 10 rules applied)."""
    have = set(shift.points.values_list("recorded_at", flat=True))
    for sec, m in route.steps:
        if at(sec) in have:
            continue
        p = LocationPoint(shift=shift, vehicle=shift.vehicle, recorded_at=at(sec),
                          point=Point(LON, north(m), srid=4326))
        track.apply(p)
        p.save()


@pytest.fixture
def ended_shift(db):
    return f.shift(started_at=T0, ended_at=at(3600))


@pytest.mark.unit
@pytest.mark.django_db
def test_rebuild_stores_trips_and_keeps_rows_that_did_not_change(ended_shift):
    store(ended_shift, Route().drive(2000, 4).stand(6).drive(3000, 5))
    assert trips.rebuild(ended_shift) == 2
    first = list(Trip.objects.order_by("started_at").values_list("pk", "started_at", "ended_at"))
    assert [(s, e) for _, s, e in first] == [(T0, at(240)), (at(600), at(900))]
    trips.rebuild(ended_shift)
    assert list(Trip.objects.order_by("started_at")
                .values_list("pk", "started_at", "ended_at")) == first
    t = Trip.objects.order_by("started_at").first()
    assert t.vehicle_id == ended_shift.vehicle_id
    assert t.start_point.y == pytest.approx(LAT)
    assert t.end_point.y == pytest.approx(north(2000))
    assert t.points == 9


@pytest.mark.unit
@pytest.mark.django_db
def test_an_open_trip_grows_ends_and_a_new_one_starts():
    shift = f.shift(started_at=T0)
    route = Route().drive(2000, 4)
    store(shift, route)
    trips.rebuild(shift, route.end)
    [trip] = Trip.objects.all()
    assert trip.is_open and trip.last_point_at == at(240)

    route.stand(6)
    store(shift, route)
    trips.rebuild(shift, route.end)
    trip.refresh_from_db()
    assert trip.ended_at == at(240)

    route.drive(3000, 5)
    store(shift, route)
    trips.rebuild(shift, route.end)
    assert [t.is_open for t in Trip.objects.order_by("started_at")] == [False, True]


@pytest.mark.unit
@pytest.mark.django_db
def test_trips_stay_when_retention_has_deleted_the_points(ended_shift):
    store(ended_shift, Route().drive(2000, 4))
    trips.rebuild(ended_shift)
    ended_shift.points.all().delete()
    assert trips.rebuild(ended_shift) == 1
    assert Trip.objects.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_close_quiet_ends_the_trip_of_a_silent_vehicle():
    shift = f.shift(started_at=T0)
    route = Route().drive(2000, 4)
    store(shift, route)
    trips.rebuild(shift, route.end)
    assert trips.close_quiet(route.end + dt.timedelta(minutes=4)) == 0
    assert trips.close_quiet(route.end + dt.timedelta(minutes=5)) == 1
    assert Trip.objects.get().ended_at == at(240)


@pytest.mark.unit
@pytest.mark.django_db
def test_ending_the_shift_ends_its_last_trip():
    shift = f.shift()
    store(shift, Route().drive(2000, 4))
    trips.rebuild(shift, at(240))
    assert Trip.objects.get().is_open
    shifts.end(shift)
    assert Trip.objects.get().ended_at == at(240)


@pytest.mark.unit
@pytest.mark.django_db
def test_recalculate_track_rebuilds_trips(ended_shift):
    from django.core.management import call_command

    store(ended_shift, Route().drive(2000, 4).stand(6).drive(3000, 5))
    Trip.objects.all().delete()
    call_command("recalculate_track")
    assert Trip.objects.count() == 2


@pytest.mark.unit
@pytest.mark.django_db
def test_places_name_trip_ends_by_circle_or_drawn_area():
    yard = Geofence.objects.create(name="Main warehouse", kind="Warehouse", address="Sergeli",
                                   center=Point(LON, LAT, srid=4326), radius_m=150)
    square = Polygon.from_bbox((LON - 0.01, north(1900), LON + 0.01, north(2100)))
    client = Geofence.objects.create(name="Chorsu client", kind="Client", address="Chorsu",
                                     area=square)
    Geofence.objects.create(name="Closed", kind="Client", address="-", is_active=False,
                            center=Point(LON, north(5000), srid=4326), radius_m=500)
    places = trips.Places()
    assert places.at(Point(LON, north(140))) == yard
    assert places.at(Point(LON, north(160))) is None
    assert places.at(Point(LON, north(2000))) == client
    assert places.at(Point(LON, north(5000))) is None
