"""Sidebar menu of the web app.

One list, in roadmap order. An item without a url_name is shown as
"coming soon" until the day that builds it.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    icon: str  # name of an icon in templates/partials/icons.html
    url_name: str | None = None
    day: int | None = None  # roadmap day that builds the page

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
    MenuGroup("Menu", (
        MenuItem("dashboard", "Dashboard", "grid", "core:dashboard"),
        MenuItem("map", "Live map", "map", day=12),
        MenuItem("trips", "Trips", "route", day=14),
        MenuItem("approvals", "Approvals", "check", day=21),
    )),
    MenuGroup("Fleet", (
        MenuItem("vehicles", "Vehicles", "truck", day=5),
        MenuItem("drivers", "Drivers", "users", day=5),
        MenuItem("fuel", "Fuel", "fuel", day=28),
        MenuItem("maintenance", "Maintenance", "wrench", day=37),
        MenuItem("store", "Store", "box", day=46),
        MenuItem("documents", "Documents", "file", day=49),
    )),
    MenuGroup("Other", (
        MenuItem("reports", "Reports", "chart", day=58),
        MenuItem("settings", "Settings", "settings", day=26),
    )),
)


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
