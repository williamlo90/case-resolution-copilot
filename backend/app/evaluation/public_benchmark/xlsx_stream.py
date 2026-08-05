import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_RELATIONSHIP_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REFERENCE = re.compile(r"^([A-Z]+)\d+$")


def iter_xlsx_rows(
    workbook_path: Path,
    *,
    max_rows_per_sheet: int,
) -> Iterator[tuple[str, dict[str, str | None]]]:
    if max_rows_per_sheet < 1:
        raise ValueError("max_rows_per_sheet must be positive.")
    with zipfile.ZipFile(workbook_path) as archive:
        _validate_xlsx_members(archive)
        shared_strings = _read_shared_strings(archive)
        for sheet_name, sheet_path in _read_sheet_paths(archive):
            yield from _iter_sheet_rows(
                archive,
                sheet_name=sheet_name,
                sheet_path=sheet_path,
                shared_strings=shared_strings,
                max_rows=max_rows_per_sheet,
            )


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    values: list[str] = []
    with archive.open(path) as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if _local_name(element.tag) != "si":
                continue
            text = "".join(
                part.text or "" for part in element.iter() if _local_name(part.tag) == "t"
            )
            values.append(text)
            element.clear()
    return values


def _read_sheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationships = {
        item.attrib["Id"]: _normalize_sheet_target(item.attrib["Target"])
        for item in relationships_root.findall(f"{{{_PACKAGE_RELATIONSHIP_NS}}}Relationship")
        if item.attrib.get("Type", "").endswith("/worksheet")
    }
    sheets: list[tuple[str, str]] = []
    for sheet in workbook_root.findall(f".//{{{_SPREADSHEET_NS}}}sheet"):
        relationship_id = sheet.attrib.get(f"{{{_RELATIONSHIP_NS}}}id")
        if relationship_id is None or relationship_id not in relationships:
            continue
        path = relationships[relationship_id]
        if path not in archive.namelist():
            raise ValueError(f"XLSX worksheet is missing: {path}")
        sheets.append((sheet.attrib.get("name", path), path))
    if not sheets:
        raise ValueError("XLSX workbook contains no readable worksheets.")
    return sheets


def _iter_sheet_rows(
    archive: zipfile.ZipFile,
    *,
    sheet_name: str,
    sheet_path: str,
    shared_strings: list[str],
    max_rows: int,
) -> Iterator[tuple[str, dict[str, str | None]]]:
    headers: dict[int, str] | None = None
    emitted = 0
    with archive.open(sheet_path) as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if _local_name(element.tag) != "row":
                continue
            cells: dict[int, str | None] = {}
            for cell in element:
                if _local_name(cell.tag) != "c":
                    continue
                reference = cell.attrib.get("r", "")
                column = _column_index(reference)
                cells[column] = _cell_value(cell, shared_strings)
            element.clear()
            if not cells:
                continue
            if headers is None:
                headers = {
                    index: value.strip()
                    for index, value in cells.items()
                    if value is not None and value.strip()
                }
                continue
            row = {header: cells.get(index) for index, header in headers.items()}
            yield sheet_name, row
            emitted += 1
            if emitted >= max_rows:
                break


def _cell_value(element: ET.Element, shared_strings: list[str]) -> str | None:
    cell_type = element.attrib.get("t")
    if cell_type == "inlineStr":
        text = "".join(part.text or "" for part in element.iter() if _local_name(part.tag) == "t")
        return text
    value_element = next(
        (child for child in element if _local_name(child.tag) == "v"),
        None,
    )
    if value_element is None or value_element.text is None:
        return None
    raw = value_element.text
    if cell_type == "s":
        index = int(raw)
        if index < 0 or index >= len(shared_strings):
            raise ValueError(f"XLSX shared-string index is out of range: {index}")
        return shared_strings[index]
    if cell_type == "b":
        return "true" if raw == "1" else "false"
    return raw


def _column_index(reference: str) -> int:
    match = _CELL_REFERENCE.match(reference)
    if match is None:
        raise ValueError(f"Invalid XLSX cell reference: {reference}")
    result = 0
    for character in match.group(1):
        result = result * 26 + (ord(character) - ord("A") + 1)
    return result - 1


def _normalize_sheet_target(target: str) -> str:
    normalized = target.replace("\\", "/").lstrip("/")
    if not normalized.startswith("xl/"):
        normalized = f"xl/{normalized}"
    path = PurePosixPath(normalized)
    if ".." in path.parts:
        raise ValueError(f"Unsafe XLSX worksheet target: {target}")
    return path.as_posix()


def _validate_xlsx_members(archive: zipfile.ZipFile) -> None:
    required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
    missing = required.difference(archive.namelist())
    if missing:
        raise ValueError(f"Invalid XLSX archive; missing {sorted(missing)}.")
    for name in archive.namelist():
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe XLSX archive member: {name}")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]
