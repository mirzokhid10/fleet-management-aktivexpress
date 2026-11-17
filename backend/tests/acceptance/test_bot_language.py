import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bot_helpers import FakeTelegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("bot_language.feature")

LANG = {"Uzbek": "lang:uz", "Russian": "lang:ru"}


@pytest.fixture
def ctx():
    return {}


@given("a driver who has never used the bot")
def new_driver(ctx):
    ctx["tg"] = FakeTelegram(first_name="Vali")


@given(parsers.parse("a driver who chose {language}"))
def chose(ctx, language):
    ctx["tg"] = FakeTelegram(first_name="Vali")
    ctx["tg"].send("/start")
    ctx["tg"].tap(LANG[language])


@when(parsers.parse('they send "{text}"'))
def send(ctx, text):
    ctx["calls"] = ctx["tg"].send(text)


@when(parsers.parse('they tap "{label}"'))
def tap(ctx, label):
    data = dict(FakeTelegram.buttons(ctx["calls"]))[label]
    ctx["calls"] = ctx["tg"].tap(data)


@then(parsers.parse('the bot asks "{text}"'))
def asks(ctx, text):
    assert FakeTelegram.texts(ctx["calls"]) == [text]


@then(parsers.parse('offers the buttons "{labels}"'))
def offers(ctx, labels):
    assert [t for t, _ in FakeTelegram.buttons(ctx["calls"])] == labels.split(", ")


@then(parsers.parse('the bot says "{text}"'))
def says(ctx, text):
    assert any(t.startswith(text) for t in FakeTelegram.texts(ctx["calls"])), \
        FakeTelegram.texts(ctx["calls"])
