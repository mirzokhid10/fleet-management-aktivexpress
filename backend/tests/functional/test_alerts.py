"""Alerts in the managers' group and reminders to drivers (Day 11)."""

import datetime as dt

import pytest
from aiogram.methods import SendMessage
from asgiref.sync import async_to_sync
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.bot import alerts
from apps.bot.models import BotGroup
from apps.core.admin import CompanySettingsForm
from apps.core.models import CompanySettings
from apps.tracking.models import LiveSession, LocationPoint
from tests import factories as f
from tests.bot_helpers import FakeTelegram, RecordingSession, link_telegram

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

GROUP = -100123


@pytest.fixture
def group():
    BotGroup.objects.create(chat_id=GROUP, title="Aktiv dispetcherlar")
    cs = CompanySettings.load()
    cs.alert_chat_id = GROUP
    cs.save()
    return GROUP


@pytest.fixture
def bot():
    from apps.bot.setup import build_bot
    from tests.bot_helpers import TOKEN

    session = RecordingSession()
    b = build_bot(TOKEN, session=session)
    b.calls = session.calls
    return b


def sent(bot):
    return [(c.chat_id, c.text) for c in bot.calls if isinstance(c, SendMessage)]


def driver_off_for(minutes, language="ru", point=True):
    person = f.user(role="driver", language=language, telegram_id=777)
    sh = f.shift(driver=f.driver(user=person, full_name="Aliyev Vali"),
                 vehicle=f.vehicle(plate="01A123BC"),
                 started_at=timezone.now() - dt.timedelta(hours=1))
    if point:
        at = (timezone.now() - dt.timedelta(minutes=minutes)).replace(second=0, microsecond=0)
        s = LiveSession.objects.create(shift=sh, chat_id=777, message_id=1,
                                       live_period_s=0x7FFFFFFF, started_at=at, last_update_at=at,
                                       ended_at=at, end_reason="stopped")
        LocationPoint.objects.create(shift=sh, vehicle=sh.vehicle, session=s, recorded_at=at,
                                     point=Point(69.279737, 41.311081))
    return sh


def test_group_and_driver_are_told(bot, group):
    driver_off_for(12)
    async_to_sync(alerts.check_once)(bot)
    (g_chat, g_text), (d_chat, d_text) = sent(bot)
    assert g_chat == GROUP
    assert g_text.startswith("⚠️ Aliyev Vali · 01 A 123 BC: joylashuv 12 daqiqadan beri o'chiq (")
    assert ("Oxirgi joy: https://www.openstreetmap.org/?mlat=41.311081&mlon=69.279737"
            in g_text)
    assert d_chat == 777
    assert d_text.startswith("⚠️ Ваша геопозиция выключена уже 12 мин. Диспетчер уведомлён.\n")
    # nothing new on the next round
    async_to_sync(alerts.check_once)(bot)
    assert len(sent(bot)) == 2


def test_never_shared_says_so(bot, group):
    driver_off_for(0, point=False)
    async_to_sync(alerts.check_once)(bot)
    assert "Smena boshlanganidan beri joylashuv yo'q." in sent(bot)[0][1]


def test_back_on_is_posted_to_the_group_only(bot, group):
    sh = driver_off_for(15)
    async_to_sync(alerts.check_once)(bot)
    now = timezone.now()
    LiveSession.objects.create(shift=sh, chat_id=777, message_id=2, live_period_s=0x7FFFFFFF,
                               started_at=now, last_update_at=now)
    async_to_sync(alerts.check_once)(bot)
    chat, text = sent(bot)[-1]
    assert chat == GROUP
    assert text == ("✅ Aliyev Vali · 01 A 123 BC: joylashuv yana yoqildi (15 daqiqa o'chiq "
                    "edi).")


def test_without_a_group_the_driver_is_still_reminded(bot, caplog):
    driver_off_for(12)
    async_to_sync(alerts.check_once)(bot)
    assert [c for c, _ in sent(bot)] == [777]
    assert "no alert group in Company settings" in caplog.text


def test_a_failed_send_does_not_stop_the_others(group):
    class Failing(RecordingSession):
        async def make_request(self, bot, method, timeout=None):
            if isinstance(method, SendMessage) and method.chat_id == GROUP:
                raise RuntimeError("group gone")
            return await super().make_request(bot, method, timeout)

    from apps.bot.setup import build_bot
    session = Failing()
    driver_off_for(12)
    async_to_sync(alerts.check_once)(build_bot("42:T", session=session))
    assert [c.chat_id for c in session.calls if isinstance(c, SendMessage)] == [777]


def test_adding_the_bot_to_a_group_remembers_it_and_says_hello():
    tg = FakeTelegram()
    calls = tg.bot_in_group(-100555, "Dispetcherlar")
    assert FakeTelegram.texts(calls) == [
        "Salom! Direktor bu guruhni kompaniya sozlamalarida tanlagach, ogohlantirishlarni shu "
        "yerga yuboraman."]
    g = BotGroup.objects.get()
    assert (g.chat_id, g.title, g.is_member) == (-100555, "Dispetcherlar", True)
    tg.bot_in_group(-100555, "Dispetcherlar", added=False)
    g.refresh_from_db()
    assert g.is_member is False


def test_settings_offer_only_groups_the_bot_is_in():
    BotGroup.objects.create(chat_id=-1, title="Dispetcherlar")
    BotGroup.objects.create(chat_id=-2, title="Old group", is_member=False)
    form = CompanySettingsForm(instance=CompanySettings.load())
    assert form.fields["alert_chat_id"].choices == [("", "— none —"), (-1, "Dispetcherlar")]


def test_settings_save_the_chosen_group():
    BotGroup.objects.create(chat_id=-1, title="Dispetcherlar")
    cs = CompanySettings.load()
    data = {k: getattr(cs, k) for k in ("work_start", "work_end", "work_days",
                                        "speed_limit_city_kmh", "speed_limit_highway_kmh",
                                        "retention_months", "daily_reminder_at",
                                        "stop_alert_minutes")}
    form = CompanySettingsForm({**data, "alert_chat_id": "-1"}, instance=cs)
    assert form.is_valid(), form.errors
    form.save()
    assert CompanySettings.load().alert_chat_id == -1


def test_admin_shows_the_group_picker(client):
    admin = f.user(role="director", is_staff=True, is_superuser=True)
    BotGroup.objects.create(chat_id=-1, title="Dispetcherlar")
    CompanySettings.load()
    client.force_login(admin)
    body = client.get("/admin/core/companysettings/1/change/").content.decode()
    assert "Dispetcherlar" in body and "Alert group" in body


def test_driver_linked_to_telegram_gets_the_reminder(bot, group):
    person = f.user(role="driver", language="uz")
    link_telegram(person, telegram_id=888)
    f.shift(driver=f.driver(user=person), started_at=timezone.now() - dt.timedelta(minutes=20))
    async_to_sync(alerts.check_once)(bot)
    assert [c for c, _ in sent(bot)] == [GROUP, 888]
