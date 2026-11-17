"""Shared fixtures: a blank template and a helper to fill it like the company would."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from openpyxl import load_workbook

from fleet_import.schema import SHEETS_BY_KEY
from fleet_import.workbook import FIRST_DATA_ROW, write_template

# A complete, valid set of company data (two vehicles, two drivers).
VALID_DATA: dict[str, list[dict]] = {
    "vehicles": [
        {"plate": "01 A 123 BC", "brand": "Isuzu", "model": "NPR 82", "year": 2021,
         "vin": "JALC4B16507000001", "odometer_km": 154300, "fuel_type": "Dizel",
         "fuel_norm": 14.5},
        {"plate": "01 777 AAA", "brand": "Chevrolet", "model": "Damas", "year": 2019,
         "vin": "XWB4A11BV0A000002", "odometer_km": 98000, "fuel_type": "AI-80",
         "second_fuel_type": "Metan", "fuel_norm": 9, "second_fuel_norm": 8},
    ],
    "drivers": [
        {"full_name": "Aliyev Vali", "phone": "+998 90 123 45 67",
         "licence_number": "AF1234567", "licence_categories": "B, C",
         "licence_expiry": "31.12.2028", "default_plate": "01 A 123 BC"},
        {"full_name": "Karimov Ali", "phone": "93 765 43 21",
         "licence_number": "AF7654321", "licence_expiry": "01.06.2027"},
    ],
    "last_service": [
        {"plate": "01 A 123 BC", "service": "Oil", "date": "15.10.2026", "odometer_km": 150000},
        {"plate": "01 777 AAA", "service": "Tires", "date": "01.04.2026", "odometer_km": 90000},
    ],
    "service_intervals": [
        {"model": "NPR 82", "service": "Oil", "interval_km": 10000, "interval_months": 6},
        {"model": "Damas", "service": "Oil", "interval_km": 8000, "interval_months": 6},
    ],
    "documents": [
        {"owner_type": "Vehicle", "owner": "01 A 123 BC", "document_type": "Insurance",
         "expiry_date": "01.03.2027"},
        {"owner_type": "Driver", "owner": "+998901234567", "document_type": "Power of attorney",
         "expiry_date": "01.01.2027"},
    ],
    "store_opening": [
        {"item": "Motor oil 15W-40", "category": "Oil", "unit": "l", "quantity": 120,
         "min_level": 40, "supplier": "Lukoil", "unit_price_uzs": 45000},
    ],
    "geofences": [
        {"name": "Main warehouse", "place_type": "Warehouse", "address": "Toshkent, Sergeli",
         "latitude": 41.2265, "longitude": 69.2210, "radius_m": 150},
    ],
    "approvers": [
        {"full_name": "Karimova Dilnoza", "phone": "+998 93 000 11 22", "role": "Dispatcher",
         "daily_data": "Yes", "fuel": "Yes", "service": "No", "parts": "No"},
    ],
    "settings": [
        {"work_start": "08:00", "work_end": "19:00", "work_days": "Mon-Sat",
         "speed_limit_city": 70, "speed_limit_highway": 100, "retention_months": "3",
         "daily_reminder": "18:00"},
    ],
}


def fill_template(path: Path, data: dict[str, list[dict]]) -> Path:
    """Write rows into a blank template, from row 3, like a person would."""
    wb = load_workbook(path)
    for key, rows in data.items():
        sheet = SHEETS_BY_KEY[key]
        ws = wb[sheet.title]
        for r, row in enumerate(rows, start=FIRST_DATA_ROW):
            for c, fld in enumerate(sheet.fields, start=1):
                if fld.key in row:
                    ws.cell(r, c, row[fld.key])
    wb.save(path)
    return path


@pytest.fixture
def valid_data() -> dict[str, list[dict]]:
    return copy.deepcopy(VALID_DATA)


@pytest.fixture
def template_path(tmp_path: Path) -> Path:
    return write_template(tmp_path / "fleet-data-template.xlsx")


@pytest.fixture
def filled(template_path: Path):
    """filled(data) -> path of the template filled with data."""
    return lambda data: fill_template(template_path, data)
