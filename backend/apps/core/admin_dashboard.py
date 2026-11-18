"""The Django admin's home page (Unfold DASHBOARD_CALLBACK) and its environment badge.

A quick look for the superuser: how big the fleet is, who is on shift right
now, open location alerts, whether the alert group is set, and the latest
changes from the audit log.
"""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.text import capfirst
from django.utils.translation import gettext as _

RECENT_CHANGES = 10


def environment(request) -> list[str] | None:
    """Badge in the admin header, so nobody mistakes a dev copy for the real one."""
    return [_("Development"), "warning"] if settings.DEBUG else None


def _stat(title: str, value: int, url_name: str, query: str = "") -> dict:
    return {"title": title, "value": value, "url": reverse(url_name) + query}


def _changes_table(rows) -> dict:
    return {
        "headers": [_("When"), _("Who"), _("Action"), _("What")],
        "rows": [[formats.date_format(timezone.localtime(r.at), "SHORT_DATETIME_FORMAT"),
                  r.actor or _("system"), r.get_action_display(),
                  f"{capfirst(r.content_type.name)}: {r.object_repr}"] for r in rows],
    }


def dashboard(request, context: dict) -> dict:
    from apps.audit.models import AuditLog
    from apps.fleet.models import Driver, Shift, Vehicle
    from apps.tracking.models import LiveSession, SharingGap

    from .models import CompanySettings

    sharing = (LiveSession.objects.filter(ended_at__isnull=True, shift__ended_at__isnull=True)
               .values("shift").distinct().count())
    context.update({
        "stats": [
            _stat(_("Active vehicles"), Vehicle.objects.filter(is_active=True).count(),
                  "admin:fleet_vehicle_changelist", "?is_active__exact=1"),
            _stat(_("Active drivers"), Driver.objects.filter(is_active=True).count(),
                  "admin:fleet_driver_changelist", "?is_active__exact=1"),
            _stat(_("On shift now"), Shift.objects.filter(ended_at__isnull=True).count(),
                  "admin:fleet_shift_changelist", "?ended_at__isnull=True"),
            _stat(_("Sharing location now"), sharing,
                  "admin:tracking_livesession_changelist", "?ended_at__isnull=True"),
            _stat(_("Location alerts open"),
                  SharingGap.objects.filter(resolved_at__isnull=True).count(),
                  "admin:tracking_sharinggap_changelist", "?resolved_at__isnull=True"),
        ],
        "alert_group_set": CompanySettings.load().alert_chat_id is not None,
        "settings_url": reverse("admin:core_companysettings_change", args=[1]),
        "recent_changes": _changes_table(AuditLog.objects.select_related("actor", "content_type")
                                         .order_by("-at")[:RECENT_CHANGES]),
        "audit_url": reverse("admin:audit_auditlog_changelist"),
    })
    return context
