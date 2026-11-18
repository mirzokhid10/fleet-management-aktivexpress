"""/start_shift and /end_shift in the bot (Day 8)."""

import pytest
from aiogram.methods import EditMessageText

from apps.audit.models import AuditLog
from apps.fleet.models import Shift
from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

T = FakeTelegram


def a_driver(language="uz", **kw):
    """A registered driver chatting with the bot."""
    person = f.user(role="driver", first_name="Vali", language=language)
    d = f.driver(user=person, full_name="Aliyev Vali", **kw)
    return d, link_telegram(person)


def take(tg, vehicle):
    return tg.tap(f"shift:take:{vehicle.pk}")


# --- who may -----------------------------------------------------------------

def test_unregistered_person_is_sent_to_start():
    tg = FakeTelegram()
    tg.send("/start")
    tg.tap("lang:uz")
    assert T.texts(tg.send("/start_shift")) == [
        "Siz hali ro'yxatdan o'tmagansiz. Avval /start yuboring va telefon raqamingizni "
        "ulashing."]


def test_staff_cannot_take_shifts():
    tg = link_telegram(f.user(role="dispatcher", language="ru"))
    assert T.texts(tg.send("/start_shift")) == ["Смены только для водителей."]
    assert T.texts(tg.send("/end_shift")) == ["Смены только для водителей."]


# --- start -------------------------------------------------------------------

def test_picker_shows_own_vehicle_first_with_a_star():
    other = f.vehicle(plate="01A001AA")
    own = f.vehicle(plate="01A123BC")
    _, tg = a_driver(default_vehicle=own)
    calls = tg.send("/start_shift")
    assert T.texts(calls) == ["Qaysi avtomobilni olyapsiz?\nRo'yxatda yo'qmi? Davlat "
                              "raqamining bir qismini yozing, masalan 123."]
    assert T.buttons(calls) == [("⭐ 01 A 123 BC · Isuzu NPR 82", f"shift:take:{own.pk}"),
                                ("01 A 001 AA · Isuzu NPR 82", f"shift:take:{other.pk}")]


def test_tapping_a_vehicle_starts_the_shift():
    v = f.vehicle(plate="01A123BC")
    d, tg = a_driver()
    tg.send("/start_shift")
    calls = take(tg, v)
    edited = [c for c in calls if isinstance(c, EditMessageText)]
    assert edited[0].text.startswith("✅ Smena boshlandi: 01 A 123 BC, ")
    assert edited[0].text.endswith("Ishni tugatganingizda /end_shift yuboring.")
    shift = Shift.objects.get()
    assert (shift.driver, shift.vehicle, shift.ended_at) == (d, v, None)
    assert AuditLog.objects.get().actor == d.user


def test_start_shift_while_on_shift_says_so():
    v = f.vehicle(plate="01A123BC")
    _, tg = a_driver(language="ru")
    tg.send("/start_shift")
    take(tg, v)
    text = T.texts(tg.send("/start_shift"))[0]
    assert text.startswith("Вы на смене на 01 A 123 BC с ")
    assert T.buttons(tg.send("/start_shift")) == []


def test_many_vehicles_are_cut_and_found_by_typing():
    vehicles = [f.vehicle(plate=f"01A{n:03d}AA") for n in range(1, 11)]
    _, tg = a_driver()
    calls = tg.send("/start_shift")
    assert len(T.buttons(calls)) == 8
    assert "10 tadan 8 tasi ko'rsatilgan." in T.texts(calls)[0]

    found = tg.send("010")
    assert T.buttons(found) == [("01 A 010 AA · Isuzu NPR 82", f"shift:take:{vehicles[-1].pk}")]
    take(tg, vehicles[-1])
    assert Shift.objects.get().vehicle == vehicles[-1]


def test_typing_a_plate_nobody_has():
    f.vehicle(plate="01A001AA")
    _, tg = a_driver()
    tg.send("/start_shift")
    assert T.texts(tg.send("999")) == [
        "“999” bo'yicha bo'sh avtomobil topilmadi. Qayta urinib ko'ring yoki dispetcherga "
        "qo'ng'iroq qiling."]


def test_typing_without_start_shift_is_not_a_search():
    f.vehicle(plate="01A001AA")
    _, tg = a_driver()
    assert T.buttons(tg.send("001")) == []


def test_no_free_vehicles():
    v = f.vehicle()
    f.shift(vehicle=v)
    _, tg = a_driver()
    assert T.texts(tg.send("/start_shift")) == [
        "Bo'sh avtomobil yo'q. Dispetcherga qo'ng'iroq qiling."]


def test_vehicle_taken_meanwhile_names_the_other_driver():
    v = f.vehicle(plate="01A123BC")
    _, tg = a_driver()
    tg.send("/start_shift")
    f.shift(vehicle=v, driver=f.driver(full_name="Karimov Ali"))  # was faster
    text = T.texts(take(tg, v))[0]
    assert text.startswith("01 A 123 BC ")
    assert "Karimov Ali smenasida. Agar bu xato bo'lsa, dispetcherga" in text
    assert Shift.objects.count() == 1


def test_vehicle_switched_off_meanwhile():
    v = f.vehicle()
    _, tg = a_driver()
    tg.send("/start_shift")
    v.is_active = False
    v.save()
    assert T.texts(take(tg, v)) == [
        "Bu avtomobilni endi tanlab bo'lmaydi. /start_shift ni qayta yuboring."]


# --- end ---------------------------------------------------------------------

def test_end_shift_without_a_shift():
    _, tg = a_driver()
    assert T.texts(tg.send("/end_shift")) == [
        "Sizda ochiq smena yo'q. Boshlash uchun /start_shift yuboring."]


def test_end_shift_asks_then_ends():
    v = f.vehicle(plate="01A123BC")
    _, tg = a_driver()
    tg.send("/start_shift")
    take(tg, v)
    shift = Shift.objects.get()

    ask = tg.send("/end_shift")
    assert T.texts(ask)[0].startswith("01 A 123 BC bilan smenani tugatasizmi?")
    assert T.buttons(ask) == [("✅ Ha, smenani tugatish", f"shift:end:{shift.pk}"),
                              ("Yo'q, ishni davom ettiraman", "shift:keep")]

    done = T.texts(tg.tap(f"shift:end:{shift.pk}"))[0]
    assert done.startswith("✅ Smena tugadi: 01 A 123 BC, ")
    shift.refresh_from_db()
    assert shift.ended_at is not None
    # the vehicle is free again
    assert f"shift:take:{v.pk}" in dict(T.buttons(tg.send("/start_shift"))).values()


def test_keep_working_leaves_the_shift_open():
    v = f.vehicle()
    _, tg = a_driver(language="ru")
    tg.send("/start_shift")
    take(tg, v)
    tg.send("/end_shift")
    assert T.texts(tg.tap("shift:keep")) == ["Хорошо, смена продолжается."]
    assert Shift.objects.get().is_open


def test_old_end_button_after_the_dispatcher_ended_it():
    v = f.vehicle()
    _, tg = a_driver()
    tg.send("/start_shift")
    take(tg, v)
    shift = Shift.objects.get()
    tg.send("/end_shift")
    from apps.fleet import shifts
    shifts.end(shift, source="web")
    assert T.texts(tg.tap(f"shift:end:{shift.pk}")) == ["Bu smena allaqachon tugagan."]


def test_cannot_end_someone_elses_shift():
    theirs = f.shift()
    _, tg = a_driver()
    assert T.texts(tg.tap(f"shift:end:{theirs.pk}")) == []
    theirs.refresh_from_db()
    assert theirs.is_open


def test_help_and_command_menu_list_the_shift_commands():
    from apps.bot.setup import commands

    _, tg = a_driver()
    help_text = T.texts(tg.send("/help"))[0]
    assert "/start_shift — smenani boshlash" in help_text
    assert "/end_shift — smenani tugatish" in help_text
    assert [c.command for c in commands("ru")] == ["start", "start_shift", "end_shift",
                                                   "language", "help"]
