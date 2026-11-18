"""Registration in the bot and the New users page (Day 7)."""

import datetime as dt
import html

import pytest
from aiogram.methods import SendMessage
from aiogram.types import Contact

from apps.bot.models import BotUser, RegistrationRequest
from tests import factories as f
from tests.bot_helpers import FakeTelegram, _ids

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

T = FakeTelegram
PHONE = "+998901234567"


def share(tg: FakeTelegram, phone: str = "998901234567", user_id: int | None = None):
    from aiogram.types import Message, Update
    start = len(tg.session.calls)
    msg = Message(message_id=next(_ids), date=dt.datetime.now(dt.UTC), chat=tg.chat,
                  from_user=tg.user, contact=Contact(phone_number=phone, first_name="X",
                                                     user_id=user_id or tg.user.id))
    tg._feed(Update(update_id=next(_ids), message=msg))
    return tg.session.calls[start:]


def registered_language(tg, code="uz"):
    tg.send("/start")
    return tg.tap(f"lang:{code}")


def page(response) -> str:
    return html.unescape(response.content.decode())


# --- bot -------------------------------------------------------------------

def test_after_choosing_a_language_the_bot_asks_for_the_phone():
    calls = registered_language(FakeTelegram())
    asks = [c for c in calls if isinstance(c, SendMessage) and c.reply_markup is not None]
    button = asks[-1].reply_markup.keyboard[0][0]
    assert button.request_contact is True
    assert button.text == "📱 Telefon raqamimni yuborish"


def test_someone_elses_contact_is_refused():
    tg = FakeTelegram()
    registered_language(tg)
    calls = share(tg, user_id=999)
    assert T.texts(calls) == ["Iltimos, tugma orqali o'z raqamingizni yuboring."]
    assert not RegistrationRequest.objects.exists()


def test_unknown_number_is_told_to_ask_the_dispatcher():
    tg = FakeTelegram()
    registered_language(tg, "ru")
    calls = share(tg)
    assert T.texts(calls) == ["Номера +998901234567 нет в списке компании. Попросите "
                              "диспетчера добавить вас, затем отправьте его снова через /start."]


def test_foreign_number_is_refused():
    tg = FakeTelegram()
    registered_language(tg)
    assert "+998" in T.texts(share(tg, phone="+79161234567"))[0]


def test_known_driver_waits_for_a_manager():
    f.driver(phone=PHONE)
    tg = FakeTelegram()
    registered_language(tg)
    assert T.texts(share(tg))[0].startswith("Rahmat!")
    assert RegistrationRequest.objects.get().status == "pending"
    assert T.texts(tg.send("/start")) == [
        "Ro'yxatdan o'tishingiz rahbar tasdig'ini kutmoqda. Shu yerda sizga yozaman."]


# --- web -------------------------------------------------------------------

def pending_request(phone=PHONE, staff_role=None, telegram_id=1001):
    person = f.user(role=staff_role, phone=phone) if staff_role else f.driver(phone=phone)
    bu = BotUser.objects.create(telegram_id=telegram_id, language="ru", first_name="Vali",
                                username="vali90")
    return RegistrationRequest.objects.create(
        bot_user=bu, phone=phone, **({"staff": person} if staff_role else {"driver": person}))


def test_storekeeper_cannot_open_the_page(login_as):
    assert login_as("storekeeper").get("/users/requests/").status_code == 403


def test_dispatcher_sees_drivers_but_not_staff(login_as):
    driver_req = pending_request()
    staff_req = pending_request("+998901111111", staff_role="storekeeper", telegram_id=2)
    text = page(login_as("dispatcher").get("/users/requests/"))
    assert f'data-request="{driver_req.pk}"' in text and "@vali90" in text
    assert f'data-request="{staff_req.pk}"' not in text


def test_dispatcher_confirms_a_driver_and_the_bot_tells_them(login_as, sent_by_bot):
    req = pending_request()
    client = login_as("dispatcher")
    response = client.post(f"/users/requests/{req.pk}/approve/", follow=True)
    assert "ro'yxatdan o'tdi" in page(response)
    assert sent_by_bot == [(1001, f"✅ Регистрация подтверждена. Добро пожаловать, "
                                  f"{req.driver.full_name.split()[0]}!")]
    req.refresh_from_db()
    assert req.status == "approved" and req.driver.user.telegram_id == 1001
    assert "Nobody" not in page(response) and 'data-testid="recent"' in page(response)


def test_dispatcher_cannot_confirm_staff(login_as, sent_by_bot):
    req = pending_request(staff_role="director")
    assert login_as("dispatcher").post(f"/users/requests/{req.pk}/approve/").status_code == 403
    assert sent_by_bot == []


def test_reject_sends_the_result(login_as, sent_by_bot):
    req = pending_request()
    login_as("director").post(f"/users/requests/{req.pk}/reject/", {"reason": "wrong_person"})
    req.refresh_from_db()
    assert (req.status, req.reject_reason) == ("rejected", "wrong_person")
    assert sent_by_bot[0][1].startswith("❌ Регистрация не подтверждена.")


def test_deciding_twice_is_refused_politely(login_as, sent_by_bot):
    req = pending_request()
    client = login_as("director")
    client.post(f"/users/requests/{req.pk}/approve/")
    response = client.post(f"/users/requests/{req.pk}/reject/", follow=True)
    assert "allaqachon hal qilingan" in page(response)
    req.refresh_from_db()
    assert req.status == "approved"


def test_approval_stands_when_telegram_is_down(login_as, monkeypatch):
    async def broken(chat_id, text):
        raise ConnectionError("telegram down")

    monkeypatch.setattr("apps.bot.notify._send", broken)
    req = pending_request()
    response = login_as("director").post(f"/users/requests/{req.pk}/approve/", follow=True)
    assert "Bot unga xabar yubora olmadi." in page(response)
    req.refresh_from_db()
    assert req.status == "approved"
