"""Opt-in real-model acceptance on synthetic chats and an isolated database.

Run manually from the repository root; never discovered by unittest.
Each analysis has a hard 45-second wall-clock ceiling. Credentials are not logged.
"""
import copy
import faulthandler
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import ai_service
import auth_store
import database
import main

source = '客户：我是松禾商贸的陈晓明，负责采购。我们关心交货时间，方案要交主管批准，先用文字沟通。\n商家：收到，我先整理方案。'
follow_up = '客户：我是松禾商贸的陈晓明，采购负责人。现在不用主管审批了，我能直接决定。另外价格也很重要，请先发阶梯报价。\n商家：收到，我先核实价格。'
evidence_dir = Path(__file__).resolve().parents[2] / 'docs' / 'evidence' / 'customers'
evidence_dir.mkdir(parents=True, exist_ok=True)
report = {'synthetic_data': True, 'quality_review_changed': False, 'stages': []}
settings = ai_service.load_settings()
settings = ai_service.Settings(**{**settings.__dict__, 'timeout': min(settings.timeout, 40)})
directory = tempfile.TemporaryDirectory(prefix='keyoushu-customers-live-')
with directory, patch.object(database, 'DB_PATH', Path(directory.name) / 'test.db'), patch.dict(
        os.environ, {'KEYOUSHU_JWT_SECRET': 'isolated-live-customer-acceptance-secret-2026'}), patch.object(
        ai_service, 'load_settings', return_value=settings), TestClient(main.app) as client:
    user = auth_store.create_user('synthetic_customer_tester', 'Synthetic-customer-2026', ['member'])
    logged = client.post('/api/auth/login', json={'username': 'synthetic_customer_tester', 'password': 'Synthetic-customer-2026'})
    client.headers['Authorization'] = 'Bearer ' + logged.json()['data']['token']
    previous = None
    for label, text in [('first', source), ('same_again', source), ('new_information', follow_up)]:
        print('START ' + label, flush=True)
        raw_responses, contexts = [], []
        original = ai_service.ChatCompletionsClient.complete
        def capture(self, system, content, schema=None):
            if schema and schema['name'] == 'keyoushu_sales_analysis':
                payload = json.loads(content[0]['text'])
                contexts.append(copy.deepcopy(payload.get('previous_profile')))
            raw = original(self, system, content, schema)
            raw_responses.append(json.loads(raw))
            return raw
        start = time.monotonic()
        faulthandler.dump_traceback_later(45, exit=True)
        try:
            with patch.object(ai_service.ChatCompletionsClient, 'complete', capture):
                response = client.post('/analyze', json={'text': text})
        finally:
            faulthandler.cancel_dump_traceback_later()
        stage = {'name': label, 'duration_seconds': round(time.monotonic()-start, 2),
                 'status': response.status_code, 'response': response.json(),
                 'previous_profile_sent': contexts, 'raw_model_responses': raw_responses}
        report['stages'].append(stage)
        if response.status_code == 200:
            listing = client.get('/api/customers').json()['data']
            stage['customers_total'] = listing['total']
            assert listing['total'] == 1, listing
            customer_id = listing['items'][0]['id']
            detail = client.get(f'/api/customers/{customer_id}').json()['data']
            timeline = client.get(f'/api/customers/{customer_id}/snapshots').json()['data']
            stage.update(current=detail, snapshot_count=timeline['total'])
            if previous:
                assert contexts and contexts[0] == previous, 'Existing profile not supplied'
            if label == 'same_again':
                assert timeline['total'] == 2
            if label == 'new_information':
                assert timeline['total'] == 3
                assert detail['profile'] != previous, 'New information did not update portrait'
            previous = detail['profile']
        (evidence_dir / 'live-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:stage[k] for k in ('name','duration_seconds','status','snapshot_count') if k in stage}, ensure_ascii=False), flush=True)
        if response.status_code != 200:
            print('STOP: no automatic cloud retry', flush=True)
            sys.exit(1)
    with database._connect() as conn:
        report['database_query'] = [dict(row) for row in conn.execute('SELECT id,display_name,company,version,communication_strategy,communication_points_json FROM customer_profiles WHERE owner_id=?', (user['id'],))]
        report['snapshots_query'] = [dict(row) for row in conn.execute('SELECT id,profile_id,source_record_id,created_at FROM customer_profile_snapshots ORDER BY id')]
    (evidence_dir / 'live-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS three real analyses, same customer, prior context and three snapshots', flush=True)
