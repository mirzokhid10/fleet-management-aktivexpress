"""Sidebar menu of the web app.

One list, in roadmap order. Each item says which roles see it (Day 1 kickoff,
section 2). An item without a url_name is shown as "coming on day N" until the
day that builds it.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User

D, P, S = User.Role.DIRECTOR, User.Role.DISPATCHER, User.Role.STOREKEEPER
ALL_STAFF = frozenset({D, P, S})
MANAGERS = frozenset({D, P})


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    icon: str  # name of an icon in templates/partials/icon.html
    url_name: str | None = None
    day: int | None = None  # roadmap day that builds the page
    roles: frozenset = ALL_STAFF

    @property
    def url(self) -> str | None:
        if not self.url_name:
            return None
        try:
            return reverse(self.url_name)
        except NoReverseMatch:
            return None

    @property
    def ready(self) -> bool:
        return self.url is not None


@dataclass(frozen=True)
class MenuGroup:
    title: str
    items: tuple[MenuItem, ...]


MENU: tuple[MenuGroup, ...] = (
    MenuGroup(_("Menu"), (
        MenuItem("dashboard", _("Dashboard"), "grid", "core:dashboard"),
        # Day 12: where every vehicle is now (Telegram live location).
        MenuItem("map", _("Live map"), "map", "tracking:map", roles=MANAGERS),
        MenuItem("trips", _("Trips"), "route", day=14, roles=MANAGERS),
        # Storekeepers confirm part requests here when marked as approvers.
        MenuItem("approvals", _("Approvals"), "check", day=21),
        # Day 7: people who registered in the bot, waiting for a manager.
        MenuItem("registrations", _("New users"), "user-plus", "bot:requests", roles=MANAGERS),
    )),
    MenuGroup(_("Fleet"), (
        MenuItem("vehicles", _("Vehicles"), "truck", "fleet:vehicles", roles=MANAGERS),
        MenuItem("drivers", _("Drivers"), "users", "fleet:drivers", roles=MANAGERS),
        # Day 8: who drove which vehicle when (/start_shift … /end_shift in the bot).
        MenuItem("shifts", _("Shifts"), "clock", "fleet:shifts", roles=MANAGERS),
        MenuItem("fuel", _("Fuel"), "fuel", day=28, roles=MANAGERS),
        # Storekeeper doubles as mechanic in V1 (kickoff Q3).
        MenuItem("maintenance", _("Maintenance"), "wrench", day=37),
        MenuItem("store", _("Store"), "box", day=46),
        MenuItem("documents", _("Documents"), "file", day=49, roles=MANAGERS),
    )),
    MenuGroup(_("Other"), (
        MenuItem("reports", _("Reports"), "chart", day=58),
        MenuItem("settings", _("Settings"), "settings", day=26, roles=frozenset({D})),
    )),
)


def menu_for(user) -> list[MenuGroup]:
    """The menu groups and items this user may see; empty groups are dropped."""
    if not getattr(user, "is_authenticated", False):
        return []
    groups = []
    for group in MENU:
        items = tuple(i for i in group.items if user.is_superuser or user.role in i.roles)
        if items:
            groups.append(MenuGroup(group.title, items))
    return groups


def active_key(path: str) -> str | None:
    """Menu key whose page is the longest prefix of the request path."""
    best, best_len = None, -1
    for group in MENU:
        for item in group.items:
            url = item.url
            if url and (path == url or (url != "/" and path.startswith(url))):
                if len(url) > best_len:
                    best, best_len = item.key, len(url)
    return best
