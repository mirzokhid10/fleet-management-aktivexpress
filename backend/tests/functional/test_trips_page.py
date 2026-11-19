"""The trips page (Day 14)."""

import datetime as dt
import html

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.tracking.models import Geofence, Trip
from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

URL = "/trips/"
LAT, LON = 41.3, 69.2


def page(response) -> str:
    return html.unescape(response.content.decode())


def trip(shift, started_at, minutes=20, km=4.2, open_=False, start=(LON, LAT),
         end=(LON + 0.05, LAT)):
    ended = started_at + dt.timedelta(minutes=minutes)
    return Trip.objects.create(
        shift=shift, vehicle=shift.vehicle, started_at=started_at,
        ended_at=None if open_ else ended, last_point_at=ended,
        start_point=Point(*start, srid=4326), end_point=Point(*end, srid=4326),
        distance_m=km * 1000, max_speed_kmh=61.4, points=40)


@pytest.mark.parametrize("role, status", [("director", 200), ("dispatcher", 200),
                                          ("storekeeper", 403)])
def test_who_sees_trips(login_as, role, status):
    assert login_as(role).get(URL).status_code == status


def test_menu_links_to_trips(login_as):
    assert 'href="/trips/"' in page(login_as("dispatcher").get("/"))


def test_empty_page_tells_where_trips_come_from(login_as):
    body = page(login_as("dispatcher", language="uz").get(URL))
    assert "Hali reyslar yo'q." in body
    assert "5 daqiqa yoki undan uzoq to'xtash reysni tugatadi." in body


def test_lists_trips_newest_first_with_places_and_totals(login_as):
    Geofence.objects.create(name="Asosiy ombor", kind="Warehouse", address="Sergeli",
                            center=Point(LON, LAT, srid=4326), radius_m=150)
    now = timezone.now()
    sh = f.shift(driver=f.driver(full_name="Aliyev Vali"),
                 vehicle=f.vehicle(plate="01A123BC"), started_at=now - dt.timedelta(hours=3))
    old = trip(sh, now - dt.timedelta(hours=2), minutes=75, km=4.2)
    new = trip(sh, now - dt.timedelta(minutes=30), km=1.5, start=(LON + 0.05, LAT),
               end=(LON + 0.1, LAT))
    r = login_as("dispatcher", language="uz").get(URL)
    assert [t.pk for t in r.context["page"]] == [new.pk, old.pk]
    body = page(r)
    assert "Aliyev Vali" in body and "01 A 123 BC" in body
    assert "Asosiy ombor" in body  # start of the old trip is the warehouse
    assert "41.30000, 69.25000" in body  # a place with no name: coordinates
    assert "1 soat 15 daqiqa" in body
    assert "4,2 km" in body and "maks. 61 km/soat" in body
    assert r.context["total_trips"] == 2 and r.context["total_km"] == 5.7


def test_a_trip_on_the_way(login_as):
    now = timezone.now()
    sh = f.shift(started_at=now - dt.timedelta(hours=1))
    trip(sh, now - dt.timedelta(minutes=10), minutes=9, open_=True)
    body = page(login_as("dispatcher", language="uz").get(URL))
    assert "Yo'lda" in body and 'data-open="1"' in body


def test_a_silent_open_trip_is_ended_when_the_page_opens(login_as):
    now = timezone.now()
    sh = f.shift(started_at=now - dt.timedelta(hours=1))
    for i in range(9):  # drove 2 km, then nothing for 20 min
        f.point(sh, LON, LAT + i * 0.0025, now - dt.timedelta(minutes=24 - i / 2),
                distance_m=0 if i == 0 else 278, speed_kmh=33)
    from apps.tracking import trips
    trips.rebuild(sh, now - dt.timedelta(minutes=20))
    assert Trip.objects.get().is_open
    login_as("dispatcher").get(URL)
    assert not Trip.objects.get().is_open


def test_filters_by_driver_plate_and_day(login_as):
    now = timezone.now()
    a = f.shift(driver=f.driver(full_name="Aliyev Vali"), vehicle=f.vehicle(plate="01A123BC"),
                started_at=now - dt.timedelta(days=2))
    b = f.shift(driver=f.driver(full_name="Karimov Ali"), vehicle=f.vehicle(plate="10B777CD"),
                started_at=now - dt.timedelta(days=2))
    ta = trip(a, now - dt.timedelta(days=1, hours=1))
    tb = trip(b, now - dt.timedelta(hours=1))
    client = login_as("dispatcher")

    def rows(**q):
        return [t.pk for t in client.get(URL, q).context["page"]]

    assert rows(q="aliyev") == [ta.pk]
    assert rows(q="10 b 777") == [tb.pk]
    assert rows(day=timezone.localtime(tb.started_at).date().isoformat()) == [tb.pk]
    assert rows(day="2026-02-30") == [tb.pk, ta.pk]  # impossible date: ignored
    assert "Hech narsa topilmadi." in page(client.get(URL, {"q": "nobody"}))
