"""
*`@file`* `gui/services/transaction/transaction`
"""

from pathlib import Path
import threading, time
from typing import (Any, Callable, Optional, Self)

from pyqi.models import StageTransition, Telemetry, Flow
from pyqi import (Json, Array, fs, String, require, dt, safe)
from lute import LogMsg, get_logger, annotate
from resin.gui.components.control import (TextField, CTextField, CheckBox)
from resin.models._field import (resolve_field_dict, resolve_field_value, SentinelKey)
from resin.gui.models._export._method import ExportMethod
from resin.gui.models._export.result import ExportResult
from resin.gui.models.transaction import (
    TransactionOptions, 
    TransactionResult, 
    TransactionDetails, 
    TransactionStage,
    VariantOptions,
    ExecutionType
)
from resin.gui.core import (Session)
from resin.gui.utils import (gui_id as GUI, wait_for_component)
from resin.gui.exceptions import (SapGuiError)
import re

mlog = get_logger(__file__)


def _default_id_extractor(p: Path) -> str:
    return re.sub(r"^\d{4}(\.|-)\d{2}(\.|-)\d{2}_", "", p.stem)

class Transaction(Flow[TransactionStage]):
    code: str
    options: TransactionOptions
    fields: dict[str, Any]
    """ 
    resolved field entries. 
    - can view `self.options.fields` for original/unresovled field dictionary 
    """
    execute_fn: Callable[[Self, Session], Any] | None
    """ 
    injection for executing transaction (e.g. if have different SAPGUI setup or something) 
    """

    def __init__(
        self, 
        options: TransactionOptions, 
        /,
        _id: fs.StrPath | None = None,
        extract_id_from_path: Callable[[Path], str] = _default_id_extractor,
        strict: bool = True,
        execute_fn: Callable[[Self, Session], Any] | None = None
    ): 
        self.strict = strict
        self.execute_fn = execute_fn

        self.options = options
        self.code = options.code
        self.fields = resolve_field_dict(options.fields)
        self.layout = options.layout
        self.method = ExecutionType.resolve(options.method)
        self.export_options = options.export
        self.variant = options.variant
        self.id = resolve_transaction_id(options, _id, extract_id_from_path)

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

    @property
    def id(self) -> str:
        return self._id
    @id.setter
    def id(self, value: str) -> None:
        _id = _id = require.non_empty_string(value, "Transaction Id")
        self._id = _id
        self.options._id = _id
    
    @property
    def stage(self) -> TransactionStage:
        with self._state_lock:
            return self._stage

    @property
    def stage_history(self) -> tuple[StageTransition, ...]:
        with self._state_lock:
            return tuple(self._stage_history)

    @property
    def failure(self) -> Optional[BaseException]:
        with self._state_lock:
            return self._failure

    @property
    def export_result(self) -> Optional[ExportResult]:
        with self._state_lock:
            return self._export_result

    @property
    def requires_export(self) -> bool:
        return (
            self.export_options is not None 
            and self.export_options.method != ExportMethod.NONE
        )
    
    @property
    def is_terminal(self) -> bool:
        return self.stage in {
            TransactionStage.COMPLETED,
            TransactionStage.FAILED,
        }


    # =========================================================================
    # Stage synchronization
    # =========================================================================
    def _transition(
        self, 
        expected: TransactionStage | set[TransactionStage], 
        target: TransactionStage
    ) -> None:
        """_summary_

        Args:
            expected (TransactionStage | set[TransactionStage]): stage(s) expected to transition from
                - (i.e. valid starting states)
            target (TransactionStage): stage trying to transition to

        Raises:
            RuntimeError: _description_
        """
        expected_stages = (
            {expected}
            if isinstance(expected, TransactionStage)
            else expected
        )
        with self._state_changed:
            current = self._stage
            if current not in expected_stages:
                expected_names = ", ".join(
                    sorted(stage.value for stage in expected_stages)
                )
                raise RuntimeError(LogMsg(
                    f"Invalid {self.__class__.__name__} stage transition.",
                    f"self.id={getattr(self, 'id', None)!r}",
                    f"attempted: {current.value} -> {target.value}",
                    f"expected: current stage in [{expected_names}]"
                ))
            self._stage = target
            self._stage_history.append(
                StageTransition(
                    previous=current,
                    current=target,
                    changed_at=dt.now(),
                )
            )
            self._state_changed.notify_all()

    def _fail(self, error: BaseException, /) -> None:
        with self._state_changed:
            previous = self._stage
            self._failure = error
            self._stage = TransactionStage.FAILED
            self._stage_history.append(
                StageTransition(
                    previous=previous,
                    current=TransactionStage.FAILED,
                    changed_at=dt.now(),
                )
            )
            self._state_changed.notify_all()

    def wait_for_stage(
        self,
        target: TransactionStage | set[TransactionStage],
        *,
        timeout: Optional[float] = None,
    ) -> TransactionStage:
        """
        Wait for this Transaction's local lifecycle state.

        This method performs no SAP COM calls, so a coordinator/watch thread
        can safely use it to observe readiness.
        """
        target_stages = (
            {target}
            if isinstance(target, TransactionStage)
            else target
        )
        with self._state_changed:
            reached = self._state_changed.wait_for(
                lambda: (
                    self._stage in target_stages
                    or self._stage is TransactionStage.FAILED
                ),
                timeout=timeout,
            )
            if not reached:
                expected = ", ".join(
                    sorted(stage.value for stage in target_stages)
                )
                raise TimeoutError(LogMsg(
                    f"Transaction {self.id!r} did not reach",
                    f"stage {{{expected}}} within {timeout} seconds",
                    f"current stage={self._stage.value!r}"
                ))
            if self._stage is TransactionStage.FAILED:
                error = self._failure
                raise RuntimeError(
                    f"Transaction {self.id!r} failed"
                ) from error
            return self._stage

    # =========================================================================
    # Configuration
    # =========================================================================
    def set_field(self, key: str, value: Any, /) -> None:
        """ if want to overwrite an entry in `self.fields` """
        key = require.non_empty_string(key, "Field Id")
        self.fields[key] = resolve_field_value(value)
    
    # =========================================================================
    # Core Transaction Flow
    # =========================================================================

    def open(self, session: Session, /) -> None:
        self._transition(
            set([TransactionStage.CREATED, TransactionStage.COMPLETED]), 
            TransactionStage.OPENING
        )
        session.start_transaction(self.code)

    def populate_selection_screen(self, session: Session, /) -> None:
        self._transition(TransactionStage.OPENING, TransactionStage.POPULATING_SELECTION)
        if (self.variant):
            self._load_variant(session, self.variant)
        if (self.fields):
            self._load_fields(session)
        if (self.strict and (not self.variant and not self.fields)):
            raise RuntimeError(LogMsg(
                f"No variant or fields available to populate transaction parameters",
            ))
        self._transition(
            TransactionStage.POPULATING_SELECTION, 
            TransactionStage.READY_TO_EXECUTE
        )
    
    def _load_variant(
        self, 
        session: Session,
        variant: VariantOptions,
        /,
    ) -> None:
        try:
            mlog.debug(LogMsg(
                f"Before send vkey to get variant, {session.active_window.id=}"
            ))
            session.main_window.send_vkey(GUI.VKey.GET_TXN_VARIANT)
            mlog.debug(LogMsg(
                f"After sent vkey, {session.active_window.id=}"
            ))
            wait_for_component(
                session, 
                GUI.txn_variant_name(),  #TODO: change
                component_cls=TextField,
                _raise=True
            ).set(variant.name)
            wait_for_component(
                session,
                GUI.txn_variant_created_by(),  #TODO: change
                component_cls=TextField,
                _raise=True
            ).set(variant.created_by)
            session.main_window.send_vkey(GUI.VKey.F8)
            time.sleep(0.5)
            mlog.debug(LogMsg(
                f"After confirm variant, {session.active_window.id=}"
            ))
        except SapGuiError:
            raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to load transaction variant",
                txn_id=self.id,
                txn_code=self.code,
                variant=str(self.variant)
            ))
        
    def _load_fields(self, session: Session, /):
        for (field_id, value) in self.fields.items():
            try:
                if (isinstance(value, list)):
                    raise NotImplementedError(f"Setting multiple values for field not yet supported")
                if (value == SentinelKey.RADIO_BUTTON_SELECT.value ):
                    session.select_radio_option(field_id)
                    continue
                stem = GUI.stem(field_id).lower()
                field_cls = (
                    TextField if stem.startswith(("txt", "ctxt", "okcd"))
                    else CheckBox if stem.startswith("chk")
                    else None
                )
                if (field_cls is None):
                    raise ValueError(LogMsg(
                        f"Unable to infer field_id's component class, or it is unsupported"
                    ))
                session.set_field_value(field_id, value, field_cls=field_cls)
            except Exception as e:
                raise RuntimeError(LogMsg.err(
                    e,
                    f"Failed to set field value",
                    txn_id=self.id,
                    txn_code=self.code,
                    field_id=field_id,
                    value=annotate(value),
                    status=safe.readattr(session, "status")
                )) from e


    def execute(self, session: Session, /) -> None:
        self._transition(
            TransactionStage.READY_TO_EXECUTE, 
            TransactionStage.EXECUTION_RUNNING
        )
        self.exec_tel.start()
        result: Any | None = None
        if (self.execute_fn is not None):
            mlog.info(LogMsg(f"Using injected execute function"))
            result = self.execute_fn(self, session)
        match self.method:
            case ExecutionType.STANDARD:
                result = self._execute_standard(session)
            case ExecutionType.BACKGROUND:
                result = self._execute_async(session)
            case _: # should be unreachable
                raise RuntimeError(LogMsg.bad_arg(
                    self.method, "Transaction.method",
                    "Invalid/unsupported ExecutionType", 
                    ExecutionType
                ))
        self.exec_tel.stop()
        self._transition(
            TransactionStage.EXECUTION_RUNNING, 
            TransactionStage.POST_EXECUTE
        )
        return result
    
    def _execute_standard(self, session: Session, /) -> None:
        session.main_window.send_vkey(GUI.VKey.EXEC_TXN)
        active_wnd_id = session.active_window.id
        confirm_btn = session.active_window.find(GUI.btn(0))
        raise NotImplementedError()

    def _execute_async(self, session: Session, /) -> None: 
        raise NotImplementedError()

def resolve_transaction_id(
    txn: Transaction | TransactionOptions, 
    /, 
    _id: fs.StrPath | None=None,
    extract_id_from_path: Callable[[Path], str] = _default_id_extractor
) -> str:
    if (_id is not None):
        return _id.stem if isinstance(_id, Path) else _id
    _txn = txn.options if isinstance(txn, Transaction) else txn
    layout_label = (_txn.layout.name if _txn.layout is not None else None)
    id_from_path: str | None = None
    if _txn.export and _txn.export.file and _txn.export.file.path:
        id_from_path = extract_id_from_path(_txn.export.file.path)
    return id_from_path or layout_label or _txn.code