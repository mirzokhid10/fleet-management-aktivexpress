"""Sign in to the web by confirming in the Telegram bot (Day 7).

Browser                                   Bot
  "Sign in with Telegram" -> start()
  shows number 47, link + QR   ------->   /start login_<token>  -> open()
                                          "Tap the number on your screen": 12 47 83
  polls status() every 2 s                tap 47 -> pick()  (wrong number = denied)
  approved -> signed in, used once

Number matching stops a phishing trick: someone sends a staff member their own
sign-in link; the staff member cannot see the attacker's screen, so cannot
pick the right number.
"""

from __future__ import annotations

import datetime as dt
import random
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import TelegramLogin, User
from .roles import can_use_web

LIFETIME = dt.timedelta(minutes=3)
START_PREFIX = "login_"
_rng = random.SystemRandom()

# Results of open() / pick(), for the bot to word.
OK, EXPIRED, NOT_REGISTERED, NOT_STAFF, WRONG_NUMBER, DENIED = (
    "ok", "expired", "not_registered", "not_staff", "wrong_number", "denied")


def _browser(user_agent: str) -> str:
    ua = user_agent or ""
    name = next((n for key, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("YaBrowser", "Yandex"),
                                  ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
                                  ("Safari/", "Safari")) if key in ua), "")
    system = next((n for key, n in (("Windows", "Windows"), ("Android", "Android"),
                                    ("iPhone", "iPhone"), ("Mac OS", "macOS"),
                                    ("Linux", "Linux")) if key in ua), "")
    return " · ".join(p for p in (name, system) if p)[:200]


def start(user_agent: str = "", ip: str | None = None) -> TelegramLogin:
    return TelegramLogin.objects.create(
        token=secrets.token_urlsafe(32), code=_rng.randint(10, 99),
        expires_at=timezone.now() + LIFETIME, browser=_browser(user_agent), ip=ip)


def bot_username() -> str:
    """From settings, or asked from Telegram once and cached for a day."""
    if settings.TELEGRAM_BOT_USERNAME:
        return settings.TELEGRAM_BOT_USERNAME

    def ask() -> str:
        from asgiref.sync import async_to_sync

        from apps.bot.setup import build_bot

        async def get() -> str:
            bot = build_bot()
            try:
                return (await bot.get_me()).username
            finally:
                await bot.session.close()

        return async_to_sync(get)()

    return cache.get_or_set("telegram_bot_username", ask, 24 * 3600)


def deep_link(login: TelegramLogin) -> str:
    return f"https://t.me/{bot_username()}?start={START_PREFIX}{login.token}"


def _alive(qs):
    return qs.filter(status=TelegramLogin.Status.PENDING, expires_at__gt=timezone.now())


@dataclass(frozen=True)
class Opened:
    result: str
    login: TelegramLogin | None = None
    numbers: tuple[int, ...] = ()


def _check_person(user: User | None) -> str:
    if user is None:
        return NOT_REGISTERED
    if not (user.is_active and can_use_web(user)):
        return NOT_STAFF
    return OK


def open_link(token: str, user: User | None) -> Opened:
    """The person opened the deep link in the bot."""
    login = _alive(TelegramLogin.objects).filter(token=token).first()
    if login is None:
        return Opened(EXPIRED)
    result = _check_person(user)
    if result != OK:
        return Opened(result)
    others = _rng.sample([n for n in range(10, 100) if n != login.code], 2)
    return Opened(OK, login, tuple(sorted([login.code, *others])))


def pick(login_id: int, user: User | None, number: int | None) -> str:
    """The person tapped a number (or None for "it wasn't me")."""
    login = _alive(TelegramLogin.objects).filter(pk=login_id).first()
    if login is None:
        return EXPIRED
    result = _check_person(user)
    if result != OK:
        return result
    login.decided_at = timezone.now()
    if number is None or number != login.code:
        login.status = TelegramLogin.Status.DENIED
        login.save(update_fields=["status", "decided_at"])
        return DENIED if number is None else WRONG_NUMBER
    login.status, login.user = TelegramLogin.Status.APPROVED, user
    login.save(update_fields=["status", "user", "decided_at"])
    return OK


def status(login_id: int | None) -> tuple[str, User | None]:
    """For the polling browser: pending / approved / denied / expired."""
    login = TelegramLogin.objects.select_related("user").filter(pk=login_id).first()
    if login is None:
        return EXPIRED, None
    if login.status == TelegramLogin.Status.APPROVED:
        # Approved logins are still checked: the role may have changed meanwhile.
        if login.expires_at <= timezone.now() or _check_person(login.user) != OK:
            return EXPIRED, None
        # Used once: of two polls arriving together, only one signs in.
        used = TelegramLogin.objects.filter(pk=login.pk, status=TelegramLogin.Status.APPROVED) \
            .update(status=TelegramLogin.Status.USED)
        return ("approved", login.user) if used else (EXPIRED, None)
    if login.status == TelegramLogin.Status.PENDING:
        return ("pending" if login.expires_at > timezone.now() else EXPIRED), None
    return ("denied" if login.status == TelegramLogin.Status.DENIED else EXPIRED), None
