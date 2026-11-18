"""Live location in the bot (Day 9)."""

import datetime as dt

import pytest

from apps.tracking.models import LiveSession, LocationPoint
from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

T = FakeTelegram
HOW = ("Jonli joylashuvni ulashing: 📎 ni bosing, «Joylashuv»ni tanlang, so'ng «Jonli "
       "joylashuvni ulashish» va «O'chirmagunimcha»ni tanlang.")


def a_driver(language="uz"):
    person = f.user(role="driver", first_name="Vali", language=language)
    d = f.driver(user=person, full_name="Aliyev Vali")
    return d, link_telegram(person)


def on_shift(language="uz"):
    d, tg = a_driver(language)
    v = f.vehicle(plate="01A123BC")
    tg.send("/start_shift")
    calls = tg.tap(f"shift:take:{v.pk}")
    return d, tg, calls


def test_shift_start_asks_for_live_location():
    _, _, calls = on_shift()
    text = T.texts(calls)[0]
    assert HOW in text
    assert text.endswith("Ishni tugatganingizda /end_shift yuboring.")


def test_sharing_says_once_that_location_is_on_then_stays_quiet():
    d, tg, _ = on_shift()
    t0 = dt.datetime.now(dt.UTC)
    message_id, calls = tg.share_location(41.311, 69.279, at=t0, horizontal_accuracy=8)
    assert T.texts(calls) == ["📍 Joylashuvingiz yoqildi. /end_shift gacha o'chirmang."]
    for n in range(1, 4):
        at = t0 + dt.timedelta(seconds=30 * n)
        assert T.texts(tg.move(message_id, 41.311 + n / 1000, 69.279, at=at, started=t0)) == []
    shift = d.shifts.get()
    assert shift.points.count() == 4
    assert LiveSession.objects.get().shift == shift


def test_stopping_is_noticed_and_explained():
    _, tg, _ = on_shift(language="ru")
    message_id, _ = tg.share_location(41.3, 69.2)
    calls = tg.move(message_id, 41.301, 69.2, live_period=None)
    assert T.texts(calls) == [
        "⚠️ Вы остановили трансляцию геопозиции. Пока вы на смене, включите её снова.\n"
        "Включите трансляцию геопозиции: нажмите 📎, выберите «Геопозиция», затем "
        "«Транслировать геопозицию» и «Пока не выключу»."]
    assert LiveSession.objects.get().end_reason == "stopped"


def test_one_time_location_gets_instructions():
    _, tg, _ = on_shift()
    _, calls = tg.share_location(41.3, 69.2, live_period=None)
    assert T.texts(calls) == ["Bu bir martalik joylashuv. Menga jonli joylashuv kerak.\n" + HOW]
    assert not LocationPoint.objects.exists()


def test_location_without_a_shift():
    _, tg = a_driver()
    _, calls = tg.share_location(41.3, 69.2)
    assert T.texts(calls) == [
        "Avval /start_shift bilan smenani boshlang, keyin jonli joylashuvni ulashing."]
    assert not LocationPoint.objects.exists()


def test_share_started_early_counts_once_the_shift_starts():
    d, tg = a_driver()
    message_id, _ = tg.share_location(41.3, 69.2)
    v = f.vehicle()
    tg.send("/start_shift")
    tg.tap(f"shift:take:{v.pk}")
    calls = tg.move(message_id, 41.301, 69.2)
    assert T.texts(calls) == ["📍 Joylashuvingiz yoqildi. /end_shift gacha o'chirmang."]
    assert d.shifts.get().points.count() == 1


def test_end_shift_says_location_can_be_turned_off_and_drops_later_points():
    d, tg, _ = on_shift()
    message_id, _ = tg.share_location(41.3, 69.2)
    shift = d.shifts.get()
    tg.send("/end_shift")
    done = T.texts(tg.tap(f"shift:end:{shift.pk}"))[0]
    assert done.endswith("Endi joylashuvni ulashishni to'xtatishingiz mumkin.")
    assert LiveSession.objects.get().end_reason == "shift_ended"
    assert T.texts(tg.move(message_id, 41.302, 69.2)) == []
    assert shift.points.count() == 1


def test_points_use_telegram_times():
    d, tg, _ = on_shift()
    t0 = dt.datetime(2026, 11, 18, 5, 0, tzinfo=dt.UTC)
    message_id, _ = tg.share_location(41.3, 69.2, at=t0)
    tg.move(message_id, 41.301, 69.2, at=t0 + dt.timedelta(seconds=30), started=t0)
    assert [p.recorded_at for p in d.shifts.get().points.all()] == [
        t0, t0 + dt.timedelta(seconds=30)]


def test_staff_and_strangers_are_not_tracked():
    staff = link_telegram(f.user(role="dispatcher", language="uz"))
    _, calls = staff.share_location(41.3, 69.2)
    assert T.texts(calls) == ["Smenalar faqat haydovchilar uchun."]
    stranger = FakeTelegram(telegram_id=4242)
    stranger.send("/start")
    stranger.tap("lang:uz")
    _, calls = stranger.share_location(41.3, 69.2)
    assert T.texts(calls)[0].startswith("Siz hali ro'yxatdan o'tmagansiz.")
    assert not LocationPoint.objects.exists()
