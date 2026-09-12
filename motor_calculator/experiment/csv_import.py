"""Phase 11A: reading a measurement CSV without inventing anything.

Design rules, all of which exist because the opposite behaviour is common and
destroys data quietly:

* **No silent coercion.** ``12,5`` in a comma-separated file is an error with a
  row and column number, not ``12``. ``n/a`` is a missing value, not zero.
* **Missing is missing.** A blank cell becomes ``None`` and the row records
  which fields it lacks. It never becomes 0.0, and a row missing a field an
  analysis needs is excluded from that analysis by name, not dropped silently.
* **Errors accumulate.** The importer reports every problem in the file, so a
  user fixes a file once rather than discovering its faults one row at a time.
* **Determinism.** Same bytes in, same result out, including the hash and the
  order of rows and errors. No dict ordering, no set iteration, no locale.
* **Units come from somewhere explicit.** Either a header suffix, or the
  caller's declaration. A column whose unit cannot be established is an error;
  the importer never assumes SI.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .columns import (
    AmbiguousColumnError,
    CANONICAL_BY_NAME,
    CanonicalColumn,
    UnknownColumnError,
    missing_required_columns,
    resolve_header,
    unit_suffix,
)
from .schema import TestType
from .units import NormalizedValue, UnitError, normalize

CSV_IMPORT_SCHEMA_VERSION = "phase11a.experiment.csv.v1"

#: A line whose first non-space character is one of these is a comment.
COMMENT_PREFIXES = ("#", "//")

#: Cell contents recognised as "no value here". Compared case-insensitively
#: after stripping. Anything else that is not a number is an error.
MISSING_TOKENS = frozenset({"", "na", "n/a", "nan", "null", "none", "-", "--", "—"})


@dataclass(frozen=True)
class ImportError_:
    """One specific, located problem. Never a summary."""

    #: 1-based line number in the source file, as a user's editor shows it.
    line: int | None
    column: str | None
    code: str
    message_zh: str

    def __str__(self) -> str:
        where = []
        if self.line is not None:
            where.append(f"第 {self.line} 行")
        if self.column:
            where.append(f"列「{self.column}」")
        prefix = "，".join(where)
        return f"[{self.code}] {prefix}：{self.message_zh}" if prefix else f"[{self.code}] {self.message_zh}"


@dataclass(frozen=True)
class MeasurementRow:
    """One sample. Canonical values plus the originals they came from."""

    line: int
    values: Mapping[str, float]
    normalized: Mapping[str, NormalizedValue]
    missing: tuple[str, ...] = ()

    def get(self, name: str, default: Any = None) -> Any:
        return self.values.get(name, default)

    def has(self, *names: str) -> bool:
        return all(name in self.values for name in names)


@dataclass(frozen=True)
class ColumnBinding:
    """How one source header was understood."""

    source_header: str
    canonical: str
    original_unit: str
    canonical_unit: str
    #: "HEADER_SUFFIX", "EXPLICIT_UNIT", "CANONICAL_DEFAULT"
    unit_provenance: str
    #: "HEADER_ALIAS" or "EXPLICIT_MAPPING"
    mapping_provenance: str


@dataclass(frozen=True)
class ImportedDataset:
    """The result of reading one file."""

    schema_version: str
    test_type: TestType
    rows: tuple[MeasurementRow, ...]
    bindings: tuple[ColumnBinding, ...]
    errors: tuple[ImportError_, ...]
    ignored_headers: tuple[str, ...] = ()
    raw_sha256: str | None = None
    source_name: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """True only when nothing at all went wrong.

        A dataset with any error is not partially usable: the caller decides
        what to do, but it is never presented as a clean import.
        """

        return not self.errors

    @property
    def present_columns(self) -> frozenset[str]:
        return frozenset(binding.canonical for binding in self.bindings)

    @property
    def sample_count(self) -> int:
        return len(self.rows)


class CsvImportRejected(ValueError):
    """Raised by :func:`import_csv_strict` when a file has any error."""

    def __init__(self, dataset: ImportedDataset) -> None:
        self.dataset = dataset
        super().__init__(
            "CSV import rejected with "
            f"{len(dataset.errors)} error(s):\n"
            + "\n".join(str(error) for error in dataset.errors[:20])
        )


def _is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return any(stripped.startswith(prefix) for prefix in COMMENT_PREFIXES)


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith("﻿") else text


def _parse_number(raw: str) -> float | None:
    """A float, or ``None`` for a recognised missing token.

    Raises ``ValueError`` for anything else -- including ``1,5``, which is a
    decimal comma in a comma-separated file and cannot be silently reinterpreted.
    """

    text = raw.strip()
    if text.lower() in MISSING_TOKENS:
        return None
    return float(text)


def import_csv_text(
    text: str,
    *,
    test_type: TestType | str,
    column_mapping: Mapping[str, str] | None = None,
    column_units: Mapping[str, str] | None = None,
    source_name: str | None = None,
    raw_sha256: str | None = None,
) -> ImportedDataset:
    """Parse measurement CSV text. Always returns; never raises on bad data.

    ``column_mapping`` maps a source header to a canonical field name and always
    wins over header recognition, because it is a statement by somebody who
    knows the file. ``column_units`` does the same for units.
    """

    test_type = TestType(test_type)
    mapping = {str(k).strip(): str(v).strip() for k, v in (column_mapping or {}).items()}
    units = {str(k).strip(): str(v).strip() for k, v in (column_units or {}).items()}

    errors: list[ImportError_] = []
    warnings: list[str] = []

    lines = _strip_bom(text).splitlines()
    # Keep the original 1-based line numbers so an error points at the file a
    # user is looking at, not at a filtered copy of it.
    numbered = [
        (index + 1, line)
        for index, line in enumerate(lines)
        if line.strip() and not _is_comment(line)
    ]
    if not numbered:
        return ImportedDataset(
            schema_version=CSV_IMPORT_SCHEMA_VERSION,
            test_type=test_type,
            rows=(),
            bindings=(),
            errors=(
                ImportError_(None, None, "EMPTY_FILE", "文件中没有任何数据行（空行与注释已忽略）。"),
            ),
            raw_sha256=raw_sha256,
            source_name=source_name,
        )

    header_line, header_text = numbered[0]
    headers = [cell.strip() for cell in next(csv.reader([header_text]))]
    if len(headers) != len(set(headers)):
        duplicates = sorted({h for h in headers if headers.count(h) > 1})
        errors.append(
            ImportError_(
                header_line, ", ".join(duplicates), "DUPLICATE_HEADER",
                "表头中存在重复列名；无法确定哪一列是哪一个量。",
            )
        )

    bindings: list[ColumnBinding] = []
    index_to_binding: dict[int, ColumnBinding] = {}
    ignored: list[str] = []

    for index, header in enumerate(headers):
        if not header:
            ignored.append(f"<第 {index + 1} 列，无表头>")
            continue
        column: CanonicalColumn | None = None
        mapping_provenance = "HEADER_ALIAS"
        if header in mapping:
            target = mapping[header]
            if target not in CANONICAL_BY_NAME:
                errors.append(
                    ImportError_(
                        header_line, header, "UNKNOWN_MAPPING_TARGET",
                        f"显式映射的目标字段 {target!r} 不是已知的规范字段。",
                    )
                )
                continue
            column = CANONICAL_BY_NAME[target]
            mapping_provenance = "EXPLICIT_MAPPING"
        else:
            try:
                column = resolve_header(header)
            except AmbiguousColumnError as error:
                errors.append(
                    ImportError_(
                        header_line, header, "AMBIGUOUS_COLUMN",
                        f"该列未说明其测量基准，拒绝猜测。可显式映射为："
                        f"{'、'.join(error.candidates)}。",
                    )
                )
                continue
            except UnknownColumnError:
                ignored.append(header)
                continue

        unit = units.get(header)
        unit_provenance = "EXPLICIT_UNIT"
        if unit is None:
            suffix = unit_suffix(header)
            if suffix is not None:
                unit, unit_provenance = suffix, "HEADER_SUFFIX"
            else:
                unit, unit_provenance = column.canonical_unit, "CANONICAL_DEFAULT"
        try:
            probe = normalize(0.0, unit, expected_canonical=column.canonical_unit)
        except UnitError as error:
            errors.append(
                ImportError_(header_line, header, "BAD_UNIT", str(error))
            )
            continue

        binding = ColumnBinding(
            source_header=header,
            canonical=column.name,
            original_unit=probe.original_unit,
            canonical_unit=column.canonical_unit,
            unit_provenance=unit_provenance,
            mapping_provenance=mapping_provenance,
        )
        if any(existing.canonical == column.name for existing in bindings):
            errors.append(
                ImportError_(
                    header_line, header, "DUPLICATE_CANONICAL_COLUMN",
                    f"多个列都映射到规范字段 {column.name!r}。",
                )
            )
            continue
        bindings.append(binding)
        index_to_binding[index] = binding

    if unit_provenance_warning := [
        b.source_header for b in bindings if b.unit_provenance == "CANONICAL_DEFAULT"
    ]:
        warnings.append(
            "以下列的单位未在表头或导入设置中给出，按规范单位读取："
            + "、".join(unit_provenance_warning)
        )

    rows: list[MeasurementRow] = []
    for line_number, raw_line in numbered[1:]:
        cells = next(csv.reader([raw_line]))
        if len(cells) != len(headers):
            errors.append(
                ImportError_(
                    line_number, None, "COLUMN_COUNT_MISMATCH",
                    f"该行有 {len(cells)} 个字段，表头有 {len(headers)} 个。",
                )
            )
            continue
        values: dict[str, float] = {}
        normalized: dict[str, NormalizedValue] = {}
        missing: list[str] = []
        for index, binding in sorted(index_to_binding.items()):
            raw_cell = cells[index]
            try:
                number = _parse_number(raw_cell)
            except ValueError:
                errors.append(
                    ImportError_(
                        line_number, binding.source_header, "NOT_A_NUMBER",
                        f"无法解析为数值：{raw_cell!r}。"
                        "本导入器不会把无法解析的单元格当作 0 或忽略掉。",
                    )
                )
                continue
            if number is None:
                missing.append(binding.canonical)
                continue
            try:
                converted = normalize(
                    number, binding.original_unit,
                    expected_canonical=binding.canonical_unit,
                )
            except UnitError as error:
                errors.append(
                    ImportError_(line_number, binding.source_header, "BAD_VALUE", str(error))
                )
                continue
            values[binding.canonical] = converted.value
            normalized[binding.canonical] = converted
        rows.append(
            MeasurementRow(
                line=line_number,
                values=values,
                normalized=normalized,
                missing=tuple(missing),
            )
        )

    present = frozenset(binding.canonical for binding in bindings)
    for group in missing_required_columns(test_type, present):
        errors.append(
            ImportError_(
                header_line, None, "MISSING_REQUIRED_COLUMN",
                f"{test_type.value} 至少需要以下列之一：{'、'.join(group)}。",
            )
        )
    if not rows and not errors:
        errors.append(
            ImportError_(None, None, "NO_DATA_ROWS", "文件只有表头，没有数据行。")
        )

    return ImportedDataset(
        schema_version=CSV_IMPORT_SCHEMA_VERSION,
        test_type=test_type,
        rows=tuple(rows),
        bindings=tuple(bindings),
        errors=tuple(errors),
        ignored_headers=tuple(ignored),
        raw_sha256=raw_sha256,
        source_name=source_name,
        warnings=tuple(warnings),
    )


def import_csv_file(path: str | Path, **kwargs: Any) -> ImportedDataset:
    """Read a UTF-8 CSV file and record the hash of the exact bytes read."""

    from .schema import file_sha256

    file_path = Path(path)
    raw = file_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return ImportedDataset(
            schema_version=CSV_IMPORT_SCHEMA_VERSION,
            test_type=TestType(kwargs.get("test_type", TestType.NO_LOAD_BACK_EMF)),
            rows=(), bindings=(),
            errors=(
                ImportError_(
                    None, None, "NOT_UTF8",
                    f"文件不是 UTF-8 编码，无法确定性解析：{error}。"
                    "请另存为 UTF-8 后重新导入。",
                ),
            ),
            source_name=file_path.name,
        )
    kwargs.setdefault("source_name", file_path.name)
    kwargs["raw_sha256"] = file_sha256(file_path)
    return import_csv_text(text, **kwargs)


def import_csv_strict(path: str | Path, **kwargs: Any) -> ImportedDataset:
    """As :func:`import_csv_file`, but raise on any error."""

    dataset = import_csv_file(path, **kwargs)
    if not dataset.ok:
        raise CsvImportRejected(dataset)
    return dataset


def rows_from_records(
    records: Sequence[Mapping[str, float]], *, start_line: int = 1
) -> tuple[MeasurementRow, ...]:
    """Build rows from already-canonical values, for manual GUI entry.

    Manual entry bypasses parsing but not the row shape, so every downstream
    analysis behaves identically whether a number was typed or imported.
    """

    built: list[MeasurementRow] = []
    for offset, record in enumerate(records):
        values = {
            str(key): float(value)
            for key, value in record.items()
            if value is not None and str(key) in CANONICAL_BY_NAME
        }
        normalized = {
            name: NormalizedValue(
                original_value=value,
                original_unit=CANONICAL_BY_NAME[name].canonical_unit,
                value=value,
                unit=CANONICAL_BY_NAME[name].canonical_unit,
                factor=1.0,
                provenance="MANUAL_ENTRY",
            )
            for name, value in values.items()
        }
        built.append(
            MeasurementRow(
                line=start_line + offset, values=values, normalized=normalized
            )
        )
    return tuple(built)
