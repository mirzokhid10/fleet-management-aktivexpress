"""The live map page (Day 12) and its refresh feed (Day 13)."""

import datetime as dt
import html
import json
import re

import pytest
from django.utils import timezone

from apps.tracking.models import LiveSession
from apps.tracking.views import map_data
from apps.tracking import livemap
from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

URL = "/map/"


DATA_URL = "/map/data/"


def _script(response, name):
    page = response.content.decode()
    raw = page.split(f'<script id="{name}" type="application/json">', 1)[1]
    return json.loads(raw.split("</script>", 1)[0])


def _vehicles(response) -> list[dict]:
    return _script(response, "map-feed")["vehicles"]


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
        assert re.search(rf'data-testid="count-{key}"[^>]*>{n}<', page), key
    assert "Harakatda" in page and "To'xtagan" in page and "Smenada emas" in page


def test_russian(login_as):
    _driving()
    page = login_as("dispatcher", language="ru").get(URL).content.decode()
    assert "В движении" in page and "Карта онлайн" in page


def test_page_loads_maplibre_and_the_configured_map(login_as, settings):
    settings.MAP_STYLE_URL = "https://tiles.example.test/styles/own"
    page = login_as("dispatcher").get(URL).content.decode()
    assert "vendor/maplibre-gl.js" in page and "vendor/maplibre-gl.css" in page
    response = login_as("dispatcher").get(URL)
    assert _script(response, "map-config") == {
        "style": "https://tiles.example.test/styles/own", "center": [69.2401, 41.2995],
        "refresh_s": 10}


def test_names_are_data_not_html(login_as):
    _driving(name='<img src=x onerror="alert(1)">')
    page = login_as("dispatcher").get(URL).content.decode()
    assert "<img src=x" not in page


def test_vehicle_without_position_is_listed_not_mapped(login_as):
    f.shift(driver=f.driver(full_name="Aliyev Vali"), vehicle=f.vehicle(plate="01A123BC"))
    response = login_as("dispatcher", language="uz").get(URL)
    v = _vehicles(response)[0]
    assert (v["status"], v["lat"], v["when"]) == ("no_signal", None, "")
    assert _script(response, "map-texts")["no_position"] == "Joylashuv hali yo'q"


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


# --- Day 13: the page refreshes itself -----------------------------------------

def test_feed_has_the_same_data_as_the_page(login_as):
    _driving()
    f.vehicle(plate="01777AAA")
    client = login_as("dispatcher", language="uz")
    page_data = _script(client.get(URL), "map-feed")
    response = client.get(DATA_URL)
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    data = response.json()
    assert data["vehicles"] == page_data["vehicles"]
    assert data["counts"] == {"moving": 1, "stopped": 0, "no_signal": 0, "off_shift": 1}


def test_feed_sees_the_vehicle_move(login_as):
    sh = _driving()
    client = login_as("dispatcher")
    assert client.get(DATA_URL).json()["vehicles"][0]["lat"] == 41.2995
    later = timezone.now() + dt.timedelta(seconds=30)
    f.point(sh, 69.2401, 41.3025, later, speed_kmh=36)
    LiveSession.objects.filter(shift=sh).update(last_update_at=later)
    v = client.get(DATA_URL).json()["vehicles"][0]
    assert (v["lat"], v["speed"], v["status"]) == (41.3025, 36, "moving")


def test_feed_is_for_managers_only(login_as, client):
    assert login_as("storekeeper").get(DATA_URL).status_code == 403
    client.logout()
    assert client.get(DATA_URL).status_code == 302


def test_panel_details_driver_phone_shift_start_and_distance(login_as):
    sh = _driving()
    sh.driver.phone = "+998901112233"
    sh.driver.save()
    f.point(sh, 69.2401, 41.3, timezone.now() - dt.timedelta(minutes=5), distance_m=2500)
    f.point(sh, 69.2401, 41.3, timezone.now() - dt.timedelta(minutes=4), distance_m=900,
            is_valid=False)  # a bad point never counts (Day 10)
    v = login_as("dispatcher").get(DATA_URL).json()["vehicles"][0]
    assert v["phone"] == "+998901112233" and v["shift_id"] == sh.pk
    assert v["shift_km"] == 2.5
    assert v["shift_since"] == f"{timezone.localtime(sh.started_at):%H:%M}"


def test_off_shift_vehicle_has_no_panel_shift_details(login_as):
    f.vehicle(plate="01777AAA")
    v = login_as("dispatcher").get(DATA_URL).json()["vehicles"][0]
    assert (v["driver"], v["phone"], v["shift_id"], v["shift_km"], v["shift_since"]) == (
        "", "", None, None, "")


def test_page_texts_are_translated(login_as):
    texts = _script(login_as("dispatcher", language="ru").get(URL), "map-texts")
    assert texts["follow"] == "Следить"
    assert texts["minutes_ago"] == "%(n)s мин назад"
    assert texts["updated"] == "Обновлено: %(time)s"
    assert texts["decimal"] == ","
