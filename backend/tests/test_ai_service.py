import base64
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import ai_service
from ai_contract import AnalysisOutcome


class SettingsTests(unittest.TestCase):
    def test_endpoint_normalizes_openai_compatible_base_urls(self):
        for base, expected in (
            ('https://api.openai-next.com', 'https://api.openai-next.com/v1/chat/completions'),
            ('https://api.openai-next.com/v1/', 'https://api.openai-next.com/v1/chat/completions'),
            ('https://api.openai-next.com/v1/chat/completions', 'https://api.openai-next.com/v1/chat/completions'),
        ):
            self.assertEqual(ai_service.Settings('test-key', base).endpoint, expected)

    def test_settings_reject_missing_credentials_and_invalid_reasoning(self):
        with self.assertRaises(ai_service.ConfigurationError):
            ai_service.Settings('').validate()
        with self.assertRaises(ai_service.ConfigurationError):
            ai_service.Settings('test-key', reasoning_effort='extreme').validate()


class ClientTests(unittest.TestCase):
    class Response:
        headers = {'Content-Type': 'application/json; charset=utf-8'}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _limit):
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]}).encode()

    def test_openai_payload_uses_selected_model_reasoning_and_bearer_auth(self):
        settings = ai_service.Settings('test-secret', reasoning_effort='medium', quality_review=False)
        with patch('ai_service.urllib.request.build_opener') as build:
            build.return_value.open.return_value = self.Response()
            output = ai_service.ChatCompletionsClient(settings).complete('system', [{'type': 'text', 'text': 'hello'}])
        self.assertEqual(output, '{"ok":true}')
        request = build.return_value.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, settings.endpoint)
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-secret')
        self.assertEqual(payload['model'], 'gpt-6.1-sol')
        self.assertEqual(payload['reasoning_effort'], 'medium')
        self.assertEqual(payload['messages'][0]['content'], 'system')
        self.assertNotIn('test-secret', request.data.decode())

    def test_oversized_provider_response_is_rejected(self):
        response = self.Response()
        response.read = lambda limit: b' ' * (ai_service.MAX_RESPONSE + 1)
        with patch('ai_service.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaises(ai_service.InvalidModelOutput):
                ai_service.ChatCompletionsClient(ai_service.Settings('test-key')).complete('system', [])

    def test_403_does_not_claim_model_permission_is_the_only_cause(self):
        import urllib.error
        with patch('ai_service.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = urllib.error.HTTPError('https://example.test', 403, 'Forbidden', {}, io.BytesIO(b'private upstream body'))
            with self.assertRaises(ai_service.ModelAPIError) as error:
                ai_service.ChatCompletionsClient(ai_service.Settings('test-secret')).complete('system', [])
        self.assertIn('访问规则', str(error.exception))
        self.assertNotIn('private upstream body', str(error.exception))
        self.assertNotIn('test-secret', str(error.exception))

    def test_image_is_encoded_as_openai_data_url(self):
        encoded = base64.b64encode(b'image-bytes').decode()
        content = ai_service.ChatCompletionsClient._openai_content([
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': encoded}},
        ])
        self.assertEqual(content[0]['type'], 'image_url')
        self.assertEqual(content[0]['image_url']['url'], f'data:image/png;base64,{encoded}')

    def test_response_rejects_incomplete_and_filtered_completions(self):
        client = ai_service.ChatCompletionsClient(ai_service.Settings('test-key'))
        for reason in (None, 'content_filter', 'tool_calls'):
            with self.subTest(reason=reason), self.assertRaises(ai_service.InvalidModelOutput):
                client._response({'choices': [{'finish_reason': reason, 'message': {'content': '{}'}}]})

    def test_response_rejects_truncation(self):
        client = ai_service.ChatCompletionsClient(ai_service.Settings('test-key'))
        with self.assertRaises(ai_service.InvalidModelOutput):
            client._response({'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]})


class ContractTests(unittest.TestCase):
    def test_source_guard_rejects_seller_evidence(self):
        response = {'requirements': [{'field': '数量', 'value': '999件', 'evidence': '需要999件'}], 'questions': [], 'tasks': [], 'reply': ''}
        with self.assertRaises(ai_service.InvalidModelOutput):
            ai_service.validate_result(response, '乙方：需要999件')

    def test_source_guard_requires_verbatim_customer_evidence(self):
        response = {'requirements': [{'field': '数量', 'value': '150件', 'evidence': '改成150件'}], 'questions': [], 'tasks': [], 'reply': ''}
        result = ai_service.validate_result(response, '甲方：数量改成150件。')
        self.assertEqual(set(result), {'requirements', 'questions', 'tasks', 'reply', 'is_sample'})
        self.assertFalse(result['is_sample'])

    def test_uncertainty_in_another_field_does_not_reject_exact_quantity(self):
        result = {'requirements': [{'field': '数量', 'value': '100件', 'evidence': '数量100件，预算大概3000元'}], 'questions': [], 'tasks': [], 'reply': ''}
        self.assertEqual(ai_service.validate_result(result, '甲方：数量100件，预算大概3000元。')['requirements'][0]['value'], '100件')

    def test_quality_review_receives_original_source_and_candidate(self):
        text = '甲方：大概100件。'
        draft = {'requirements': [{'field': '数量', 'value': '100件', 'evidence': '大概100件'}], 'questions': [], 'tasks': [], 'reply': ''}
        reviewed = {**draft, 'requirements': [{'field': '数量', 'value': '大概100件', 'evidence': '大概100件'}]}
        client = ai_service.ChatCompletionsClient(ai_service.Settings('test-key', quality_review=True))
        with patch.object(client, 'complete', side_effect=[json.dumps(draft), json.dumps(reviewed)]) as complete:
            result = ai_service._analyze(text, client)
        self.assertEqual(result['requirements'][0]['value'], '大概100件')
        review_input = json.loads(complete.call_args_list[1].args[1][0]['text'])
        self.assertEqual(review_input, {'chat_text': text, 'candidate': draft})

    def test_image_entry_returns_transcript_without_changing_contract(self):
        from PIL import Image
        image_data = io.BytesIO()
        Image.new('RGB', (2, 2), 'white').save(image_data, format='PNG')
        transcript = '甲方：数量改成150件。'
        result = {'requirements': [{'field': '数量', 'value': '150件', 'evidence': '数量改成150件'}], 'questions': [], 'tasks': [], 'reply': ''}
        client = ai_service.ChatCompletionsClient(ai_service.Settings('test-key', quality_review=False))
        with patch.object(ai_service, 'load_settings', return_value=client.settings), patch.object(
            client, 'complete', side_effect=[json.dumps({'transcript': transcript}), json.dumps(result)]
        ), patch.object(ai_service, 'ChatCompletionsClient', return_value=client):
            outcome = ai_service.analyze_chat_with_source('', image_data.getvalue(), 'image/png')
        self.assertIsInstance(outcome, AnalysisOutcome)
        self.assertEqual(outcome.source_text, transcript)
        self.assertEqual(outcome.result['requirements'][0]['value'], '150件')


if __name__ == '__main__':
    unittest.main()
