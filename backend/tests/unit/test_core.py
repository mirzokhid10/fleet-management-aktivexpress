"""Unit tests for the core app: menu, health aggregation, settings helpers."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.core.health import run_checks
from apps.core.menu import MENU, MenuItem, active_key
from config import settings as cfg

pytestmark = pytest.mark.unit

ALL_ITEMS = [item for group in MENU for item in group.items]


def test_menu_keys_are_unique():
    keys = [item.key for item in ALL_ITEMS]
    assert len(keys) == len(set(keys))


def test_every_unbuilt_page_says_which_roadmap_day_builds_it():
    for item in ALL_ITEMS:
        if not item.ready:
            assert item.day and 1 <= item.day <= 70, item.key


def test_pages_ready_by_day_8():
    assert [item.key for item in ALL_ITEMS if item.ready] == ["dashboard", "registrations",
                                                              "vehicles", "drivers", "shifts"]


def test_item_with_unknown_url_name_is_not_ready():
    assert MenuItem("x", "X", "grid", url_name="core:does-not-exist").ready is False


@pytest.mark.parametrize("path, key", [("/", "dashboard"), ("/admin/", None), ("/nope/", None),
                                       ("/vehicles/import/", "vehicles"),
                                       ("/shifts/", "shifts")])
def test_active_key(path, key):
    assert active_key(path) == key


def test_run_checks_all_ok():
    result = run_checks({"a": lambda: {"ok": True}, "b": lambda: {"ok": True, "v": 1}})
    assert result == {"ok": True, "checks": {"a": {"ok": True}, "b": {"ok": True, "v": 1}}}


def test_run_checks_reports_failures_without_raising():
    def boom():
        raise ConnectionError("down")

    result = run_checks({"db": boom, "cache": lambda: {"ok": True}})
    assert result["ok"] is False
    assert result["checks"]["db"] == {"ok": False, "error": "ConnectionError"}
    assert result["checks"]["cache"]["ok"] is True


def test_env_helpers(monkeypatch):
    monkeypatch.setenv("X_BOOL", "Yes")
    monkeypatch.setenv("X_LIST", " a, b ,,c ")
    monkeypatch.delenv("X_MISSING", raising=False)
    assert cfg.env_bool("X_BOOL") is True
    assert cfg.env_bool("X_MISSING") is False
    assert cfg.env_list("X_LIST") == ["a", "b", "c"]
    assert cfg.env("X_MISSING", "dflt") == "dflt"
    with pytest.raises(ImproperlyConfigured, match="X_MISSING"):
        cfg.env("X_MISSING")


def test_project_defaults():
    assert cfg.TIME_ZONE == "Asia/Tashkent"
    assert [code for code, _ in cfg.LANGUAGES] == ["uz", "ru"]
    assert cfg.DATABASES["default"]["ENGINE"] == "django.contrib.gis.db.backends.postgis"
