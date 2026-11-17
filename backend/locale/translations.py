"""Source of truth for our own UI strings in Uzbek (Latin) and Russian.

Workflow when you add or change text:
    python manage.py makemessages -l uz -l ru --no-obsolete
    python locale/translations.py          # fills the .po files from this dict
    python manage.py compilemessages

A test fails if any of our strings is left untranslated.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# msgid: (uz, ru)
T: dict[str, tuple[str, str]] = {
    # menu
    "Menu": ("Menyu", "Меню"),
    "Fleet": ("Avtopark", "Автопарк"),
    "Other": ("Boshqa", "Прочее"),
    "Dashboard": ("Bosh sahifa", "Главная"),
    "Live map": ("Jonli xarita", "Карта онлайн"),
    "Trips": ("Reyslar", "Поездки"),
    "Approvals": ("Tasdiqlash", "Подтверждения"),
    "Vehicles": ("Avtomobillar", "Автомобили"),
    "Drivers": ("Haydovchilar", "Водители"),
    "Fuel": ("Yoqilg'i", "Топливо"),
    "Maintenance": ("Texnik xizmat", "Техобслуживание"),
    "Store": ("Ombor", "Склад"),
    "Documents": ("Hujjatlar", "Документы"),
    "Reports": ("Hisobotlar", "Отчёты"),
    "Settings": ("Sozlamalar", "Настройки"),
    "Day %(day)s": ("%(day)s-kun", "День %(day)s"),
    "Coming on day %(day)s": ("%(day)s-kunda tayyor bo'ladi", "Будет готово в день %(day)s"),
    # layout
    "Skip to the main content": ("Asosiy qismga o'tish", "Перейти к основному содержимому"),
    "Sidebar": ("Yon panel", "Боковая панель"),
    "Main menu": ("Asosiy menyu", "Главное меню"),
    "Home": ("Bosh sahifa", "Главная"),
    "Breadcrumb": ("Navigatsiya", "Навигация"),
    "Toggle sidebar": ("Yon panelni ochish/yopish", "Показать/скрыть боковую панель"),
    "Toggle dark mode": ("Tungi rejim", "Тёмная тема"),
    "Log out": ("Chiqish", "Выйти"),
    # roles
    "Director": ("Direktor", "Директор"),
    "Dispatcher": ("Dispetcher", "Диспетчер"),
    "Storekeeper": ("Omborchi", "Кладовщик"),
    "Driver": ("Haydovchi", "Водитель"),
    # login
    "Sign in": ("Kirish", "Вход"),
    "Enter your username and password.": ("Login va parolingizni kiriting.",
                                          "Введите логин и пароль."),
    "Username": ("Login", "Логин"),
    "Password": ("Parol", "Пароль"),
    "Show password": ("Parolni ko'rsatish", "Показать пароль"),
    "Hide password": ("Parolni yashirish", "Скрыть пароль"),
    "Keep me logged in": ("Meni eslab qol", "Запомнить меня"),
    "Drivers: use the company Telegram bot.": ("Haydovchilar: kompaniya Telegram botidan "
                                               "foydalaning.",
                                               "Водители: пользуйтесь Telegram-ботом компании."),
    "Drivers use the Telegram bot, not the web app.": (
        "Haydovchilar veb-ilovadan emas, Telegram botdan foydalanadi.",
        "Водители работают через Telegram-бот, а не через веб-приложение."),
    "Vehicles, drivers, fuel, service and store in one place.": (
        "Avtomobillar, haydovchilar, yoqilg'i, texnik xizmat va ombor — bir joyda.",
        "Автомобили, водители, топливо, обслуживание и склад — в одном месте."),
    "No access": ("Ruxsat yo'q", "Нет доступа"),
    "Your role cannot open this page.": ("Sizning lavozimingiz bu sahifani ocha olmaydi.",
                                         "Ваша роль не позволяет открыть эту страницу."),
    # dashboard
    "System status": ("Tizim holati", "Состояние системы"),
    "Open health check (JSON)": ("Tekshiruvni ochish (JSON)", "Открыть проверку (JSON)"),
    "The director's dashboard (vehicles on the road, alerts, service due, documents, stock, "
    "approvals waiting) is built on day 57. Pages in the menu unlock on the day shown next to "
    "them.": (
        "Direktor paneli (yo'ldagi mashinalar, ogohlantirishlar, texnik xizmat, hujjatlar, "
        "ombor, tasdiq kutayotganlar) 57-kuni tayyor bo'ladi. Menyudagi sahifalar yonida "
        "ko'rsatilgan kuni ochiladi.",
        "Панель директора (машины в пути, оповещения, ТО, документы, склад, ожидающие "
        "подтверждения) будет готова на 57-й день. Пункты меню открываются в день, указанный "
        "рядом с ними."),
}

LANGS = {"uz": 0, "ru": 1}
BASE = Path(__file__).resolve().parent


def _unquote(block: str) -> str:
    return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', block)).replace('\\"', '"')


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


ENTRY = re.compile(r'(msgid ((?:"(?:[^"\\]|\\.)*"\n?)+))(msgstr ((?:"(?:[^"\\]|\\.)*"\n?)+))')


def fill(lang: str) -> list[str]:
    """Fill msgstr for every msgid we know. Returns msgids still untranslated."""
    path = BASE / lang / "LC_MESSAGES" / "django.po"
    text = path.read_text(encoding="utf-8")
    missing: list[str] = []

    def replace(m: re.Match) -> str:
        msgid = _unquote(m.group(2))
        if not msgid:  # header
            return m.group(0)
        if msgid in T:
            return f"{m.group(1)}msgstr {_quote(T[msgid][LANGS[lang]])}\n"
        if not _unquote(m.group(4)):
            missing.append(msgid)
        return m.group(0)

    text = ENTRY.sub(replace, text)
    text = text.replace("#, fuzzy\n", "")
    path.write_text(text, encoding="utf-8")
    return missing


if __name__ == "__main__":
    problems = {lang: fill(lang) for lang in LANGS}
    for lang, missing in problems.items():
        for msgid in missing:
            print(f"{lang}: untranslated: {msgid!r}")
    sys.exit(1 if any(problems.values()) else 0)
