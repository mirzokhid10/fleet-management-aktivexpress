"""Receive Telegram live location and store the points (Day 9).

How Telegram sends a live location:
  1. the driver shares it: a message with location.live_period set
  2. while it runs: the same message comes back edited, new coordinates each time
  3. the driver stops it: one more edit, this time without live_period

Each share is one LiveSession; every update is one LocationPoint on the
driver's open shift. Points outside a shift are not stored.

Plain (sync) functions: the bot calls them via sync_to_async.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from apps.fleet.models import Shift
from apps.fleet.shifts import driver_of, open_shift

from . import track, trips
from .models import LiveSession, LocationPoint

logger = logging.getLogger(__name__)

# What happened, for the bot to word (most updates get no answer at all).
NOT_DRIVER, NO_SHIFT, NOT_LIVE, STARTED, POINT, STOPPED, IGNORED = (
    "not_driver", "no_shift", "not_live", "started", "point", "stopped", "ignored")


@dataclass(frozen=True)
class Fix:
    """One location as Telegram sent it."""

    chat_id: int
    message_id: int
    latitude: float
    longitude: float
    at: dt.datetime  # message date, or edit_date for updates
    live_period: int | None = None
    accuracy_m: float | None = None
    heading: int | None = None


def _save_point(session: LiveSession, fix: Fix) -> LocationPoint | None:
    if session.points.filter(recorded_at=fix.at).exists():  # Telegram sent it twice
        return None
    point = LocationPoint(
        vehicle_id=session.shift.vehicle_id, shift=session.shift, session=session,
        recorded_at=fix.at, point=Point(fix.longitude, fix.latitude, srid=4326),
        accuracy_m=fix.accuracy_m, heading=fix.heading)
    track.apply(point)  # Day 10: distance, speed, bad points
    point.save()
    trips.rebuild(session.shift, fix.at)  # Day 14
    return point


def _close(session: LiveSession, at: dt.datetime, reason: str) -> None:
    session.ended_at = max(at, session.started_at)
    session.end_reason = reason
    session.save(update_fields=["ended_at", "end_reason"])


def _start_session(shift: Shift, fix: Fix) -> LiveSession:
    # A new share replaces any older one still open on this shift.
    for old in shift.live_sessions.filter(ended_at__isnull=True):
        _close(old, fix.at, LiveSession.EndReason.STOPPED_BY_DRIVER)
    return LiveSession.objects.create(
        shift=shift, chat_id=fix.chat_id, message_id=fix.message_id,
        live_period_s=fix.live_period, started_at=fix.at, last_update_at=fix.at)


@transaction.atomic
def receive(user_id: int | None, fix: Fix, edited: bool) -> str:
    session = (LiveSession.objects.select_for_update().select_related("shift")
               .filter(chat_id=fix.chat_id, message_id=fix.message_id).first())

    if session is None:
        driver = driver_of(user_id)
        if driver is None:
            return NOT_DRIVER if not edited else IGNORED
        if fix.live_period is None:
            # A plain location, or the "stopped" edit of a share we never stored.
            return NOT_LIVE if not edited else IGNORED
        shift = open_shift(driver)
        if shift is None:
            return NO_SHIFT if not edited else IGNORED
        # Edited: the share began before /start_shift and is still running. Adopt it.
        session = _start_session(shift, fix)
        _save_point(session, fix)
        return STARTED

    if session.ended_at is not None:
        return IGNORED
    if session.shift.ended_at is not None:
        _close(session, session.shift.ended_at, LiveSession.EndReason.SHIFT_ENDED)
        return IGNORED
    if fix.at > session.started_at + dt.timedelta(seconds=session.live_period_s):
        _close(session, fix.at, LiveSession.EndReason.PERIOD_EXPIRED)
        return IGNORED

    _save_point(session, fix)
    session.last_update_at = max(fix.at, session.last_update_at)
    session.save(update_fields=["last_update_at"])
    if fix.live_period is None:
        _close(session, fix.at, LiveSession.EndReason.STOPPED_BY_DRIVER)
        logger.info("live location stopped: session %s", session.pk)
        return STOPPED
    return POINT


def end_sessions(shift: Shift, at: dt.datetime | None = None) -> int:
    """The shift ended: its open shares end too. Returns how many."""
    at = at or timezone.now()
    sessions = list(shift.live_sessions.filter(ended_at__isnull=True))
    for s in sessions:
        _close(s, at, LiveSession.EndReason.SHIFT_ENDED)
    return len(sessions)


def is_sharing(shift: Shift) -> bool:
    return shift.live_sessions.filter(ended_at__isnull=True).exists()
