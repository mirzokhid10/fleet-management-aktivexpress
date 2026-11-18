import datetime as dt
import html

import pytest
from django.conf import settings
from django.test import Client
from pytest_bdd import given, parsers, scenarios, then, when

from apps.fleet.models import Shift
from apps.tracking import track
from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("clean_track.feature")

M_PER_DEG_LAT = 111_195


@pytest.fixture
def ctx():
    return {"t0": dt.datetime.now(dt.UTC) - dt.timedelta(minutes=10)}


def _shift(ctx):
    return Shift.objects.get(driver=ctx["driver"])


@given(parsers.parse('"{name}" is on shift and sharing live location'))
def on_shift(ctx, name):
    person = f.user(role="driver", first_name=name.split()[0], language="uz")
    ctx["driver"] = f.driver(user=person, full_name=name)
    tg = ctx["tg"] = link_telegram(person)
    v = f.vehicle()
    tg.send("/start_shift")
    tg.tap(f"shift:take:{v.pk}")
    ctx["message_id"], _ = tg.share_location(41.3, 69.2, at=ctx["t0"], horizontal_accuracy=10)


@when("their location moves like this")
def moves(ctx, datatable):
    header, *rows = datatable
    for row in rows:
        sec, meters, acc = (int(x) for x in row)
        ctx["tg"].move(ctx["message_id"], 41.3 + meters / M_PER_DEG_LAT, 69.2,
                       horizontal_accuracy=acc, at=ctx["t0"] + dt.timedelta(seconds=sec),
                       started=ctx["t0"])


@then(parsers.parse("{bad:d} of the {total:d} points are marked bad"))
def marked_bad(ctx, bad, total):
    t = track.totals(_shift(ctx))
    assert (t.bad_points, t.points) == (bad, total)


@then(parsers.parse("the clean track is {km:f} km with top speed {speed:d} km/h"))
def clean(ctx, km, speed):
    t = track.totals(_shift(ctx))
    assert t.distance_km == pytest.approx(km, abs=0.05)
    assert round(t.max_speed_kmh) == speed


@when("they end the shift")
def end(ctx):
    ctx["tg"].send("/end_shift")
    ctx["calls"] = ctx["tg"].tap(f"shift:end:{_shift(ctx).pk}")


@then(parsers.parse('the bot says "{text}"'))
def bot_says(ctx, text):
    assert text in FakeTelegram.texts(ctx["calls"])[0]


@then(parsers.parse("the dispatcher sees {km} km for the shift"))
def dispatcher_sees(ctx, km):
    client = Client()
    client.force_login(f.user(role="dispatcher"))
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    r = client.get("/shifts/")
    assert r.context["page"][0].km == float(km.replace(",", "."))
    assert f"{km} km" in html.unescape(r.content.decode())
