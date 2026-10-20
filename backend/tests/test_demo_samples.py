import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo_samples
from analysis_models import AIOutput


ROOT = Path(__file__).resolve().parents[2]


class ReviewedDemoTests(unittest.TestCase):
    def setUp(self):
        self.text = (demo_samples.DATA / 'text-source.txt').read_text(encoding='utf-8')
        self.image = (ROOT / 'frontend/public/demo-sales-chat.png').read_bytes()

    def test_current_frontend_text_matches_and_preserves_all_23_rounds(self):
        source = (ROOT / 'frontend/src/components/ChatInput.vue').read_text(encoding='utf-8')
        self.assertEqual(re.search(r'const demoText = `([\s\S]*?)`', source).group(1), self.text)
        self.assertEqual(len(self.text.splitlines()), 46)

    def test_text_has_live_contract_and_corrected_customer_facts(self):
        for source in [self.text, demo_samples.CUSTOMER_PREFIX + self.text]:
            result = demo_samples.get_demo_analysis(source)['result']
            AIOutput.model_validate(result)
            self.assertEqual(len(result), 7)
            self.assertNotIn('is_sample', result)
            requirements = {item['field']: item['value'] for item in result['requirements']}
            self.assertEqual(requirements['采购数量'], '150件')
            self.assertEqual(requirements['预算上限'], '6000元')
            self.assertTrue(result['ddl_tasks'])
            self.assertTrue(result['questions'])
            self.assertTrue(result['suggested_tasks'])

    def test_text_changes_and_mixed_inputs_do_not_match(self):
        for text in [self.text + ' ', self.text.replace('150件', '200件'),
                     '客户名称：另一客户\n' + self.text, '\n' + self.text]:
            self.assertIsNone(demo_samples.get_demo_analysis(text))
        self.assertIsNone(demo_samples.get_demo_analysis(self.text, self.image, 'image/png'))

    def test_image_exact_match_only_and_dates_are_inferred_with_questions(self):
        with patch.object(demo_samples, '_reference_date', return_value=date(2026, 12, 31)):
            value = demo_samples.get_demo_analysis('', self.image, 'image/png')
            result = value['result']
            AIOutput.model_validate(result)
            self.assertEqual(result['ddl_tasks'][0]['ddl_date'], '2027-01-01')
            self.assertEqual(result['ddl_tasks'][1]['ddl_date'], '2027-11-20')
            self.assertIn('10月19日', result['questions'][0]['initial_guess'])
            self.assertEqual({q['related_ddl_index'] for q in result['questions']
                              if q['related_ddl_index'] is not None}, {0, 1})
            self.assertIn('客户：', value['transcript'])
        self.assertIsNotNone(demo_samples.get_demo_analysis(demo_samples.CUSTOMER_PREFIX, self.image, 'image/png'))
        for text, image, mime in [('', self.image + b'x', 'image/png'),
                                  ('', self.image, 'image/jpeg'),
                                  ('新增信息', self.image, 'image/png'),
                                  ('客户名称：其他客户\n', self.image, 'image/png')]:
            self.assertIsNone(demo_samples.get_demo_analysis(text, image, mime))

    def test_return_values_do_not_share_mutable_user_state(self):
        first = demo_samples.get_demo_analysis(self.text)
        first['result']['tasks'].append('用户修改')
        self.assertEqual(demo_samples.get_demo_analysis(self.text)['result']['tasks'], [])

    def test_fixtures_have_no_runtime_secrets_or_customer_details(self):
        for name in ['text-result.json', 'image-result.json']:
            result = json.loads((demo_samples.DATA / name).read_text(encoding='utf-8'))
            self.assertEqual(result['customer_profile']['display_name'], '未知')
            self.assertEqual(result['customer_profile']['company'], '未知')


if __name__ == '__main__':
    unittest.main()
