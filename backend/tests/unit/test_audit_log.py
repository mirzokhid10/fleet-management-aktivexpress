"""Audit log helpers (Day 5)."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.audit import log

pytestmark = pytest.mark.unit


def test_snapshot_never_holds_the_password():
    user = User(username="a", role="director")
    user.set_password("secret-Passw0rd")
    assert "password" not in log.snapshot(user)
    assert log.snapshot(user)["username"] == "a"


def test_diff_lists_only_changed_fields_as_plain_json():
    before = {"a": 1, "b": Decimal("1.50"), "c": dt.date(2026, 1, 1)}
    after = {"a": 1, "b": Decimal("2.00"), "c": dt.date(2026, 1, 2)}
    assert log.diff(before, after) == {"b": ["1.50", "2.00"], "c": ["2026-01-01", "2026-01-02"]}
