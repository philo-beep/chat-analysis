"""No network: private reuse, exact demo gate, review corrections and rollback."""
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
from pydantic import ValidationError
import ai_service
import analysis_cache
import auth_store
import database
import demo_samples
import main
import profile_store
from analysis_models import AIReview
from expanded_fixture import SOURCE, output, review_output

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = dict(display_name='林晓', company='云杉公司',name_quote='我是云杉公司的林晓', company_quote='我是云杉公司的林晓')


class ReviewTests(unittest.TestCase):
    def test_compact_review_preserves_unchanged_fields_and_applies_corrections(self):
        client=ai_service.ChatCompletionsClient(ai_service.Settings('test-key',quality_review=True))
        fixed_reply='请核对日期与数量。'
        with patch.object(client,'complete',side_effect=[json.dumps(output()),json.dumps(review_output(reply=fixed_reply))]) as calls:
            result=ai_service._analyze(SOURCE,client)
        self.assertEqual(result['reply'],fixed_reply)
        self.assertEqual(result['requirements'],output()['requirements'])
        self.assertEqual(calls.call_args.kwargs['schema']['name'],'keyoushu_sales_review')
        self.assertEqual(set(result)-{'is_sample'},set(output()))

    def test_review_can_clear_fields_and_final_constraints_still_reject_bad_links(self):
        AIReview.model_validate(review_output(tasks=[]))
        for candidate in (review_output(questions=[]),review_output(ddl_tasks=[])):
            client=ai_service.ChatCompletionsClient(ai_service.Settings('test-key',quality_review=True))
            with patch.object(client,'complete',side_effect=[json.dumps(output()),json.dumps(candidate),json.dumps(candidate)]):
                with self.assertRaises(ai_service.InvalidModelOutput):
                    ai_service._analyze(SOURCE,client)
        with self.assertRaises(ValidationError):
            AIReview.model_validate({**review_output(), 'approved':False})
        with self.assertRaises(ValidationError):
            AIReview.model_validate({**review_output(reply=''), 'approved':True})

    def test_bad_review_retries_only_review_not_the_valid_draft(self):
        client=ai_service.ChatCompletionsClient(ai_service.Settings('test-key',quality_review=True))
        with patch.object(client,'complete',side_effect=[json.dumps(output()),'not JSON',json.dumps(review_output())]) as calls:
            result=ai_service._analyze(SOURCE,client)
        self.assertEqual(calls.call_count,3)
        self.assertEqual([call.kwargs['schema']['name'] for call in calls.call_args_list],
                         ['keyoushu_sales_analysis','keyoushu_sales_review','keyoushu_sales_review'])
        self.assertEqual(result['requirements'],output()['requirements'])

    def test_no_prior_customer_skips_identity_but_resolves_validated_portrait(self):
        client=ai_service.ChatCompletionsClient(ai_service.Settings('test-key',quality_review=True))
        seen=[]
        def resolver(identity): seen.append(identity); return None
        resolver.has_profiles=False
        with patch.object(client,'complete',side_effect=[json.dumps(output()),json.dumps(review_output())]) as calls:
            result=ai_service._analyze(SOURCE,client,resolver)
        self.assertEqual(calls.call_count,2)
        self.assertEqual(seen[0]['display_name'],'林晓')
        self.assertIn(seen[0]['name_quote'],SOURCE)
        self.assertEqual(result['customer_profile'],output()['customer_profile'])

    def test_identity_input_excludes_seller_and_ui_name_and_repair_receives_reason(self):
        client=ai_service.ChatCompletionsClient(ai_service.Settings('test-key',quality_review=False))
        with patch.object(client,'complete',side_effect=['{}',json.dumps(IDENTITY)]) as calls:
            ai_service._identify_customer('客户名称：演示客户\n'+SOURCE,client)
        sent=json.loads(calls.call_args.args[1][0]['text'])['chat_text']
        self.assertNotIn('演示客户',sent)
        self.assertNotIn('商家：',sent)
        self.assertIn('上次识别未通过',calls.call_args.args[0])


class SpeedIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=self.enterContext(tempfile.TemporaryDirectory(prefix='keyoushu-speed-'))
        self.enterContext(patch.object(database,'DB_PATH',Path(temp)/'test.db'))
        self.enterContext(patch.dict(os.environ,{'KEYOUSHU_JWT_SECRET':'speed-integration-test-private-key-2026','FOLLOWUP_CACHE_ENABLED':'true'}))
        self.settings=ai_service.Settings('test-key',quality_review=False)
        self.enterContext(patch.object(ai_service,'load_settings',return_value=self.settings))
        analysis_cache.clear()
        self.addCleanup(analysis_cache.clear)
        self.client=self.enterContext(TestClient(main.app,raise_server_exceptions=False))
        self.user=auth_store.create_user('speed_owner','Speed-test-2026',['member'])
        self.other=auth_store.create_user('speed_other','Speed-test-2026',['member'])
        self.login('speed_owner')

    def login(self,name):
        reply=self.client.post('/api/auth/login',json={'username':name,'password':'Speed-test-2026'})
        self.client.headers['Authorization']='Bearer '+reply.json()['data']['token']

    def test_repeat_reuses_validated_output_and_creates_fresh_record_and_snapshot(self):
        with patch.object(ai_service.ChatCompletionsClient,'complete',return_value=json.dumps(output())) as calls:
            first=self.client.post('/analyze',json={'text':SOURCE})
            second=self.client.post('/analyze',json={'text':SOURCE})
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(calls.call_count,1)
        self.assertNotEqual(first.json()['id'],second.json()['id'])
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profile_snapshots').fetchone()[0],2)
        self.assertFalse(second.json()['is_sample'])
        self.assertNotIn('customer_profile',second.json())

    def test_cache_does_not_cross_accounts_and_input_or_profile_changes_invalidate(self):
        with patch.object(ai_service.ChatCompletionsClient,'complete',return_value=json.dumps(output())):
            self.assertEqual(self.client.post('/analyze',json={'text':SOURCE}).status_code,200)
        self.login('speed_other')
        with patch.object(ai_service.ChatCompletionsClient,'complete',return_value=json.dumps(output())) as calls:
            self.assertEqual(self.client.post('/analyze',json={'text':SOURCE}).status_code,200)
        self.assertEqual(calls.call_count,1)
        self.login('speed_owner')
        with database._connect() as conn:
            conn.execute('UPDATE customer_profiles SET version=version+1 WHERE owner_id=?',(self.user['id'],))
        with patch.object(ai_service.ChatCompletionsClient,'complete',side_effect=[json.dumps(IDENTITY),json.dumps(output())]) as calls:
            response=self.client.post('/analyze',json={'text':SOURCE})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(calls.call_count,2)
        with patch.object(ai_service.ChatCompletionsClient,'complete',side_effect=[json.dumps(IDENTITY),json.dumps(output())]) as calls:
            response=self.client.post('/analyze',json={'text':SOURCE+'\n商家：待确认。'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(calls.call_count,2)

    def test_demo_is_exact_opt_in_no_cloud_no_profile_with_saved_history(self):
        text=(demo_samples.DATA/'text-source.txt').read_text(encoding='utf-8')
        image=(ROOT/'frontend/public/demo-sales-chat.png').read_bytes()
        with patch.object(ai_service.ChatCompletionsClient,'complete',side_effect=AssertionError('demo called cloud')):
            first=self.client.post('/analyze',json={'text':demo_samples.CUSTOMER_PREFIX+text},headers={'X-Keyoushu-Demo':'1'})
            second=self.client.post('/analyze',data={'text':demo_samples.CUSTOMER_PREFIX.replace('\n','\r\n')},
                files={'image':('demo.png',image,'image/png')},headers={'X-Keyoushu-Demo':'1'})
        for response in (first,second):
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.json()['is_sample'])
            record=self.client.get('/records/'+str(response.json()['id'])).json()
            self.assertTrue(record['result']['is_sample'])
            self.assertTrue(record['result']['ddl_tasks'])
        self.assertTrue(self.client.get('/records/'+str(second.json()['id'])).json()['source_transcript'])
        with database._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profiles').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM customer_profile_snapshots').fetchone()[0],0)
        raw=first.json()
        action=self.client.post('/api/records/'+str(raw['id'])+'/actions',json={'action':'add_ddl_task','index':0,'expected_result':{k:v for k,v in raw.items() if k!='id'}})
        self.assertEqual(action.status_code,200,action.text)

    def test_modified_demo_or_missing_optin_uses_real_entry(self):
        text=(demo_samples.DATA/'text-source.txt').read_text(encoding='utf-8')
        fixture={'requirements':[],'questions':[],'tasks':[],'reply':'真实链路替身','is_sample':False}
        with patch.object(main,'analyze_chat',return_value=fixture) as calls:
            for source,headers in [(text,{}),(text+' ',{'X-Keyoushu-Demo':'1'}),
                                    (text.replace('150件','200件'),{'X-Keyoushu-Demo':'1'})]:
                response=self.client.post('/analyze',json={'text':source},headers=headers)
                self.assertEqual(response.status_code,200,response.text)
                self.assertFalse(response.json()['is_sample'])
        self.assertEqual(calls.call_count,3)

    def test_cache_copies_and_expiry_bound(self):
        value={'result':{'tasks':[]}}
        analysis_cache.put('private',value)
        value['result']['tasks'].append('changed')
        cached=analysis_cache.get('private')
        self.assertEqual(cached['result']['tasks'],[])
        cached['result']['tasks'].append('another change')
        self.assertEqual(analysis_cache.get('private')['result']['tasks'],[])
        with patch.object(analysis_cache,'TTL_SECONDS',-1):
            self.assertIsNone(analysis_cache.get('private'))


if __name__=='__main__': unittest.main()
