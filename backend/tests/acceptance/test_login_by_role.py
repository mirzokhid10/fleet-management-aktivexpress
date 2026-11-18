import html
import re

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram, telegram_sign_in

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("login_by_role.feature")

@pytest.fixture
def ctx(client):
    return {"client": client}


def _account(ctx, role, language="uz"):
    user = f.user(role=role, language=language, first_name="Ali")
    ctx["user"] = user
    ctx["tg"] = link_telegram(user)


def _labels(response) -> list[str]:
    page = html.unescape(response.content.decode())
    return re.findall(r'data-menu="[^"]+"[\s\S]*?class="menu-item-text"[^>]*>([^<]+)<', page)


def _split(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip() not in ("", "-")]


@given(parsers.parse("a {role} account that prefers Russian"))
def russian_account(ctx, role):
    _account(ctx, role, language="ru")


@given(parsers.parse("a {role} account"))
def account(ctx, role):
    _account(ctx, role)


@when("they sign in with Telegram")
def sign_in(ctx):
    client = ctx["client"]
    ctx["status"] = telegram_sign_in(client, ctx["tg"])
    ctx["bot_said"] = FakeTelegram.texts(ctx["tg"].session.calls)
    data = ctx["status"].json()
    ctx["response"] = client.get(data["next"]) if data["status"] == "ok" else \
        client.get("/accounts/login/")


@when("they switch the language to Russian")
def switch_to_russian(ctx):
    ctx["client"].post("/accounts/language/", {"language": "ru", "next": "/"})


@when("they log out and sign in again")
def log_out_and_in(ctx):
    client = ctx["client"]
    client.post("/accounts/logout/")
    client.cookies.clear()  # a different browser: only the saved preference remains
    sign_in(ctx)


@when("someone opens the dashboard without signing in")
def open_anonymously(ctx):
    ctx["response"] = ctx["client"].get("/")


@then("they land on the dashboard")
def on_dashboard(ctx):
    assert ctx["status"].json() == {"status": "ok", "next": "/"}
    assert ctx["response"].status_code == 200


@then(parsers.parse('the menu shows "{labels}"'))
def menu_shows(ctx, labels):
    shown = _labels(ctx["response"])
    for label in _split(labels):
        assert label in shown, f"{label} not in {shown}"


@then(parsers.parse('the menu does not show "{labels}"'))
def menu_hides(ctx, labels):
    shown = _labels(ctx["response"])
    for label in _split(labels):
        assert label not in shown, f"{label} should be hidden"


@then("they stay on the sign-in page")
def still_on_login(ctx):
    assert ctx["response"].request["PATH_INFO"] == "/accounts/login/"
    assert "_auth_user_id" not in ctx["client"].session


@then(parsers.parse('the bot tells them "{text}"'))
def bot_tells(ctx, text):
    assert any(text in t for t in ctx["bot_said"]), ctx["bot_said"]


@then("they are sent to the sign-in page")
def sent_to_login(ctx):
    assert ctx["response"].status_code == 302
    assert ctx["response"]["Location"].startswith("/accounts/login/")
