"""The live map page (Day 12)."""

import datetime as dt
import html
import json

import pytest
from django.utils import timezone

from apps.tracking.models import LiveSession
from apps.tracking.views import map_data
from apps.tracking import livemap
from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

URL = "/map/"


def _vehicles(response) -> list[dict]:
    html = response.content.decode()
    raw = html.split('<script id="map-vehicles" type="application/json">', 1)[1]
    return json.loads(raw.split("</script>", 1)[0])


def _driving(plate="01A123BC", name="Aliyev Vali", speed=40.0):
    now = timezone.now()
    sh = f.shift(driver=f.driver(full_name=name), vehicle=f.vehicle(plate=plate))
    LiveSession.objects.create(shift=sh, chat_id=1, message_id=sh.pk, live_period_s=0x7FFFFFFF,
                               started_at=now - dt.timedelta(minutes=30), last_update_at=now)
    f.point(sh, 69.2401, 41.2995, now, speed_kmh=speed)
    return sh


@pytest.mark.parametrize("role", ["director", "dispatcher"])
def test_managers_open_the_map(login_as, role):
    _driving()
    f.vehicle(plate="01777AAA")
    response = login_as(role).get(URL)
    assert response.status_code == 200
    data = _vehicles(response)
    assert [(v["plate"], v["status"], v["driver"]) for v in data] == [
        ("01 A 123 BC", "moving", "Aliyev Vali"), ("01 777 AAA", "off_shift", "")]
    moving = data[0]
    assert (moving["lat"], moving["lon"], moving["speed"]) == (41.2995, 69.2401, 40)


@pytest.mark.parametrize("role, status", [("storekeeper", 403)])
def test_storekeepers_do_not(login_as, role, status):
    assert login_as(role).get(URL).status_code == status


def test_sign_in_needed(client):
    response = client.get(URL)
    assert response.status_code == 302 and "/accounts/login/" in response["Location"]


def test_status_buttons_count_vehicles(login_as):
    _driving("01A123BC", speed=40)
    _driving("01B123BC", name="Karimov Ali", speed=0)
    f.vehicle(plate="01777AAA")
    page = html.unescape(login_as("dispatcher", language="uz").get(URL).content.decode())
    for key, n in [("moving", 1), ("stopped", 1), ("no_signal", 0), ("off_shift", 1)]:
        assert f'data-testid="count-{key}">{n}<' in page
    assert "Harakatda" in page and "To'xtagan" in page and "Smenada emas" in page


def test_russian(login_as):
    _driving()
    page = login_as("dispatcher", language="ru").get(URL).content.decode()
    assert "В движении" in page and "Карта онлайн" in page


def test_page_loads_maplibre_and_the_configured_map(login_as, settings):
    settings.MAP_STYLE_URL = "https://tiles.example.test/styles/own"
    page = login_as("dispatcher").get(URL).content.decode()
    assert "vendor/maplibre-gl.js" in page and "vendor/maplibre-gl.css" in page
    assert 'data-style="https://tiles.example.test/styles/own"' in page
    assert '<script id="map-center" type="application/json">[69.2401, 41.2995]</script>' in page


def test_names_are_data_not_html(login_as):
    _driving(name='<img src=x onerror="alert(1)">')
    page = login_as("dispatcher").get(URL).content.decode()
    assert "<img src=x" not in page


def test_vehicle_without_position_is_listed_not_mapped(login_as):
    f.shift(driver=f.driver(full_name="Aliyev Vali"), vehicle=f.vehicle(plate="01A123BC"))
    response = login_as("dispatcher", language="uz").get(URL)
    v = _vehicles(response)[0]
    assert (v["status"], v["lat"], v["when"]) == ("no_signal", None, "")
    assert "Joylashuv hali yo'q" in html.unescape(response.content.decode())


def test_time_shows_the_date_only_when_not_today():
    now = timezone.now()
    today = timezone.localtime(now)
    yesterday = timezone.localtime(now - dt.timedelta(days=1))
    items = [livemap.VehicleOnMap(1, "A", "", livemap.OFF_SHIFT, lat=41, lon=69, at=now),
             livemap.VehicleOnMap(2, "B", "", livemap.OFF_SHIFT, lat=41, lon=69,
                                  at=now - dt.timedelta(days=1))]
    first, second = map_data(items)
    assert first["when"] == f"{today:%H:%M}"
    assert second["when"] == f"{yesterday:%d.%m %H:%M}"


def test_live_map_is_in_the_menu(login_as):
    page = login_as("dispatcher").get("/").content.decode()
    assert f'href="{URL}"' in page
