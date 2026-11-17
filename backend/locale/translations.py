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
    # lists (Day 5)
    "Search": ("Qidirish", "Поиск"),
    "%(shown)s of %(total)s": ("%(total)s tadan %(shown)s", "%(shown)s из %(total)s"),
    "Total: %(total)s": ("Jami: %(total)s", "Всего: %(total)s"),
    "Pages": ("Sahifalar", "Страницы"),
    "Previous": ("Oldingi", "Назад"),
    "Next": ("Keyingi", "Вперёд"),
    "Page %(n)s of %(total)s": ("%(n)s / %(total)s sahifa", "Страница %(n)s из %(total)s"),
    "Nothing found.": ("Hech narsa topilmadi.", "Ничего не найдено."),
    "Admin panel": ("Admin panel", "Админ-панель"),
    # vehicles
    "Plate, brand, model or VIN": ("Raqam, marka, model yoki VIN",
                                   "Госномер, марка, модель или VIN"),
    "Plate": ("Davlat raqami", "Госномер"),
    "Vehicle": ("Avtomobil", "Автомобиль"),
    "Year": ("Yili", "Год"),
    "Norm / 100 km": ("Me'yor / 100 km", "Норма / 100 км"),
    "Odometer, km": ("Probeg, km", "Пробег, км"),
    "Status": ("Holati", "Статус"),
    "Active": ("Faol", "Активен"),
    "Inactive": ("Nofaol", "Неактивен"),
    "No vehicles yet. Import them from the company data template.": (
        "Hali avtomobillar yo'q. Ularni kompaniya ma'lumotlar shablonidan import qiling.",
        "Автомобилей пока нет. Импортируйте их из шаблона данных компании."),
    # drivers
    "Name, phone or licence": ("F.I.Sh., telefon yoki guvohnoma",
                               "Ф.И.О., телефон или права"),
    "Full name": ("F.I.Sh.", "Ф.И.О."),
    "Telegram phone": ("Telegram telefoni", "Телефон в Telegram"),
    "Licence": ("Guvohnoma", "Права"),
    "Licence valid until": ("Guvohnoma muddati", "Права действуют до"),
    "Main vehicle": ("Asosiy mashina", "Основная машина"),
    "Bot": ("Bot", "Бот"),
    "Expired": ("Muddati o'tgan", "Просрочены"),
    "Within %(warn_days)s days": ("%(warn_days)s kun ichida", "В течение %(warn_days)s дней"),
    "Linked": ("Ulangan", "Подключён"),
    "Not yet": ("Hali yo'q", "Ещё нет"),
    "No drivers yet. Import them from the company data template.": (
        "Hali haydovchilar yo'q. Ularni kompaniya ma'lumotlar shablonidan import qiling.",
        "Водителей пока нет. Импортируйте их из шаблона данных компании."),
    # import
    "Import from Excel": ("Exceldan import", "Импорт из Excel"),
    "Filled data template (.xlsx)": ("To'ldirilgan shablon (.xlsx)",
                                     "Заполненный шаблон (.xlsx)"),
    "The file is larger than %(mb)s MB.": ("Fayl %(mb)s MB dan katta.",
                                           "Файл больше %(mb)s МБ."),
    "1. Upload the filled template": ("1. To'ldirilgan shablonni yuklang",
                                      "1. Загрузите заполненный шаблон"),
    "Vehicles and drivers are read from the Vehicles and Drivers sheets. Nothing is saved "
    "until you confirm. Rows are matched by plate and phone, so the same file can be imported "
    "again.": (
        "Avtomobillar va haydovchilar Vehicles va Drivers varaqlaridan o'qiladi. Siz "
        "tasdiqlamaguningizcha hech narsa saqlanmaydi. Qatorlar davlat raqami va telefon "
        "bo'yicha solishtiriladi, shuning uchun bir faylni qayta import qilish mumkin.",
        "Автомобили и водители читаются с листов Vehicles и Drivers. Ничего не сохраняется, "
        "пока вы не подтвердите. Строки сопоставляются по госномеру и телефону, поэтому тот же "
        "файл можно импортировать повторно."),
    "Check the file": ("Faylni tekshirish", "Проверить файл"),
    "Blank template": ("Bo'sh shablon", "Пустой шаблон"),
    "Headers in Uzbek and Russian, dropdowns for fixed choices, an example on row 2.": (
        "Sarlavhalar o'zbek va rus tillarida, tanlov ro'yxatlari, 2-qatorda namuna.",
        "Заголовки на узбекском и русском, выпадающие списки, пример во 2-й строке."),
    "Download template": ("Shablonni yuklab olish", "Скачать шаблон"),
    "2. Check what will change": ("2. Nima o'zgarishini tekshiring",
                                  "2. Проверьте, что изменится"),
    "Problems found: %(n)s. Nothing was imported. Fix the file in Excel and upload it again.": (
        "Topilgan xatolar: %(n)s. Hech narsa import qilinmadi. Faylni Excelda tuzatib, "
        "qayta yuklang.",
        "Найдено ошибок: %(n)s. Ничего не импортировано. Исправьте файл в Excel и загрузите "
        "снова."),
    "Sheet": ("Varaq", "Лист"),
    "Row": ("Qator", "Строка"),
    "Column": ("Ustun", "Столбец"),
    "Problem": ("Xato", "Ошибка"),
    "New": ("Yangi", "Новый"),
    "Changed": ("O'zgargan", "Изменён"),
    "Unchanged": ("O'zgarmagan", "Без изменений"),
    "New vehicles": ("Yangi avtomobillar", "Новые автомобили"),
    "Changed vehicles": ("O'zgargan avtomobillar", "Изменённые автомобили"),
    "New drivers": ("Yangi haydovchilar", "Новые водители"),
    "Changed drivers": ("O'zgargan haydovchilar", "Изменённые водители"),
    "3. Import": ("3. Import qilish", "3. Импортировать"),
    "Cancel": ("Bekor qilish", "Отмена"),
    "This is not a valid Excel file.": ("Bu yaroqli Excel fayli emas.",
                                        "Это не файл Excel."),
    "The preview has expired. Upload the file again.": (
        "Ko'rib chiqish muddati tugadi. Faylni qayta yuklang.",
        "Предпросмотр устарел. Загрузите файл снова."),
    "The data changed since the preview. Upload the file again.": (
        "Ko'rib chiqishdan keyin ma'lumotlar o'zgardi. Faylni qayta yuklang.",
        "Данные изменились после предпросмотра. Загрузите файл снова."),
    "Imported: %(nv)s new and %(uv)s changed vehicles, %(nd)s new and %(ud)s changed "
    "drivers.": (
        "Import qilindi: avtomobillar — %(nv)s yangi, %(uv)s o'zgargan; haydovchilar — "
        "%(nd)s yangi, %(ud)s o'zgargan.",
        "Импортировано: автомобили — %(nv)s новых, %(uv)s изменённых; водители — %(nd)s "
        "новых, %(ud)s изменённых."),
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
