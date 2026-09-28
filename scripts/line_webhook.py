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
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_engine import RAGChatService, load_project_env  # noqa: E402


LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
MAX_WEBHOOK_BYTES = 1_000_000
MAX_QUESTION_CHARS = 800
MAX_LINE_TEXT_UNITS = 5000


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


def send_line_reply(access_token: str, reply_token: str, text: str) -> None:
    payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
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
        reply_sender: Callable[[str, str, str], None] = send_line_reply,
    ) -> None:
        self.channel_secret = channel_secret
        self.access_token = access_token
        self.provider = provider
        self.mode = mode
        self.top_k = top_k
        self.service_factory = service_factory
        self.reply_sender = reply_sender
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
            question = event["question"]
            if len(question) > MAX_QUESTION_CHARS:
                message = "คำถามยาวเกิน 800 ตัวอักษร กรุณาย่อคำถามแล้วส่งใหม่"
            else:
                try:
                    self.warmup()
                    result = self._service.answer(
                        question, provider=self.provider, mode=self.mode, top_k=self.top_k
                    )
                    message = format_answer(result)
                except Exception as exc:
                    print(f"RAG processing failed: {type(exc).__name__}", file=sys.stderr)
                    message = "ขออภัย ระบบยังตอบคำถามนี้ไม่ได้ กรุณาลองใหม่ภายหลัง"
            try:
                self.reply_sender(self.access_token, event["reply_token"], message)
            except HTTPError as exc:
                print(f"LINE reply failed: HTTP {exc.code}", file=sys.stderr)
            except (URLError, TimeoutError, OSError, RuntimeError) as exc:
                print(f"LINE reply failed: {type(exc).__name__}", file=sys.stderr)
        finally:
            self._capacity.release()

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
            events = text_events(payload)
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
