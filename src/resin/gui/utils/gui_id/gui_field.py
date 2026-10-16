"""
*`@file`* `gui/utils/gui_id/gui_field`
"""
from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass
from typing import (Any, Self)
from pyqi import (export)
from resin.models._field import resolve_field_value
import re

# Uppercase SAP identifier segment:
#   BWART
#   RSCSEL_255
#   SLOW_I
#
# Underscores are allowed internally, but not at either end.
_IDENTIFIER_PATTERN = r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*"


_COMPONENT_PATTERN = re.compile(
    rf"""
    ^
    (?P<component_type>[a-z]+)
    (?P<body>.*)
    $
    """,
    re.VERBOSE,
)


_INDEX_PATTERN = re.compile(
    r"""
    ^
    (?P<body>.*?)
    (?:
        \[
            (?P<first_index>\d+)
            (?:
                ,
                (?P<second_index>\d+)
            )?
        \]
    )?
    $
    """,
    re.VERBOSE,
)


_STANDARD_BODY_PATTERN = re.compile(
    rf"""
    ^
    (?:
        (?P<base>{_IDENTIFIER_PATTERN})
        (?:
            -
            (?P<field_variant>{_IDENTIFIER_PATTERN})
        )?
    )?
    $
    """,
    re.VERBOSE,
)


_SELECTION_BUTTON_BODY_PATTERN = re.compile(
    rf"""
    ^
    %_
    (?P<base>{_IDENTIFIER_PATTERN})
    _%_APP_%
    (?:
        -
        (?P<field_variant>{_IDENTIFIER_PATTERN})
    )?
    $
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class SapFieldIdStem:
    """
    `@dataclass(frozen=True, slots=True)`
    - every part except `component_type` is optional 
    
    `component_id = 'app/ses[i]/wnd[j]/path/to/{field_id_stem}'`
    - `field_id_stem` = `'<component_type><base>-<field_variant>[<index>]'`

    example stems:
    - `"btn%_BWART_%_APP_%-VALU_PUSH"`
    - `"ctxtRSCSEL_255-SLOW_I[1,0]"`
    - `"btn[8]"`
    """
    component_type: str
    base: str | None = None
    field_variant: str | None = None
    is_selection_button: bool = False
    grid_x: int | None = None
    grid_y: int | None = None
    container_index: int | None = None

    def __post_init__(self) -> None:
        if not self.component_type:
            raise ValueError("component_type cannot be empty")

        if not self.component_type.isalpha():
            raise ValueError(
                "component_type must contain only alphabetic characters"
            )

        if not self.component_type.islower():
            raise ValueError("component_type must be lowercase")

        if self.is_selection_button and self.base is None:
            raise ValueError(
                "A selection button must have a base identifier"
            )

        has_grid_x = self.grid_x is not None
        has_grid_y = self.grid_y is not None

        if has_grid_x != has_grid_y:
            raise ValueError(
                "grid_x and grid_y must either both be set or both be None"
            )

        if has_grid_x and self.container_index is not None:
            raise ValueError(
                "Grid coordinates and container_index are mutually exclusive"
            )

        for name, value in (
            ("grid_x", self.grid_x),
            ("grid_y", self.grid_y),
            ("container_index", self.container_index),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")

        for name, value in (
            ("base", self.base),
            ("field_variant", self.field_variant),
        ):
            if value is not None and re.fullmatch(
                _IDENTIFIER_PATTERN,
                value,
            ) is None:
                raise ValueError(
                    f"Invalid {name}: {value!r}. "
                    "Expected an uppercase SAP identifier with optional "
                    "internal underscores."
                )

    @classmethod
    def parse(cls, field_id: str, /) -> Self:
        """
        Parse either a complete SAP GUI field ID or an isolated field-ID stem.

        Examples:
            wnd[0]/usr/ctxtBWART-LOW
            ctxtBWART-LOW
            btn[8]
        """
        if not isinstance(field_id, str):
            raise TypeError(
                f"field_id must be str, not {type(field_id).__name__}"
            )

        stem = field_id.rsplit("/", maxsplit=1)[-1]
        if not stem:
            raise ValueError("field_id does not contain a non-empty stem")

        index_match = _INDEX_PATTERN.fullmatch(stem)
        if index_match is None:
            raise ValueError(f"Invalid SAP field ID stem: {stem!r}")

        stem_without_index = index_match["body"]
        first_index = index_match["first_index"]
        second_index = index_match["second_index"]

        component_match = _COMPONENT_PATTERN.fullmatch(stem_without_index)
        if component_match is None:
            raise ValueError(
                f"Could not parse component type from stem: {stem!r}"
            )

        component_type = component_match["component_type"]
        body = component_match["body"]

        selection_match = _SELECTION_BUTTON_BODY_PATTERN.fullmatch(body)
        if selection_match is not None:
            is_selection_button = True
            base = selection_match["base"]
            field_variant = selection_match["field_variant"]
        else:
            standard_match = _STANDARD_BODY_PATTERN.fullmatch(body)
            if standard_match is None:
                raise ValueError(
                    f"Could not parse SAP field ID body {body!r} "
                    f"from stem {stem!r}"
                )
            is_selection_button = False
            base = standard_match["base"]
            field_variant = standard_match["field_variant"]
        if second_index is not None:
            grid_x = int(first_index)
            grid_y = int(second_index)
            container_index = None
        else:
            grid_x = None
            grid_y = None
            container_index = (
                int(first_index)
                if first_index is not None
                else None
            )
        return cls(
            component_type=component_type,
            base=base,
            field_variant=field_variant,
            is_selection_button=is_selection_button,
            grid_x=grid_x,
            grid_y=grid_y,
            container_index=container_index,
        )

    @property
    def without_index(self) -> str:
        """ 
        the part of the stem up to the grid/container indexing part

        i.e. 
        - `'{this_part}[grid_x,grid_y]'` 
        - `'{this_part][container_index]'`
        """
        parts = [self.component_type]
        parts = [self.component_type]
        if self.base is not None:
            if self.is_selection_button:
                parts.append(self.wrap_selection_button_base(self.base))
            else:
                parts.append(self.base)
        if self.field_variant is not None:
            parts.append(f"-{self.field_variant}")
        return "".join(parts)



    def compile(self) -> str:
        """Compile the parsed components back into an SAP GUI ID stem."""
        parts = [self.without_index]
        if self.grid_x is not None:
            # __post_init__ guarantees that grid_y is also set.
            parts.append(f"[{self.grid_x},{self.grid_y}]")
        elif self.container_index is not None:
            parts.append(f"[{self.container_index}]")
        return "".join(parts)

    def __str__(self) -> str:
        return self.compile()

    @staticmethod
    def wrap_selection_button_base(base: str, /) -> str:
        """ 
        *`@returns`* `f"%_{base}_%_APP_%"`
        - use for combo text field button
        """
        return f"%_{base}_%_APP_%"

    @staticmethod
    def selection_button(base: str, /) -> str:
        """
        *`@returns`* `f"btn{SapFieldIdStem.wrap_selection_button_base(base)}-VALU-PUSH"`
        """
        return (
            f"btn{SapFieldIdStem.wrap_selection_button_base(base)}-VALU-PUSH"
        )

    # def generate_grid_entries(
    #     self, 
    #     values: Iterable[Any],
    #     /,
    # ) -> dict[str, str]:
    #     result: dict[str, Any] = {}

    #     raise NotImplementedError

    # def generate_grid_indices(self, row_count: int, /) -> list[str]:
    #     raise NotImplementedError


__all__ = export (SapFieldIdStem)