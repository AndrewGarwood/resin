"""
*`@file`* `gui/services/transaction/transaction`
"""

from pathlib import Path
import threading
from typing import Callable, Optional

from pyqi.models import StageTransition, Telemetry

from resin.gui.models._export.result import ExportResult

from ...models.transaction import (
    TransactionOptions, 
    TransactionResult, 
    TransactionDetails, 
    TransactionStage
)
from resin.models._field import (resolve_field_dict)
from pyqi.models import (Flow)
from pyqi import (Json, Array, fs, String)
import re


class Transaction(Flow[TransactionStage]):
    code: str
    options: TransactionOptions

    def __init__(
        self, 
        options: TransactionOptions, 
        /,
        _id: fs.StrPath | None = None
    ): 
        self.options = options
        self.code = options.code
        self.fields = resolve_field_dict(options.fields)
        self.layout = options.layout
        self.method = options.method
        self.export_options = options.export
        self.variant = options.variant

        if (options.layout and options.layout.field_id not in self.fields):
            self.fields[options.layout.field_id] = options.layout.name

        self.exec_tel = Telemetry()
        self.export_tel = Telemetry()

        self._stage = TransactionStage.CREATED
        self._stage_history: list[StageTransition[TransactionStage]] = []

        self._failure: Optional[BaseException] = None
        self._export_result: Optional[ExportResult] = None

        self._state_lock = threading.RLock()
        self._state_changed = threading.Condition(self._state_lock)


def resolve_transaction_id(
    txn: Transaction | TransactionOptions, 
    /, 
    _id: fs.StrPath | None=None,
    extract_id_from_path: Callable[[Path], str] = lambda p: re.sub(r"^\d{4}(\.|-)\d{2}(\.|-)\d{2}_", "", p.stem)
) -> str:
    if (_id is not None):
        return _id.stem if isinstance(_id, Path) else _id
    _txn = txn.options if isinstance(txn, Transaction) else txn
    layout_label = (_txn.layout.name if _txn.layout is not None else None)
    id_from_path: str | None = None
    if _txn.export and _txn.export.file and _txn.export.file.path:
        id_from_path = extract_id_from_path(_txn.export.file.path)
    return id_from_path or layout_label or _txn.code