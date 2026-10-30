from copy import deepcopy
from types import SimpleNamespace
from typing import Any
import re
import unittest
from unittest.mock import Mock, patch

from resin.gui.com.gateway import ComGateway
from resin.gui.components.control import Tab, TextField
from resin.gui.components.table_control import TableControl
from resin.gui.components.window import FrameWindow
from resin.gui.context import SapContext
from resin.gui.core import Session
from resin.gui.exceptions import SapComError, SapGuiError
from resin.gui.models.transaction import TransactionOptions
from resin.gui.models.transaction.multiscreen import ScreenFieldSelection, ScreenStep
from resin.gui.services.transaction.field_operation import _SetMultiSelection
from resin.gui.services.transaction.multi_selection import (
    apply_multi_selection,
    prepare_multi_selection,
)
from resin.gui.services.transaction.transaction import Transaction
from resin.gui.utils import gui_id as GUI
from resin.models._field import (
    MultiSelection, SENTINEL_FUNCTION_REGISTRY, ValueOptions, ValueRange,
)


FIELD_ID = 'wnd[0]/usr/ctxtS_PLANT-LOW'
BUTTON_ID = 'wnd[0]/usr/btn%_S_PLANT_%_APP_%-VALU_PUSH'


class MultiSelectionPreparationTests(unittest.TestCase):
    def test_lists_and_tuples_split_values_and_ranges(self):
        for constructor in (list, tuple):
            with self.subTest(constructor=constructor):
                definition = constructor(['1000', {'lower': '2000', 'upper': '2999'}, 0])
                original = deepcopy(definition)
                options = ValueOptions.from_sequence(definition)
                self.assertEqual(options, ValueOptions(
                    include=MultiSelection(
                        values=['1000', 0], ranges=[ValueRange('2000', '2999')]
                    )
                ))
                operation = prepare_multi_selection(FIELD_ID, definition)
                self.assertEqual(operation, _SetMultiSelection(
                    FIELD_ID, BUTTON_ID, ('1000', '0'), (('2000', '2999'),), (), (),
                ))
                self.assertEqual(definition, original)

    def test_short_ids_and_text_selection_fields(self):
        operation = prepare_multi_selection('txtS_PLANT-HIGH', ['1000'])
        self.assertEqual(operation.button_id, 'btn%_S_PLANT_%_APP_%-VALU_PUSH')

    def test_all_four_selections_and_action_wrapper(self):
        definition = {
            'include': {
                'values': ['1000'], 'ranges': [{'lower': '2000', 'upper': '2999'}],
            },
            'exclude': {
                'values': ['2100'], 'ranges': [{'lower': '2200', 'upper': '2299'}],
            },
        }
        expected = _SetMultiSelection(
            FIELD_ID, BUTTON_ID, ('1000',), (('2000', '2999'),),
            ('2100',), (('2200', '2299'),),
        )
        self.assertEqual(prepare_multi_selection(FIELD_ID, definition), expected)
        self.assertEqual(prepare_multi_selection(
            FIELD_ID, {'sentinel': 'MULTIPLE_SELECTION', **definition}
        ), expected)
        self.assertEqual(prepare_multi_selection(
            FIELD_ID, ValueOptions.from_dict(definition)
        ), expected)

    def test_dynamic_values_and_bounds_are_evaluated_once(self):
        for definition in (
            ['CURRENT_DAY', {'lower': 'CURRENT_DAY', 'upper': {'sentinel': 'CURRENT_DAY'}}],
            {'include': {
                'values': ['CURRENT_DAY'],
                'ranges': [{'lower': 'CURRENT_DAY', 'upper': {'sentinel': 'CURRENT_DAY'}}],
            }},
        ):
            with self.subTest(definition=definition):
                with patch.object(
                    SENTINEL_FUNCTION_REGISTRY, 'call', return_value='CURRENT_DAY'
                ) as provider:
                    transaction = Transaction(TransactionOptions(code='TEST'))
                    operation = transaction._prepare_field(FIELD_ID, definition)
                    self.assertIsInstance(operation, _SetMultiSelection)
                    assert isinstance(operation, _SetMultiSelection)
                    self.assertEqual(operation.include_values, ('CURRENT_DAY',))
                    self.assertEqual(operation.include_ranges, (('CURRENT_DAY', 'CURRENT_DAY'),))
                    self.assertEqual(provider.call_count, 3)

    def test_provider_can_return_concrete_multi_selection(self):
        outputs = [
            ['CURRENT_DAY', {'lower': 'CURRENT_DAY', 'upper': 'CURRENT_DAY'}],
            {'include': {
                'values': ['CURRENT_DAY'],
                'ranges': [{'lower': 'CURRENT_DAY', 'upper': 'CURRENT_DAY'}],
            }},
        ]
        transaction = Transaction(TransactionOptions(code='TEST'))
        for output in outputs:
            with self.subTest(output=output):
                with patch.object(
                    SENTINEL_FUNCTION_REGISTRY, 'call', return_value=output
                ) as provider:
                    operation = transaction._prepare_field(FIELD_ID, 'CURRENT_DAY')
                    assert isinstance(operation, _SetMultiSelection)
                    self.assertEqual(operation.include_values, ('CURRENT_DAY',))
                    self.assertEqual(operation.include_ranges, (('CURRENT_DAY', 'CURRENT_DAY'),))
                    provider.assert_called_once()

    def test_existing_value_options_are_concrete_and_not_mutated(self):
        options = ValueOptions(include=MultiSelection(
            values=['CURRENT_DAY'], ranges=[ValueRange('CURRENT_DAY', 'CURRENT_DAY')]
        ))
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call') as provider:
            operation = prepare_multi_selection(FIELD_ID, options)
            provider.assert_not_called()
        assert options.include is not None
        options.include.values.append('changed')
        self.assertEqual(operation.include_values, ('CURRENT_DAY',))

    def test_empty_definitions_prepare_clear_operations(self):
        for definition in ([], (), ValueOptions(), {'include': {}}, {'exclude': None}):
            with self.subTest(definition=definition):
                self.assertEqual(prepare_multi_selection(FIELD_ID, definition), _SetMultiSelection(
                    FIELD_ID, BUTTON_ID, (), (), (), (),
                ))

    def test_bad_entries_fail_before_any_session_calls(self):
        transaction = Transaction(TransactionOptions(code='TEST'))
        session = Mock(spec=Session)
        invalid = [
            [None], [''], [{}], [['1000']],
            [{'lower': '1000'}],
            [{'lower': '1000', 'upper': '2000', 'extra': 1}],
            [{'lower': None, 'upper': '2000'}],
            {'include': {'values': '1000'}},
            {'exclude': {'ranges': [{'lower': 1}]}},
            {'sentinel': 'MULTIPLE_SELECTION', 'args': []},
            {'sentinel': 'MULTIPLE_SELECTION'},
            'MULTIPLE_SELECTION',
        ]
        for definition in invalid:
            with self.subTest(definition=definition):
                with self.assertRaises(RuntimeError):
                    transaction._load_fields(session, {
                        'txtVALID': 'valid',
                        FIELD_ID: definition,
                    })
                self.assertEqual(session.mock_calls, [])

    def test_bad_target_ids_fail_during_preparation(self):
        for field_id in ('chkS_PLANT', 'ctxt', 'ctxtS_PLANT-LOW[1,0]', 'ctxtS_PLANT[0]'):
            with self.subTest(field_id=field_id):
                with self.assertRaises(ValueError):
                    prepare_multi_selection(field_id, ['1000'])


class _FakeTable:
    def __init__(self, *, visible=2, max_first=None):
        self.visible_row_count = visible
        self.first_visible_row = 0
        self.scrolls = []
        self.max_first = max_first

    def scroll_to(self, row):
        self.scrolls.append(row)
        self.first_visible_row = row if self.max_first is None else min(row, self.max_first)


class _DialogHarness:
    def __init__(self, window=0, *, max_first=None):
        self.session = Mock(spec=Session)
        self.session.busy = False
        self.original = f'/app/con[0]/ses[0]/wnd[{window}]'
        self.dialog_id = f'/app/con[0]/ses[0]/wnd[{window + 1}]'
        self.session.active_window = SimpleNamespace(id=self.original, send_vkey=Mock())
        self.dialog = Mock(spec=FrameWindow)
        self.dialog.id = self.dialog_id
        self.tables = {}
        self.tabs = []
        self.cells = {}
        self.max_first = max_first
        self.session.press_button.side_effect = self.press_button
        self.session.wait_for_component.side_effect = self.find_component
        self.session.set_field_value.side_effect = self.set_field_value

    def press_button(self, button_id):
        if button_id.endswith('-VALU_PUSH'):
            self.session.active_window.id = self.dialog_id
        elif button_id.endswith('/btn[16]'):
            self.cells.clear()
        elif button_id.endswith('/btn[8]'):
            self.session.active_window.id = self.original

    def find_component(self, component_id, *, component_cls, _raise):
        if component_cls is FrameWindow:
            return self.dialog
        if component_cls is Tab:
            tab = Mock(spec=Tab)
            tab.select.side_effect = lambda: self.tabs.append(component_id.rsplit('/', 1)[-1])
            return tab
        if component_cls is TableControl:
            if component_id not in self.tables:
                self.tables[component_id] = _FakeTable(max_first=self.max_first)
            return self.tables[component_id]
        raise AssertionError(f'Unexpected component class: {component_cls}')

    def set_field_value(self, field_id, value, *, field_cls):
        assert field_cls is TextField
        match = re.fullmatch(r'(.+)/([^/]+)\[(\d+),(\d+)\]', field_id)
        assert match is not None, field_id
        table_id, field, column, row = match.groups()
        absolute_row = self.tables[table_id].first_visible_row + int(row)
        self.cells[(table_id, field, int(column), absolute_row)] = value


class MultiSelectionDialogTests(unittest.TestCase):
    def test_writes_all_four_tabs_using_exact_standard_ids(self):
        harness = _DialogHarness()
        operation = prepare_multi_selection(FIELD_ID, {
            'include': {
                'values': ['1000', '1100'],
                'ranges': [{'lower': '2000', 'upper': '2999'}],
            },
            'exclude': {
                'values': ['2100'],
                'ranges': [{'lower': '2200', 'upper': '2299'}],
            },
        })
        harness.cells['old'] = 'old'
        apply_multi_selection(harness.session, operation)
        base = 'wnd[1]/usr/tabsTAB_STRIP'
        self.assertEqual(harness.cells, {
            (f'{base}/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE',
             'ctxtRSCSEL_255-SLOW_I', 1, 0): '1000',
            (f'{base}/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE',
             'ctxtRSCSEL_255-SLOW_I', 1, 1): '1100',
            (f'{base}/tabpINTL/ssubSCREEN_HEADER:SAPLALDB:3020/tblSAPLALDBINTERVAL',
             'ctxtRSCSEL_255-ILOW_I', 1, 0): '2000',
            (f'{base}/tabpINTL/ssubSCREEN_HEADER:SAPLALDB:3020/tblSAPLALDBINTERVAL',
             'ctxtRSCSEL_255-IHIGH_I', 2, 0): '2999',
            (f'{base}/tabpNOSV/ssubSCREEN_HEADER:SAPLALDB:3030/tblSAPLALDBSINGLE_E',
             'ctxtRSCSEL_255-SLOW_E', 1, 0): '2100',
            (f'{base}/tabpNOINT/ssubSCREEN_HEADER:SAPLALDB:3040/tblSAPLALDBINTERVAL_E',
             'ctxtRSCSEL_255-ILOW_E', 1, 0): '2200',
            (f'{base}/tabpNOINT/ssubSCREEN_HEADER:SAPLALDB:3040/tblSAPLALDBINTERVAL_E',
             'ctxtRSCSEL_255-IHIGH_E', 2, 0): '2299',
        })
        self.assertEqual(harness.tabs, ['tabpSIVA', 'tabpSIVA', 'tabpINTL', 'tabpNOSV', 'tabpNOINT'])
        self.assertEqual(
            [c.args[0] for c in harness.session.press_button.call_args_list],
            [BUTTON_ID, f'{harness.dialog_id}/tbar[0]/btn[16]',
             f'{harness.dialog_id}/tbar[0]/btn[8]'],
        )

    def test_empty_list_clears_and_confirms(self):
        harness = _DialogHarness()
        harness.cells['existing variant value'] = '1000'
        operation = prepare_multi_selection(FIELD_ID, [])
        apply_multi_selection(harness.session, operation)
        self.assertEqual(harness.cells, {})
        harness.session.set_field_value.assert_not_called()
        self.assertEqual(harness.session.active_window.id, harness.original)

    def test_pagination_covers_more_than_two_pages(self):
        for definition in (
            list(range(7)),
            {'exclude': {'ranges': [{'lower': i, 'upper': i + 1} for i in range(7)]}},
        ):
            with self.subTest(definition=definition):
                harness = _DialogHarness()
                apply_multi_selection(
                    harness.session, prepare_multi_selection(FIELD_ID, definition)
                )
                table = next(t for t in harness.tables.values() if len(t.scrolls) > 1)
                self.assertEqual(table.scrolls, [0, 2, 4, 6])
                self.assertEqual(harness.dialog.send_vkey.call_count, 3)
                self.assertEqual({key[3] for key in harness.cells}, set(range(7)))

    def test_clamped_last_page_uses_actual_scroll_position(self):
        harness = _DialogHarness(max_first=3)
        apply_multi_selection(
            harness.session, prepare_multi_selection(FIELD_ID, list(range(5)))
        )
        self.assertEqual({key[3] for key in harness.cells}, set(range(5)))
        self.assertEqual(len(harness.cells), 5)

    def test_failure_to_reveal_row_is_explicit_and_not_confirmed(self):
        harness = _DialogHarness(max_first=0)
        with self.assertRaisesRegex(SapGuiError, 'cannot reveal row 2'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, list(range(3)))
            )
        self.assertFalse(any(
            c.args[0].endswith('/btn[8]') for c in harness.session.press_button.call_args_list
        ))

    def test_nested_window_index_is_not_hardcoded(self):
        harness = _DialogHarness(window=1)
        field_id = 'wnd[1]/usr/ctxtS_PLANT-LOW'
        apply_multi_selection(
            harness.session, prepare_multi_selection(field_id, ['1000'])
        )
        self.assertTrue(all(key[0].startswith('wnd[2]/') for key in harness.cells))
        self.assertEqual(harness.session.active_window.id, harness.original)

    def test_initial_and_additional_screens_load_multi_selection_dynamically(self):
        harness = _DialogHarness()
        transaction = Transaction(TransactionOptions(
            code='TEST',
            fields={FIELD_ID: ['CURRENT_DAY']},
            screens=[ScreenFieldSelection(
                step_in=ScreenStep(vkey=5),
                fields={FIELD_ID: {'exclude': {'values': ['CURRENT_DAY']}}},
            )],
        ))
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call', side_effect=['first', 'second']
        ) as provider:
            transaction.open(harness.session)
            provider.assert_not_called()
            transaction.populate_selection_screen(harness.session)
            self.assertEqual(provider.call_count, 2)
        self.assertEqual(
            [c.args[1] for c in harness.session.set_field_value.call_args_list],
            ['first', 'second'],
        )
        self.assertEqual(
            len([c for c in harness.session.press_button.call_args_list
                 if c.args[0].endswith('/btn[16]')]), 2,
        )
        self.assertEqual(transaction.fields[FIELD_ID], ['CURRENT_DAY'])

    def test_unexpected_active_window_does_not_clear(self):
        harness = _DialogHarness()
        harness.session.press_button.side_effect = lambda button_id: None
        with self.assertRaisesRegex(SapGuiError, 'not the active window'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, ['1000'])
            )
        self.assertEqual(harness.session.press_button.call_count, 1)

    def test_unexpected_window_after_clear_is_an_error(self):
        harness = _DialogHarness()
        press = harness.press_button

        def press_with_confirmation(button_id):
            press(button_id)
            if button_id.endswith('/btn[16]'):
                harness.session.active_window.id = 'wnd[2]'

        harness.session.press_button.side_effect = press_with_confirmation
        with self.assertRaisesRegex(SapGuiError, 'after clearing'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, ['1000'])
            )
        harness.session.set_field_value.assert_not_called()

    def test_missing_dialog_does_not_clear_or_write(self):
        harness = _DialogHarness()
        harness.session.wait_for_component.side_effect = SapGuiError('not found')
        with self.assertRaisesRegex(SapGuiError, 'not found'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, ['1000'])
            )
        self.assertEqual(harness.session.press_button.call_count, 1)
        harness.session.set_field_value.assert_not_called()

    def test_nonstandard_dialog_is_not_cleared(self):
        harness = _DialogHarness()
        find = harness.find_component

        def find_without_standard_table(component_id, *, component_cls, _raise):
            if component_cls is TableControl:
                raise SapGuiError('standard table missing')
            return find(component_id, component_cls=component_cls, _raise=_raise)

        harness.session.wait_for_component.side_effect = find_without_standard_table
        with self.assertRaisesRegex(SapGuiError, 'standard table missing'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, ['1000'])
            )
        self.assertEqual(harness.session.press_button.call_count, 1)

    def test_com_failure_is_chained_and_does_not_confirm(self):
        harness = _DialogHarness()
        error = SapComError('write failed')
        harness.session.set_field_value.side_effect = error
        transaction = Transaction(TransactionOptions(code='TEST'))
        with self.assertRaises(RuntimeError) as caught:
            transaction._load_fields(harness.session, {FIELD_ID: ['1000']})
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(harness.session.press_button.call_count, 2)

    def test_confirm_that_does_not_close_is_an_error(self):
        harness = _DialogHarness()
        press = harness.press_button
        harness.session.press_button.side_effect = (
            lambda button_id: None if button_id.endswith('/btn[8]') else press(button_id)
        )
        with self.assertRaisesRegex(SapGuiError, 'did not return'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, ['1000'])
            )

    def test_unexpected_window_during_pagination_is_an_error(self):
        harness = _DialogHarness()
        harness.dialog.send_vkey.side_effect = (
            lambda key: setattr(harness.session.active_window, 'id', 'wnd[2]')
        )
        with self.assertRaisesRegex(SapGuiError, 'Unexpected window'):
            apply_multi_selection(
                harness.session, prepare_multi_selection(FIELD_ID, list(range(3)))
            )
        self.assertEqual(harness.session.press_button.call_count, 2)


class TableControlTests(unittest.TestCase):
    def setUp(self):
        self.scrollbar = SimpleNamespace(Position=0)
        self.gateway = Mock(spec=ComGateway)
        self.gateway.find_component.side_effect = lambda *a, **k: SimpleNamespace(
            VisibleRowCount=3, VerticalScrollbar=self.scrollbar
        )
        self.gateway.get_property.side_effect = lambda obj, name, *a, **k: getattr(obj, name)
        self.table = TableControl(
            gateway=self.gateway,
            context=SapContext(
                connection_id='/app/con[0]', session_id='/app/con[0]/ses[0]',
                component_id='wnd[1]/usr/tblTABLE',
            ),
        )

    def test_resolves_fresh_dispatch_after_scrolling(self):
        self.assertEqual(self.table.visible_row_count, 3)
        self.table.scroll_to(7)
        self.assertEqual(self.table.first_visible_row, 7)
        self.assertEqual(self.gateway.find_component.call_count, 3)

    def test_invalid_scroll_positions_and_no_visible_rows(self):
        invalid_rows: list[Any] = [-1, True, '1']
        for row in invalid_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    self.table.scroll_to(row)
        self.gateway.find_component.return_value = SimpleNamespace(VisibleRowCount=0)
        self.gateway.find_component.side_effect = None
        with self.assertRaisesRegex(SapComError, 'no visible rows'):
            _ = self.table.visible_row_count

    def test_scroll_failure_is_chained(self):
        error = RuntimeError('COM failed')
        self.gateway.get_property.side_effect = error
        with self.assertRaises(SapComError) as caught:
            self.table.scroll_to(2)
        self.assertIs(caught.exception.__cause__, error)

    def test_negative_scrollbar_position_is_an_error(self):
        self.scrollbar.Position = -1
        with self.assertRaisesRegex(SapComError, 'invalid scrollbar position'):
            _ = self.table.first_visible_row

    def test_selection_button_round_trips(self):
        stem = GUI.SapFieldIdStem.selection_button('S_PLANT')
        self.assertEqual(stem, 'btn%_S_PLANT_%_APP_%-VALU_PUSH')
        self.assertEqual(GUI.SapFieldIdStem.parse(stem).compile(), stem)


if __name__ == '__main__':
    unittest.main()
