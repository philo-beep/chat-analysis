"""Explicit real-model acceptance run; does not run during unittest discovery.

Use --images for actual configured cloud model calls. Results are measured, never fixture outputs.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import database
import auth_store
import main
from fastapi.testclient import TestClient


def criteria(case_id, result):
    facts = result['requirements']
    def values(field):
        return ' '.join(r['value'] for r in facts if field in r['field']).replace(' ', '')
    all_values = ' '.join(r['value'] for r in facts).replace(' ', '')
    questions = ' '.join(item if isinstance(item, str) else item['question'] + ' ' + item['initial_guess'] for item in result['questions'])
    checks = {'real_source': result['is_sample'] is False}
    if case_id == 'normal':
        checks.update(quantity='100' in values('数量'), budget='3000' in values('预算'),
                      date='10月30' in all_values, design='设计' in all_values,
                      missing_year='年' in questions, sizes='尺码' in questions)
    elif case_id == 'missing':
        checks.update(no_numeric_facts=not any(c.isdigit() for c in all_values),
                      ask_quantity='数量' in questions, ask_budget='预算' in questions,
                      ask_date=any(k in questions for k in ['时间','日期','交期']))
    elif case_id == 'correction':
        checks.update(final_150='150' in values('数量') and '100' not in values('数量'),
                      change_evidence=any('150' in r['evidence'] for r in facts if '数量' in r['field']))
    elif case_id == 'approximate':
        checks.update(approx_quantity=any(k in values('数量') for k in ['约','大概','左右']),
                      budget_range='三四千' in values('预算'),
                      date_pending=any(k in questions for k in ['时间','日期','交期']))
    elif case_id == 'ambiguous':
        checks.update(budget_pending='3000' in questions and '5000' in questions,
                      no_final_budget=not any('预算' in r['field'] and not any(k in r['value'] for k in ['待确认','歧义','未确认']) for r in facts))
    elif case_id == 'deadline':
        if 'ddl_tasks' in result:
            checks.update(explicit_deadline=any(task['ddl_date'] == '2026-10-25' and '初稿' in task['title'] for task in result['ddl_tasks']),
                          unscheduled_task=any('尺码' in task for task in result['tasks']) or any('尺码' in task['title'] for task in result['suggested_tasks']))
        else:
            checks.update(explicit_deadline=any('DDL:2026-10-25' in task.replace(' ', '') and '初稿' in task for task in result['tasks']),
                          unscheduled_task=any('尺码' in task and 'DDL:' not in task for task in result['tasks']))
    elif case_id == 'roles':
        checks.update(final_150='150' in values('数量') and '100' not in values('数量'),
                      cotton='纯棉' in all_values, unit_budget=any('40' in r['value'] and any(k in r['field']+r['value'] for k in ['单','每件','/件','一件']) for r in facts),
                      relative_date='下周' in all_values, date_pending=any(k in questions for k in ['日期','时间']),
                      seller_not_fact=not any('初步方案' in r['value'] for r in facts))
    return checks


def run(images=False, case_ids=None):
    root = BACKEND.parent
    cases = json.loads((root/'samples/acceptance-cases.json').read_text(encoding='utf-8'))
    if case_ids:
        cases = [case for case in cases if case['id'] in case_ids]
    measurements = []
    with tempfile.TemporaryDirectory(prefix='keyoushu-real-acceptance-') as temp:
        with patch.object(database, 'DB_PATH', Path(temp)/'acceptance.db'):
            with patch.dict(os.environ, {'KEYOUSHU_JWT_SECRET': 'acceptance-test-only-c1560b6ecc124a86982cf9e97ecc89d0'}), TestClient(main.app, raise_server_exceptions=False) as client:
                # 真实模型验收也必须经过正式鉴权；账号只存在于临时数据库。
                auth_store.create_user('acceptance-admin', 'Acceptance-admin-987654!', role_codes=['admin'])
                login = client.post('/api/auth/login', json={
                    'username': 'acceptance-admin', 'password': 'Acceptance-admin-987654!',
                })
                if login.status_code != 200:
                    raise RuntimeError(f'Acceptance login failed: {login.status_code} {login.text}')
                client.headers['Authorization'] = f"Bearer {login.json()['data']['token']}"
                for kind in (['text','image'] if images else ['text']):
                    for case in cases:
                        start = time.monotonic()
                        if kind == 'text':
                            response = client.post('/analyze', json={'text':case['text']})
                        else:
                            data = (root/'samples/screenshots'/f"{case['id']}.png").read_bytes()
                            response = client.post('/analyze', data={'text':''}, files={'image':('chat.png',data,'image/png')})
                        body = response.json()
                        entry = {'case':case['id'], 'kind':kind, 'seconds':round(time.monotonic()-start,2), 'status':response.status_code, 'result':body}
                        if response.status_code == 200:
                            record = client.get(f"/records/{body['id']}").json()
                            checks = criteria(case['id'], body)
                            checks['grounded_evidence'] = all(r['evidence'] in record['text'] for r in body['requirements'])
                            if case['id'] == 'deadline':
                                if body.get('analysis_version') == 2:
                                    actions = [('add_ddl_task', 'ddl_tasks', index) for index in range(len(body['ddl_tasks']))]
                                    actions += [('accept_suggestion', kind, index) for kind in ('tasks', 'suggested_tasks') for index in range(len(body[kind]))]
                                    for action, kind, index in actions:
                                        current = client.get(f"/records/{body['id']}").json()['result']
                                        payload = {'action': action, 'index': index, 'expected_result': current}
                                        if kind != 'ddl_tasks': payload['kind'] = kind
                                        response_action = client.post(f"/api/records/{body['id']}/actions", json=payload)
                                        if response_action.status_code != 200:
                                            raise RuntimeError('Acceptance action failed: ' + response_action.text)
                                scheduled = client.get('/api/calendar/items?scheduled=true').json()['data']['items']
                                pool = client.get('/api/calendar/items?scheduled=false').json()['data']['items']
                                checks['deadline_synced'] = any(item['due_date'] == '2026-10-25' and '初稿' in item['title'] for item in scheduled)
                                checks['pool_synced'] = any('尺码' in item['title'] for item in pool)
                            if kind == 'image':
                                checks['source_image_retained'] = record['source_image'].startswith('data:image/png;base64,')
                                checks['transcript_retained'] = bool(record['source_transcript'].strip())
                                entry['transcript'] = record['source_transcript']
                            entry['checks'] = checks
                            entry['passed'] = all(checks.values())
                        else:
                            entry['passed'] = False
                        measurements.append(entry)
                        print(json.dumps({k:v for k,v in entry.items() if k not in ('result','transcript')},ensure_ascii=False),flush=True)
    return measurements


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case', dest='case_ids', action='append', choices=['normal','missing','correction','approximate','ambiguous','roles','deadline'], help='Only run selected cases; repeat to select several')
    args = parser.parse_args()
    results = run(args.images, args.case_ids)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)
