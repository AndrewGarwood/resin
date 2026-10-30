"""
*`@file`* `gui/services/transaction/field_operation`
"""
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class _SetText:
    field_id: str
    value: str


@dataclass(frozen=True, slots=True)
class _SetCheckbox:
    field_id: str
    value: bool


@dataclass(frozen=True, slots=True)
class _SelectRadio:
    field_id: str


@dataclass(frozen=True, slots=True)
class _SetMultiSelection:
    field_id: str
    button_id: str
    include_values: tuple[str, ...]
    include_ranges: tuple[tuple[str, str], ...]
    exclude_values: tuple[str, ...]
    exclude_ranges: tuple[tuple[str, str], ...]


_FieldOperation: TypeAlias = _SetText | _SetCheckbox | _SelectRadio | _SetMultiSelection

__all__ = ["_FieldOperation", "_SetText", "_SetCheckbox", "_SelectRadio", "_SetMultiSelection"]