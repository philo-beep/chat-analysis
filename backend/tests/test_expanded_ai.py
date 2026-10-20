import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_service
from analysis_models import AIOutput
from expanded_fixture import SOURCE, output


class ExpandedAITests(unittest.TestCase):
    def client(self):
        return ai_service.ChatCompletionsClient(ai_service.Settings('isolated-test', quality_review=False))

    def test_strict_schema_and_seven_fields_with_source(self):
        value = ai_service.validate_result(output(), SOURCE)
        self.assertIn('customer_profile', value)
        self.assertFalse(value['is_sample'])
        schema = AIOutput.response_schema()['schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(len(schema['required']), 7)

    def test_invalid_json_repaired_once(self):
        client = self.client()
        with patch.object(client, 'complete', side_effect=['not JSON', json.dumps(output())]) as call:
            result = ai_service._analyze(SOURCE, client)
        self.assertEqual(call.call_count, 2)
        self.assertIn('ddl_tasks', result)
        self.assertTrue(call.call_args.kwargs['schema']['strict'])

    def test_invalid_output_stops_after_one_retry(self):
        client = self.client()
        with patch.object(client, 'complete', return_value='{}') as call:
            with self.assertRaises(ai_service.InvalidModelOutput):
                ai_service._analyze(SOURCE, client)
        self.assertEqual(call.call_count, 2)

    def test_dates_references_and_quotes_are_checked(self):
        for change in ('bad_date', 'start_after', 'bad_index', 'no_question', 'bad_quote', 'extra'):
            candidate = output()
            if change == 'bad_date': candidate['ddl_tasks'][0]['ddl_date'] = '2026-02-30'
            if change == 'start_after': candidate['ddl_tasks'][0]['start_date'] = '2026-11-01'
            if change == 'bad_index': candidate['questions'][0]['related_ddl_index'] = 3
            if change == 'no_question': candidate['questions'] = []
            if change == 'bad_quote': candidate['ddl_tasks'][0]['source_quote'] = '捏造引用'
            if change == 'extra': candidate['undocumented'] = True
            with self.subTest(change=change), self.assertRaises(ai_service.InvalidModelOutput):
                ai_service.validate_result(candidate, SOURCE)

    def test_quality_review_keeps_seven_field_schema(self):
        client = self.client()
        client.settings = ai_service.Settings('isolated-test', quality_review=True)
        with patch.object(client, 'complete', return_value=json.dumps(output())) as call:
            ai_service._analyze(SOURCE, client)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args.kwargs['schema']['strict'], True)
        self.assertEqual(json.loads(call.call_args.args[1][0]['text'])['chat_text'], SOURCE)


if __name__ == '__main__': unittest.main()
