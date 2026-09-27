"""Offline tests for both Phase 5 providers and the retrieval-to-LLM handoff."""

import json
import os
import unittest
from unittest.mock import patch

from src.llm_engine import LLMServiceError, RAGChatService, generate_answer


class FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.raw


class FakeRetriever:
    def __init__(self, result):
        self.result = result
        self.context_items = None

    def retrieve(self, query, mode, top_k):
        return self.result

    def build_augmented_context(self, query, ranked_items, graph_context, selected_mode):
        self.context_items = ranked_items
        return ("ข้อมูลคู่มือ: " + ", ".join(item["title"] for item in ranked_items), [])


class Phase5Tests(unittest.TestCase):
    def test_local_ollama_payload_and_usage(self):
        response = FakeResponse({
            "message": {"content": "คำตอบจากคู่มือ"},
            "prompt_eval_count": 42,
            "eval_count": 12,
        })
        with patch("src.llm_engine.urlopen", return_value=response) as send:
            with patch.dict(os.environ, {"OLLAMA_MODEL": "qwen2.5:3b"}):
                result = generate_answer([{"role": "user", "content": "ทดสอบ"}], "local")
        request = send.call_args.args[0]
        body = json.loads(request.data)
        self.assertTrue(request.full_url.endswith("/api/chat"))
        self.assertEqual(body["model"], "qwen2.5:3b")
        self.assertFalse(body["stream"])
        self.assertEqual(result["answer"], "คำตอบจากคู่มือ")
        self.assertEqual(result["usage"]["prompt_tokens"], 42)

    def test_openrouter_key_and_payload(self):
        response = FakeResponse({
            "choices": [{"message": {"content": "คำตอบ API"}}],
            "usage": {"total_tokens": 33},
        })
        with patch("src.llm_engine.urlopen", return_value=response) as send:
            with patch.dict(os.environ, {
                "OPENROUTER_API_KEY": "test-only-key",
                "OPENROUTER_MODEL": "openai/gpt-oss-20b:free",
            }):
                result = generate_answer([{"role": "user", "content": "ทดสอบ"}], "openrouter")
        request = send.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only-key")
        self.assertEqual(json.loads(request.data)["model"], "openai/gpt-oss-20b:free")
        self.assertEqual(result["answer"], "คำตอบ API")
        self.assertEqual(result["usage"]["total_tokens"], 33)

    def test_openrouter_without_key_fails_before_network(self):
        with patch("src.llm_engine.urlopen") as send:
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
                with self.assertRaisesRegex(LLMServiceError, "OPENROUTER_API_KEY"):
                    generate_answer([{"role": "user", "content": "ทดสอบ"}], "openrouter")
        send.assert_not_called()

    def test_avoided_exercise_is_removed_before_llm(self):
        retriever = FakeRetriever({
            "selected_mode": "hybrid",
            "total_latency_ms": 25,
            "graph_summary": "ห้ามท่าอันตราย",
            "avoid_exercises": [{"exercise": "ท่าอันตราย", "condition": "ปวดเข่า"}],
            "ranked_items": [
                {"title": "ท่าอันตราย", "page_number": 1, "safety_status": "AVOID_CONTRAINDICATION"},
                {"title": "ท่าปลอดภัย", "page_number": 2, "safety_status": "SAFE"},
            ],
        })
        with patch("src.llm_engine.generate_answer", return_value={
            "answer": "ลองท่าปลอดภัย (หน้า 2)", "model": "qwen2.5:3b", "usage": {}
        }) as generate:
            result = RAGChatService(retriever).answer("ปวดเข่าเล่นอะไร", provider="local")
        self.assertEqual([item["title"] for item in retriever.context_items], ["ท่าปลอดภัย"])
        self.assertEqual(result["sources"], [{"title": "ท่าปลอดภัย", "page": 2, "image_path": None}])
        self.assertIn("ท่าปลอดภัย", generate.call_args.args[0][1]["content"])
        self.assertIn("ปรึกษาแพทย์", result["answer"])

    def test_no_evidence_does_not_call_llm(self):
        retriever = FakeRetriever({
            "selected_mode": "hybrid", "total_latency_ms": 12,
            "graph_summary": "", "avoid_exercises": [], "ranked_items": [],
        })
        with patch("src.llm_engine.generate_answer") as generate:
            result = RAGChatService(retriever).answer("คำถามที่ไม่มีข้อมูล")
        generate.assert_not_called()
        self.assertIn("ไม่พบข้อมูล", result["answer"])


if __name__ == "__main__":
    unittest.main()
