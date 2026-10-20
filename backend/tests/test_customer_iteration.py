"""Source-checked model context through real analysis/auth/storage; no network."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import ai_service
import auth_store
import database
import main
import profile_store
from analysis_models import AIOutput
from expanded_fixture import SOURCE, output

IDENTITY = dict(display_name='林晓', company='云杉公司', name_quote='我是云杉公司的林晓', company_quote='我是云杉公司的林晓')


class CustomerIterationTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix='keyoushu-iteration-'))
        self.enterContext(patch.object(database, 'DB_PATH', Path(directory) / 'test.db'))
        self.enterContext(patch.dict(os.environ, {'KEYOUSHU_JWT_SECRET': 'customer-iteration-secret-only-test-2026'}))
        self.client = self.enterContext(TestClient(main.app))
        self.user = auth_store.create_user('iteration_owner', 'Iteration-test-2026', ['member'])
        login = self.client.post('/api/auth/login', json={'username': 'iteration_owner', 'password': 'Iteration-test-2026'})
        self.client.headers['Authorization'] = 'Bearer ' + login.json()['data']['token']
        self.settings = ai_service.Settings('isolated-key', quality_review=False)

    def analyze(self, candidate):
        client = ai_service.ChatCompletionsClient(self.settings)
        with patch.object(ai_service, 'load_settings', return_value=self.settings), patch.object(
                ai_service, 'ChatCompletionsClient', return_value=client), patch.object(
                client, 'complete', side_effect=[json.dumps(IDENTITY), json.dumps(candidate)]) as calls:
            response = self.client.post('/analyze', json={'text': SOURCE})
        self.assertEqual(response.status_code, 200, response.text)
        return response, calls.call_args_list

    def test_second_analysis_receives_existing_profile_and_writes_new_snapshot(self):
        first, calls = self.analyze(output())
        self.assertIsNone(json.loads(calls[-1].args[1][0]['text'])['previous_profile'])
        second, calls = self.analyze(output())
        context = json.loads(calls[-1].args[1][0]['text'])
        self.assertEqual(context['previous_profile']['concerns'], ['交期'])
        self.assertEqual(context['selected_identity']['display_name'], '林晓')
        self.assertNotEqual(first.json()['id'], second.json()['id'])
        self.assertNotIn('customer_profile', second.json())
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profiles').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profile_snapshots').fetchone()[0], 2)

    def test_retained_identity_allowed_but_old_requirement_evidence_not_allowed(self):
        candidate = output()
        candidate.update(requirements=[], questions=[], ddl_tasks=[], tasks=[], suggested_tasks=[], reply='')
        previous = copy.deepcopy(candidate['customer_profile'])
        ai_service.validate_result(candidate, '客户：还是按之前的安排。', previous)
        with self.assertRaises(ai_service.InvalidModelOutput):
            ai_service.validate_result(candidate, '客户：还是按之前的安排。')
        candidate['requirements'] = output()['requirements']
        with self.assertRaises(ai_service.InvalidModelOutput):
            ai_service.validate_result(candidate, '客户：还是按之前的安排。', previous)

    def test_identity_cannot_be_seller_third_party_or_wrong_output(self):
        client = ai_service.ChatCompletionsClient(self.settings)
        with patch.object(client, 'complete', return_value=json.dumps(IDENTITY)):
            with self.assertRaises(ai_service.InvalidModelOutput):
                ai_service._identify_customer('商家：我是云杉公司的林晓。', client)
        candidate = output()
        with self.assertRaises(ai_service.InvalidModelOutput):
            ai_service.validate_result(candidate, SOURCE, selected_identity={**IDENTITY, 'display_name': '其他人'})

    def test_live_schema_requires_guidance_and_review_keeps_prior_context(self):
        profile_schema = AIOutput.response_schema()['schema']['$defs']['CustomerProfile']
        self.assertIn('communication_strategy', profile_schema['required'])
        self.assertIn('communication_points', profile_schema['required'])
        client = ai_service.ChatCompletionsClient(ai_service.Settings('isolated-key', quality_review=True))
        previous = output()['customer_profile']
        with patch.object(client, 'complete', side_effect=[json.dumps(IDENTITY), json.dumps(output()), json.dumps(output())]) as calls:
            ai_service._analyze(SOURCE, client, lambda identity: {'profile': previous})
        self.assertEqual(json.loads(calls.call_args_list[-1].args[1][0]['text'])['previous_profile'], previous)

    def test_stale_profile_returns_409_and_rolls_back_whole_chat(self):
        self.analyze(output())
        original = profile_store.context_for_identity
        def race(owner_id, identity):
            context = original(owner_id, identity)
            with database._connect() as conn:
                conn.execute('UPDATE customer_profiles SET version=version+1 WHERE id=?', (context['profile_id'],))
            return context
        client = ai_service.ChatCompletionsClient(self.settings)
        with patch.object(profile_store, 'context_for_identity', side_effect=race), patch.object(
                ai_service, 'load_settings', return_value=self.settings), patch.object(
                ai_service, 'ChatCompletionsClient', return_value=client), patch.object(
                client, 'complete', side_effect=[json.dumps(IDENTITY), json.dumps(output())]):
            response = self.client.post('/analyze', json={'text': SOURCE})
        self.assertEqual(response.status_code, 409)
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM records').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
