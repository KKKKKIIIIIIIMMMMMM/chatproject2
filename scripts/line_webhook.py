"""LINE Messaging API webhook for the existing fitness RAG service.

Run from the repository root:
    python scripts/run_with_neo4j.py -- python scripts/line_webhook.py

Expose http://localhost:8000 with an HTTPS tunnel, then register
https://<tunnel-host>/webhook in LINE Developers. Credentials are read from
the ignored .env file; never put them in source control or logs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.line_chest import (  # noqa: E402
    ChestExercise, load_chest_exercises, prompt_for_exercise,
)
from src.line_catalog import (  # noqa: E402
    Exercise, ExerciseCatalog, GROUPS, SUBGROUPS, overview_prompt, safety_sensitive,
    text_action, unsupported_topic,
)
from src.llm_engine import RAGChatService, generate_answer, load_project_env  # noqa: E402


LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
MAX_WEBHOOK_BYTES = 1_000_000
MAX_QUESTION_CHARS = 800
MAX_LINE_TEXT_UNITS = 5000
PUBLIC_URL_FILE = ROOT / ".runtime" / "line_public_base_url.txt"


def valid_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """Verify the original request bytes before decoding or parsing JSON."""
    if not signature or not channel_secret:
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


def text_events(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Keep only text messages with a reply token and a stable replay key."""
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("events must be an array")
    selected = []
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "message":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("type") != "text":
            continue
        reply_token = event.get("replyToken")
        question = message.get("text")
        if not isinstance(reply_token, str) or not reply_token:
            continue
        if not isinstance(question, str) or not question.strip():
            continue
        replay_key = event.get("webhookEventId") or message.get("id") or reply_token
        selected.append({
            "reply_token": reply_token,
            "question": question.strip(),
            "replay_key": str(replay_key),
        })
    return selected


def chat_events(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Accept text and allowlisted navigation postbacks in their original order."""
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("events must be an array")
    selected = []
    for event in events:
        if isinstance(event, dict) and event.get("type") == "message":
            selected.extend(text_events({"events": [event]}))
            continue
        if not isinstance(event, dict) or event.get("type") != "postback":
            continue
        postback = event.get("postback")
        token = event.get("replyToken")
        data = postback.get("data") if isinstance(postback, dict) else None
        if not isinstance(token, str) or not token or not isinstance(data, str):
            continue
        legacy = {"chest:menu", "chest:all", "chest:upper", "chest:middle", "chest:lower"}
        valid = (
            data in legacy or data in {"menu:groups", "menu:arms"}
            or (data.startswith("group:") and data[6:] in GROUPS)
            or (data.startswith("sub:") and any(
                data == f"sub:{group}:{sub}" for group, subs in SUBGROUPS.items() for sub in subs
            ))
            or (data.startswith("exercise:") and bool(re.fullmatch(r"[a-z0-9_]+", data[9:])))
        )
        if not valid:
            continue
        selected.append({
            "reply_token": token,
            "action": data,
            "replay_key": str(event.get("webhookEventId") or token),
        })
    return selected


def limit_line_text(text: str, maximum: int = MAX_LINE_TEXT_UNITS) -> str:
    """LINE counts text length in UTF-16 code units, not Python characters."""
    if len(text.encode("utf-16-le")) // 2 <= maximum:
        return text
    shortened = []
    used = 0
    for character in text:
        units = len(character.encode("utf-16-le")) // 2
        if used + units > maximum - 1:
            break
        shortened.append(character)
        used += units
    return "".join(shortened) + "…"


def format_answer(result: dict[str, Any]) -> str:
    answer = str(result.get("answer") or "ไม่พบข้อมูลที่ตอบได้จากคู่มือ").strip()
    references = []
    seen = set()
    for source in result.get("sources") or []:
        page = source.get("page")
        title = str(source.get("title") or "คู่มือ").strip()
        if page is None:
            continue
        item = f"{title} (หน้า {page})"
        if item not in seen:
            seen.add(item)
            references.append(item)
        if len(references) == 3:
            break
    if references:
        answer += "\n\nอ้างอิงจากคู่มือ: " + "; ".join(references)
    return limit_line_text(answer)


def public_base_url() -> str | None:
    """Read the current HTTPS tunnel URL at reply time, after launcher setup."""
    configured = os.getenv("LINE_PUBLIC_BASE_URL", "").strip()
    if not configured and PUBLIC_URL_FILE.is_file():
        configured = PUBLIC_URL_FILE.read_text(encoding="utf-8").strip()
    parsed = urlsplit(configured)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return None
    return f"https://{parsed.netloc}"


def quick_reply() -> dict[str, Any]:
    buttons = [
        ("อกบน", "chest:upper"),
        ("อกกลาง", "chest:middle"),
        ("อกล่าง", "chest:lower"),
        ("ดูทั้งหมด", "chest:all"),
    ]
    return {"items": [
        {"type": "action", "action": {
            "type": "postback", "label": label, "data": action, "displayText": label,
        }} for label, action in buttons
    ]}


def navigation_quick_reply(group: str | None = None) -> dict[str, Any]:
    if group and group in SUBGROUPS:
        buttons = [
            (label, f"sub:{group}:{subkey}")
            for subkey, (label, _pages, _aliases) in SUBGROUPS[group].items()
        ]
        buttons.append(("ทุกท่าในหมวด", f"group:{group}"))
    elif group:
        buttons = [("ทุกท่าในหมวด", f"group:{group}")]
    else:
        buttons = [(spec[0], f"group:{key}") for key, spec in GROUPS.items()]
    buttons.append(("เมนูหลัก", "menu:groups"))
    return {"items": [{"type": "action", "action": {
        "type": "postback", "label": label, "data": action, "displayText": label,
    }} for label, action in buttons]}


def menu_message() -> dict[str, Any]:
    return {
        "type": "text",
        "text": (
            "อยากเล่นอกส่วนไหนครับ? เลือกด้านล่างได้เลย — "
            "แต่ละตัวเลือกอ้างอิงท่าและรูปจากคู่มือจริง\n"
            "อกบน: Incline Press · อกกลาง: Chest Press · อกล่าง: Decline Dumbbell Press"
        ),
        "quickReply": quick_reply(),
    }


def exercise_card(exercise: ChestExercise | Exercise, base_url: str, *, selected: bool = False) -> dict[str, Any]:
    group = getattr(exercise, "group", "chest")
    exercise_id = getattr(exercise, "exercise_id", None)
    if selected:
        buttons = [
            ("ท่าอื่นในหมวด", f"group:{group}"), ("เมนูหลัก", "menu:groups"),
        ]
    elif exercise_id:
        buttons = [("ดูวิธีฝึก", f"exercise:{exercise_id}")]
    else:
        buttons = [("เลือกอกส่วนอื่น", "chest:menu")]
    return {
        "type": "flex",
        "altText": f"{exercise.label}: {exercise.title} (คู่มือหน้า {exercise.page})",
        "contents": {
            "type": "bubble",
            "hero": {
                "type": "image", "url": f"{base_url}/images/{exercise.image_name}",
                "size": "full", "aspectRatio": "20:13", "aspectMode": "fit",
            },
            "body": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": exercise.label, "weight": "bold", "size": "lg"},
                    {"type": "text", "text": exercise.title, "wrap": True, "size": "sm", "margin": "md"},
                    {"type": "text", "text": f"ภาพจากคู่มือ หน้า {exercise.page}",
                     "size": "xs", "color": "#666666", "margin": "md"},
                    *([{"type": "text", "text": exercise.target_muscles,
                        "size": "xs", "color": "#666666", "wrap": True, "margin": "sm"}]
                      if isinstance(exercise, Exercise) else []),
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "button", "style": "primary" if index == 0 else "secondary", "action": {
                        "type": "postback", "label": label, "data": action, "displayText": label,
                    }} for index, (label, action) in enumerate(buttons)
                ],
            },
        },
    }


def send_line_messages(access_token: str, reply_token: str, messages: list[dict[str, Any]]) -> None:
    if not 1 <= len(messages) <= 5:
        raise ValueError("LINE replies require 1-5 messages")
    payload = {"replyToken": reply_token, "messages": messages}
    request = Request(
        LINE_REPLY_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # Never log the request, authorization header, reply token, or response body.
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"LINE reply returned HTTP {response.status}")


def send_line_reply(access_token: str, reply_token: str, text: str) -> None:
    """Compatibility helper for single-text callers."""
    send_line_messages(access_token, reply_token, [{"type": "text", "text": text}])


class LineBot:
    """One RAG worker keeps model initialization bounded on a local machine."""

    def __init__(
        self,
        channel_secret: str,
        access_token: str,
        provider: str = "local",
        mode: str = "auto",
        top_k: int = 4,
        service_factory: Callable[[], Any] = RAGChatService,
        reply_sender: Callable[[str, str, list[dict[str, Any]]], None] = send_line_messages,
    ) -> None:
        self.channel_secret = channel_secret
        self.access_token = access_token
        self.provider = provider
        self.mode = mode
        self.top_k = top_k
        self.service_factory = service_factory
        self.reply_sender = reply_sender
        self.catalog = ExerciseCatalog()
        self.chest_exercises = load_chest_exercises()
        self._service: Any | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="line-rag")
        self._capacity = threading.BoundedSemaphore(3)
        self._seen: dict[str, float] = {}
        self._seen_lock = threading.Lock()

    def warmup(self) -> None:
        """Load embedding and graph clients before LINE's first reply token arrives."""
        if self._service is None:
            self._service = self.service_factory()

    def enqueue(self, events: list[dict[str, str]]) -> bool:
        """Queue accepted events and acknowledge the webhook without waiting for LLM."""
        for event in events:
            if not self._capacity.acquire(blocking=False):
                return False
            key = event["replay_key"]
            with self._seen_lock:
                now = time.monotonic()
                self._seen = {k: expiry for k, expiry in self._seen.items() if expiry > now}
                duplicate = key in self._seen
                if not duplicate:
                    self._seen[key] = now + 600
            if duplicate:
                self._capacity.release()
                continue
            try:
                self._executor.submit(self._process, event)
            except RuntimeError:
                with self._seen_lock:
                    self._seen.pop(key, None)
                self._capacity.release()
                return False
        return True

    def _process(self, event: dict[str, str]) -> None:
        try:
            try:
                messages = self._messages_for_event(event)
            except Exception as exc:
                print(f"LINE processing failed: {type(exc).__name__}", file=sys.stderr)
                messages = [{"type": "text", "text": "ขออภัย ระบบยังตอบคำถามนี้ไม่ได้ กรุณาลองใหม่ภายหลัง"}]
            try:
                self.reply_sender(self.access_token, event["reply_token"], messages)
            except HTTPError as exc:
                print(f"LINE reply failed: HTTP {exc.code}", file=sys.stderr)
            except (URLError, TimeoutError, OSError, RuntimeError) as exc:
                print(f"LINE reply failed: {type(exc).__name__}", file=sys.stderr)
        finally:
            self._capacity.release()

    def _messages_for_event(self, event: dict[str, str]) -> list[dict[str, Any]]:
        question = event.get("question", "")
        if len(question) > MAX_QUESTION_CHARS:
            return [{"type": "text", "text": "คำถามยาวเกิน 800 ตัวอักษร กรุณาย่อคำถามแล้วส่งใหม่"}]
        if question and (notice := unsupported_topic(question)):
            return [{"type": "text", "text": notice,
                     "quickReply": navigation_quick_reply()}]
        # Explicit names must bypass multi-chunk retrieval: a similarly named
        # exercise can otherwise leak its instructions or photo into the reply.
        if question and not safety_sensitive(question) and (named := self.catalog.named_exercise(question)):
            return self._exercise_messages(named)
        action = event.get("action") or text_action(question)
        if action == "menu:groups":
            return self._menu_messages()
        if action == "menu:arms":
            return self._menu_messages(("biceps", "triceps"))
        if action in ("chest:menu", "chest:all"):
            return self._group_messages("chest")
        if action in ("chest:upper", "chest:middle", "chest:lower"):
            page = {"chest:upper": 20, "chest:middle": 21, "chest:lower": 45}[action]
            return self._exercise_messages(self.catalog.by_page[page])
        if action and action.startswith("group:") and action[6:] in GROUPS:
            return self._group_messages(action[6:])
        if action and action.startswith("sub:"):
            parts = action.split(":")
            if len(parts) == 3 and parts[1] in SUBGROUPS and parts[2] in SUBGROUPS[parts[1]]:
                items = self.catalog.subgroup(parts[1], parts[2])
                if len(items) == 1:
                    return self._exercise_messages(items[0])
                label = SUBGROUPS[parts[1]][parts[2]][0]
                return self._selection_messages(label, items, parts[1])
        if action and action.startswith("exercise:"):
            exercise = self.catalog.by_id.get(action[9:])
            if exercise:
                return self._exercise_messages(exercise)
        if not question:
            return self._menu_messages()
        return self._rag_messages(question)

    def _rag_messages(self, question: str) -> list[dict[str, Any]]:
        self.warmup()
        result = self._service.answer(
            question, provider=self.provider, mode=self.mode, top_k=self.top_k
        )
        # Unconstrained retrieval can include related-but-different exercises.
        # Only deterministic catalogue selections receive a manual photo.
        return [{"type": "text", "text": format_answer(result)}]

    def _exercise_messages(self, exercise: ChestExercise | Exercise) -> list[dict[str, Any]]:
        try:
            generated = generate_answer(prompt_for_exercise(exercise), self.provider)
            text = limit_line_text(
                f"{generated['answer']}\n\nอ้างอิง: {exercise.title} (คู่มือหน้า {exercise.page})"
            )
        except Exception as exc:
            print(f"Exercise guide generation failed: {type(exc).__name__}", file=sys.stderr)
            text = (
                f"ขออภัย ยังสรุปวิธีฝึก {exercise.label} ไม่สำเร็จ "
                f"ท่าที่ตรงกับคู่มือคือ {exercise.title} (หน้า {exercise.page})"
            )
        messages: list[dict[str, Any]] = [{"type": "text", "text": text}]
        base = public_base_url()
        group = getattr(exercise, "group", "chest")
        if base:
            card = exercise_card(exercise, base, selected=isinstance(exercise, Exercise))
            card["quickReply"] = navigation_quick_reply(group)
            messages.append(card)
        else:
            messages[0]["text"] = limit_line_text(text + "\n\nยังส่งรูปไม่ได้: กรุณาเปิดระบบผ่าน START_PROJECT.cmd หรือกำหนด LINE_PUBLIC_BASE_URL")
            messages[0]["quickReply"] = navigation_quick_reply(group)
        return messages

    def _all_chest_messages(self) -> list[dict[str, Any]]:
        """Compatibility entry point for older chest menu callers."""
        return self._group_messages("chest")

    def _selection_messages(self, label: str, items: list[Exercise], group: str) -> list[dict[str, Any]]:
        pages = ", ".join(str(item.page) for item in items)
        try:
            generated = generate_answer(overview_prompt(label, items), self.provider)
            summary = generated["answer"]
        except Exception as exc:
            print(f"Exercise overview generation failed: {type(exc).__name__}", file=sys.stderr)
            summary = "เลือกการ์ดท่าที่สนใจเพื่อดูวิธีฝึกจากคู่มือได้เลย"
        text = limit_line_text(f"{label}: พบ {len(items)} ท่าในคู่มือ (หน้า {pages})\n{summary}")
        base = public_base_url()
        if not base:
            listing = "\n".join(f"• {item.title} (หน้า {item.page})" for item in items)
            return [{"type": "text", "text": limit_line_text(text + "\n" + listing),
                     "quickReply": navigation_quick_reply(group)}]
        return [
            {"type": "text", "text": text},
            self._carousel_message(items, base, f"ท่า{label}จากคู่มือ", group),
        ]

    def _group_messages(self, group: str) -> list[dict[str, Any]]:
        return self._selection_messages(GROUPS[group][0], self.catalog.group(group), group)

    def _carousel_message(
        self, items: list[Exercise], base: str, alt_text: str, group: str | None,
    ) -> dict[str, Any]:
        bubbles = [exercise_card(item, base)["contents"] for item in items[:12]]
        return {
            "type": "flex", "altText": alt_text[:400],
            "contents": {"type": "carousel", "contents": bubbles} if len(bubbles) > 1 else bubbles[0],
            "quickReply": navigation_quick_reply(group),
        }

    def _menu_messages(self, groups: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        groups = groups or tuple(GROUPS)
        base = public_base_url()
        text = "เลือกหมวดที่อยากฝึก: " + ", ".join(GROUPS[key][0] for key in groups)
        if not base:
            return [{"type": "text", "text": text, "quickReply": navigation_quick_reply()}]
        bubbles = []
        for key in groups:
            representative = self.catalog.group(key)[0]
            bubbles.append({
                "type": "bubble",
                "hero": {"type": "image", "url": f"{base}/images/{representative.image_name}",
                         "size": "full", "aspectRatio": "20:13", "aspectMode": "fit"},
                "body": {"type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": GROUPS[key][0], "weight": "bold", "size": "lg", "wrap": True},
                    {"type": "text", "text": f"{len(GROUPS[key][1])} ท่า/เครื่องในคู่มือ",
                     "size": "sm", "margin": "md"},
                    {"type": "text", "text": f"ภาพตัวอย่าง: หน้า {representative.page}",
                     "size": "xs", "color": "#666666", "margin": "sm"},
                ]},
                "footer": {"type": "box", "layout": "vertical", "contents": [{
                    "type": "button", "style": "primary", "action": {
                        "type": "postback", "label": "ดูท่าในหมวด", "data": f"group:{key}",
                        "displayText": GROUPS[key][0],
                    },
                }]},
            })
        return [
            {"type": "text", "text": text},
            {"type": "flex", "altText": "เลือกหมวดออกกำลังกายจากคู่มือ",
             "contents": {"type": "carousel", "contents": bubbles},
             "quickReply": navigation_quick_reply()},
        ]

    def close(self) -> None:
        self._executor.shutdown(wait=True)


class WebhookHandler(BaseHTTPRequestHandler):
    bot: LineBot

    def log_message(self, _format: str, *args: Any) -> None:
        # Avoid logging chat text, tokens, signatures, or user identifiers.
        pass

    def respond(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.respond(200, {"ok": True, "service": "fitness-rag-line"})
        elif self.path.startswith("/images/"):
            filename = self.path.removeprefix("/images/")
            path = self.bot.catalog.image_path(filename)
            if path is None:
                self.respond(404, {"error": "not_found"})
                return
            image = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(image)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(image)
        else:
            self.respond(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/webhook":
            self.respond(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.respond(411, {"error": "content_length_required"})
            return
        if length < 0 or length > MAX_WEBHOOK_BYTES:
            self.respond(413, {"error": "payload_too_large"})
            return
        body = self.rfile.read(length)
        signature = self.headers.get("x-line-signature", "")
        if not valid_signature(body, signature, self.bot.channel_secret):
            reason = "signature mismatch" if signature else "signature missing"
            print(f"Rejected LINE webhook: {reason}", file=sys.stderr)
            self.respond(401, {"error": "invalid_signature"})
            return
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("webhook body must be an object")
            events = chat_events(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self.respond(400, {"error": "invalid_payload"})
            return
        if not self.bot.enqueue(events):
            self.respond(503, {"error": "server_busy"})
            return
        self.respond(200, {"ok": True})


def main() -> int:
    # The user's channel credentials in this project's private .env must win
    # over stale LINE_* values inherited from previous lab terminal sessions.
    load_project_env(override_keys={"LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN"})
    secret = os.getenv("LINE_CHANNEL_SECRET", "").strip()
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not secret or not token:
        print("Set LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN in .env first.", file=sys.stderr)
        return 2
    provider = os.getenv("LINE_PROVIDER", "local").lower()
    mode = os.getenv("LINE_RETRIEVAL_MODE", "auto").lower()
    if provider not in {"local", "openrouter"} or mode not in {"auto", "dense", "graph", "hybrid"}:
        print("Invalid LINE_PROVIDER or LINE_RETRIEVAL_MODE configuration.", file=sys.stderr)
        return 2
    try:
        top_k = int(os.getenv("LINE_TOP_K", "4"))
        port = int(os.getenv("LINE_PORT", "8000"))
    except ValueError:
        print("LINE_TOP_K and LINE_PORT must be integers.", file=sys.stderr)
        return 2
    if not 1 <= top_k <= 20 or not 1 <= port <= 65535:
        print("LINE_TOP_K or LINE_PORT is outside the allowed range.", file=sys.stderr)
        return 2
    host = os.getenv("LINE_HOST", "127.0.0.1")
    bot = LineBot(secret, token, provider=provider, mode=mode, top_k=top_k)
    print("Loading local retrieval indexes before accepting LINE messages...", flush=True)
    try:
        bot.warmup()
    except Exception as exc:
        bot.close()
        print(f"Cannot initialize RAG service: {type(exc).__name__}", file=sys.stderr)
        return 2
    WebhookHandler.bot = bot
    server = ThreadingHTTPServer((host, port), WebhookHandler)
    print(f"LINE webhook listening on http://{host}:{port}/webhook (provider={provider}, mode={mode})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        bot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
