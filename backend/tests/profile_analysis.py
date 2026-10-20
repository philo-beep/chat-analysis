"""Opt-in profiling only: temporary timers, synthetic fixtures, isolated database.

No production imports this file. Model/settings/schema/retry/transactions unchanged.
Run: python -B backend/tests/profile_analysis.py text|image --limit 90
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
import functools
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
STACK = ContextVar('profiling_stack', default=())


class Trace:
    def __init__(self, target):
        self.target = target
        self.start = time.perf_counter()
        self.active = False
        self.lock = threading.RLock()
        self.spans = []
        self.metadata = {}
        self.events = target.with_suffix('.jsonl')
        self.events.write_text('', encoding='utf-8')

    def emit(self, event):
        with self.events.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + '\n')

    @contextmanager
    def span(self, name, **metadata):
        if not self.active:
            yield
            return
        stack = STACK.get()
        with self.lock:
            item = dict(id=len(self.spans)+1, parent=stack[-1] if stack else None,
                        phase=name, start_ms=(time.perf_counter()-self.start)*1000, **metadata)
            self.spans.append(item)
            self.emit(dict(event='start', **item))
        token = STACK.set((*stack, item['id']))
        try:
            yield
        except BaseException as exc:
            item['error_type'] = type(exc).__name__
            raise
        finally:
            with self.lock:
                item['duration_ms'] = (time.perf_counter()-self.start)*1000-item['start_ms']
                self.emit(dict(event='end', **item))
            STACK.reset(token)

    def save(self, **extra):
        with self.lock:
            elapsed = (time.perf_counter()-self.start)*1000
            spans = [dict(item) for item in self.spans]
            groups = defaultdict(lambda: dict(calls=0, duration_ms=0, exclusive_ms=0, unfinished=0))
            for item in spans:
                duration = item.get('duration_ms', elapsed-item['start_ms'])
                children = sum(child.get('duration_ms', elapsed-child['start_ms'])
                               for child in spans if child['parent'] == item['id'])
                group = groups[item['phase']]
                group['calls'] += 1
                group['duration_ms'] += duration
                group['exclusive_ms'] += max(0, duration-children)
                group['unfinished'] += 'duration_ms' not in item
            report = dict(self.metadata, **extra, elapsed_ms=round(elapsed, 3),
                          timings={key:{k:round(v,3) if isinstance(v,float) else v for k,v in value.items()}
                                   for key,value in groups.items()}, spans=spans)
            self.target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            return report


def install(trace):
    import ai_service
    import calendar_store
    import database
    import main
    import profile_store
    from analysis_models import AIOutput, CustomerIdentity, CustomerProfile
    from starlette.requests import Request

    def sync(obj, attribute, name):
        original = getattr(obj, attribute)
        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            with trace.span(name):
                return original(*args, **kwargs)
        setattr(obj, attribute, wrapped)

    def asynchronous(obj, attribute, name):
        original = getattr(obj, attribute)
        @functools.wraps(original)
        async def wrapped(*args, **kwargs):
            with trace.span(name):
                return await original(*args, **kwargs)
        setattr(obj, attribute, wrapped)
        return wrapped

    for obj, attr, name in [
        (main, 'normalize_analyze_request', 'request.normalize'),
        (main, 'validate_image', 'image.local_validate'),
        (main, '_analyze_and_save', 'analysis_and_save'),
        (ai_service, 'load_settings', 'ai.settings'),
        (ai_service, '_transcribe', 'image.transcription_pipeline'),
        (ai_service, '_analyze', 'ai.analysis_pipeline'),
        (ai_service, '_identify_customer', 'ai.identity_pipeline'),
        (ai_service, '_json', 'ai.json_parse'),
        (ai_service, 'validate_result', 'ai.source_validation'),
        (profile_store, 'context_for_identity', 'database.profile_lookup'),
        (database, 'save_record', 'database.transaction_total'),
        (profile_store, 'save_snapshot', 'database.profile_and_snapshot'),
        (calendar_store, 'sync_record_tasks', 'database.calendar_sync'),
        (urllib.request.OpenerDirector, 'open', 'cloud.wait_response_headers'),
        (http.client.HTTPResponse, 'read', 'cloud.read_response_body'),
    ]:
        sync(obj, attr, name)
    asynchronous(Request, 'json', 'request.parse_json')
    asynchronous(Request, '_get_form', 'request.parse_multipart')
    original_stream = Request.stream
    async def stream(request):
        with trace.span('request.body_receive'):
            async for chunk in original_stream(request):
                yield chunk
    Request.stream = stream
    endpoint = asynchronous(main, 'analyze', 'request.handler')
    for route in main.app.routes:
        if getattr(route, 'path', '') == '/analyze':
            route.dependant.call = endpoint
    import auth
    original_user = auth.require_user
    @functools.wraps(original_user)
    def user(*args, **kwargs):
        with trace.span('request.authentication'):
            return original_user(*args, **kwargs)
    def dependency_timers(dependency):
        if dependency.call is original_user:
            dependency.call = user
        for child in dependency.dependencies:
            dependency_timers(child)
    for route in main.app.routes:
        if hasattr(route, 'dependant'):
            dependency_timers(route.dependant)

    for model, name in [(main.AnalyzeRequest,'request.schema_validation'), (AIOutput,'ai.schema_validation'),
                        (main.ResultModel,'result.schema_validation'), (CustomerIdentity,'ai.identity_validation'),
                        (CustomerProfile,'ai.previous_profile_validation')]:
        original = model.model_validate
        def validation(cls, *args, _original=original, _name=name, **kwargs):
            with trace.span(_name):
                return _original(*args, **kwargs)
        model.model_validate = classmethod(validation)
    original_schema = AIOutput.response_schema
    def schema(cls):
        with trace.span('ai.schema_prepare'):
            return original_schema()
    AIOutput.response_schema = classmethod(schema)
    original_read = Path.read_text
    def read_text(path, *args, **kwargs):
        if path == ai_service.ROOT / 'prompts' / 'analysis.txt':
            with trace.span('ai.prompt_load'):
                result = original_read(path, *args, **kwargs)
                trace.metadata['analysis_prompt_chars'] = len(result)
                return result
        return original_read(path, *args, **kwargs)
    Path.read_text = read_text

    original_complete = ai_service.ChatCompletionsClient.complete
    def complete(client, system, content, schema=None):
        name = ('identity' if schema and schema['name'] == 'keyoushu_customer_identity' else
                'review' if '独立复核：' in system else 'analysis' if schema else 'transcription')
        with trace.span('cloud.' + name, system_chars=len(system),
                        input_chars=sum(len(block.get('text','')) for block in content),
                        image_bytes_base64=sum(len(block.get('source',{}).get('data','')) for block in content)):
            return original_complete(client, system, content, schema=schema)
    ai_service.ChatCompletionsClient.complete = complete
    original_response = ai_service.ChatCompletionsClient._response
    def response(client, body):
        with trace.span('ai.provider_response_validate'):
            usage = body.get('usage') if isinstance(body, dict) else None
            if isinstance(usage, dict) and trace.active:
                trace.metadata.setdefault('token_usage', []).append({key:value for key,value in usage.items()
                    if key in ('prompt_tokens','completion_tokens','total_tokens') and isinstance(value, int)})
            return original_response(client, body)
    ai_service.ChatCompletionsClient._response = response


def worker(args):
    import ai_service
    import auth_store
    import database
    import main
    from fastapi.testclient import TestClient
    from PIL import Image

    target = Path(args.output)
    trace = Trace(target)
    settings = ai_service.load_settings()
    if args.dry_run:
        def stub(client, system, content, schema=None):
            if schema and schema['name']=='keyoushu_customer_identity':
                return json.dumps(dict(display_name='未知',company='未知',name_quote='',company_quote=''))
            if not schema:
                return json.dumps({'transcript':'客户：我们需要150件文化衫。'},ensure_ascii=False)
            from analysis_models import CustomerProfile
            profile=dict(display_name='未知',company='未知',role='未知',industry='未知',concerns=[],
                decision_style='未知',communication_preferences=[],risk_points=[],next_follow_up='未知')
            return json.dumps(dict(requirements=[],questions=[],tasks=[],reply='',ddl_tasks=[],suggested_tasks=[],
                customer_profile=CustomerProfile.model_validate(profile).model_dump()),ensure_ascii=False)
        ai_service.ChatCompletionsClient.complete=stub
    component = (ROOT/'frontend/src/components/ChatInput.vue').read_text(encoding='utf-8')
    text = component.split('const demoText = `',1)[1].split('`',1)[0]
    image_path = ROOT/'frontend/public/demo-sales-chat.png'
    image = image_path.read_bytes()
    trace.metadata = dict(scenario=args.scenario, dry_run=args.dry_run, limit_seconds=args.limit, model=settings.model,
        reasoning_effort=settings.reasoning_effort, quality_review=settings.quality_review,
        fixture='current built-in demo, synthetic data, real cloud, temporary database',
        measured_scope='TestClient -> real /analyze -> full response; excludes browser rendering',
        text_chars=len(text), text_messages=len(text.splitlines()),
        image_bytes=len(image), image_dimensions=list(Image.open(image_path).size),
        input_sha256=hashlib.sha256(text.encode() if args.scenario=='text' else image).hexdigest())
    install(trace)
    def deadline():
        report = trace.save(status='deadline_exceeded', complete=False)
        print(json.dumps(dict(status='deadline_exceeded', elapsed_ms=report['elapsed_ms'],
                              active_phases=[span['phase'] for span in report['spans'] if 'duration_ms' not in span])), flush=True)
        os._exit(124)
    with tempfile.TemporaryDirectory(prefix='keyoushu-profile-') as folder, patch.object(
            database,'DB_PATH',Path(folder)/'test.db'), patch.dict(os.environ,{
                'KEYOUSHU_JWT_SECRET':'isolated-analysis-profiling-secret-2026'}), TestClient(main.app, raise_server_exceptions=False) as client:
        user=auth_store.create_user('profile_synthetic','Profiling-synthetic-2026',['member'])
        login = client.post('/api/auth/login',json={'username':'profile_synthetic','password':'Profiling-synthetic-2026'})
        client.headers['Authorization']='Bearer '+login.json()['data']['token']
        trace.start=time.perf_counter()
        trace.active=True
        timer=threading.Timer(args.limit,deadline)
        timer.daemon=True
        timer.start()
        print('START '+args.scenario,flush=True)
        try:
            with trace.span('request.total'):
                if args.scenario=='text':
                    response=client.post('/analyze',json={'text':'客户名称：演示客户\n'+text})
                else:
                    response=client.post('/analyze',data={'text':'客户名称：演示客户\n'},
                        files={'image':('demo-sales-chat.png',image,'image/png')})
            trace.active=False
            report=trace.save(status=response.status_code,complete=True,
                result_keys=list(response.json()),
                saved_records=len(database.list_records(owner_id=user['id'],include_all=False)))
            print(json.dumps(dict(status=report['status'],elapsed_ms=report['elapsed_ms'],timings=report['timings']),ensure_ascii=False),flush=True)
        finally:
            timer.cancel()


def main_entry():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario',choices=['text','image'])
    parser.add_argument('--limit',type=int,default=90)
    parser.add_argument('--output')
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--dry-run',action='store_true',help='Instrumentation sanity check; no cloud calls')
    args=parser.parse_args()
    target=Path(args.output) if args.output else ROOT/'docs/evidence/profiling'/('baseline-'+args.scenario+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    args.output=str(target)
    if args.worker:
        worker(args)
    else:
        command=[sys.executable,'-B','-u',__file__,args.scenario,'--worker','--limit',str(args.limit),'--output',str(target)]
        if args.dry_run:
            command.append('--dry-run')
        try:
            result=subprocess.run(command,timeout=args.limit+15)
        except subprocess.TimeoutExpired:
            print('STOP: worker exceeded setup plus request time budget',flush=True)
            sys.exit(124)
        sys.exit(result.returncode)


if __name__=='__main__':
    main_entry()
