"""Notice drivers on shift who stopped sharing location (Day 11).

The bot calls check() every 30 seconds. For each open shift, location is
"missing since" the last update we got (or the shift start, if they never
shared). Once that is longer than CompanySettings.stop_alert_minutes:

  - a SharingGap is opened (once per gap, so nobody gets the same alert twice)
  - the managers' group is told, and the driver is reminded

When location comes back, the gap closes and the group hears that too.
A gap still open when the shift ends just closes, silently.

Plain (sync) functions; the bot sends the messages.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Max, Min
from django.utils import timezone

from apps.core.models import CompanySettings
from apps.fleet.models import Shift

from .models import LiveSession, LocationPoint, SharingGap

# What the bot posts.
GAP, BACK = "gap", "back"


@dataclass(frozen=True)
class Event:
    kind: str  # GAP or BACK
    shift: Shift
    since: dt.datetime  # location missing since
    minutes: int  # how long it was / has been missing
    last_point: LocationPoint | None = None
    driver_chat_id: int | None = None
    driver_language: str = ""


def _missing_since(shift: Shift, limit: dt.timedelta, now: dt.datetime) -> dt.datetime | None:
    """When location stopped coming, or None if it is coming."""
    sessions = shift.live_sessions.all()
    for s in sessions.filter(ended_at__isnull=True):
        if s.last_update_at > now - limit:
            return None
        # Still "open" but silent: phone off, app closed, no internet.
        s.ended_at, s.end_reason = s.last_update_at, LiveSession.EndReason.NO_UPDATES
        s.save(update_fields=["ended_at", "end_reason"])
    last = sessions.aggregate(at=Max("last_update_at"))["at"]
    return max(last, shift.started_at) if last else shift.started_at


def _event(kind: str, shift: Shift, since: dt.datetime, until: dt.datetime) -> Event:
    person = getattr(shift.driver, "user", None)
    return Event(kind, shift, since, int((until - since).total_seconds() // 60),
                 last_point=shift.points.filter(is_valid=True).order_by("-recorded_at").first(),
                 driver_chat_id=person.telegram_id if person else None,
                 driver_language=person.language if person else "")


def check(now: dt.datetime | None = None) -> list[Event]:
    now = now or timezone.now()
    limit = dt.timedelta(minutes=CompanySettings.load().stop_alert_minutes)
    events: list[Event] = []

    # Gaps of shifts that ended meanwhile close silently.
    SharingGap.objects.filter(resolved_at__isnull=True, shift__ended_at__isnull=False) \
        .update(resolved_at=now)

    shifts = (Shift.objects.filter(ended_at__isnull=True)
              .select_related("driver__user", "vehicle"))
    for shift in shifts:
        with transaction.atomic():
            since = _missing_since(shift, limit, now)
            gap = shift.sharing_gaps.filter(resolved_at__isnull=True).first()
            if gap and (since is None or since > gap.since):
                # Location came back, even if it went off again since then.
                back_at = shift.live_sessions.filter(last_update_at__gt=gap.since) \
                    .aggregate(at=Min("started_at"))["at"] or now
                gap.resolved_at = now
                gap.save(update_fields=["resolved_at"])
                events.append(_event(BACK, shift, gap.since, back_at))
                gap = None
            if since is None or gap or now - since < limit:
                continue
            try:
                with transaction.atomic():
                    SharingGap.objects.create(shift=shift, since=since, alerted_at=now)
            except IntegrityError:  # another checker was faster
                continue
            events.append(_event(GAP, shift, since, now))
    return events


def alert_chat_id() -> int | None:
    return CompanySettings.load().alert_chat_id
