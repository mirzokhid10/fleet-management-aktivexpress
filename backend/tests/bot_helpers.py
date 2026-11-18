"""Drive the bot in tests without Telegram: fake updates in, recorded API calls out."""

from __future__ import annotations

import datetime as dt
import itertools
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (AnswerCallbackQuery, EditMessageText, SendMessage, TelegramMethod)
from aiogram.types import CallbackQuery, Chat, Location, Message, Update, User
from asgiref.sync import async_to_sync

from apps.bot.setup import build_bot, build_dispatcher

_ids = itertools.count(1)
TOKEN = "42:TEST-TOKEN"


class RecordingSession(BaseSession):
    """Answers every Bot API call locally and remembers it."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None):
        self.calls.append(method)
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=next(_ids), date=dt.datetime.now(dt.UTC),
                           chat=Chat(id=method.chat_id or 0, type="private"), text=method.text)
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):
        yield b""


class FakeTelegram:
    """One person chatting with the bot."""

    def __init__(self, telegram_id: int = 1001, first_name: str = "Vali",
                 language_code: str | None = "uz", **user: Any) -> None:
        self.session = RecordingSession()
        self.bot = build_bot(TOKEN, session=self.session)
        self.dp = build_dispatcher()
        self.user = User(id=telegram_id, is_bot=False, first_name=first_name,
                         language_code=language_code, **user)
        self.chat = Chat(id=telegram_id, type="private")
        self.last_bot_message: Message | None = None

    def _feed(self, update: Update) -> None:
        async_to_sync(self.dp.feed_update)(self.bot, update)

    def send(self, text: str) -> list[TelegramMethod]:
        start = len(self.session.calls)
        message = Message(message_id=next(_ids), date=dt.datetime.now(dt.UTC), chat=self.chat,
                          from_user=self.user, text=text)
        self._feed(Update(update_id=next(_ids), message=message))
        return self.session.calls[start:]

    def tap(self, data: str) -> list[TelegramMethod]:
        """Tap an inline button on the bot's last message."""
        start = len(self.session.calls)
        on = Message(message_id=next(_ids), date=dt.datetime.now(dt.UTC), chat=self.chat,
                     text="…")
        query = CallbackQuery(id=str(next(_ids)), from_user=self.user, chat_instance="1",
                              data=data, message=on)
        self._feed(Update(update_id=next(_ids), callback_query=query))
        return self.session.calls[start:]

    # --- live location (Day 9) ---
    LIVE = 0x7FFFFFFF  # "until I turn it off"

    def share_location(self, lat: float, lon: float, live_period: int | None = LIVE,
                       at: dt.datetime | None = None, **loc: Any) -> tuple[int, list]:
        """Share a location; live unless live_period=None. Returns (message_id, calls)."""
        start = len(self.session.calls)
        message_id = next(_ids)
        message = Message(message_id=message_id, date=at or dt.datetime.now(dt.UTC),
                          chat=self.chat, from_user=self.user,
                          location=Location(latitude=lat, longitude=lon,
                                            live_period=live_period, **loc))
        self._feed(Update(update_id=next(_ids), message=message))
        return message_id, self.session.calls[start:]

    def move(self, message_id: int, lat: float, lon: float, live_period: int | None = LIVE,
             at: dt.datetime | None = None, started: dt.datetime | None = None,
             **loc: Any) -> list:
        """Telegram's edit of a live location. live_period=None: the driver stopped it."""
        start = len(self.session.calls)
        now = dt.datetime.now(dt.UTC)
        message = Message(message_id=message_id, date=started or now - dt.timedelta(minutes=1),
                          edit_date=int((at or now).timestamp()), chat=self.chat, from_user=self.user,
                          location=Location(latitude=lat, longitude=lon,
                                            live_period=live_period, **loc))
        self._feed(Update(update_id=next(_ids), edited_message=message))
        return self.session.calls[start:]

    # what the person sees
    @staticmethod
    def texts(calls) -> list[str]:
        return [c.text for c in calls if isinstance(c, (SendMessage, EditMessageText))]

    @staticmethod
    def buttons(calls) -> list[tuple[str, str]]:
        out = []
        for c in calls:
            markup = getattr(c, "reply_markup", None)
            for row in getattr(markup, "inline_keyboard", []) or []:
                out += [(b.text, b.callback_data) for b in row]
        return out

    @staticmethod
    def popups(calls) -> list[str]:
        return [c.text for c in calls if isinstance(c, AnswerCallbackQuery) and c.text]


# --- staff with Telegram (Day 7) -------------------------------------------

def link_telegram(user, telegram_id: int | None = None) -> FakeTelegram:
    """An approved registration: user's Telegram is linked to the bot."""
    from apps.bot.models import BotUser

    telegram_id = telegram_id or 500_000 + user.pk
    BotUser.objects.create(telegram_id=telegram_id, user=user, language=user.language,
                           first_name=user.first_name)
    user.telegram_id = telegram_id
    user.save(update_fields=["telegram_id"])
    return FakeTelegram(telegram_id=telegram_id, first_name=user.first_name or "Staff",
                        language_code=user.language)


def telegram_sign_in(client, tg: FakeTelegram, next: str = "", pick: str = "right"):
    """The whole browser + bot dance. Returns the browser's last status response."""
    client.post("/accounts/login/telegram/start/", {"next": next})
    login = client.get("/accounts/login/telegram/").context["login"]
    calls = tg.send(f"/start login_{login.token}")
    buttons = dict(FakeTelegram.buttons(calls))
    if buttons:
        wrong = [t for t in buttons if t.isdigit() and t != str(login.code)][0]
        refuse = [t for t in buttons if not t.isdigit()][0]
        label = {"right": str(login.code), "wrong": wrong, "no": refuse}[pick]
        tg.tap(buttons[label])
    return client.get("/accounts/login/telegram/status/")
