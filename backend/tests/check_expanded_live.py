"""Opt-in real cloud acceptance with synthetic conversations and a temporary DB."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
import ai_service
import auth_store
import database
import main

parser = argparse.ArgumentParser()
parser.add_argument('scenario', choices=['long', 'short', 'image'])
parser.add_argument('--output', required=True)
parser.add_argument('--no-review', action='store_true', help='This acceptance only; leave runtime configuration untouched')
args = parser.parse_args()
target = Path(args.output)
target.parent.mkdir(parents=True, exist_ok=True)
raw_completions = []
original_complete = ai_service.ChatCompletionsClient.complete
original_settings = ai_service.load_settings

def complete(self, *a, **kw):
    began = time.monotonic()
    value = original_complete(self, *a, **kw)
    raw_completions.append({'seconds': round(time.monotonic()-began, 2), 'json': json.loads(value)})
    return value

def settings():
    from dataclasses import replace
    configured = original_settings()
    return replace(configured, timeout=45, quality_review=False if args.no_review else configured.quality_review)

text = (ROOT / 'samples/expanded-business-chat.txt').read_text(encoding='utf-8') if args.scenario == 'long' else '客户：在吗\n商家：在的，什么事'
began = time.monotonic()
evidence = {'scenario': args.scenario, 'source': text, 'fixture': 'synthetic chat, temporary DB, real cloud model', 'raw_completions': raw_completions}
with tempfile.TemporaryDirectory(prefix='keyoushu-expanded-live-') as folder, patch.object(database, 'DB_PATH', Path(folder) / 'test.db'), patch.dict(os.environ, {'KEYOUSHU_JWT_SECRET': 'expanded-live-synthetic-acceptance-only-2026'}), patch.object(ai_service.ChatCompletionsClient, 'complete', complete), patch.object(ai_service, 'load_settings', settings):
    with TestClient(main.app, raise_server_exceptions=False) as client:
        auth_store.create_user('live_synthetic', 'Live-synthetic-2026', ['member'])
        token = client.post('/api/auth/login', json={'username':'live_synthetic','password':'Live-synthetic-2026'}).json()['data']['token']
        client.headers['Authorization'] = 'Bearer ' + token
        if args.scenario == 'image':
            image = (ROOT / 'frontend/public/demo-sales-chat.png').read_bytes()
            response = client.post('/analyze', data={'text':''}, files={'image':('demo.png', image, 'image/png')})
        else:
            response = client.post('/analyze', json={'text': text})
        evidence.update(status=response.status_code, response=response.json())
        if response.status_code == 200:
            id = response.json()['id']
            record = client.get(f'/records/{id}').json()
            assert 'customer_profile' not in record['result']
            assert all(key in record['result'] for key in ('requirements','questions','tasks','reply','ddl_tasks','suggested_tasks'))
            if args.scenario == 'long':
                assert record['result']['ddl_tasks'], 'long conversation must yield date tasks'
                assert record['result']['suggested_tasks'], 'long conversation must yield suggestions'
                action = client.post(f'/api/records/{id}/actions', json={'action':'add_ddl_task','index':0,'expected_result':record['result']})
                assert action.status_code == 200, action.text
                evidence['calendar_action'] = action.json()['data']
                evidence['calendar_items'] = client.get('/api/calendar/items?status=all').json()['data']['items']
                assert evidence['calendar_items'][0]['due_date'] == record['result']['ddl_tasks'][0]['ddl_date']
            if args.scenario == 'short':
                assert record['result']['ddl_tasks'] == []
                assert record['result']['requirements'] == []
                assert record['result']['suggested_tasks'] == []
            with database._connect() as conn:
                evidence['profile_query'] = [dict(row) for row in conn.execute('SELECT * FROM customer_profiles')]
                evidence['snapshot_query'] = [dict(row) for row in conn.execute('SELECT * FROM customer_profile_snapshots')]
            assert len(evidence['profile_query']) == 1
            evidence['passed'] = True
        else:
            evidence['passed'] = False
evidence['seconds'] = round(time.monotonic()-began, 2)
target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'scenario':args.scenario, 'status':evidence['status'], 'passed':evidence['passed'], 'seconds':evidence['seconds'], 'output':str(target)},ensure_ascii=False))
sys.exit(0 if evidence['passed'] else 1)
