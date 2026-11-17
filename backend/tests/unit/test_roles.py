"""Roles, menu visibility and translations (Day 4)."""

import re
from pathlib import Path

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from apps.accounts.forms import StaffLoginForm
from apps.accounts.models import User
from apps.accounts.roles import can_use_web, has_role
from apps.core.menu import menu_for

pytestmark = pytest.mark.unit

LOCALE = Path(__file__).resolve().parents[2] / "locale"


def keys(user):
    return [item.key for group in menu_for(user) for item in group.items]


EVERYTHING = ["dashboard", "map", "trips", "approvals", "vehicles", "drivers", "fuel",
              "maintenance", "store", "documents", "reports", "settings"]


@pytest.mark.parametrize("role, expected", [
    ("director", EVERYTHING),
    ("dispatcher", [k for k in EVERYTHING if k != "settings"]),
    ("storekeeper", ["dashboard", "approvals", "maintenance", "store", "reports"]),
    ("driver", []),
])
def test_menu_follows_the_kickoff_role_matrix(role, expected):
    assert keys(User(role=role)) == expected


def test_anonymous_sees_no_menu_and_superuser_sees_all():
    assert menu_for(AnonymousUser()) == []
    assert keys(User(role="driver", is_superuser=True)) == EVERYTHING


def test_menu_labels_follow_the_active_language():
    from django.utils import translation

    with translation.override("ru"):
        assert [str(g.title) for g in menu_for(User(role="storekeeper"))] == \
            ["Меню", "Автопарк", "Прочее"]
    with translation.override("uz"):
        assert str(menu_for(User(role="storekeeper"))[1].items[1].label) == "Ombor"


@pytest.mark.parametrize("role, web", [("director", True), ("dispatcher", True),
                                       ("storekeeper", True), ("driver", False)])
def test_only_staff_use_the_web_app(role, web):
    assert can_use_web(User(role=role)) is web


def test_has_role():
    assert has_role(User(role="dispatcher"), {"dispatcher"})
    assert not has_role(User(role="storekeeper"), {"director", "dispatcher"})
    assert not has_role(AnonymousUser(), {"director"})


def test_login_form_turns_drivers_away():
    form = StaffLoginForm()
    with pytest.raises(ValidationError) as exc:
        form.confirm_login_allowed(User(role="driver", is_active=True))
    assert exc.value.code == "driver"
    form.confirm_login_allowed(User(role="dispatcher", is_active=True))


@pytest.mark.parametrize("lang", ["uz", "ru"])
def test_every_ui_string_is_translated(lang):
    po = (LOCALE / lang / "LC_MESSAGES" / "django.po").read_text(encoding="utf-8")
    entries = re.findall(r'\nmsgid ((?:"(?:[^"\\]|\\.)*"\n)+)msgstr ((?:"(?:[^"\\]|\\.)*"\n?)+)', po)
    join = lambda block: "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', block))  # noqa: E731
    untranslated = [join(i) for i, s in entries if join(i) and not join(s)]
    assert entries, "no messages found"
    assert untranslated == []
    assert (LOCALE / lang / "LC_MESSAGES" / "django.mo").exists(), "run compilemessages"
