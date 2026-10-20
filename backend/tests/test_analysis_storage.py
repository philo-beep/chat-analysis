"""Expanded result integration: temporary DB, real auth, no network or user data."""
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
import auth_store
import database
import main
import profile_store
import calendar_store
import ai_service
from expanded_fixture import SOURCE, output


class ExpandedStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix='keyoushu-expanded-'))
        self.enterContext(patch.object(database, 'DB_PATH', Path(self.temp) / 'test.db'))
        self.enterContext(patch.dict(os.environ, {'KEYOUSHU_JWT_SECRET': 'expanded-integration-test-only-secret-2026'}))
        self.enterContext(patch.object(main, 'logger'))
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))
        self.user = auth_store.create_user('expanded_member', 'Expanded-test-2026', ['member'])
        self.other = auth_store.create_user('expanded_other', 'Expanded-test-2026', ['member'])
        response = self.client.post('/api/auth/login', json={'username': 'expanded_member', 'password': 'Expanded-test-2026'})
        self.client.headers['Authorization'] = 'Bearer ' + response.json()['data']['token']

    def analyze(self, candidate=None):
        with patch.object(main, 'analyze_chat', return_value=output() if candidate is None else candidate):
            response = self.client.post('/analyze', json={'text': SOURCE})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def record(self, id):
        return self.client.get(f'/records/{id}').json()

    def act(self, id, action, index=0, **extra):
        return self.client.post(f'/api/records/{id}/actions', json={
            'action': action, 'index': index, 'expected_result': self.record(id)['result'], **extra})

    def test_profile_is_silent_and_new_tasks_require_click(self):
        result = self.analyze()
        self.assertIn('requirements', result)
        self.assertIn('reply', result)
        self.assertNotIn('customer_profile', result)
        self.assertNotIn('customer_profile', self.record(result['id'])['result'])
        self.assertNotIn('customer_profile', self.client.get(f"/records/{result['id']}/export").json()['result'])
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM task_items').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT display_name FROM customer_profiles').fetchone()[0], '林晓')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profile_snapshots').fetchone()[0], 1)

    def test_calendar_start_date_idempotency_pool_and_ignore(self):
        id = self.analyze()['id']
        response = self.act(id, 'add_ddl_task')
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['data']['item']
        self.assertEqual(item['due_date'], '2026-10-30')
        self.assertEqual(item['start_date'], '2026-10-20')
        self.assertEqual(item['manual_level'], None)
        self.assertEqual(self.act(id, 'add_ddl_task').json()['data']['item']['id'], item['id'])
        response = self.act(id, 'accept_suggestion', kind='tasks')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()['data']['item']['due_date'])
        self.assertEqual(self.act(id, 'ignore_suggestion', kind='suggested_tasks').status_code, 200)
        self.assertEqual(self.record(id)['result']['suggested_tasks'][0]['status'], 'ignored')
        self.assertEqual(self.act(id, 'accept_suggestion', kind='suggested_tasks').status_code, 200)

    def test_confirmation_and_edit_cannot_forge_server_state_or_start(self):
        id = self.analyze()['id']
        response = self.act(id, 'confirm_question', answer='客户确认2026-10-30')
        self.assertEqual(response.status_code, 200, response.text)
        stored = self.record(id)['result']
        self.assertEqual(stored['questions'][0]['confirmed_answer'], '客户确认2026-10-30')
        stored['questions'][0]['confirmed_answer'] = '伪造普通保存答案'
        stored['ddl_tasks'][0]['status'] = 'added'
        stored['ddl_tasks'][0]['calendar_task_id'] = 999
        self.assertEqual(self.client.put(f'/records/{id}', json={'result': stored}).status_code, 200)
        refreshed = self.record(id)['result']
        self.assertEqual(refreshed['questions'][0]['confirmed_answer'], '客户确认2026-10-30')
        self.assertNotEqual(refreshed['ddl_tasks'][0].get('status'), 'added')
        refreshed['ddl_tasks'][0]['start_date'] = '2026-10-21'
        self.assertEqual(self.client.put(f'/records/{id}', json={'result': refreshed}).status_code, 422)

    def test_stale_action_and_cross_account_rejected(self):
        id = self.analyze()['id']
        original = self.record(id)['result']
        edited = copy.deepcopy(original)
        edited['reply'] = '人工更新回复'
        self.assertEqual(self.client.put(f'/records/{id}', json={'result': edited}).status_code, 200)
        self.assertEqual(self.client.post(f'/api/records/{id}/actions', json={
            'action': 'add_ddl_task', 'index': 0, 'expected_result': original}).status_code, 409)
        login = self.client.post('/api/auth/login', json={'username': 'expanded_other', 'password': 'Expanded-test-2026'})
        self.client.headers['Authorization'] = 'Bearer ' + login.json()['data']['token']
        self.assertEqual(self.client.post(f'/api/records/{id}/actions', json={
            'action': 'add_ddl_task', 'index': 0, 'expected_result': edited}).status_code, 404)

    def test_profile_identity_history_delete_and_unknown_separation(self):
        first = self.analyze()['id']
        changed = output()
        changed['customer_profile']['next_follow_up'] = '继续核实报价'
        second = self.analyze(changed)['id']
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profiles').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profile_snapshots').fetchone()[0], 2)
        self.assertEqual(self.client.delete(f'/api/records/{second}').status_code, 200)
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT next_follow_up FROM customer_profiles').fetchone()[0], '确认可行交期')
        self.assertEqual(self.client.delete(f'/api/records/{first}').status_code, 200)
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profiles').fetchone()[0], 0)
        unknown = output()
        unknown['customer_profile'].update(display_name='未知', company='未知')
        self.analyze(unknown)
        self.analyze(unknown)
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profiles').fetchone()[0], 2)

    def test_profile_and_action_failures_rollback(self):
        with patch.object(profile_store, 'save_snapshot', side_effect=__import__('sqlite3').OperationalError('test rollback')):
            with patch.object(main, 'analyze_chat', return_value=output()):
                self.assertEqual(self.client.post('/analyze', json={'text': SOURCE}).status_code, 500)
        self.assertEqual(database.list_records(), [])
        id = self.analyze()['id']
        before = self.record(id)['result']
        real_insert = calendar_store._insert
        def fail_after_insert(*args, **kwargs):
            real_insert(*args, **kwargs)
            raise __import__('sqlite3').OperationalError('test rollback')
        with patch.object(calendar_store, '_insert', side_effect=fail_after_insert):
            self.assertEqual(self.act(id, 'add_ddl_task').status_code, 500)
        self.assertEqual(self.record(id)['result'], before)
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM task_items').fetchone()[0], 0)

    def test_expanded_profile_cannot_be_sent_by_client(self):
        id = self.analyze()['id']
        result = self.record(id)['result']
        result['customer_profile'] = output()['customer_profile']
        self.assertEqual(self.client.put(f'/records/{id}', json={'result': result}).status_code, 422)

    def test_curated_model_error_reaches_frontend(self):
        with patch.object(main, 'analyze_chat', side_effect=ai_service.ModelAPIError('智能整理暂时无法连接，请稍后重试')):
            response = self.client.post('/analyze', json={'text': SOURCE})
        self.assertEqual(response.status_code, 502)
        self.assertIn('暂时无法连接', response.text)


if __name__ == '__main__': unittest.main()
