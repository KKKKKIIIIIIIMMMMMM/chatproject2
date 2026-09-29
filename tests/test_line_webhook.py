"""Offline LINE webhook tests: no API calls or model downloads."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from scripts.line_webhook import (
    LineBot,
    WebhookHandler,
    chat_events,
    contextual_followup,
    exercise_card,
    format_answer,
    limit_line_text,
    menu_message,
    text_events,
    valid_signature,
)
from src.line_catalog import ExerciseCatalog, GROUPS, SUBGROUPS, text_action, unsupported_topic
from src.line_chest import chest_intent, load_chest_exercises, safe_image_path


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

    def test_postback_events_are_explicitly_allowlisted(self) -> None:
        payload = {"events": [
            {"type": "postback", "webhookEventId": "p1", "replyToken": "r1",
             "postback": {"data": "chest:upper"}},
            {"type": "postback", "webhookEventId": "p2", "replyToken": "r3",
             "postback": {"data": "group:legs"}},
            {"type": "postback", "webhookEventId": "p3", "replyToken": "r4",
             "postback": {"data": "exercise:08_leg_extension"}},
            {"type": "postback", "replyToken": "r2", "postback": {"data": "admin:delete"}},
        ]}
        self.assertEqual(chat_events(payload), [
            {"reply_token": "r1", "action": "chest:upper", "replay_key": "p1"},
            {"reply_token": "r3", "action": "group:legs", "replay_key": "p2"},
            {"reply_token": "r4", "action": "exercise:08_leg_extension", "replay_key": "p3"},
        ])

    def test_conversation_keys_are_private_and_scoped(self) -> None:
        payload = {"events": [
            {"type": "message", "replyToken": "r1", "source": {"type": "user", "userId": "Ualice"},
             "message": {"type": "text", "text": "ท่านี้หายใจยังไง"}},
            {"type": "message", "replyToken": "r2", "source": {"type": "user", "userId": "Ubob"},
             "message": {"type": "text", "text": "ท่านี้หายใจยังไง"}},
            {"type": "message", "replyToken": "r3", "source": {"type": "group", "groupId": "G1", "userId": "Ualice"},
             "message": {"type": "text", "text": "ท่านี้หายใจยังไง"}},
            {"type": "message", "replyToken": "r4", "source": {"type": "group", "groupId": "G1"},
             "message": {"type": "text", "text": "ท่านี้หายใจยังไง"}},
        ]}
        events = chat_events(payload, SECRET)
        keys = [event.get("conversation_key") for event in events]
        self.assertEqual(len(set(keys[:3])), 3)
        self.assertTrue(all("Ualice" not in key for key in keys[:3]))
        self.assertNotIn("conversation_key", events[3])

    def test_short_context_resolves_last_exercise_without_chat_history(self) -> None:
        bot = LineBot(SECRET, "test-access-token", service_factory=lambda: None)
        try:
            with patch("scripts.line_webhook.generate_answer", return_value={"answer": "ตามคู่มือ"}) as generate, \
                 patch("scripts.line_webhook.public_base_url", return_value=None):
                bot._messages_for_event({"question": "วิธีเล่น Leg Extension", "conversation_key": "user-a"})
                self.assertEqual(len(bot._last_exercise), 1)
                self.assertIsInstance(bot._last_exercise["user-a"][0], str)
                followup = bot._messages_for_event({"question": "แล้วท่านี้หายใจอย่างไร", "conversation_key": "user-a"})
                self.assertIn("หน้า 13", followup[0]["text"])
                self.assertIn("แล้วท่านี้หายใจอย่างไร", generate.call_args.args[0][1]["content"])
                self.assertIn("CONTEXT จากคู่มือหน้า 13", generate.call_args.args[0][1]["content"])
                self.assertNotIn("CONTEXT จากคู่มือหน้า 14", generate.call_args.args[0][1]["content"])
                self.assertIsNone(bot._recall_exercise("user-b"))
                bot._messages_for_event({"action": "menu:groups", "conversation_key": "user-a"})
                self.assertIsNone(bot._recall_exercise("user-a"))
        finally:
            bot.close()

    def test_short_context_expires_and_does_not_guess_medical_safety(self) -> None:
        self.assertTrue(contextual_followup("แล้วท่านี้หายใจอย่างไร"))
        self.assertFalse(contextual_followup("ขอข้อมูลเครื่องเดินวงรี"))
        bot = LineBot(SECRET, "test-access-token", service_factory=lambda: None)
        try:
            exercise = bot.catalog.by_page[13]
            bot._remember_exercise("user-a", exercise)
            with patch("scripts.line_webhook.generate_answer") as generate:
                response = bot._messages_for_event({
                    "question": "ท่านี้ปวดเข่าฝึกต่อได้ไหม", "conversation_key": "user-a",
                })
                generate.assert_not_called()
            self.assertIn("ปรึกษา", response[0]["text"])
            bot._last_exercise["user-a"] = (exercise.exercise_id, 0)
            self.assertIsNone(bot._recall_exercise("user-a"))
        finally:
            bot.close()

    def test_line_accepts_moderately_long_questions_but_caps_excessive_input(self) -> None:
        class FakeService:
            def answer(self, _query: str, **_kwargs: object) -> dict:
                return {"answer": "จากคู่มือ", "sources": []}

        bot = LineBot(SECRET, "test-access-token", service_factory=FakeService)
        try:
            self.assertIn("จากคู่มือ", bot._messages_for_event({"question": "ทดสอบ" * 250})[0]["text"])
            self.assertIn("1500", bot._messages_for_event({"question": "ก" * 1501})[0]["text"])
        finally:
            bot.close()

    def test_chest_intent_avoids_symptom_messages(self) -> None:
        self.assertEqual(chest_intent("อยากเล่นอก"), "menu")
        self.assertEqual(chest_intent("อกกลาง"), "middle")
        self.assertEqual(chest_intent("อยากเล่นอกล่าง"), "lower")
        self.assertIsNone(chest_intent("เจ็บหน้าอก อยากเล่นอก"))
        self.assertIsNone(chest_intent("ปวดอก อยากเล่นอก"))

    def test_catalogue_covers_all_eight_groups_and_pictured_pages(self) -> None:
        catalog = ExerciseCatalog()
        self.assertEqual(len(GROUPS), 8)
        self.assertEqual(set(catalog.by_page), set(range(6, 46)))
        self.assertEqual(len({item.image_name for item in catalog.by_id.values()}), 40)
        self.assertEqual(catalog.by_page[11].group, "core")
        self.assertEqual(len(catalog.group("legs")), 7)
        self.assertEqual(len(catalog.group("chest")), 7)
        self.assertEqual(len(catalog.group("core")), 4)
        self.assertEqual(len(catalog.group("triceps")), 5)
        self.assertEqual(catalog.named_exercise("วิธีเล่น Leg Extension").page, 13)
        self.assertEqual(catalog.named_exercise("วิธีใช้เครื่องเดินวงรี").page, 8)
        self.assertEqual(catalog.named_exercise("วิธีใช้เครื่องบริหารต้นขาด้านหน้า").page, 13)
        self.assertEqual(catalog.named_exercise("เครื่องบริหารกล้ามเนื้อหลังส่วนบนใช้อย่างไร").page, 24)
        self.assertEqual(catalog.named_exercise("Dumbbell Row").page, 40)
        self.assertEqual(catalog.named_exercise("Two Arm Dumbbell Row").page, 41)
        for group, subgroups in SUBGROUPS.items():
            for subkey in subgroups:
                with self.subTest(group=group, subgroup=subkey):
                    self.assertTrue(set(catalog.subgroup(group, subkey)) <= set(catalog.group(group)))

    def test_all_body_part_inputs_route_to_menus(self) -> None:
        expected = {
            "อยากเล่นขา": "group:legs", "อยากเล่นอก": "group:chest",
            "อยากเล่นหลัง": "group:back", "อยากเล่นไหล่": "group:shoulders",
            "อยากเล่นหน้าแขน": "group:biceps", "อยากเล่นหลังแขน": "group:triceps",
            "อยากเล่นท้อง": "group:core", "อยากเล่นคาร์ดิโอ": "group:cardio",
            "เล่นน่อง": "sub:legs:calf", "เล่นอกล่าง": "sub:chest:lower",
            "เล่นแขน": "menu:arms", "เมนู": "menu:groups",
        }
        for query, action in expected.items():
            with self.subTest(query=query):
                self.assertEqual(text_action(query), action)
        self.assertIsNone(text_action("ปวดเข่า อยากเล่นขา"))
        self.assertIsNone(text_action("มือใหม่อยากเล่นอก"))

    def test_unsupported_request_does_not_invent_exercises(self) -> None:
        self.assertIsNotNone(unsupported_topic("อยากบริหารคอ"))
        self.assertIsNotNone(unsupported_topic("แนะนำยี่ห้อโปรตีน"))
        self.assertIsNone(unsupported_topic("วิธีล็อคข้อมือขณะเล่นอก"))
        bot = LineBot(SECRET, "test-access-token", service_factory=lambda: None)
        try:
            messages = bot._messages_for_event({"question": "อยากบริหารคอ"})
        finally:
            bot.close()
        self.assertEqual(len(messages), 1)
        self.assertIn("ไม่พบ", messages[0]["text"])
        self.assertIsNone(chest_intent("อกหัก"))

    def test_verified_exercises_and_image_allowlist(self) -> None:
        exercises = load_chest_exercises()
        self.assertEqual({key: item.page for key, item in exercises.items()},
                         {"upper": 20, "middle": 21, "lower": 45})
        self.assertIsNotNone(safe_image_path("15_incline_press.jpg", exercises))
        self.assertIsNone(safe_image_path("../.env", exercises))
        self.assertIsNone(safe_image_path("39_pullovers.jpg", exercises))
        catalog = ExerciseCatalog()
        self.assertIsNotNone(catalog.preview_path("15_incline_press.jpg"))
        self.assertIsNone(catalog.preview_path("../.env"))
        for item in catalog.by_id.values():
            preview = catalog.preview_path(item.image_name)
            self.assertIsNotNone(preview)
            with Image.open(preview) as picture:
                self.assertEqual(picture.size, (960, 720))

    def test_menu_and_card_have_structured_actions(self) -> None:
        menu = menu_message()
        actions = [item["action"]["data"] for item in menu["quickReply"]["items"]]
        self.assertEqual(actions, ["chest:upper", "chest:middle", "chest:lower", "chest:all"])
        exercise = load_chest_exercises()["lower"]
        card = exercise_card(exercise, "https://example.com")
        self.assertEqual(card["contents"]["hero"]["url"],
                         "https://example.com/previews/40_decline_dumbbell_press.jpg")
        self.assertEqual(card["contents"]["body"]["contents"][1]["text"],
                         "Decline Dumbbell Press")
        self.assertEqual(card["contents"]["hero"]["aspectRatio"], "4:3")
        self.assertEqual(card["contents"]["footer"]["contents"][0]["height"], "sm")
        self.assertIn("45", card["altText"])

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
        event = {"reply_token": "r1", "question": "คำถามทดสอบ", "replay_key": "e1"}
        try:
            self.assertTrue(bot.enqueue([event]))
            self.assertTrue(bot.enqueue([event]))
        finally:
            bot.close()
        self.assertEqual(len(replies), 1)
        self.assertIn("คำถามทดสอบ", replies[0][2][0]["text"])

    def test_line_uses_9b_for_rag_and_exercise_answers(self) -> None:
        calls: list[dict] = []

        class FakeService:
            def answer(self, _query: str, **kwargs: object) -> dict:
                calls.append(kwargs)
                return {"answer": "คำตอบจากคู่มือ", "sources": []}

        bot = LineBot(SECRET, "test-access-token", service_factory=FakeService)
        try:
            bot._rag_messages("มีวิธีฝึกอย่างไร")
            with patch("scripts.line_webhook.generate_answer",
                       return_value={"answer": "คำตอบจากคู่มือ"}) as generate:
                bot._selection_messages("ขา", bot.catalog.group("legs"), "legs")
                generate.assert_not_called()
                bot._exercise_messages(bot.catalog.group("legs")[0])
                self.assertEqual(generate.call_args.kwargs["local_model"],
                                 "qwen3.5:9b-q4_K_M")
        finally:
            bot.close()
        self.assertEqual(calls[0]["local_model"], "qwen3.5:9b-q4_K_M")

    def test_line_local_model_can_be_overridden(self) -> None:
        class FakeService:
            def answer(self, _query: str, **kwargs: object) -> dict:
                self.kwargs = kwargs
                return {"answer": "คำตอบ", "sources": []}

        bot = LineBot(SECRET, "test-access-token", local_model="qwen2.5:3b",
                      service_factory=FakeService)
        try:
            bot._rag_messages("คำถาม")
            self.assertEqual(bot._service.kwargs["local_model"], "qwen2.5:3b")
        finally:
            bot.close()

    def test_chest_button_generates_from_one_chunk_and_attaches_image(self) -> None:
        replies = []
        bot = LineBot(SECRET, "test-access-token", service_factory=lambda: None,
                      reply_sender=lambda *_args: replies.append(_args))
        try:
            with patch("scripts.line_webhook.generate_answer") as generate, \
                 patch("scripts.line_webhook.public_base_url", return_value="https://example.com"):
                generate.return_value = {"answer": "ดันแขนขึ้นและหายใจออก"}
                self.assertTrue(bot.enqueue([{
                    "reply_token": "r1", "action": "chest:upper", "replay_key": "p1"
                }]))
                bot.close()
        finally:
            # shutdown is idempotent and also handles assertion failures above.
            bot.close()
        self.assertEqual(len(replies), 1)
        self.assertEqual(len(replies[0][2]), 2)
        self.assertIn("หน้า 20", replies[0][2][0]["text"])
        self.assertIn("/previews/15_incline_press.jpg",
                      replies[0][2][1]["contents"]["hero"]["url"])
        prompt = generate.call_args.args[0][1]["content"]
        self.assertIn("Incline Press", prompt)
        self.assertNotIn("Decline Dumbbell", prompt)

    def test_all_chest_is_one_swipeable_carousel(self) -> None:
        bot = LineBot(SECRET, "test-access-token", service_factory=lambda: None)
        try:
            with patch("scripts.line_webhook.public_base_url", return_value="https://example.com"), \
                 patch("scripts.line_webhook.generate_answer", return_value={"answer": "เลือกท่า"}):
                messages = bot._all_chest_messages()
        finally:
            bot.close()
        self.assertEqual(len(messages), 2)
        carousel = messages[1]
        self.assertEqual(carousel["type"], "flex")
        self.assertEqual(carousel["contents"]["type"], "carousel")
        bubbles = carousel["contents"]["contents"]
        self.assertEqual(len(bubbles), 7)
        self.assertEqual(
            [bubble["footer"]["contents"][0]["action"]["data"] for bubble in bubbles],
            [f"exercise:{item.exercise_id}" for item in bot.catalog.group("chest")],
        )
        self.assertEqual(len(carousel["quickReply"]["items"]), 6)

    def test_leg_group_has_short_intro_and_seven_photo_cards(self) -> None:
        bot = LineBot(SECRET, "test-access-token", service_factory=lambda: None)
        try:
            with patch("scripts.line_webhook.public_base_url", return_value="https://example.com"), \
                 patch("scripts.line_webhook.generate_answer") as generate:
                messages = bot._messages_for_event({"question": "อยากเล่นขา"})
                generate.assert_not_called()
        finally:
            bot.close()
        self.assertIn("7 ท่าจากคู่มือ", messages[0]["text"])
        self.assertNotIn("Leg press", messages[0]["text"])
        self.assertEqual(len(messages[1]["contents"]["contents"]), 7)
        self.assertIn("/previews/07_leg_press.jpg",
                      messages[1]["contents"]["contents"][0]["hero"]["url"])

    def test_named_exercise_bypasses_multi_source_rag(self) -> None:
        class FakeService:
            def answer(self, _query: str, **_kwargs: object) -> dict:
                raise AssertionError("named exercise must not use broad RAG")
        bot = LineBot(SECRET, "test-access-token", service_factory=FakeService)
        try:
            with patch("scripts.line_webhook.public_base_url", return_value="https://example.com"), \
                 patch("scripts.line_webhook.generate_answer", return_value={"answer": "วิธีจากหน้า 13"}) as generate:
                messages = bot._messages_for_event({"question": "วิธีเล่น Leg Extension"})
        finally:
            bot.close()
        self.assertEqual(len(messages), 2)
        self.assertIn("/previews/08_leg_extension.jpg", messages[1]["contents"]["hero"]["url"])
        prompt = generate.call_args.args[0][1]["content"]
        self.assertIn("Leg Extension", prompt)
        self.assertNotIn("Hyper Extension", prompt)

    def test_auto_line_keeps_selected_exercise_local_and_compares_through_rag(self) -> None:
        calls = []

        class FakeService:
            def answer(self, query: str, **kwargs: object) -> dict:
                calls.append((query, kwargs))
                return {"answer": "เปรียบเทียบจากคู่มือ", "provider": "openrouter", "sources": []}

        bot = LineBot(SECRET, "test-access-token", provider="auto", service_factory=FakeService)
        try:
            with patch("scripts.line_webhook.generate_answer", return_value={"answer": "วิธีเล่น"}) as generate, \
                 patch("scripts.line_webhook.public_base_url", return_value=None):
                bot._messages_for_event({"question": "วิธีเล่น Leg Extension"})
                self.assertEqual(generate.call_args.args[1], "local")
                comparison = bot._messages_for_event({
                    "question": "เปรียบเทียบ Leg Press กับ Leg Extension",
                })
        finally:
            bot.close()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["provider"], "auto")
        self.assertEqual(calls[0][1]["local_model"], "qwen3.5:9b-q4_K_M")
        self.assertIn("API", comparison[0]["text"])

    def test_safety_query_does_not_open_named_exercise_card(self) -> None:
        class FakeService:
            def answer(self, _query: str, **_kwargs: object) -> dict:
                return {"answer": "ควรตรวจสอบอาการก่อน", "sources": []}
        bot = LineBot(SECRET, "test-access-token", service_factory=FakeService)
        try:
            messages = bot._messages_for_event({"question": "ปวดเข่า เล่น Leg Extension ได้ไหม"})
        finally:
            bot.close()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["type"], "text")

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

    def test_http_serves_only_verified_manual_images(self) -> None:
        class FakeBot:
            catalog = ExerciseCatalog()

        WebhookHandler.bot = FakeBot()  # type: ignore[assignment]
        server = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/images/15_incline_press.jpg", timeout=3) as response:
                self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                self.assertTrue(response.read(3).startswith(b"\xff\xd8"))
            with urlopen(base + "/images/09_leg_curl.jpg", timeout=3) as response:
                self.assertEqual(response.headers.get_content_type(), "image/jpeg")
            with urlopen(base + "/previews/15_incline_press.jpg", timeout=3) as response:
                self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                self.assertTrue(response.read(3).startswith(b"\xff\xd8"))
            with self.assertRaises(HTTPError) as failure:
                urlopen(base + "/images/not_in_manual.jpg", timeout=3)
            self.assertEqual(failure.exception.code, 404)
            failure.exception.close()
            with self.assertRaises(HTTPError) as failure:
                urlopen(base + "/previews/not_in_manual.jpg", timeout=3)
            self.assertEqual(failure.exception.code, 404)
            failure.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
