"""Registration by phone number and its approval (Day 7)."""

import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.bot import registration as reg
from apps.bot.models import BotUser, RegistrationRequest
from tests import factories as f

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PHONE = "+998901234567"


def bot_user(**kw):
    kw.setdefault("telegram_id", 777)
    kw.setdefault("language", "ru")
    return BotUser.objects.create(**kw)


def test_staff_number_wins_over_a_driver_with_the_same_number():
    staff = f.user(role="dispatcher", phone=PHONE)
    f.driver(phone=PHONE)
    assert reg.match(PHONE) == (staff, None)


def test_inactive_people_are_not_matched():
    f.driver(phone=PHONE, is_active=False)
    f.user(role="dispatcher", phone="+998901111111", is_active=False)
    assert reg.match(PHONE) == (None, None)
    assert reg.match("+998901111111") == (None, None)


def test_sharing_a_phone_outcomes():
    bu = bot_user()
    assert reg.share_phone(bu, "+998909999999").kind == reg.UNKNOWN
    driver = f.driver(phone=PHONE)
    created = reg.share_phone(bu, PHONE)
    assert created.kind == reg.CREATED and created.request.driver == driver
    assert reg.share_phone(bu, PHONE).kind == reg.PENDING
    assert BotUser.objects.get(pk=bu.pk).phone == PHONE


def test_already_linked_person_is_not_asked_again():
    bu = bot_user(user=f.user(role="driver"))
    assert reg.share_phone(bu, PHONE).kind == reg.LINKED


@pytest.mark.parametrize("role, driver_ok, staff_ok", [
    ("director", True, True), ("dispatcher", True, False), ("storekeeper", False, False)])
def test_who_may_decide(role, driver_ok, staff_ok):
    user = User(role=role)
    assert reg.can_decide(user, RegistrationRequest(driver_id=1)) is driver_ok
    assert reg.can_decide(user, RegistrationRequest(staff_id=1)) is staff_ok


def test_approving_a_driver_creates_their_bot_only_account():
    driver = f.driver(phone=PHONE, full_name="Aliyev Vali")
    bu = bot_user()
    request = reg.share_phone(bu, PHONE).request
    dispatcher = f.user(role="dispatcher")

    user = reg.approve(request, dispatcher)

    assert (user.role, user.first_name, user.last_name, user.telegram_id, user.language) == \
        ("driver", "Aliyev", "Vali", 777, "ru")
    assert not user.has_usable_password()
    driver.refresh_from_db()
    bu.refresh_from_db()
    assert driver.user == user and bu.user == user
    request.refresh_from_db()
    assert (request.status, request.decided_by) == ("approved", dispatcher)
    assert AuditLog.objects.filter(action="confirm", actor=dispatcher).count() == 1


def test_a_new_telegram_account_replaces_the_old_link():
    staff = f.user(role="storekeeper", phone=PHONE)
    old = bot_user(telegram_id=1, user=staff)
    staff.telegram_id = 1
    staff.save()
    new = bot_user(telegram_id=2)
    reg.approve(reg.share_phone(new, PHONE).request, f.user(role="director"))
    old.refresh_from_db()
    staff.refresh_from_db()
    assert old.user is None and staff.telegram_id == 2


def test_reject_keeps_the_reason_and_decisions_are_final():
    f.driver(phone=PHONE)
    request = reg.share_phone(bot_user(), PHONE).request
    director = f.user(role="director")
    reg.reject(request, director, "not_employee")
    request.refresh_from_db()
    assert (request.status, request.reject_reason) == ("rejected", "not_employee")
    with pytest.raises(ValueError):
        reg.approve(request, director)
