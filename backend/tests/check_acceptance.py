"""Explicit real-model acceptance run; does not run during unittest discovery.

Use --images for actual local Qwen calls. Results are measured, never fixture outputs.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import database
import main
from fastapi.testclient import TestClient


def criteria(case_id, result):
    facts = result['requirements']
    def values(field):
        return ' '.join(r['value'] for r in facts if field in r['field']).replace(' ', '')
    all_values = ' '.join(r['value'] for r in facts).replace(' ', '')
    questions = ' '.join(result['questions'])
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
                      budget_range='3000' in values('预算') and '4000' in values('预算'),
                      date_pending=any(k in questions for k in ['时间','日期','交期']))
    elif case_id == 'ambiguous':
        checks.update(budget_pending='3000' in questions and '5000' in questions,
                      no_final_budget=not any('预算' in r['field'] and not any(k in r['value'] for k in ['待确认','歧义','未确认']) for r in facts))
    elif case_id == 'roles':
        checks.update(final_150='150' in values('数量') and '100' not in values('数量'),
                      cotton='纯棉' in all_values, unit_budget=any('40' in r['value'] and any(k in r['field']+r['value'] for k in ['单','每件','/件']) for r in facts),
                      relative_date='下周' in all_values, date_pending=any(k in questions for k in ['日期','时间']),
                      seller_not_fact=not any('初步方案' in r['value'] for r in facts))
    return checks


def run(images=False):
    root = BACKEND.parent
    cases = json.loads((root/'samples/acceptance-cases.json').read_text(encoding='utf-8'))
    measurements = []
    with tempfile.TemporaryDirectory(prefix='keyoushu-real-acceptance-') as temp:
        with patch.object(database, 'DB_PATH', Path(temp)/'acceptance.db'):
            with TestClient(main.app, raise_server_exceptions=False) as client:
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
    args = parser.parse_args()
    results = run(args.images)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)
