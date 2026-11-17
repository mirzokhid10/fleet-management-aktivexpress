"""Build the blank data-template workbook the company fills in."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .schema import ALL_SHEETS, Sheet

HEADER_ROW = 1
HINT_ROW = 2
FIRST_DATA_ROW = 3
MAX_ROWS = 1000

BRAND = "465FFF"  # TailAdmin brand-500, same as the web app
HEADER_FILL = PatternFill("solid", fgColor=BRAND)
HEADER_FONT = Font(bold=True, color="FFFFFF")
HINT_FONT = Font(italic=True, color="667085")
REQUIRED_MARK = " *"

INSTRUCTIONS = [
    ("Aktivexpress Fleet — boshlang'ich ma'lumotlar / начальные данные", True),
    ("", False),
    ("UZ: Har bir varaqni to'ldiring. 1-qator — sarlavha, 2-qator — namuna (o'chirmang). "
     "Ma'lumotni 3-qatordan yozing. * — majburiy ustun.", False),
    ("RU: Заполните каждый лист. Строка 1 — заголовок, строка 2 — пример (не удаляйте). "
     "Данные пишите с 3-й строки. * — обязательный столбец.", False),
    ("EN: Fill every sheet. Row 1 is the header, row 2 is an example (keep it). "
     "Enter data from row 3. * marks a required column.", False),
    ("", False),
    ("Dates: 31.12.2026 · Phones: +998 90 123 45 67 · Plates: 01 A 123 BC / 01 123 ABC", False),
    ("", False),
]


def _hint(field) -> str:
    parts = []
    if field.example is not None:
        parts.append(f"e.g. {field.example}")
    if field.choices:
        parts.append("pick from list")
    if field.note:
        parts.append(field.note)
    return " · ".join(parts)


def _write_sheet(ws, sheet: Sheet) -> None:
    for col, field in enumerate(sheet.fields, start=1):
        letter = get_column_letter(col)
        header = ws.cell(HEADER_ROW, col, field.header + (REQUIRED_MARK if field.required else ""))
        header.fill = HEADER_FILL
        header.font = HEADER_FONT
        header.alignment = Alignment(wrap_text=True, vertical="center")

        hint = ws.cell(HINT_ROW, col, _hint(field))
        hint.font = HINT_FONT
        hint.alignment = Alignment(wrap_text=True, vertical="top")

        ws.column_dimensions[letter].width = field.width

        if field.choices:
            dv = DataValidation(
                type="list",
                formula1='"' + ",".join(field.choices) + '"',
                allow_blank=not field.required,
                showErrorMessage=True,
                errorTitle="Invalid value",
                error="Pick a value from the list",
            )
            dv.add(f"{letter}{FIRST_DATA_ROW}:{letter}{MAX_ROWS}")
            ws.add_data_validation(dv)

    ws.row_dimensions[HEADER_ROW].height = 36
    ws.row_dimensions[HINT_ROW].height = 30
    ws.freeze_panes = ws.cell(FIRST_DATA_ROW, 1)


def build_workbook() -> Workbook:
    wb = Workbook()
    intro = wb.active
    intro.title = "Instructions"
    intro.column_dimensions["A"].width = 120
    for row, (text, bold) in enumerate(INSTRUCTIONS, start=1):
        cell = intro.cell(row, 1, text)
        cell.font = Font(bold=bold, size=14 if bold else 11)
        cell.alignment = Alignment(wrap_text=True)
    start = len(INSTRUCTIONS) + 1
    for i, sheet in enumerate(ALL_SHEETS):
        intro.cell(start + i, 1, f"• {sheet.title}: {sheet.purpose}")

    for sheet in ALL_SHEETS:
        _write_sheet(wb.create_sheet(sheet.title), sheet)
    return wb


def write_template(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    build_workbook().save(path)
    return path
