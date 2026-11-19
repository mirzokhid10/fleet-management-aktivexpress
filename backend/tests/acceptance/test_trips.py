import html
import re

import pytest
from django.conf import settings
from django.test import Client
from pytest_bdd import parsers, scenarios, then

from tests import factories as f
from tests.acceptance.drive_steps import *  # noqa: F403 - shared drive steps
from tests.acceptance.drive_steps import send_moves

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("trips.feature")


def _trips_page(ctx):
    send_moves(ctx)
    client = Client()
    client.force_login(f.user(role="dispatcher"))
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    return client.get("/trips/")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(fragment))).strip()


@then("the dispatcher sees these trips")
def sees_trips(ctx, datatable):
    _, *rows = datatable
    body = _trips_page(ctx).content.decode()
    routes = [_text(m) for m in re.findall(r'data-testid="route">(.*?)</td>', body, re.S)]
    km = [_text(m).split(" maks.")[0]
          for m in re.findall(r'data-testid="distance">(.*?)</td>', body, re.S)]
    assert [[r, d] for r, d in zip(routes, km, strict=True)] == [
        [_text(r), d] for r, d in rows]


@then(parsers.parse("the trips total {km} km"))
def total(ctx, km):
    assert _text(_trips_page(ctx).content.decode().split('data-testid="total-km">')[1]
                 .split("</p>")[0]) == f"{km} km"


@then(parsers.parse("the dispatcher sees {n:d} trip on the way"))
@then(parsers.parse("the dispatcher sees {n:d} trips on the way"))
def on_the_way(ctx, n):
    assert _trips_page(ctx).content.decode().count('data-open="1"') == n
