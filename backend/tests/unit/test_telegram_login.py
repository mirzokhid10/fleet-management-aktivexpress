"""Sign in to the web by confirming in the bot (Day 7)."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts import telegram_login as tl
from apps.accounts.models import TelegramLogin
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

CHROME_WINDOWS = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def test_a_new_sign_in_has_a_secret_token_and_a_two_digit_number():
    login = tl.start(CHROME_WINDOWS, "127.0.0.1")
    assert len(login.token) == 43 and 10 <= login.code <= 99
    assert login.browser == "Chrome · Windows"
    assert dt.timedelta(minutes=2) < login.expires_at - timezone.now() <= tl.LIFETIME


@pytest.mark.parametrize("ua, shown", [
    ("Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36", "Chrome · Android"),
    ("Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36 Edg/130.0", "Edge · Windows"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Version/17.0 Safari/605.1.15",
     "Safari · macOS"),
    ("", ""),
])
def test_browser_is_described_plainly(ua, shown):
    assert tl._browser(ua) == shown


def test_deep_link_uses_the_bot_username():
    login = tl.start()
    assert tl.deep_link(login) == f"https://t.me/fleet_test_bot?start=login_{login.token}"


def test_opening_the_link_offers_three_numbers_including_the_right_one():
    login = tl.start()
    opened = tl.open_link(login.token, f.user(role="dispatcher"))
    assert opened.result == tl.OK
    assert login.code in opened.numbers and len(set(opened.numbers)) == 3


@pytest.mark.parametrize("who, result", [(None, tl.NOT_REGISTERED), ("driver", tl.NOT_STAFF)])
def test_only_registered_staff_may_confirm(who, result):
    user = f.user(role=who) if who else None
    assert tl.open_link(tl.start().token, user).result == result


def test_expired_or_unknown_links_are_refused():
    login = tl.start()
    TelegramLogin.objects.filter(pk=login.pk).update(expires_at=timezone.now())
    assert tl.open_link(login.token, f.user()).result == tl.EXPIRED
    assert tl.open_link("nope", f.user()).result == tl.EXPIRED


def test_right_number_signs_in_once():
    login, user = tl.start(), f.user(role="storekeeper")
    assert tl.status(login.pk) == ("pending", None)
    assert tl.pick(login.pk, user, login.code) == tl.OK
    assert tl.status(login.pk) == ("approved", user)
    assert tl.status(login.pk) == (tl.EXPIRED, None)  # used


def test_wrong_number_cancels_the_sign_in():
    login, user = tl.start(), f.user()
    wrong = 10 if login.code != 10 else 11
    assert tl.pick(login.pk, user, wrong) == tl.WRONG_NUMBER
    assert tl.status(login.pk) == ("denied", None)
    assert tl.pick(login.pk, user, login.code) == tl.EXPIRED  # no second chance


def test_it_wasnt_me_cancels_the_sign_in():
    login = tl.start()
    assert tl.pick(login.pk, f.user(), None) == tl.DENIED
    assert tl.status(login.pk)[0] == "denied"


def test_approval_is_rechecked_when_the_browser_collects_it():
    login, user = tl.start(), f.user(role="dispatcher")
    tl.pick(login.pk, user, login.code)
    user.is_active = False
    user.save()
    assert tl.status(login.pk) == (tl.EXPIRED, None)


def test_status_of_nothing_is_expired():
    assert tl.status(None) == (tl.EXPIRED, None)
