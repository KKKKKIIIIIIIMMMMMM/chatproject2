"""Offline LINE webhook tests: no API calls or model downloads."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.line_webhook import (
    LineBot,
    WebhookHandler,
    format_answer,
    limit_line_text,
    text_events,
    valid_signature,
)


SECRET = "test-channel-secret"


def signed(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


class LineWebhookTests(unittest.TestCase):
    def test_signature_uses_original_bytes(self) -> None:
        body = b'{"events":[]}'
        self.assertTrue(valid_signature(body, signed(body), SECRET))
        self.assertFalse(valid_signature(body + b" ", signed(body), SECRET))
        self.assertFalse(valid_signature(body, "wrong", SECRET))

    def test_extracts_only_text_events(self) -> None:
        payload = {"events": [
            {"type": "message", "webhookEventId": "e1", "replyToken": "r1",
             "message": {"type": "text", "text": " วิธีเล่น Bike "}},
            {"type": "message", "replyToken": "r2", "message": {"type": "image"}},
        ]}
        self.assertEqual(text_events(payload), [{
            "reply_token": "r1", "question": "วิธีเล่น Bike", "replay_key": "e1"
        }])

    def test_format_answer_includes_sources_and_respects_utf16_limit(self) -> None:
        answer = format_answer({
            "answer": "เริ่มจากปรับเบาะ",
            "sources": [{"title": "จักรยาน", "page": 6}, {"title": "จักรยาน", "page": 6}],
        })
        self.assertIn("จักรยาน (หน้า 6)", answer)
        self.assertEqual(answer.count("จักรยาน (หน้า 6)"), 1)
        shortened = limit_line_text("😀" * 2600)
        self.assertLessEqual(len(shortened.encode("utf-16-le")) // 2, 5000)
        self.assertTrue(shortened.endswith("…"))

    def test_duplicate_event_is_answered_once(self) -> None:
        replies = []

        class FakeService:
            def answer(self, query: str, **_kwargs: object) -> dict:
                return {"answer": f"ตอบ {query}", "sources": []}

        bot = LineBot(SECRET, "test-access-token", service_factory=FakeService,
                      reply_sender=lambda *_args: replies.append(_args))
        event = {"reply_token": "r1", "question": "วิธีเล่น Bike", "replay_key": "e1"}
        try:
            self.assertTrue(bot.enqueue([event]))
            self.assertTrue(bot.enqueue([event]))
        finally:
            bot.close()
        self.assertEqual(len(replies), 1)
        self.assertIn("วิธีเล่น Bike", replies[0][2])

    def test_http_verify_empty_events_and_reject_bad_signature(self) -> None:
        class FakeBot:
            channel_secret = SECRET
            received: list = []

            def enqueue(self, events: list) -> bool:
                self.received.append(events)
                return True

        bot = FakeBot()
        WebhookHandler.bot = bot  # type: ignore[assignment]
        server = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"events": []}).encode()
            url = f"http://127.0.0.1:{server.server_port}/webhook"
            request = Request(url, data=body, method="POST", headers={
                "Content-Type": "application/json", "x-line-signature": signed(body)
            })
            with urlopen(request, timeout=3) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(bot.received, [[]])

            request = Request(url, data=body, method="POST", headers={
                "Content-Type": "application/json", "x-line-signature": "invalid"
            })
            with self.assertRaises(HTTPError) as failure:
                urlopen(request, timeout=3)
            self.assertEqual(failure.exception.code, 401)
            failure.exception.close()
            self.assertEqual(bot.received, [[]])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
