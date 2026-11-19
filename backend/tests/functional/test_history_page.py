"""The route history page (Day 15)."""

import html
import json
import re

import pytest

from apps.tracking import trips
from tests import factories as f
from tests.unit.test_trips import Route, at, store

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

URL = "/history/"


def page(response) -> str:
    return html.unescape(response.content.decode())


def data(response) -> dict:
    found = re.search(r'<script id="history-data" type="application/json">(.*?)</script>',
                      response.content.decode(), re.S)
    return json.loads(found.group(1)) if found else None


@pytest.fixture
def drive(db):
    shift = f.shift(vehicle=f.vehicle(plate="01A123BC"), started_at=at(-60), ended_at=at(3600))
    store(shift, Route().drive(2000, 4).stand(6).drive(3000, 5))
    trips.rebuild(shift)
    return shift


@pytest.mark.parametrize("role, status", [("director", 200), ("dispatcher", 200),
                                          ("storekeeper", 403)])
def test_who_sees_route_history(login_as, role, status):
    assert login_as(role).get(URL).status_code == status


def test_menu_links_to_route_history(login_as):
    body = page(login_as("dispatcher", language="uz").get("/"))
    assert 'href="/history/"' in body and "Yo'l tarixi" in body


def test_opens_the_vehicle_that_drove_last_on_its_last_day(login_as, drive):
    f.vehicle(plate="01A000AA")  # first by plate, never drove
    r = login_as("dispatcher", language="uz").get(URL)
    assert r.context["choice"].vehicle == drive.vehicle
    assert r.context["choice"].day.isoformat() == "2026-11-18"
    d = data(r)
    assert [len(s["points"]) for s in d["shifts"]] == [31]
    assert len(d["trips"]) == 2
    body = page(r)
    assert "Reys bo'lgan kunlar:" in body and ">18.11<" in body
    assert "5,0 km" in body


def test_a_trip_link_opens_its_vehicle_day_and_trip(login_as, drive):
    other = f.vehicle(plate="10B777CD")
    trip = drive.trips.order_by("started_at").last()
    r = login_as("dispatcher").get(URL, {"trip": trip.pk})
    assert r.context["choice"].vehicle == drive.vehicle
    assert r.context["trip_id"] == trip.pk
    # The trip belongs to another vehicle than the one asked for: no highlight.
    r = login_as("dispatcher").get(URL, {"trip": trip.pk, "vehicle": other.pk})
    assert r.context["choice"].vehicle == other and r.context["trip_id"] is None


def test_empty_day_says_so(login_as, drive):
    r = login_as("dispatcher", language="uz").get(
        URL, {"vehicle": drive.vehicle.pk, "day": "2026-11-10"})
    assert data(r) is None
    assert "Bu kunlarda yo'l yo'q." in page(r)


def test_bad_inputs_fall_back(login_as, drive):
    r = login_as("dispatcher").get(URL, {"vehicle": "x", "day": "2026-02-30", "days": "99"})
    assert r.status_code == 200
    assert r.context["choice"].vehicle == drive.vehicle and r.context["choice"].days == 1


def test_no_vehicles_at_all(login_as):
    body = page(login_as("dispatcher", language="uz").get(URL))
    assert "Hozircha avtomobillar yo'q." in body


def test_trips_page_and_live_map_link_here(login_as, drive):
    client = login_as("dispatcher", language="uz")
    trip = drive.trips.first()
    assert f'href="/history/?trip={trip.pk}"' in page(client.get("/trips/"))
    assert client.get("/map/").context["texts"]["history"] == "Yo'l tarixi"
