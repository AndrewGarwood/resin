"""
*`@file`* `gui/services/transaction/transaction`
"""
from __future__ import annotations
from pathlib import Path
import threading, time
from typing import (Any, Callable, Optional, Self)
from pyqi.models import StageTransition, Telemetry, Flow
from pyqi import (fs, require, dt, safe, export, Array)
from lute import LogMsg, get_logger, annotate
from pyqi.models._result import Result
from resin.gui.components.control import (TextField,  CheckBox)
from resin.gui.models.transaction.multiscreen import ScreenStep
from resin.models._field import (
    resolve_field_value,
    SentinelKey,
    is_sentinel_value_dict,
    )
from resin.gui.models._export._method import ExportMethod
from resin.gui.models._export.result import (ExportDetails, CompletedExport)
from resin.gui.models.transaction import (
    TransactionOptions, 
    TransactionDetails, 
    TransactionStage,
    VariantOptions,
    ExecutionType
)
from .field_operation import (
    _FieldOperation, _SelectRadio, _SetCheckbox, _SetText, _SetMultiSelection
)
from .multi_selection import (
    is_multi_selection_value, prepare_multi_selection, apply_multi_selection
)
from copy import deepcopy
from .. import _export as ExportService
from resin.gui.core import (Session)
from resin.gui.utils import (gui_id as GUI)
from resin.gui.exceptions import (SapGuiError)
import re

mlog = get_logger(__file__)


def default_id_extractor(p: Path) -> str:
    """ 
    *`@returns`* `re.sub(r"^\\d{4}(\\.|-)\\d{2}(\\.|-)\\d{2}_", "", p.stem)` 
    """
    return re.sub(r"^\d{4}(\.|-)\d{2}(\.|-)\d{2}_", "", p.stem)

class Transaction(Flow[TransactionStage]):
    code: str
    options: TransactionOptions
    fields: dict[str, Any]
    """
    - these are fields that can be populated on the first screen when starting a transaction
    - stores independent, unresolved definitions; evaluated before each screen load.
    - `self.options.fields` retains the original configured definitions.
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
        extract_id_from_path: Callable[[Path], str] | None = default_id_extractor,
        strict: bool = True,
        execute_fn: Callable[[Self, Session], Any] | None = None
    ): 
        self.strict = strict
        self.execute_fn = execute_fn

        self.options = options
        self.code = options.code
        self.fields = deepcopy(options.fields)
        self.layout = options.layout
        self.method = ExecutionType.resolve(options.method)
        self.export_options = options.export
        self.variant = options.variant
        self.screens = Array.map(
            options.screens, 
            lambda s: s.with_fields(deepcopy(s.fields))
        )
        self.id = resolve_transaction_id(options, _id, extract_id_from_path)

        if (options.layout and options.layout.field_id not in self.fields):
            self.fields[options.layout.field_id] = options.layout.name

        self.exec_tel = Telemetry()
        self.export_tel = Telemetry()
        self._stage = TransactionStage.CREATED
        self._stage_history: list[StageTransition[TransactionStage]] = []
        self._failure: BaseException | None = None
        self._export_result: Result[ExportDetails] | None = None
        self._state_lock = threading.RLock()
        self._state_changed = threading.Condition(self._state_lock)
        self.last_status: str | None = None

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
    def export_result(self) -> Result[ExportDetails] | None:
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
            error.add_note(self.last_status or "<last_status unavailable>")
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
        timeout: float,
    ) -> TransactionStage:
        """
        *`@param`* `timeout (float | None)` - unit is `seconds`

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
        """ if want to add/overwrite an entry in `self.fields` """
        key = require.non_empty_string(key, "Field Id")
        self.fields[key] = deepcopy(value)
    
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
        if (self.strict and not self.has_nontrivial_field_selection()):
            raise RuntimeError(LogMsg(
                f"No variant or fields available to populate transaction parameters",
            ))
        if (self.variant):
            self._load_variant(session, self.variant)
        if (self.fields):
            self._load_fields(session, self.fields)
        if (self.screens):
            self._load_screen_fields(session)
        self._transition(
            TransactionStage.POPULATING_SELECTION, 
            TransactionStage.READY_TO_EXECUTE
        )

    def read_status(self, session: Session, /):
        _status = session.get_status()
        self.last_status = _status
        return _status

    def has_nontrivial_field_selection(self) -> bool:
        """
        *`@returns`* `bool` whether one of (self.fields, self.variant, self.screens) 
        would result in manipulating parameters of the transaction in SAPGUI
        """
        return bool(
            self.variant 
            or self.fields 
            or Array.some(self.screens, lambda s: bool(s.fields))
        )

    def _load_screen_fields(self, session: Session,/):
        try:
            for s in self.screens:
                self._handle_screen_step(session, s.step_in)
                if (s.fields): 
                    self._load_fields(session, s.fields)
                if (not s.step_out): 
                    continue
                self._handle_screen_step(session, s.step_out)
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to enter fields on Transaction screen(s)",
                screens=Array.map(self.screens, lambda k: k.to_dict()),
                status=self.last_status
            )) from e

    def _handle_screen_step(self, session: Session, step: ScreenStep, /) -> None:
        if step.vkey is not None:
            session.active_window.send_vkey(step.vkey)
        elif step.button is not None:
            session.press_button(step.button)
        else: # unreachable b/c post init should throw
            raise RuntimeError(LogMsg(f"Invalid ScreenStep object"))

    
    def _load_variant(
        self, 
        session: Session,
        variant: VariantOptions,
        /,
    ) -> None:
        try:
            main_wnd = session.main_window
            main_wnd_id = main_wnd.id
            mlog.debug(LogMsg(
                f"Before send vkey to get variant", 
                active_wnd_id=session.active_window.id,
                main_wnd_id=main_wnd_id
            ))
            main_wnd.send_vkey(GUI.VKey.GET_TXN_VARIANT)
            active_wnd = session.active_window
            active_wnd_id = active_wnd.id
            mlog.debug(LogMsg(
                f"After send vkey to get variant", 
                active_wnd_id=active_wnd_id,
                main_wnd_id=main_wnd_id
            ))
            if (main_wnd_id == active_wnd_id):
                raise SapGuiError(LogMsg(
                    f"Failed to open variant window from vkey",
                    main_wnd_id=main_wnd_id,
                    active_wnd_id=active_wnd_id,
                    vkey=GUI.VKey.GET_TXN_VARIANT.value
                ))
            
            variant_field_id, created_by_field_id = GUI.txn_variant_fields(
                GUI.get_window_index(active_wnd_id) or 1
            )
            session.wait_for_component(
                variant_field_id,
                component_cls=TextField,
                _raise=True
            ).set(variant.name)
            session.wait_for_component(
                created_by_field_id,
                component_cls=TextField,
                _raise=True
            ).set(variant.created_by)
            active_wnd.send_vkey(GUI.VKey.F8)
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
                variant=str(self.variant),
                status=self.read_status(session)
            )) from e
        
    def _load_fields(self, session: Session, fields: dict[str, Any], /) -> None:
        operations: list[_FieldOperation] = []
        for field_id, value in fields.items():
            try:
                operations.append(self._prepare_field(field_id, value))
            except Exception as e:
                raise RuntimeError(LogMsg.err(
                    e,
                    "Failed to prepare field value",
                    field_id=field_id,
                    value=annotate(value),
                    txn_id=self.id,
                    txn_code=self.code,
                )) from e
        for op in operations:
            try:
                self._apply_field(session, op)
            except Exception as e:
                raise RuntimeError(LogMsg.err(
                    e,
                    f"Failed to apply prepared FieldOperation",
                    operation=str(op),
                    txn_id=self.id,
                    txn_code=self.code,
                    status=self.last_status
                )) from e


    def _prepare_field(self, field_id: str, value: Any, /) -> _FieldOperation:
        field_id = require.non_empty_string(field_id, "Field Id")
        if is_multi_selection_value(value):
            return prepare_multi_selection(field_id, value)
        value = resolve_field_value(value)
        if is_multi_selection_value(value):
            return prepare_multi_selection(field_id, value, resolve=False)
        field_type = GUI.field_type(field_id)
        sentinel = None
        if isinstance(value, str):
            sentinel = SentinelKey.try_resolve(value)
        elif is_sentinel_value_dict(value):
            sentinel = SentinelKey.resolve(value['sentinel'])
        if sentinel == SentinelKey.RADIO_BUTTON_SELECT:
            if field_type != 'rad' or GUI.stem(field_id) == 'rad':
                raise ValueError("Radio selection requires a radio field ID containing its option")
            if isinstance(value, dict) and value.keys() != {'sentinel'}:
                raise ValueError("Radio selection does not support additional options")
            return _SelectRadio(field_id)
        if field_type in ('txt', 'ctxt'):
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise TypeError("Text fields require a scalar string, number, boolean, or None")
            return _SetText(field_id, "" if value is None else str(value))
        if field_type == 'chk':
            if not isinstance(value, bool):
                raise TypeError("Checkbox fields require a boolean")
            return _SetCheckbox(field_id, value)
        raise ValueError(f"Unsupported field component type: {field_type!r}")

    def _apply_field(self, session: Session, operation: _FieldOperation, /) -> None:
        if isinstance(operation, _SetText):
            session.set_field_value(
                operation.field_id,
                operation.value,
                field_cls=TextField,
            )
        elif isinstance(operation, _SetCheckbox):
            session.set_field_value(
                operation.field_id,
                operation.value,
                field_cls=CheckBox,
            )
        elif isinstance(operation, _SelectRadio):
            session.select_radio_option(operation.field_id)
        elif isinstance(operation, _SetMultiSelection):
            apply_multi_selection(session, operation)
        else: # should be unreachable
            raise ValueError(LogMsg(f"Invalid FieldOperation {str(operation)}"))

    def execute(self, session: Session, /) -> Any:
        self._transition(
            TransactionStage.READY_TO_EXECUTE, 
            TransactionStage.DISPATCHING_EXECUTE
        )
        self.exec_tel.start()
        try:
            self._transition(
                TransactionStage.DISPATCHING_EXECUTE,
                TransactionStage.EXECUTION_RUNNING,
            )
            if (self.execute_fn is not None):
                mlog.info(LogMsg(f"Using caller-provided execute function"))
                result = self.execute_fn(self, session)
            elif (self.method == ExecutionType.STANDARD):
                result = self._execute_standard(session)
            elif (self.method == ExecutionType.ASYNC):
                result = self._execute_async(session)
            else: # should be unreachable
                raise RuntimeError(LogMsg.bad_arg(
                    self.method, 
                    "Transaction.method",
                    "Invalid/unsupported ExecutionType", 
                    ExecutionType
                ))
            self.exec_tel.stop()
            self._transition(
                TransactionStage.EXECUTION_RUNNING, 
                TransactionStage.POST_EXECUTE
            )
            return result
        except Exception as e:
            if (self.exec_tel.running):
                self.exec_tel.stop()
            self._fail(e)
            raise

    def _execute_standard(self, session: Session, /) -> None:
        main_wnd = session.main_window
        main_wnd_id = main_wnd.id
        main_wnd.send_vkey(GUI.VKey.STANDARD_EXEC_START)
        time.sleep(0.25)
        active_wnd = session.active_window
        active_wnd_id = active_wnd.id
        confirmation_wnd_exists = (
            main_wnd_id != active_wnd_id
            and active_wnd.is_vkey_allowed(GUI.VKey.ENTER)
        ) # can also try checking if active_wnd.text ~ "Information"
        if (confirmation_wnd_exists):
            active_wnd.send_vkey(GUI.VKey.ENTER)
        return None

    def _execute_async(self, session: Session, /) -> None:
        main_wnd = session.main_window
        main_wnd_id = main_wnd.id
        session.main_window.send_vkey(GUI.VKey.ASYNC_EXEC_OPEN_OPTIONS)
        time.sleep(0.25)
        active_wnd = session.active_window
        active_wnd_id = active_wnd.id
        if (active_wnd_id == main_wnd_id):
            raise SapGuiError(LogMsg(
                f"Failed to open async options window after send vkey",
                f"(expected active window to change)",
                main_wnd_id=main_wnd_id,
                active_wnd_id=active_wnd_id,
                vkey=GUI.VKey.ASYNC_EXEC_OPEN_OPTIONS
            ))
        active_wnd.send_vkey(GUI.VKey.SHIFT_F1)
        _start_time_btn_id = GUI.join(
            active_wnd_id, 
            GUI.usr(),
            GUI.btn(GUI.EXEC_ASYNC_IMMEDIATE_START_TIME_BTN_ID)
        )
        session.press_button(_start_time_btn_id)
        time.sleep(0.25)
        active_wnd.send_vkey(GUI.VKey.ASYNC_EXEC_START)
        return None

    def handle_post_execute(
        self, 
        session: Session, 
        /
    ) -> None:
        self.require_current_stage(
            TransactionStage.POST_EXECUTE, 
            f"Must be at {TransactionStage.POST_EXECUTE} before handling post execution steps"
        )
        if (self.export_options and self.export_options.layout):
            ExportService.handle_layout_selection(session, self.export_options.layout)
        self._transition(
            TransactionStage.POST_EXECUTE, 
            TransactionStage.READY_TO_EXPORT
        )
        return None
        
    
    def export(self, session: Session, /) -> Result[ExportDetails]:
        self.require_current_stage(
            TransactionStage.READY_TO_EXPORT, 
            f"Must be at {TransactionStage.READY_TO_EXPORT} before initiating export"
        )
        
        result: Result[ExportDetails]
        self.export_tel.start()
        if (not self.export_options 
            or self.export_options.method == ExportMethod.NONE
        ):
            result = Result(
                f"Transaction(id={self.id}, code={self.code}).export",
                ExportDetails(None, None), 
                success=True,
                message=LogMsg(
                    f"Transaction executed successfully.",
                    f"self.export_options is undefined or indicated 'none' as method",
                    status=self.read_status(session)
                ),
            )
        else:
            self._transition(
                TransactionStage.READY_TO_EXPORT, 
                TransactionStage.EXPORTING
            )
            mlog.debug(LogMsg(
                f"Transaction(id={self.id}) ExportMethod={self.export_options.method.value}"
            ))
            result = ExportService.EXPORT_METHOD_REGISTRY.call(
                self.export_options.method,
                session, 
                self.export_options, 
                None
            )
            result.add_note(self.last_status)
            self.export_tel.stop()
            path = self.get_export_path()
            if (path.exists()):
                proc = fs.find_process_by_open_file(path, by_filename=True)
                if (proc is not None):
                    msg = f"Closed process holding exported file = {bool(fs.kill_procs([proc]))}"
                    mlog.debug(msg)
                    result.add_note(msg)
                else:
                    mlog.debug(f"Did not find process holding exported file")
        self._export_result = result
        self._transition(
            set([TransactionStage.READY_TO_EXPORT, TransactionStage.EXPORTING]),
            TransactionStage.COMPLETED
        )
        return result
    
    def require_current_stage(
        self, 
        stage: TransactionStage, 
        /, 
        *info: str | LogMsg
    ) -> None: # require self.stage to be certain value
        if (self.stage != stage):
            raise RuntimeError(LogMsg(
                f"Invalid Transaction stage",
                *info,
                expected_stage=str(stage),
                actual_stage=str(self.stage)
            ))

    def _set_no_export_result(self) -> None:
        self._export_result = Result(
            f"Transaction(id={self.id}, code={self.code}).export",
            ExportDetails(None, None),
            success=True,
            message=LogMsg(
                "Transaction executed successfully.",
                "No export was requested.",
                last_status=self.last_status
            ),
        )

    def get_result(self) -> Result[TransactionDetails]:
        """
        - *`@returns`* `self.export_result` 
            - assumes `Result[TransactionDetails]` has been written to `export_result` by actions in previous stage
            by requiring the that current stage is `TransactionStage.COMPLETED`
            - otherwise throws error
        """
        self.require_current_stage(
            TransactionStage.COMPLETED, 
            "Only able to generate TransactionResult once completed"
        )
        export_result = self.export_result
        if (export_result) is None:
            raise RuntimeError(LogMsg(
                f"Unable to create TransactionResult",
                f"self.export_result is undefined"
            ))
        export_details = export_result.data or ExportDetails()
        return Result(
            f"Transaction(id={self.id}, code={self.code}).get_result",
            data=TransactionDetails(
                self.id, 
                self.code, 
                self.exec_tel,
                exported=CompletedExport(
                    export_details.path,
                    export_details.row_count,
                    self.export_tel
                ),
                status=self.last_status
            ),
            error=export_result.error,
        )

    def get_export_path(self) -> Path:
        if (not self.export_options or not self.export_options.file):
            raise RuntimeError(LogMsg(
                f"Unable to retrieve export path",
                export_options=self.export_options
            ))
        return self.export_options.file.path

def resolve_transaction_id( # TODO should refine this
    txn: Transaction | TransactionOptions, 
    /, 
    _id: fs.StrPath | None=None,
    extract_id_from_path: Callable[[Path], str] | None = default_id_extractor
) -> str:
    if (_id is not None):
        return (
            (
                _id.stem 
                if extract_id_from_path is None 
                else extract_id_from_path(_id)
            ) 
            if isinstance(_id, Path) 
            else _id
        )
    options = txn.options if isinstance(txn, Transaction) else txn
    if (options._id): 
        return options._id
    layout_label = (
        options.layout.name 
        if options.layout is not None 
        else None
    )
    if (options.export and options.export.file and options.export.file.path):
        return (
            options.export.file.path.stem 
            if extract_id_from_path is None 
            else extract_id_from_path(options.export.file.path)
        )
    return layout_label or options.code


__all__ = export(Transaction, resolve_transaction_id, default_id_extractor)