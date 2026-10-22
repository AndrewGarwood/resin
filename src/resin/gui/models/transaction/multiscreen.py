"""
*`@file`* `gui/models/transaction/multiscreen`
"""
from dataclasses import dataclass, replace
from typing import (Any, Literal, Mapping, Self, TypedDict)
from pyqi import export, Json, require
from resin.gui.utils import gui_id
from lute import LogMsg

class ScreenStepDict(TypedDict, total=False):
    """ requires at least one defined prop to be valid"""
    vkey: int | None
    """ vkey to send from active window"""
    button: str | None
    """ button id to find and click"""

@dataclass(frozen=True)
class ScreenStep(Json.Serial[ScreenStepDict]):
    vkey: int | None = None
    button: str | None = None

    def __post_init__(self):
        if (self.vkey is None and self.button is None):
            raise ValueError(LogMsg(
                "Invalid state for ScreenStep",
                "at least 1 of [self.vkey, self.button] must be defined"
            ))

    @classmethod
    def from_dict(cls, data: ScreenStepDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                vkey=data.get('vkey'),
                button=data.get('button')
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data))) from e

class ScreenFieldSelectionDict(TypedDict, total=False):
    step_in: ScreenStepDict | None # default to F5 ?
    fields: dict[str, Any]
    step_out: ScreenStepDict | None


@dataclass
class ScreenFieldSelection(Json.Serial[ScreenFieldSelectionDict]):
    step_in: ScreenStep # default to F5 ?
    fields: dict[str, Any]
    step_out: ScreenStep | None = None

    @classmethod
    def from_dict(cls, data: ScreenFieldSelectionDict | dict[str, Any]) -> Self:
        try:
            _in_value = data.get('step_in', None)
            _in: ScreenStep
            if (_in_value): _in = ScreenStep.from_dict(_in_value)
            else: _in = ScreenStep(vkey=gui_id.VKey.TXN_NEXT_SCREEN)
            _out_value = data.get('step_out')
            return cls(
                step_in=_in,
                fields=data.get('fields', dict()),
                step_out = ScreenStep.from_dict(_out_value) if _out_value else None
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data))) from e

    def with_fields(
        self, 
        fields: Mapping[str, Any], 
        /, 
        copy_existing: bool=False
    ) -> Self:
        """
        - *`@param`* `fields (Mapping[str, Any])` - entries that will be in returned `TransactionOptions.fields`
        - *`@param`* `copy_existing (bool)` - whether returned 
        `TransactionOptions.fields` will only contain entries in `fields` param or if it will be an updated copy of `self.fields` 
        """
        _result_fields: dict[str, Any] = {} if not copy_existing else { **self.fields }
        _result_fields.update(fields)
        return replace(self, fields=_result_fields)


    def set_field(self, field: str, value: Any, /) -> None:
        self.fields[require.non_empty_string(field, 'field')] = value
        return None





__all__ = export(ScreenStep, ScreenStepDict, ScreenFieldSelection, ScreenFieldSelectionDict)