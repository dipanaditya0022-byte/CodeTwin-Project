"""Reading a response sheet (CSV or XLSX), such as a Google Forms export, into rows of text.

Limits are checked before parsing: file size, the expanded size of an .xlsx (which is a zip
archive), rows, columns and cell length. Only values are read; formulas are never evaluated.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime

MAX_SHEET_BYTES = 5 * 1024 * 1024
MAX_XLSX_EXPANDED = 50 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 60
MAX_CELL = 2000


class SheetError(ValueError):
    pass


def read_table(filename: str, data: bytes) -> tuple[list[str], list[dict]]:
    """(headers, rows), each row a {header: text} dict. Empty rows are dropped."""
    if len(data) > MAX_SHEET_BYTES:
        raise SheetError("The spreadsheet is larger than 5 MB")
    name = (filename or "").lower()
    if name.endswith(".csv"):
        grid = _csv(data)
    elif name.endswith(".xlsx"):
        grid = _xlsx(data)
    else:
        raise SheetError("Upload the responses as .csv or .xlsx (in Google Forms: Responses → Download responses)")

    grid = [[_text(v) for v in row] for row in grid]
    grid = [row for row in grid if any(row)]
    if not grid:
        raise SheetError("The spreadsheet is empty")
    headers = _headers(grid[0])
    if len(headers) > MAX_COLUMNS:
        raise SheetError(f"The spreadsheet has more than {MAX_COLUMNS} columns")
    body = grid[1:]
    if len(body) > MAX_ROWS:
        raise SheetError(f"The spreadsheet has more than {MAX_ROWS} rows")
    rows = [{h: (row[i] if i < len(row) else "") for i, h in enumerate(headers)} for row in body]
    return headers, rows


def _csv(data: bytes) -> list[list]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SheetError("The CSV file is not UTF-8 text. Export it again as UTF-8 CSV")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _xlsx(data: bytes) -> list[list]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            if sum(i.file_size for i in zf.infolist()) > MAX_XLSX_EXPANDED:
                raise SheetError("The spreadsheet expands to more than the allowed size")
    except zipfile.BadZipFile:
        raise SheetError("This .xlsx file could not be opened")
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise SheetError("This .xlsx file could not be opened")
    try:
        sheet = wb.worksheets[0]
        grid = []
        for row in sheet.iter_rows(values_only=True):
            grid.append(list(row[:MAX_COLUMNS + 1]))
            if len(grid) > MAX_ROWS + 1:
                break
        return grid
    finally:
        wb.close()


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        value = int(value)   # roll numbers typed as numbers come back as 22014.0
    return str(value).strip()[:MAX_CELL]


def _headers(first: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for i, h in enumerate(first):
        h = " ".join(h.split()) or f"Column {i + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h} ({seen[h]})"
        else:
            seen[h] = 1
        out.append(h)
    return out
