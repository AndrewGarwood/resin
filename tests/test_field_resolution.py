from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch

from resin.models._field import (
    SENTINEL_FUNCTION_REGISTRY,
    SentinelKey,
    SentinelValueDict,
    resolve_field_dict,
    resolve_field_value,
    resolve_sentinel_value_dict,
)
from resin.models._field.value_options import (
    MultiSelection,
    ValueOptions,
    ValueRange,
    is_multi_selection_dict,
    is_value_options_dict,
    is_value_range_dict,
    resolve_range_value,
)


class FieldResolutionTests(unittest.TestCase):
    def test_normal_import_registers_builtin_providers(self):
        for key in SentinelKey:
            if key not in (SentinelKey.RADIO_BUTTON_SELECT, SentinelKey.MULTIPLE_SELECTION):
                with self.subTest(key=key):
                    self.assertTrue(SENTINEL_FUNCTION_REGISTRY.is_registered(key))
        self.assertEqual(
            resolve_field_value({'sentinel': 'FIRST_DAY_OF_YEAR', 'year': 2024}),
            '01/01/2024',
        )
        self.assertEqual(resolve_field_value('CURRENT_DAY'), date.today().strftime('%m/%d/%Y'))

    def test_actions_never_call_the_registry(self):
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call') as call:
            for key in ('RADIO_BUTTON_SELECT', 'MULTIPLE_SELECTION'):
                with self.subTest(key=key):
                    self.assertEqual(resolve_field_value(key), key)
                    action: SentinelValueDict = {'sentinel': key}
                    result = resolve_field_value(action)
                    self.assertEqual(result, action)
                    self.assertIsNot(result, action)
                    self.assertEqual(resolve_sentinel_value_dict(action), action)
            call.assert_not_called()

    def test_nested_builtin_date_providers(self):
        self.assertEqual(resolve_field_value({
            'sentinel': 'FIRST_DAY_OF_MONTH',
            'anchor': {'sentinel': 'FIRST_DAY_OF_YEAR', 'year': 2024},
        }), '01/01/2024')
        self.assertEqual(resolve_field_value({
            'sentinel': 'CUSTOM_RANGE',
            'lower': {'year': 2024, 'month': 1, 'day': 1},
            'upper': {'year': 2024, 'month': 3, 'day': 31},
        }), '01/2024 - 03/2024')

    def test_nested_args_kwargs_and_containers(self):
        definition = {
            'sentinel': 'CUSTOM_DATE',
            'args': [{'sentinel': 'CURRENT_DAY'}],
            'options': {
                'literal': 'CURRENT_DAY',
                'items': [{'sentinel': 'CURRENT_DAY'}, 'CURRENT_DAY'],
            },
        }
        original = deepcopy(definition)
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call') as call:
            call.side_effect = ['resolved', 'resolved', 'result']
            self.assertEqual(resolve_field_value(definition), 'result')
            self.assertEqual(call.call_count, 3)
            self.assertEqual(call.call_args.args, (SentinelKey.CUSTOM_DATE, 'resolved'))
            self.assertEqual(call.call_args.kwargs, {
                'options': {
                    'literal': 'CURRENT_DAY',
                    'items': ['resolved', 'CURRENT_DAY'],
                },
            })
        self.assertEqual(definition, original)

    def test_field_list_entries_support_bare_sentinels(self):
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call', return_value='today') as call:
            self.assertEqual(
                resolve_field_value(['CURRENT_DAY', {'sentinel': 'CURRENT_DAY'}, '1000']),
                ['today', 'today', '1000'],
            )
            self.assertEqual(call.call_count, 2)

    def test_ordinary_containers_are_copied_and_strings_stay_literal(self):
        definition = {'literal': 'CURRENT_DAY', 'items': [{'value': '1000'}]}
        result = resolve_field_value(definition)
        self.assertEqual(result, definition)
        result['items'][0]['value'] = '2000'
        self.assertEqual(definition['items'][0]['value'], '1000')

    def test_nested_provider_arguments_are_literal_strings(self):
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call', return_value='result') as call:
            resolve_field_value({
                'sentinel': 'CUSTOM_DATE',
                'args': ['CURRENT_DAY'],
                'anchor': 'CURRENT_DAY',
            })
            call.assert_called_once_with(
                SentinelKey.CUSTOM_DATE, 'CURRENT_DAY', anchor='CURRENT_DAY'
            )

    def test_provider_output_is_not_resolved_again(self):
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call', return_value='CURRENT_DAY'
        ) as call:
            self.assertEqual(resolve_field_value('CURRENT_DAY'), 'CURRENT_DAY')
            call.assert_called_once()

    def test_invalid_expressions_report_paths(self):
        cases = [
            ({'sentinel': 123}, TypeError, '.sentinel'),
            ({'sentinel': 'CURRENT_DYA'}, ValueError, '.sentinel'),
            ({'sentinel': 'CURRENT_DAY', 'args': None}, TypeError, '.args'),
            ({'sentinel': 'CURRENT_DAY', 'args': 'text'}, TypeError, '.args'),
            (
                {'sentinel': 'CUSTOM_DATE', 'args': [{'sentinel': 'UNKNOWN'}]},
                ValueError,
                '.args[0].sentinel',
            ),
        ]
        for definition, error, path in cases:
            with self.subTest(definition=definition):
                with self.assertRaises(error) as caught:
                    resolve_field_dict({'date': definition})
                self.assertIn(f"fields['date']{path}", str(caught.exception))

    def test_unregistered_provider_is_an_error(self):
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'is_registered', return_value=False):
            with self.assertRaisesRegex(ValueError, 'no registered function'):
                resolve_field_value('CURRENT_DAY')

    def test_provider_failure_preserves_cause_and_path(self):
        error = RuntimeError('provider failed')
        with patch.object(SENTINEL_FUNCTION_REGISTRY, 'call', side_effect=error):
            with self.assertRaises(ValueError) as caught:
                resolve_field_dict({'date': 'CURRENT_DAY'})
        self.assertIn("fields['date']", str(caught.exception))
        self.assertIs(caught.exception.__cause__, error)

    def test_scalars_are_preserved(self):
        for value in (None, False, 0, 1.5, '1000', 'UNKNOWN'):
            with self.subTest(value=value):
                self.assertEqual(resolve_field_value(value), value)


class SelectionModelTests(unittest.TestCase):
    def test_range_returns_resolved_bounds(self):
        self.assertEqual(resolve_range_value(7), 7)
        result = ValueRange.from_dict({'lower': 7, 'upper': 9})
        self.assertEqual((result.lower, result.upper), (7, 9))

    def test_selection_entries_resolve_once(self):
        with patch.object(
            SENTINEL_FUNCTION_REGISTRY, 'call', return_value='CURRENT_DAY'
        ) as call:
            result = ValueOptions.from_dict({
                'include': {
                    'values': ['CURRENT_DAY'],
                    'ranges': [{'lower': 'CURRENT_DAY', 'upper': 'CURRENT_DAY'}],
                },
            })
            self.assertIsNotNone(result.include)
            assert result.include is not None
            self.assertEqual(result.include.values, ['CURRENT_DAY'])
            self.assertEqual(result.include.ranges[0].lower, 'CURRENT_DAY')
            self.assertEqual(call.call_count, 3)

    def test_empty_selection_is_preserved(self):
        result = ValueOptions.from_dict({'include': {}, 'exclude': None})
        self.assertIsInstance(result.include, MultiSelection)
        self.assertIsNone(result.exclude)

    def test_guards_reject_invalid_shapes(self):
        cases = [
            (is_value_range_dict, {'unexpected': 1}),
            (is_value_range_dict, {'lower': 1}),
            (is_value_range_dict, {'lower': 1, 'upper': 2, 'extra': 3}),
            (is_multi_selection_dict, {'values': '1000'}),
            (is_multi_selection_dict, {'ranges': [{}]}),
            (is_multi_selection_dict, {'unknown': []}),
            (is_value_options_dict, {}),
            (is_value_options_dict, {'unexpected': 1}),
            (is_value_options_dict, {'include': []}),
            (is_value_options_dict, {'include': {}, 'unknown': 1}),
        ]
        for guard, value in cases:
            with self.subTest(guard=guard.__name__, value=value):
                self.assertFalse(guard(value))

    def test_constructors_validate_shapes(self):
        for model in (ValueRange, MultiSelection, ValueOptions):
            with self.subTest(model=model):
                with self.assertRaises(RuntimeError):
                    model.from_dict({'unexpected': 1})

    def test_invalid_range_bounds_are_rejected(self):
        for value in (None, [], {}, (1, 2)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    resolve_range_value(value)


if __name__ == '__main__':
    unittest.main()
