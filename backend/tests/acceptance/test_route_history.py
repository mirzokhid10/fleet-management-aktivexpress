import json
import re

import pytest
from django.conf import settings
from django.test import Client
from pytest_bdd import parsers, scenarios, then, when

from apps.tracking.models import Trip
from tests import factories as f

from tests.acceptance.drive_steps import *  # noqa: F403 - shared drive steps

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("route_history.feature")


@when("the dispatcher opens the first trip on the map")
def open_trip(ctx):
    client = Client()
    client.force_login(f.user(role="dispatcher"))
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    first = Trip.objects.order_by("started_at").first()
    link = f"/history/?trip={first.pk}"
    assert link in client.get("/trips/").content.decode()
    ctx["page"] = client.get(link)
    ctx["first_trip"] = first


def _data(ctx) -> dict:
    raw = re.search(r'<script id="history-data" type="application/json">(.*?)</script>',
                    ctx["page"].content.decode(), re.S).group(1)
    return json.loads(raw)


@then("route history shows the day of that vehicle")
def shows_day(ctx):
    choice = ctx["page"].context["choice"]
    assert choice.vehicle == ctx["shift"].vehicle
    assert ctx["page"].context["trip_id"] == ctx["first_trip"].pk


@then("the timeline is")
def timeline(ctx, datatable):
    _, *rows = datatable
    d = _data(ctx)
    items = [("trip", t["start"], f'{t["from"]} → {t["to"]}') for t in d["trips"]]
    # Stops between trips (not the loading before the first or the wait after the last).
    first, last = d["trips"][0]["start"], d["trips"][-1]["start"]
    items += [("stop", s["start"], f'{s["duration"]} · {s["place"]}')
              for s in d["stops"] if first < s["start"] < last]
    assert [[k, text] for k, _, text in sorted(items, key=lambda i: i[1])] == rows


@then("playback runs from the first point to the last")
def playback(ctx):
    d = _data(ctx)
    points = [p for s in d["shifts"] for p in s["points"]]
    assert points[0][0] < d["trips"][0]["start"] + 1 and points[-1][0] >= d["trips"][-1]["end"]
    assert re.search(r'data-testid="slider"', ctx["page"].content.decode())
