"""The shift log page (Day 8)."""

import datetime as dt
import html

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from tests import factories as f
from tests.bot_helpers import link_telegram

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

URL = "/shifts/"


def page(response) -> str:
    return html.unescape(response.content.decode())


def rows(response):
    return [s.pk for s in response.context["page"]]


@pytest.mark.parametrize("role, status", [("director", 200), ("dispatcher", 200),
                                          ("storekeeper", 403)])
def test_who_sees_the_shift_log(login_as, role, status):
    assert login_as(role).get(URL).status_code == status


def test_empty_log_tells_how_shifts_start(login_as):
    body = page(login_as("dispatcher", language="uz").get(URL))
    assert "Hali smenalar yo'q. Haydovchilar ularni botda /start_shift bilan boshlaydi." in body


def test_lists_shifts_newest_first_with_open_ones_marked(login_as):
    now = timezone.now()
    old = f.shift(driver=f.driver(full_name="Karimov Ali"), started_at=now - dt.timedelta(days=1),
                  ended_at=now - dt.timedelta(hours=15, minutes=30))
    current = f.shift(driver=f.driver(full_name="Aliyev Vali"),
                      vehicle=f.vehicle(plate="01A123BC"),
                      started_at=now - dt.timedelta(hours=2, minutes=5))
    r = login_as("dispatcher", language="uz").get(URL)
    assert rows(r) == [current.pk, old.pk]
    body = page(r)
    assert "01 A 123 BC" in body and "Aliyev Vali" in body
    assert 'data-testid="on-shift">1<' in body
    assert "2 soat 5 daqiqa" in body
    assert "8 soat 30 daqiqa" in body
    assert body.count("Smenani tugatish") == 1  # only the open one


def test_filters(login_as):
    now = timezone.now()
    yesterday = timezone.localdate() - dt.timedelta(days=1)
    vali = f.driver(full_name="Aliyev Vali")
    a = f.shift(driver=vali, vehicle=f.vehicle(plate="01A123BC"),
                started_at=now - dt.timedelta(days=1, hours=1),
                ended_at=now - dt.timedelta(days=1))
    b = f.shift(driver=f.driver(full_name="Karimov Ali"), vehicle=f.vehicle(plate="01A777AA"))
    client = login_as("dispatcher")
    assert rows(client.get(URL, {"q": "vali"})) == [a.pk]
    assert rows(client.get(URL, {"q": "777 aa"})) == [b.pk]
    assert rows(client.get(URL, {"open": "1"})) == [b.pk]
    assert rows(client.get(URL, {"day": yesterday.isoformat()})) == [a.pk]
    assert rows(client.get(URL, {"day": "2026-02-30"})) == [b.pk, a.pk]  # ignored


def test_shift_running_over_midnight_shows_on_both_days(login_as):
    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    sh = f.shift(started_at=dt.datetime.combine(today - dt.timedelta(days=1), dt.time(22),
                                                tzinfo=tz),
                 ended_at=dt.datetime.combine(today, dt.time(0, 30), tzinfo=tz))
    client = login_as("dispatcher")
    for day in (today - dt.timedelta(days=1), today):
        assert rows(client.get(URL, {"day": day.isoformat()})) == [sh.pk]
    assert rows(client.get(URL, {"day": (today + dt.timedelta(days=1)).isoformat()})) == []


def test_pages_keep_the_filters(login_as):
    for _ in range(51):
        f.shift(ended_at=timezone.now())
    body = page(login_as("dispatcher").get(URL, {"q": "Driver", "open": ""}))
    assert "?q=Driver&open=&page=2" in body


def test_dispatcher_ends_a_forgotten_shift_and_the_driver_is_told(login_as, sent_by_bot):
    person = f.user(role="driver", language="ru")
    sh = f.shift(driver=f.driver(user=person, full_name="Aliyev Vali"),
                 vehicle=f.vehicle(plate="01A123BC"))
    link_telegram(person, telegram_id=777)
    client = login_as("dispatcher", language="uz")
    r = client.post(f"/shifts/{sh.pk}/end/", {"back": "/shifts/?open=1"}, follow=True)
    assert r.redirect_chain[-1][0] == "/shifts/?open=1"
    assert "Aliyev Vali ning 01 A 123 BC bilan smenasi tugatildi." in page(r)
    sh.refresh_from_db()
    assert sh.ended_at is not None
    log = AuditLog.objects.get()
    assert (log.source, log.actor) == ("web", client.user)
    [(chat, text)] = sent_by_bot
    assert chat == 777
    assert text.startswith("Диспетчер закончил вашу смену на 01 A 123 BC в ")


def test_ending_twice_says_it_is_already_ended(login_as, sent_by_bot):
    sh = f.shift(ended_at=timezone.now())
    r = login_as("dispatcher", language="uz").post(f"/shifts/{sh.pk}/end/", follow=True)
    assert "Bu smena allaqachon tugagan." in page(r)
    assert sent_by_bot == []


def test_back_link_never_leaves_the_site(login_as, sent_by_bot):
    sh = f.shift()
    r = login_as("dispatcher").post(f"/shifts/{sh.pk}/end/", {"back": "https://evil.example/"})
    assert r.url == "/shifts/"


@pytest.mark.parametrize("method", ["get", "post"])
def test_storekeeper_and_get_cannot_end(login_as, method):
    sh = f.shift()
    client = login_as("storekeeper" if method == "post" else "dispatcher")
    r = getattr(client, method)(f"/shifts/{sh.pk}/end/")
    assert r.status_code == (403 if method == "post" else 405)
    sh.refresh_from_db()
    assert sh.is_open


def test_menu_has_shifts_for_managers(login_as):
    assert 'href="/shifts/"' in page(login_as("dispatcher").get("/"))
    assert 'href="/shifts/"' not in page(login_as("storekeeper").get("/"))


# --- live location on the page (Day 9) -------------------------------------

def _share(sh, n_points, open_session=True):
    from django.contrib.gis.geos import Point

    from apps.tracking.models import LiveSession, LocationPoint

    t = sh.started_at
    session = LiveSession.objects.create(
        shift=sh, chat_id=1, message_id=sh.pk, live_period_s=0x7FFFFFFF, started_at=t,
        last_update_at=t, **({} if open_session else {"ended_at": t, "end_reason": "stopped"}))
    for n in range(n_points):
        LocationPoint.objects.create(shift=sh, vehicle=sh.vehicle, session=session,
                                     recorded_at=t + dt.timedelta(seconds=30 * n),
                                     point=Point(69.2 + n / 1000, 41.3))
    return t + dt.timedelta(seconds=30 * (n_points - 1))


def test_location_column_shows_sharing_points_and_last_place(login_as):
    sharing = f.shift()
    last = _share(sharing, 3)
    stopped = f.shift()
    _share(stopped, 1, open_session=False)
    r = login_as("dispatcher", language="uz").get(URL)
    body = page(r)
    assert 'data-testid="sharing">1 / 2<' in body
    row = {s.pk: s for s in r.context["page"]}
    assert (row[sharing.pk].sharing, row[sharing.pk].n_points) == (True, 3)
    assert (row[stopped.pk].sharing, row[stopped.pk].n_points) == (False, 1)
    assert row[sharing.pk].last_point.recorded_at == last
    assert "Ulashmoqda" in body and "Ulashmayapti" in body and "Nuqtalar: 3" in body
    assert "https://www.openstreetmap.org/?mlat=41.300000&mlon=69.202000" in body
    assert f"Oxirgisi: {timezone.localtime(last):%d.%m %H:%M}" in body


def test_ended_shift_shows_points_but_no_sharing_badge(login_as):
    sh = f.shift(ended_at=timezone.now())
    _share(sh, 2, open_session=False)
    body = page(login_as("dispatcher", language="uz").get(URL))
    assert "Nuqtalar: 2" in body
    assert "Ulashmayapti" not in body and "Ulashmoqda" not in body


def test_distance_column_counts_the_clean_track_only(login_as):
    from django.contrib.gis.geos import Point

    from apps.tracking.models import LocationPoint

    sh = f.shift()
    t = sh.started_at
    for n, (meters, speed, valid) in enumerate([(None, None, True), (800.0, 48.0, True),
                                                (9000.0, 900.0, False), (1250.0, 75.0, True)]):
        LocationPoint.objects.create(shift=sh, vehicle=sh.vehicle, point=Point(69.2, 41.3),
                                     recorded_at=t + dt.timedelta(minutes=n),
                                     distance_m=meters, speed_kmh=speed, is_valid=valid)
    r = login_as("dispatcher", language="uz").get(URL)
    assert r.context["page"][0].km == 2.0
    body = page(r)
    assert "2,0 km" in body
    assert "maks. 75 km/soat" in body
    assert "maks. 900" not in body
