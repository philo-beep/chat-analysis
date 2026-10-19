"""Real-login integration tests using temporary SQLite databases only."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('KEYOUSHU_JWT_SECRET', 'temporary-test-secret-for-access-control-at-least-32-bytes')
from fastapi.testclient import TestClient
import auth_store
import database
import main


class AccessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.enterContext(patch.object(database, 'DB_PATH', Path(tmp.name)/'access.db'))
        self.client = self.enterContext(TestClient(main.app, raise_server_exceptions=False))
        self.admin = auth_store.create_user('admin_test', 'Admin-password-987!', role_codes=['admin'])
        self.admin_header = self.login('admin_test', 'Admin-password-987!')

    def login(self, username, password):
        r = self.client.post('/api/auth/login', json={'username':username,'password':password})
        self.assertEqual(r.status_code,200,r.text)
        return {'Authorization':'Bearer '+r.json()['data']['token']}

    def register(self, username='member_test'):
        r=self.client.post('/api/auth/register',json={'username':username,'password':'Member-password-987!'})
        self.assertEqual(r.status_code,200,r.text)
        return self.login(username,'Member-password-987!')

    def test_registration_hashing_and_no_escalation(self):
        headers=self.register()
        me=self.client.get('/api/auth/me',headers=headers).json()['data']
        self.assertEqual(me['roles'],['member'])
        self.assertNotIn('admin:stats',me['permissions'])
        self.assertEqual(self.client.get('/api/admin/overview',headers=headers).status_code,403)
        self.assertEqual(self.client.post('/api/auth/register',json={'username':'injected','password':'valid-password123','role':'admin'}).status_code,422)
        for username in ('member_test', 'MEMBER_TEST'):
            duplicate=self.client.post('/api/auth/register',json={'username':username,'password':'valid-password123'})
            self.assertEqual(duplicate.status_code,409)
            self.assertEqual(duplicate.json()['message'],'用户名已存在，请更换用户名。')
        with database._connect() as conn:
            value=conn.execute("SELECT password_hash FROM users WHERE username='member_test'").fetchone()[0]
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users WHERE username='member_test'").fetchone()[0],1)
        self.assertTrue(value.startswith('$argon2'))
        self.assertNotIn('password_hash',str(me))
        # A rejected duplicate must never replace the original account's password.
        self.login('member_test','Member-password-987!')

    def test_auth_failures_revoke_and_live_permissions(self):
        headers=self.register()
        for h in ({},{'Authorization':'Bearer wrong'}):
            self.assertEqual(self.client.get('/api/auth/me',headers=h).status_code,401)
        self.assertEqual(self.client.post('/api/auth/logout',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/auth/me',headers=headers).status_code,401)
        headers=self.login('member_test','Member-password-987!')
        with database._connect() as conn:
            conn.execute("DELETE FROM role_permissions WHERE role_id=(SELECT id FROM roles WHERE code='member') AND permission_id=(SELECT id FROM permissions WHERE code='analysis:run')")
        with patch.object(main,'analyze_chat') as model:
            self.assertEqual(self.client.post('/analyze',json={'text':'hello'},headers=headers).status_code,403)
            model.assert_not_called()
        with database._connect() as conn:
            conn.execute("UPDATE users SET is_active=0 WHERE username='member_test'")
        self.assertEqual(self.client.get('/api/auth/me',headers=headers).status_code,401)

    def test_record_isolation_and_legacy_visibility(self):
        alice=self.register('alice_test'); bob=self.register('bob_test')
        output={'requirements':[],'questions':[],'tasks':['联系客户'],'reply':'收到','is_sample':False}
        with patch.object(main,'analyze_chat',return_value=output):
            r=self.client.post('/analyze',json={'text':'客户：联系我'},headers=alice)
        self.assertEqual(r.status_code,200,r.text)
        rid=r.json()['id']
        for path in (f'/records/{rid}',f'/records/{rid}/export'):
            self.assertEqual(self.client.get(path,headers=bob).status_code,404)
            self.assertEqual(self.client.get(path,headers=alice).status_code,200)
        self.assertEqual(self.client.post('/api/usage/copy',json={'record_id':rid},headers=bob).status_code,404)
        self.assertEqual(self.client.post('/api/usage/copy',json={'record_id':rid},headers=alice).status_code,200)
        self.assertEqual(self.client.put(f'/records/{rid}',json={'result':output},headers=bob).status_code,404)
        self.assertEqual(self.client.get('/records',headers=bob).json(),[])
        legacy=database.save_record('legacy',output)
        self.assertEqual(self.client.get(f'/records/{legacy}',headers=alice).status_code,404)
        self.assertEqual(self.client.get(f'/records/{legacy}',headers=self.admin_header).status_code,200)

    def test_statistics_count_real_requests_and_hide_bodies(self):
        member=self.register()
        self.client.post('/api/usage/visit',json={},headers=member)
        self.client.post('/api/auth/login',json={'username':'member_test','password':'wrong-password'})
        r=self.client.get('/api/admin/overview',headers=self.admin_header)
        self.assertEqual(r.status_code,200,r.text)
        self.assertGreaterEqual(r.json()['data']['visits']['total'],1)
        events=self.client.get('/api/admin/events',headers=self.admin_header).json()['data']
        self.assertGreater(events['total'],0)
        self.assertNotIn('Member-password',str(events))
        self.assertNotIn('Bearer',str(events))
        self.assertTrue(any(e['feature']=='login' and e['status_code']==401 for e in events['items']))
        self.assertEqual(self.client.get('/api/admin/events?limit=500',headers=self.admin_header).status_code,422)

    def test_unknown_paths_are_not_logged_and_api_errors_are_uniform(self):
        r=self.client.get('/api/admin/secret-in-url')
        self.assertEqual(r.status_code,404)
        self.assertEqual(set(r.json()),{'code','message','data'})
        with database._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM access_events WHERE path LIKE '%secret-in-url%'").fetchone()[0],0)


if __name__=='__main__': unittest.main()
