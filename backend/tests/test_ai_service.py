"""Offline model/adapter regression tests; vision transport is isolated with mocks."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import ai_service
from ai_contract import AnalysisOutcome
from followup_engine import adapter


class AnalysisTests(unittest.TestCase):
    def analyze(self, text):
        result = ai_service.analyze_chat(text)
        self.assertEqual(set(result), {"requirements", "questions", "tasks", "reply", "is_sample"})
        self.assertIs(result["is_sample"], False)
        for item in result["requirements"]:
            self.assertIn(item["evidence"], text)
            self.assertEqual(set(item), {"field", "value", "evidence"})
        return result, {item["field"]: item["value"] for item in result["requirements"]}

    def test_normal_year_not_invented(self):
        result, facts = self.analyze("我们想定制100件文化衫，总预算3000元，10月30日前收到，需要你们提供设计。")
        self.assertEqual(facts["数量"], "100件")
        self.assertEqual(facts["预算"], "3000元")
        self.assertEqual(facts["交付时间"], "10月30日前")
        self.assertIn("设计", facts)
        self.assertTrue(any("年份" in q for q in result["questions"]))

    def test_missing_facts(self):
        result, facts = self.analyze("想给公司做一批文化衫，能介绍一下吗？")
        self.assertNotIn("数量", facts)
        self.assertNotIn("预算", facts)
        self.assertNotIn("交付时间", facts)
        for word in ("数量", "预算", "收货时间"):
            self.assertTrue(any(word in q for q in result["questions"]))

    def test_corrections_with_unseen_values(self):
        for first, last in ((100, 150), (68, 237), (730, 820)):
            with self.subTest(last=last):
                result, facts = self.analyze(f"客户张三：先做{first}件。\n客户张三：数量改成{last}件，其他后面说。")
                self.assertEqual(facts["数量"], f"{last}件")
                self.assertTrue(any(f"改成{last}" in r["evidence"] for r in result["requirements"]))

    def test_approximate_and_range(self):
        result, facts = self.analyze("大概100件，预算三四千，时间还没定。")
        self.assertEqual(facts["数量"], "约100件")
        self.assertEqual(facts["预算"], "3000-4000元")
        self.assertNotIn("交付时间", facts)
        _, facts_with_unit = self.analyze("客户：预算三四千元。")
        self.assertEqual(facts_with_unit["预算"], "3000-4000元")

    def test_conflict_not_latest_wins(self):
        for first, other in ((3000, 5000), (4600, 9200)):
            result, facts = self.analyze(f"甲方：总预算{first}元。\n乙方：推荐10000元。\n甲方：我记得之前说的是{other}元吧。")
            self.assertIn(str(first), facts["预算"])
            self.assertIn(str(other), facts["预算"])
            self.assertIn("待确认", facts["预算"])
            self.assertNotIn("10000", facts["预算"])
            self.assertTrue(any("最终预算" in q for q in result["questions"]))

    def test_clear_budget_change(self):
        _, facts = self.analyze("客户：总预算4600元。\n客户：总预算改为7200元。")
        self.assertEqual(facts["预算"], "7200元")

    def test_roles_unit_budget_relative_time(self):
        text = (BACKEND.parent / "samples/chat-001.txt").read_text(encoding="utf-8")
        result, facts = self.analyze(text)
        self.assertEqual(facts["数量"], "150件")
        self.assertEqual(facts["面料"], "纯棉")
        self.assertEqual(facts["单价预算"], "40元左右")
        self.assertNotIn("预算", facts)
        self.assertEqual(facts["交付时间"], "下周")
        self.assertTrue(any("具体收货日期" in q for q in result["questions"]))

    def test_seller_is_not_customer(self):
        _, facts = self.analyze("[客户(张三)] 需要237件纯棉文化衫，每件45元左右。\n[商家(李四)] 总预算9999元，明天可以发货，建议涤棉。")
        self.assertEqual(facts["数量"], "237件")
        self.assertEqual(facts["面料"], "纯棉")
        self.assertEqual(facts["单价预算"], "45元左右")
        self.assertNotIn("预算", facts)
        self.assertNotIn("交付时间", facts)

    def test_unit_price_does_not_create_quantity(self):
        _, facts = self.analyze("客户：预算40左右一件。")
        self.assertNotIn("数量", facts)

    def test_negative_quantity_and_design(self):
        result, facts = self.analyze("客户：不要100件，先不做。\n客户：不需要商家提供设计，我提供设计稿。")
        self.assertNotIn("数量", facts)
        self.assertEqual(facts["设计"], "客户提供设计稿")
        self.assertFalse(any("准备初步设计" in task for task in result["tasks"]))

    def test_question_is_not_confirmed_quantity(self):
        result, facts = self.analyze("客户：做237件可以吗？")
        self.assertIn("待确认", facts["数量"])
        self.assertTrue(any("最终数量" in q for q in result["questions"]))

    def test_unknown_speaker_is_not_customer(self):
        result, facts = self.analyze("张三：做237件，总预算9000元。\n商家：明天能交货。")
        self.assertEqual(facts, {})
        self.assertTrue(any("角色" in q for q in result["questions"]))

    def test_numeric_ranges_are_not_single_values(self):
        for low, high, budget_low, budget_high in ((270, 330, 6500, 8500), (120, 180, 4200, 5700)):
            _, facts = self.analyze(f"客户：想订{low}到{high}件文化衫，预算{budget_low}至{budget_high}元。")
            self.assertEqual(facts["数量"], f"{low}-{high}件")
            self.assertEqual(facts["预算"], f"{budget_low}-{budget_high}元")

    def test_shipping_and_deposit_are_not_budget(self):
        result, facts = self.analyze("客户：一件衣服的运费是12元，之前付了600元定金，现在需要180件。")
        self.assertEqual(facts["数量"], "180件")
        self.assertNotIn("预算", facts)
        self.assertNotIn("单价预算", facts)
        self.assertTrue(any("预算" in q for q in result["questions"]))

    def test_customer_supplies_design_no_merchant_design_task(self):
        for text in ("我们自己提供设计稿，不需要你们设计", "我们会提供设计稿", "设计我来提供，你们不用设计"):
            with self.subTest(text=text):
                result, facts = self.analyze("客户：" + text)
                self.assertEqual(facts["设计"], "客户提供设计稿")
                self.assertFalse(any("准备初步设计" in task for task in result["tasks"]))

    def test_negative_category(self):
        _, facts = self.analyze("客户：不要文化衫，想要卫衣。")
        self.assertEqual(facts["品类"], "卫衣")

    def test_previous_order_not_current_facts(self):
        result, facts = self.analyze("客户：我们2025年9月15日订过150件，这次还没定数量和交期。")
        self.assertNotIn("数量", facts)
        self.assertNotIn("交付时间", facts)
        self.assertTrue(any("数量" in q for q in result["questions"]))

    def test_quote_is_not_customer_budget(self):
        result, facts = self.analyze("客户：单价报价45元，我们预算还没定。")
        self.assertNotIn("单价预算", facts)
        self.assertNotIn("预算", facts)
        self.assertTrue(any("预算" in q for q in result["questions"]))

    def test_screenshot_title_is_not_customer_evidence(self):
        result, _ = self.analyze("文化衫定制聊天\n甲方：需要180件卫衣。\n乙方：可以介绍文化衫。")
        category = next(r for r in result["requirements"] if r["field"] == "品类")
        self.assertEqual(category["value"], "卫衣")
        self.assertEqual(category["evidence"], "需要180件卫衣")

    def test_original_classifier_is_called(self):
        with patch.object(adapter, "classify", wraps=adapter.classify) as classifier:
            self.analyze("客户：咨询文化衫定制报价。")
        classifier.assert_called_once()
        self.assertTrue(classifier.call_args.args[1]["classes"])

    def test_config_read_after_import_and_missing_model_fails(self):
        with patch.dict(os.environ, {"FOLLOWUP_MODEL_PATH": str(BACKEND / "missing-model.json")}):
            with self.assertRaises(FileNotFoundError):
                ai_service.analyze_chat("客户：需要100件文化衫")

    def test_empty_input_fails(self):
        with self.assertRaises(ValueError):
            ai_service.analyze_chat(" ")


class VisionTests(unittest.TestCase):
    def response(self, transcript):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({"message": {"content": json.dumps({"transcript": transcript})}}).encode()
        return Response()

    def test_combines_transcript_but_returns_only_transcript(self):
        transcript = "甲方：数量改成237件。\n乙方：总预算9999元。"
        with patch.object(ai_service, "_open_ollama", return_value=self.response(transcript)) as transport:
            outcome = ai_service.analyze_chat_with_source("客户：先做100件。", b"image", "image/png")
        self.assertIsInstance(outcome, AnalysisOutcome)
        self.assertEqual(outcome.source_text, transcript)
        facts = {r["field"]: r["value"] for r in outcome.result["requirements"]}
        self.assertEqual(facts["数量"], "237件")
        self.assertNotIn("预算", facts)
        self.assertEqual(transport.call_args.kwargs["timeout"], 600)
        payload = json.loads(transport.call_args.args[0].data)
        self.assertEqual(payload["model"], "qwen2.5vl:7b")
        self.assertNotIn("先做100件", payload["messages"][0]["content"])

    def test_vision_failure_never_falls_back(self):
        with patch.object(ai_service, "_open_ollama", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                ai_service.analyze_chat_with_source("客户：100件", b"image", "image/png")

    def test_blank_and_malformed_transcripts_fail(self):
        for value in ("", None, []):
            with self.subTest(value=value), patch.object(ai_service, "_open_ollama", return_value=self.response(value)):
                with self.assertRaises(ValueError):
                    ai_service.analyze_chat_with_source("", b"image", "image/png")

    def test_remote_endpoint_rejected(self):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "https://example.com"}):
            with self.assertRaises(ValueError):
                ai_service._transcribe(b"image", "image/png")

    def test_cloud_model_rejected(self):
        for name in ("qwen3-vl:cloud", "qwen3-vl-cloud", "cloud-model"):
            with self.subTest(name=name), patch.dict(os.environ, {"OLLAMA_VISION_MODEL": name}):
                with self.assertRaises(ValueError):
                    ai_service._transcribe(b"image", "image/png")

    def test_truncated_response_rejected(self):
        response = self.response("客户：100件")
        response.read = lambda: json.dumps({"done_reason": "length", "message": {"content": '{"transcript":"客户：100件"}'}}).encode()
        with patch.object(ai_service, "_open_ollama", return_value=response):
            with self.assertRaises(ValueError):
                ai_service._transcribe(b"image", "image/png")

    def test_lock_wait_is_bounded(self):
        with patch.object(ai_service, "_vision_lock") as lock, patch.dict(os.environ, {"OLLAMA_TIMEOUT": "0.01"}):
            lock.acquire.return_value = False
            with self.assertRaises(TimeoutError):
                ai_service._transcribe(b"image", "image/png")
            lock.acquire.assert_called_once_with(timeout=0.01)

    def test_transport_disables_proxies_and_redirects(self):
        with patch.object(ai_service.urllib.request, "build_opener") as build:
            ai_service._open_ollama("request", timeout=5)
        self.assertEqual(build.call_args.args[0].proxies, {})
        with self.assertRaises(ValueError):
            ai_service._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.com")

    def test_unknown_screenshot_roles_require_confirmation(self):
        with patch.object(ai_service, "_transcribe", return_value="未确认角色：需要500件，总预算20000元。"):
            result = ai_service.analyze_chat_with_source("", b"image", "image/png").result
        self.assertEqual(result["requirements"], [])
        self.assertTrue(any("角色" in q for q in result["questions"]))


if __name__ == "__main__":
    unittest.main()

