"""Sign in to the web through the bot, end to end (Day 7)."""

import pytest
from django.conf import settings

from apps.accounts.models import TelegramLogin
from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram, telegram_sign_in

pytestmark = [pytest.mark.functional, pytest.mark.django_db]


def test_the_button_leads_to_a_page_with_number_link_and_qr(client):
    response = client.post("/accounts/login/telegram/start/", follow=True)
    login = TelegramLogin.objects.get()
    text = response.content.decode()
    assert f'data-testid="login-code" aria-live="polite">{login.code}<' in text
    assert f"https://t.me/fleet_test_bot?start=login_{login.token}" in text
    assert "<svg" in text and 'data-testid="qr"' in text


def test_staff_sign_in_lands_where_they_were_going(client):
    user = f.user(role="storekeeper", language="ru", first_name="Sergey")
    tg = link_telegram(user)
    status = telegram_sign_in(client, tg, next="/vehicles/")
    assert status.json() == {"status": "ok", "next": "/vehicles/"}
    assert status.cookies[settings.LANGUAGE_COOKIE_NAME].value == "ru"
    assert client.get("/").status_code == 200
    assert FakeTelegram.texts(tg.session.calls)[-1] == "✅ Вы вошли. Можно вернуться в браузер."


def test_foreign_next_is_ignored(client):
    tg = link_telegram(f.user(role="dispatcher"))
    assert telegram_sign_in(client, tg, next="https://evil.example/").json()["next"] == "/"


@pytest.mark.parametrize("pick, bot_says", [
    ("wrong", "❌ Noto'g'ri raqam."), ("no", "❌ Kirish bekor qilindi.")])
def test_wrong_number_or_refusal_keeps_the_browser_out(client, pick, bot_says):
    tg = link_telegram(f.user(role="dispatcher"))
    status = telegram_sign_in(client, tg, pick=pick)
    assert status.json() == {"status": "denied"}
    assert FakeTelegram.texts(tg.session.calls)[-1].startswith(bot_says)
    assert client.get("/").status_code == 302


def test_unregistered_telegram_cannot_confirm(client):
    tg = FakeTelegram(telegram_id=4242)
    status = telegram_sign_in(client, tg)
    assert status.json() == {"status": "pending"}
    assert "Siz hali ro'yxatdan o'tmagansiz" in FakeTelegram.texts(tg.session.calls)[-1]


def test_driver_cannot_sign_in_to_the_web(client):
    tg = link_telegram(f.user(role="driver"))
    assert telegram_sign_in(client, tg).json() == {"status": "pending"}
    assert "Haydovchilar faqat shu botda ishlaydi." in FakeTelegram.texts(tg.session.calls)[-1]


def test_waiting_page_without_a_sign_in_goes_back_to_login(client):
    response = client.get("/accounts/login/telegram/")
    assert response.status_code == 302 and response["Location"] == "/accounts/login/"
    assert client.get("/accounts/login/telegram/status/").json() == {"status": "expired"}


def test_start_needs_post(client):
    assert client.get("/accounts/login/telegram/start/").status_code == 405
