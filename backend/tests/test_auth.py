"""Security regressions against real HTTP authentication and temporary databases."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from fastapi.testclient import TestClient

import auth
import auth_store
import database
import main


TEST_SECRET = 'isolated-auth-test-signing-key-at-least-32-characters'
TEST_PASSWORD = 'Temporary-test-password-739!'


class AuthSecurityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(database, 'DB_PATH', Path(directory.name) / 'auth.db'))
        self.enterContext(patch.dict(os.environ, {'KEYOUSHU_JWT_SECRET': TEST_SECRET}))
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))
        self.admin = auth_store.create_user('security_admin', TEST_PASSWORD, ['admin'])
        self.member = auth_store.create_user('security_member', TEST_PASSWORD, ['member'])
        self.admin_headers = self.login('security_admin')
        self.member_headers = self.login('security_member')
        self.roles = {role['code']: role['id'] for role in auth_store.list_roles()}
        self.permissions = {permission['code']: permission['id'] for permission in auth_store.list_permissions()}

    def login(self, username):
        response = self.client.post('/api/auth/login', json={'username': username, 'password': TEST_PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['data']['token']}

    def claims(self, **changes):
        now = int(time.time())
        claims = {'sub': str(self.member['id']), 'jti': os.urandom(12).hex(),
                  'iat': now, 'exp': now + 3600, 'iss': auth.ISSUER, 'aud': auth.AUDIENCE}
        claims.update(changes)
        return claims

    def check_invalid_jwt(self, claims, *, secret=TEST_SECRET, algorithm='HS256', session=True):
        token = jwt.encode(claims, secret if algorithm != 'none' else None, algorithm=algorithm)
        now = int(time.time())
        if session:
            # Keep server session valid so JWT validation is the only rejection reason.
            auth_store.save_session(self.member['id'], token, now, now + 3600)
        with patch.object(auth_store, 'session_user', wraps=auth_store.session_user) as lookup:
            response = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(response.status_code, 401, response.text)
        lookup.assert_not_called()

    def test_invalid_jwt_rejected_before_session_lookup(self):
        variants = [
            ('expired', {'claims': self.claims(exp=int(time.time()) - 10)}),
            ('wrong issuer', {'claims': self.claims(iss='other-service')}),
            ('wrong audience', {'claims': self.claims(aud='other-client')}),
            ('wrong signature', {'claims': self.claims(), 'secret': 'different-test-signing-key-at-least-32-characters'}),
            ('unsigned none', {'claims': self.claims(), 'algorithm': 'none'}),
        ]
        for label, options in variants:
            with self.subTest(label=label):
                self.check_invalid_jwt(**options)

    def test_valid_signature_without_server_session_is_rejected(self):
        token = jwt.encode(self.claims(), TEST_SECRET, algorithm='HS256')
        response = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(response.status_code, 401, response.text)

    def test_logout_and_disable_revoke_persisted_sessions(self):
        response = self.client.post('/api/auth/logout', headers=self.member_headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.member_headers).status_code, 401)
        new_headers = self.login('security_member')
        response = self.client.patch(f"/api/access-control/users/{self.member['id']}",
                                     json={'is_active': False}, headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/auth/me', headers=new_headers).status_code, 401)
        with database._connect() as connection:
            active = connection.execute('SELECT COUNT(*) FROM auth_sessions WHERE user_id=? AND revoked_at IS NULL',
                                        (self.member['id'],)).fetchone()[0]
        self.assertEqual(active, 0)
        # Reactivation never resurrects an old token.
        auth_store.set_user_active(self.member['id'], True)
        self.assertEqual(self.client.get('/api/auth/me', headers=new_headers).status_code, 401)

    def test_role_assignment_invalid_ids_preserve_entire_batch(self):
        before = auth_store.public_user(self.member['id'])['roles']
        response = self.client.put(f"/api/access-control/users/{self.member['id']}/roles",
                                   json={'role_ids': [self.roles['viewer'], 999999999]}, headers=self.admin_headers)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(auth_store.public_user(self.member['id'])['roles'], before)
        # Invalid nested role assignment must also roll back a newly created user.
        response = self.client.post('/api/access-control/users',
                                    json={'username': 'must_not_exist', 'password': TEST_PASSWORD,
                                          'role_ids': [self.roles['member'], 999999999]}, headers=self.admin_headers)
        self.assertEqual(response.status_code, 422, response.text)
        with database._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE username='must_not_exist'").fetchone()[0], 0)

    def test_permission_assignment_invalid_ids_preserve_entire_batch(self):
        role_id = self.roles['member']
        before = next(role['permission_ids'] for role in auth_store.list_roles() if role['id'] == role_id)
        response = self.client.put(f'/api/access-control/roles/{role_id}/permissions',
                                   json={'permission_ids': [self.permissions['records:read'], 999999999]},
                                   headers=self.admin_headers)
        self.assertEqual(response.status_code, 422, response.text)
        after = next(role['permission_ids'] for role in auth_store.list_roles() if role['id'] == role_id)
        self.assertEqual(after, before)

    def test_last_admin_cannot_be_disabled_or_demoted(self):
        path = f"/api/access-control/users/{self.admin['id']}"
        response = self.client.put(path + '/roles', json={'role_ids': [self.roles['member']]}, headers=self.admin_headers)
        self.assertEqual(response.status_code, 422, response.text)
        response = self.client.patch(path, json={'is_active': False}, headers=self.admin_headers)
        self.assertEqual(response.status_code, 422, response.text)
        current = auth_store.public_user(self.admin['id'])
        self.assertTrue(current['is_active'])
        self.assertIn('admin', current['roles'])
        self.assertEqual(self.client.get('/api/admin/overview', headers=self.admin_headers).status_code, 200)

    def test_schema_reinitialization_does_not_restore_removed_grants(self):
        with database._connect() as connection:
            connection.execute('DELETE FROM role_permissions WHERE role_id=? AND permission_id=?',
                               (self.roles['member'], self.permissions['analysis:run']))
        database.init_db()
        database.init_db()
        self.assertNotIn('analysis:run', auth_store.public_user(self.member['id'])['permissions'])
        response = self.client.get('/api/auth/me', headers=self.member_headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('analysis:run', response.json()['data']['permissions'])

    def test_delegated_management_cannot_escalate_or_write(self):
        role = auth_store.create_role('delegated', 'Delegated test role')
        auth_store.set_role_permissions(role['id'], [self.permissions['users:write'], self.permissions['roles:write']])
        auth_store.set_user_roles(self.member['id'], [role['id']])
        requests = [
            ('post', '/api/access-control/users', {'username': 'illegal_admin', 'password': TEST_PASSWORD, 'role_ids': [self.roles['admin']]}),
            ('put', f"/api/access-control/users/{self.member['id']}/roles", {'role_ids': [self.roles['admin']]}),
            ('patch', f"/api/access-control/users/{self.admin['id']}", {'is_active': False}),
            ('post', '/api/access-control/roles', {'code': 'illegal_role', 'name': 'Must not exist'}),
            ('put', f"/api/access-control/roles/{role['id']}/permissions", {'permission_ids': [self.permissions['admin:stats']]}),
        ]
        for method, path, payload in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, json=payload, headers=self.member_headers)
                self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(auth_store.public_user(self.member['id'])['roles'], ['delegated'])

    def test_stats_entry_permission_matches_me_and_checks_live_grants(self):
        self.assertEqual(self.client.get('/api/admin/overview', headers=self.member_headers).status_code, 403)
        role = auth_store.create_role('stats_reader', 'Stats reader')
        auth_store.set_role_permissions(role['id'], [self.permissions['admin:stats']])
        auth_store.set_user_roles(self.member['id'], [role['id']])
        me = self.client.get('/api/auth/me', headers=self.member_headers).json()['data']
        self.assertIn('admin:stats', me['permissions'])
        self.assertNotIn('admin', me['roles'])
        self.assertEqual(self.client.get('/api/admin/overview', headers=self.member_headers).status_code, 200)
        auth_store.set_role_permissions(role['id'], [])
        self.assertEqual(self.client.get('/api/admin/events', headers=self.member_headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()
