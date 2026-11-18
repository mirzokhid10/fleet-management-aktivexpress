"""Registration by phone number (Day 7).

1. In the bot the person shares their own number (Telegram's contact button).
2. The number is matched to a staff user or a driver record.
3. A manager approves: dispatchers approve drivers, the director approves staff.
4. On approval the Telegram account is linked: the person can use the bot,
   and staff can sign in to the web through Telegram.

Plain (sync) functions: the web calls them directly, the bot via sync_to_async.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import DIRECTOR, DISPATCHER, has_role
from apps.audit import log
from apps.audit.models import AuditLog
from apps.fleet.models import Driver

from .models import BotUser, RegistrationRequest

# What happened when the person shared their number.
LINKED, PENDING, CREATED, UNKNOWN = "linked", "pending", "created", "unknown"


@dataclass(frozen=True)
class Outcome:
    kind: str
    request: RegistrationRequest | None = None


def match(phone: str) -> tuple[User | None, Driver | None]:
    """Whose number is this? Staff first: a staff member can also be in the driver list."""
    staff = User.objects.filter(phone=phone, is_active=True).exclude(role=User.Role.DRIVER).first()
    if staff:
        return staff, None
    return None, Driver.objects.filter(phone=phone, is_active=True).first()


def share_phone(bot_user: BotUser, phone: str) -> Outcome:
    if bot_user.user_id:
        return Outcome(LINKED)
    pending = bot_user.registration_requests.filter(status=RegistrationRequest.Status.PENDING)
    if pending.exists():
        return Outcome(PENDING, pending.first())
    bot_user.phone = phone
    bot_user.save(update_fields=["phone", "last_seen_at"])
    staff, driver = match(phone)
    if not staff and not driver:
        return Outcome(UNKNOWN)
    request = RegistrationRequest.objects.create(bot_user=bot_user, phone=phone, staff=staff,
                                                 driver=driver)
    return Outcome(CREATED, request)


def can_decide(user, request: RegistrationRequest) -> bool:
    """Kickoff role matrix: director approves anyone, dispatcher approves drivers only."""
    if request.is_staff_request:
        return has_role(user, {DIRECTOR})
    return has_role(user, {DIRECTOR, DISPATCHER})


def _driver_user(driver: Driver, bot_user: BotUser) -> User:
    """The login-less User behind a driver: drivers never sign in to the web."""
    if driver.user_id:
        return driver.user
    first, _, last = driver.full_name.partition(" ")
    user = User(username=f"driver-{driver.phone.lstrip('+')}", role=User.Role.DRIVER,
                first_name=first[:150], last_name=last[:150], phone=driver.phone,
                language=bot_user.language or User.Language.UZ)
    user.set_unusable_password()
    user.save()
    driver.user = user
    driver.save(update_fields=["user"])
    return user


@transaction.atomic
def approve(request: RegistrationRequest, by: User) -> User:
    request = RegistrationRequest.objects.select_for_update().get(pk=request.pk)
    if request.status != RegistrationRequest.Status.PENDING:
        raise ValueError("already decided")
    bot_user = request.bot_user
    user = request.staff or _driver_user(request.driver, bot_user)

    # A new phone or Telegram account replaces the old link.
    BotUser.objects.filter(user=user).exclude(pk=bot_user.pk).update(user=None)
    User.objects.filter(telegram_id=bot_user.telegram_id).exclude(pk=user.pk).update(
        telegram_id=None)
    before = log.snapshot(user)
    user.telegram_id = bot_user.telegram_id
    if bot_user.language:
        user.language = bot_user.language
    user.save(update_fields=["telegram_id", "language"])
    bot_user.user = user
    bot_user.save(update_fields=["user", "last_seen_at"])

    request.status = RegistrationRequest.Status.APPROVED
    request.decided_by, request.decided_at = by, timezone.now()
    request.save()
    log.record(request, AuditLog.Action.CONFIRM, source=AuditLog.Source.WEB, actor=by)
    log.record(user, AuditLog.Action.UPDATE, source=AuditLog.Source.WEB, actor=by,
               changes=log.diff(before, log.snapshot(user)), reason="Telegram linked")
    return user


@transaction.atomic
def reject(request: RegistrationRequest, by: User, reason: str) -> None:
    request = RegistrationRequest.objects.select_for_update().get(pk=request.pk)
    if request.status != RegistrationRequest.Status.PENDING:
        raise ValueError("already decided")
    request.status = RegistrationRequest.Status.REJECTED
    request.reject_reason = reason
    request.decided_by, request.decided_at = by, timezone.now()
    request.save()
    log.record(request, AuditLog.Action.REJECT, source=AuditLog.Source.WEB, actor=by,
               reason=reason)
