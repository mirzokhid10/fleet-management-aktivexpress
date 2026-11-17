"""The data templates sent to the company on Day 1 ("Before Day 1" list).

One Sheet per list the company must fill. Column keys are English and stable
(code uses them); headers are Uzbek / Russian (people read them).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from .fields import (
    Field,
    parse_date,
    parse_decimal,
    parse_int,
    parse_phone,
    parse_plate,
    parse_text,
    parse_time,
    parse_vin,
    parse_yes_no,
)

FUEL_TYPES = ("Dizel", "AI-80", "AI-92", "Metan", "Propan")
SERVICE_ITEMS = ("Oil", "Tires", "Filters", "Brakes")
DOCUMENT_TYPES = (
    "Insurance",
    "Technical inspection",
    "Gas cylinder certificate",
    "Driving licence",
    "Power of attorney",
)
OWNER_TYPES = ("Vehicle", "Driver")
GEOFENCE_TYPES = ("Warehouse", "Client")
STAFF_ROLES = ("Director", "Dispatcher", "Storekeeper")
YES_NO = ("Yes", "No")
RETENTION_MONTHS = ("1", "3")


@dataclass(frozen=True)
class Sheet:
    key: str
    title: str  # Excel sheet name, max 31 chars
    purpose: str
    fields: tuple[Field, ...]
    single_row: bool = False

    def field(self, key: str) -> Field:
        return next(f for f in self.fields if f.key == key)


VEHICLES = Sheet(
    key="vehicles",
    title="Vehicles",
    purpose="Every vehicle in the fleet, one per row.",
    fields=(
        Field("plate", "Davlat raqami", "Госномер", parse_plate, unique=True,
              example="01 A 123 BC", note="01 A 123 BC or 01 123 ABC"),
        Field("brand", "Marka", "Марка", example="Isuzu"),
        Field("model", "Model", "Модель", example="NPR 82"),
        Field("year", "Yili", "Год выпуска", partial(parse_int, minimum=1980, maximum=2030),
              example=2021, width=12),
        Field("vin", "VIN", "VIN", parse_vin, unique=True, example="JALC4B16507000001", width=22),
        Field("odometer_km", "Hozirgi probeg (km)", "Текущий пробег (км)", parse_int,
              example=154300),
        Field("fuel_type", "Yoqilg'i turi", "Тип топлива", choices=FUEL_TYPES, example="Dizel"),
        Field("second_fuel_type", "Ikkinchi yoqilg'i", "Второе топливо", choices=FUEL_TYPES,
              required=False, note="Only for bi-fuel vehicles, e.g. AI-92 + Metan"),
        Field("fuel_norm", "Me'yor (l yoki m³ / 100 km)", "Норма (л или м³ / 100 км)",
              parse_decimal, example=14.5),
        Field("second_fuel_norm", "Ikkinchi yoqilg'i me'yori", "Норма второго топлива",
              parse_decimal, required=False),
        Field("notes", "Izoh", "Примечание", required=False, width=30),
    ),
)

DRIVERS = Sheet(
    key="drivers",
    title="Drivers",
    purpose="Every driver. The phone must be the number used in Telegram.",
    fields=(
        Field("full_name", "F.I.Sh.", "Ф.И.О.", example="Aliyev Vali", width=28),
        Field("phone", "Telegram telefon raqami", "Телефон в Telegram", parse_phone, unique=True,
              example="+998 90 123 45 67", width=22),
        Field("licence_number", "Guvohnoma raqami", "Номер прав", unique=True, example="AF1234567"),
        Field("licence_categories", "Toifalar", "Категории", required=False, example="B, C"),
        Field("licence_expiry", "Guvohnoma muddati", "Срок прав", parse_date,
              example="31.12.2028"),
        Field("default_plate", "Asosiy mashina", "Основная машина", parse_plate, required=False,
              example="01 A 123 BC"),
    ),
)

LAST_SERVICE = Sheet(
    key="last_service",
    title="Last service",
    purpose="Last oil, tire, filter and brake change of each vehicle, so reminders start right.",
    fields=(
        Field("plate", "Davlat raqami", "Госномер", parse_plate, example="01 A 123 BC"),
        Field("service", "Xizmat", "Работа", choices=SERVICE_ITEMS, example="Oil"),
        Field("date", "Sana", "Дата", parse_date, example="15.10.2026"),
        Field("odometer_km", "Probeg (km)", "Пробег (км)", parse_int, example=150000),
        Field("notes", "Izoh", "Примечание", required=False, width=30),
    ),
)

SERVICE_INTERVALS = Sheet(
    key="service_intervals",
    title="Service intervals",
    purpose="How often each model needs each service. Whichever comes first: km or months.",
    fields=(
        Field("model", "Model", "Модель", example="NPR 82"),
        Field("service", "Xizmat", "Работа", choices=SERVICE_ITEMS, example="Oil"),
        Field("interval_km", "Har necha km", "Каждые N км", partial(parse_int, minimum=1),
              example=10000),
        Field("interval_months", "Har necha oy", "Каждые N месяцев",
              partial(parse_int, minimum=1), example=6),
    ),
)

DOCUMENTS = Sheet(
    key="documents",
    title="Documents",
    purpose="Documents with an expiry date, for vehicles and drivers.",
    fields=(
        Field("owner_type", "Kimga tegishli", "Чей документ", choices=OWNER_TYPES,
              example="Vehicle"),
        Field("owner", "Raqam yoki telefon", "Госномер или телефон",
              example="01 A 123 BC", note="Plate for a vehicle, Telegram phone for a driver"),
        Field("document_type", "Hujjat turi", "Тип документа", choices=DOCUMENT_TYPES,
              example="Insurance", width=26),
        Field("number", "Hujjat raqami", "Номер документа", required=False),
        Field("expiry_date", "Amal qilish muddati", "Действует до", parse_date,
              example="01.03.2027"),
    ),
)

STORE_OPENING = Sheet(
    key="store_opening",
    title="Store stock",
    purpose="What is on the store shelves today (opening balance).",
    fields=(
        Field("item", "Nomi", "Наименование", unique=True, example="Motor oil 15W-40", width=28),
        Field("category", "Turkum", "Категория", example="Oil"),
        Field("unit", "O'lchov birligi", "Ед. изм.", example="l", width=10),
        Field("quantity", "Miqdori", "Количество", parse_decimal, example=120),
        Field("min_level", "Minimal qoldiq", "Мин. остаток", parse_decimal, example=40),
        Field("supplier", "Yetkazib beruvchi", "Поставщик", required=False),
        Field("unit_price_uzs", "Narxi (so'm)", "Цена (сум)", parse_decimal, required=False),
        Field("warranty_months", "Kafolat (oy)", "Гарантия (мес)", parse_int, required=False),
    ),
)

GEOFENCES = Sheet(
    key="geofences",
    title="Places",
    purpose="Warehouse and client addresses. Coordinates are optional; we can find them.",
    fields=(
        Field("name", "Nomi", "Название", unique=True, example="Main warehouse", width=24),
        Field("place_type", "Turi", "Тип", choices=GEOFENCE_TYPES, example="Warehouse"),
        Field("address", "Manzil", "Адрес", example="Toshkent, Sergeli, ...", width=36),
        Field("latitude", "Kenglik", "Широта", partial(parse_decimal, minimum=-90),
              required=False, example=41.2995),
        Field("longitude", "Uzunlik", "Долгота", partial(parse_decimal, minimum=-180),
              required=False, example=69.2401),
        Field("radius_m", "Radius (m)", "Радиус (м)", partial(parse_int, minimum=10),
              required=False, example=150),
    ),
)

APPROVERS = Sheet(
    key="approvers",
    title="Who confirms what",
    purpose="Staff who use the web app, and which driver entries each one confirms.",
    fields=(
        Field("full_name", "F.I.Sh.", "Ф.И.О.", example="Karimova Dilnoza", width=28),
        Field("phone", "Telegram telefon raqami", "Телефон в Telegram", parse_phone, unique=True,
              example="+998 93 765 43 21", width=22),
        Field("role", "Lavozimi", "Роль", choices=STAFF_ROLES, example="Dispatcher"),
        Field("daily_data", "Kunlik ma'lumot", "Ежедневные данные", parse_yes_no,
              choices=YES_NO, example="Yes"),
        Field("fuel", "Yoqilg'i", "Заправка", parse_yes_no, choices=YES_NO, example="Yes"),
        Field("service", "Moy / shina", "Масло / шины", parse_yes_no, choices=YES_NO,
              example="No"),
        Field("parts", "Ehtiyot qism", "Запчасти", parse_yes_no, choices=YES_NO, example="No"),
    ),
)

SETTINGS = Sheet(
    key="settings",
    title="Settings",
    purpose="Company rules for alerts and storage. Fill one row.",
    single_row=True,
    fields=(
        Field("work_start", "Ish boshlanishi", "Начало работы", parse_time, example="08:00"),
        Field("work_end", "Ish tugashi", "Конец работы", parse_time, example="19:00"),
        Field("work_days", "Ish kunlari", "Рабочие дни", example="Mon-Sat"),
        Field("speed_limit_city", "Shaharda tezlik (km/h)", "Скорость в городе (км/ч)",
              partial(parse_int, minimum=20, maximum=150), example=70),
        Field("speed_limit_highway", "Trassada tezlik (km/h)", "Скорость на трассе (км/ч)",
              partial(parse_int, minimum=20, maximum=150), example=100),
        Field("retention_months", "Marshrut tarixi (oy)", "Хранить маршруты (мес)",
              parse_int, choices=RETENTION_MONTHS, example="3"),
        Field("daily_reminder", "Kunlik eslatma vaqti", "Время напоминания", parse_time,
              example="18:00"),
    ),
)

ALL_SHEETS: tuple[Sheet, ...] = (
    VEHICLES,
    DRIVERS,
    LAST_SERVICE,
    SERVICE_INTERVALS,
    DOCUMENTS,
    STORE_OPENING,
    GEOFENCES,
    APPROVERS,
    SETTINGS,
)

SHEETS_BY_KEY = {s.key: s for s in ALL_SHEETS}
