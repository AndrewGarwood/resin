from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, call, patch

from resin.gui.components.control import CheckBox, TextField
from resin.gui.core import Session
from resin.gui.models.transaction import TransactionOptions, TransactionStage
from resin.gui.models.transaction.layout import LayoutOptions
from resin.gui.models.transaction.multiscreen import ScreenFieldSelection, ScreenStep
from resin.gui.services.transaction.transaction import Transaction
from resin.models._field import SENTINEL_FUNCTION_REGISTRY, ValueOptions, SentinelValueDict


class TransactionFieldTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock(spec=Session)

    def test_construction_and_set_field_preserve_raw_definitions(self):
        definition: SentinelValueDict = {'sentinel': 'CURRENT_DAY', 'args': []}
        options = TransactionOptions(
            code='TEST',
            fields={'txtDATE': definition},
            screens=[ScreenFieldSelection(
                step_in=ScreenStep(vkey=5),
                fields={'txtOTHER': definition},
            )],
        )
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call') as provider:
            transaction = Transaction(options)
            transaction.set_field('txtADDED', definition)
            provider.assert_not_called()
        definition['args'].append('changed')
        self.assertEqual(transaction.fields['txtDATE']['args'], [])
        self.assertEqual(transaction.fields['txtADDED']['args'], [])
        self.assertEqual(transaction.screens[0].fields['txtOTHER']['args'], [])

    def test_each_load_resolves_again_without_mutating_definitions(self):
        fields = {'txtDATE': {'sentinel': 'CURRENT_DAY'}}
        original = deepcopy(fields)
        transaction = Transaction(TransactionOptions(code='TEST', fields=fields))
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call', side_effect=['first', 'second']
        ) as provider:
            transaction._load_fields(self.session, transaction.fields)
            transaction._load_fields(self.session, transaction.fields)
            self.assertEqual(provider.call_count, 2)
        self.assertEqual(self.session.set_field_value.call_args_list, [
            call('txtDATE', 'first', field_cls=TextField),
            call('txtDATE', 'second', field_cls=TextField),
        ])
        self.assertEqual(fields, original)
        self.assertEqual(transaction.fields, original)

    def test_json_configuration_remains_unresolved_until_loading(self):
        data = json.loads('''{
            "code": "TEST",
            "fields": {
                "wnd[0]/usr/ctxtDATE": {
                    "sentinel": "FIRST_DAY_OF_MONTH",
                    "anchor": {"sentinel": "FIRST_DAY_OF_YEAR", "year": 2024}
                }
            }
        }''')
        original = deepcopy(data)
        transaction = Transaction(TransactionOptions.from_dict(data))
        self.assertEqual(transaction.fields, original['fields'])
        transaction._load_fields(self.session, transaction.fields)
        self.session.set_field_value.assert_called_once_with(
            'wnd[0]/usr/ctxtDATE', '01/01/2024', field_cls=TextField
        )
        self.assertEqual(data, original)

    def test_text_checkbox_and_radio_dispatch(self):
        transaction = Transaction(TransactionOptions(code='TEST'))
        transaction._load_fields(self.session, {
            'wnd[0]/usr/ctxtPLANT': '1000',
            'wnd[0]/usr/txtCOUNT': 0,
            'wnd[0]/usr/txtCLEAR': None,
            'wnd[0]/usr/chkDETAIL': False,
            'wnd[0]/usr/radSUMMARY': 'RADIO_BUTTON_SELECT',
            'wnd[0]/usr/radDETAIL': {'sentinel': 'RADIO_BUTTON_SELECT'},
        })
        self.assertEqual(self.session.mock_calls, [
            call.set_field_value('wnd[0]/usr/ctxtPLANT', '1000', field_cls=TextField),
            call.set_field_value('wnd[0]/usr/txtCOUNT', '0', field_cls=TextField),
            call.set_field_value('wnd[0]/usr/txtCLEAR', '', field_cls=TextField),
            call.set_field_value('wnd[0]/usr/chkDETAIL', False, field_cls=CheckBox),
            call.select_radio_option('wnd[0]/usr/radSUMMARY'),
            call.select_radio_option('wnd[0]/usr/radDETAIL'),
        ])

    def test_preflight_failure_performs_zero_session_calls(self):
        invalid_fields = [
            ('chkDETAIL', 'false'),
            ('txtBAD', {'sentinel': 'UNKNOWN'}),
            ('txtBAD', {'sentinel': 123}),
            ('txtBAD', {'unexpected': 'object'}),
            ('chkBAD', ['1000']),
            ('chkBAD', {'include': {'values': ['1000']}}),
            ('chkBAD', ValueOptions()),
            ('txtBAD', 'MULTIPLE_SELECTION'),
            ('txtBAD', {'sentinel': 'MULTIPLE_SELECTION'}),
            ('txtBAD', 'RADIO_BUTTON_SELECT'),
            ('rad', 'RADIO_BUTTON_SELECT'),
            ('radOPTION', {'sentinel': 'RADIO_BUTTON_SELECT', 'option': 'OTHER'}),
            ('radOPTION', True),
            ('btn[8]', 'value'),
        ]
        transaction = Transaction(TransactionOptions(code='TEST'))
        for field_id, value in invalid_fields:
            with self.subTest(field_id=field_id, value=value):
                self.session.reset_mock()
                with self.assertRaises(RuntimeError) as caught:
                    transaction._load_fields(self.session, {
                        'txtVALID': 'valid',
                        field_id: value,
                    })
                self.assertIn('Failed to prepare field value', str(caught.exception))
                self.assertIn(field_id, str(caught.exception))
                self.assertEqual(self.session.mock_calls, [])

    def test_all_fields_resolve_before_first_write(self):
        transaction = Transaction(TransactionOptions(code='TEST'))
        events = []
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call',
            side_effect=lambda *args: events.append('resolve') or 'value',
        ):
            self.session.set_field_value.side_effect = lambda *a, **k: events.append('write')
            transaction._load_fields(self.session, {
                'txtFIRST': 'CURRENT_DAY',
                'txtSECOND': 'CURRENT_DAY',
            })
        self.assertEqual(events, ['resolve', 'resolve', 'write', 'write'])

    def test_provider_output_is_not_evaluated_twice(self):
        transaction = Transaction(TransactionOptions(code='TEST'))
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call', return_value='CURRENT_DAY'
        ) as provider:
            transaction._load_fields(self.session, {'txtDATE': 'CURRENT_DAY'})
            provider.assert_called_once()
        self.session.set_field_value.assert_called_once_with(
            'txtDATE', 'CURRENT_DAY', field_cls=TextField
        )

    def test_initial_and_additional_screens_use_same_pipeline(self):
        transaction = Transaction(TransactionOptions(
            code='TEST',
            fields={'txtDATE': 'CURRENT_DAY'},
            screens=[ScreenFieldSelection(
                step_in=ScreenStep(vkey=5),
                fields={'txtSECOND': {'sentinel': 'CURRENT_DAY'}},
                step_out=ScreenStep(button='wnd[0]/tbar[1]/btn[8]'),
            )],
        ))
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call', side_effect=['first', 'second']
        ) as provider:
            transaction.open(self.session)
            provider.assert_not_called()
            transaction.populate_selection_screen(self.session)
            self.assertEqual(provider.call_count, 2)
        self.assertEqual(transaction.stage, TransactionStage.READY_TO_EXECUTE)
        self.assertEqual(self.session.mock_calls, [
            call.start_transaction('TEST'),
            call.set_field_value('txtDATE', 'first', field_cls=TextField),
            call.active_window.send_vkey(5),
            call.set_field_value('txtSECOND', 'second', field_cls=TextField),
            call.press_button('wnd[0]/tbar[1]/btn[8]'),
        ])

    def test_field_failure_is_not_masked_by_status_access(self):
        error = RuntimeError('COM write failed')
        self.session.set_field_value.side_effect = error
        self.session.get_status.side_effect = RuntimeError('status failed')
        transaction = Transaction(TransactionOptions(code='TEST'))
        with self.assertRaises(RuntimeError) as caught:
            transaction._load_fields(self.session, {'txtDATE': 'value'})
        self.assertIs(caught.exception.__cause__, error)
        self.session.get_status.assert_not_called()

    def test_additional_screen_failure_preserves_field_error(self):
        self.session.get_status.side_effect = RuntimeError('status failed')
        transaction = Transaction(TransactionOptions(
            code='TEST',
            screens=[ScreenFieldSelection(
                step_in=ScreenStep(vkey=5),
                fields={'chkDETAIL': 'false'},
            )],
        ))
        with self.assertRaises(RuntimeError) as caught:
            transaction._load_screen_fields(self.session)
        self.assertIn('Failed to prepare field value', str(caught.exception.__cause__))
        self.session.set_field_value.assert_not_called()
        self.session.get_status.assert_not_called()

    def test_layout_default_and_explicit_precedence_are_preserved(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                fields = {'ctxtLAYOUT': 'EXPLICIT'} if explicit else {}
                transaction = Transaction(TransactionOptions(
                    code='TEST',
                    fields=fields,
                    layout=LayoutOptions(field_id='ctxtLAYOUT', name='DEFAULT'),
                ))
                transaction._load_fields(self.session, transaction.fields)
                self.session.set_field_value.assert_called_with(
                    'ctxtLAYOUT', 'EXPLICIT' if explicit else 'DEFAULT',
                    field_cls=TextField,
                )
                self.assertEqual(fields, {'ctxtLAYOUT': 'EXPLICIT'} if explicit else {})


if __name__ == '__main__':
    unittest.main()
