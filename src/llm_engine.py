"""Phase 5: answer questions with the existing retrieval pipeline and two LLMs.

No API key is stored here. Put OPENROUTER_API_KEY in the process environment or
in an ignored .env file in the repository root.
"""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT = """คุณเป็นผู้ช่วยอธิบายการใช้เครื่องออกกำลังกายจากคู่มือสถานกีฬาและสุขภาพ
ตอบเป็นภาษาไทยโดยใช้เฉพาะข้อมูลใน CONTEXT ที่ให้มาเท่านั้น ไม่เติมขั้นตอนหรือข้อเท็จจริงเอง
ถ้าข้อมูลไม่พอ ให้บอกอย่างชัดเจนว่าไม่พบข้อมูลในคู่มือ และขอให้ผู้ใช้ระบุคำถามเพิ่มเติม
ถ้ามีข้อห้าม AVOID ห้ามแนะนำท่านั้นเป็นทางเลือกที่ปลอดภัย และเตือนให้ปรึกษาผู้เชี่ยวชาญเมื่อเกี่ยวกับอาการบาดเจ็บ
เมื่ออ้างรายละเอียดท่า ให้ระบุชื่อท่าและเลขหน้าคู่มือที่ปรากฏใน CONTEXT; ห้ามสร้างเลขหน้าเอง
ตอบให้กระชับ มีขั้นตอนเมื่อผู้ใช้ถามวิธีเล่น และแยกข้อควรระวังจากคำแนะนำ"""


class LLMServiceError(RuntimeError):
    """A safe, user-facing model or configuration error."""


def load_project_env() -> None:
    """Read simple KEY=VALUE entries from .env without adding a dependency.

    Existing process environment values take precedence. Secrets are never logged.
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            raw = response.read()
    except HTTPError as exc:
        # Do not include the response body: it could contain submitted prompt data.
        raise LLMServiceError(f"บริการ LLM ส่ง HTTP {exc.code} กลับมา") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMServiceError("LLM ตอบช้าเกิน 120 วินาที") from exc
    except URLError as exc:
        raise LLMServiceError("เชื่อมต่อบริการ LLM ไม่ได้ ตรวจสอบว่าเซิร์ฟเวอร์ทำงานอยู่และเข้าถึงเครือข่ายได้") from exc
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise LLMServiceError("บริการ LLM ส่งข้อมูลที่ไม่ใช่ JSON") from exc
    if not isinstance(data, dict):
        raise LLMServiceError("บริการ LLM ส่ง JSON ในรูปแบบที่ไม่รองรับ")
    return data


def generate_answer(messages: list[dict[str, str]], provider: str) -> dict[str, Any]:
    """Call Ollama or OpenRouter and return text, model and token usage."""
    load_project_env()
    if provider == "local":
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        data = _post_json(
            f"{base_url}/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 512},
            },
        )
        answer = data.get("message", {}).get("content", "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
        }
    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise LLMServiceError("ยังไม่ได้ตั้ง OPENROUTER_API_KEY ใน .env หรือ environment")
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
        data = _post_json(
            "https://openrouter.ai/api/v1/chat/completions",
            {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 512},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        choices = data.get("choices") or []
        answer = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage") or {}
        model = data.get("model") or model
    else:
        raise ValueError("provider ต้องเป็น 'local' หรือ 'openrouter'")

    if not isinstance(answer, str) or not answer.strip():
        raise LLMServiceError("LLM ไม่ส่งข้อความคำตอบกลับมา")
    return {"answer": answer.strip(), "model": model, "usage": usage}


class RAGChatService:
    """Retrieve once, remove prohibited exercises, then ask the selected LLM."""

    def __init__(self, retriever: Any | None = None):
        if retriever is None:
            load_project_env()
            from src.hybrid_rag import HybridRAG

            retriever = HybridRAG()
        self.retriever = retriever

    def answer(self, query: str, provider: str = "local", mode: str = "auto", top_k: int = 4) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("กรุณาใส่คำถาม")
        if provider not in ("local", "openrouter"):
            raise ValueError("provider ต้องเป็น 'local' หรือ 'openrouter'")
        if mode not in ("auto", "dense", "graph", "hybrid"):
            raise ValueError("mode ต้องเป็น auto, dense, graph หรือ hybrid")
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k ต้องอยู่ระหว่าง 1 ถึง 20")
        started = time.perf_counter()
        retrieval = self.retriever.retrieve(query, mode=mode, top_k=top_k)
        avoid = retrieval.get("avoid_exercises", [])
        avoided_titles = {item.get("exercise", "").strip().casefold() for item in avoid}
        safe_items = [
            item for item in retrieval.get("ranked_items", [])
            if item.get("title", "").strip().casefold() not in avoided_titles
            and item.get("safety_status") != "AVOID_CONTRAINDICATION"
        ]

        graph_summary = retrieval.get("graph_summary", "")
        if not safe_items and not graph_summary and not avoid:
            return {
                "answer": "ไม่พบข้อมูลที่เกี่ยวข้องในคู่มือ กรุณาระบุชื่อท่าหรืออุปกรณ์ให้ชัดเจนขึ้น",
                "provider": provider,
                "model": None,
                "retrieval_mode": retrieval.get("selected_mode", mode),
                "graph_backend": retrieval.get("graph_backend"),
                "sources": [],
                "avoid_exercises": [],
                "usage": {},
                "retrieval_latency_ms": retrieval.get("total_latency_ms"),
                "llm_latency_ms": 0.0,
                "total_latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }

        graph_context = {
            "avoid_exercises": avoid,
            "subgraph_text": graph_summary,
        }
        context, _ = self.retriever.build_augmented_context(
            query, safe_items, graph_context, retrieval.get("selected_mode", mode)
        )
        context = context[:12000]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"คำถาม: {query}\n\nCONTEXT จากคู่มือ:\n{context}"},
        ]
        llm_started = time.perf_counter()
        generated = generate_answer(messages, provider)
        llm_latency_ms = round((time.perf_counter() - llm_started) * 1000, 2)
        answer_text = generated["answer"]
        if avoid and "ปรึกษา" not in answer_text:
            answer_text += "\n\nหากมีอาการปวดหรือบาดเจ็บ ควรปรึกษาแพทย์หรือนักกายภาพก่อนฝึก"
        sources = [
            {"title": item.get("title"), "page": item.get("page_number"), "image_path": item.get("image_path")}
            for item in safe_items
        ]
        return {
            "answer": answer_text,
            "provider": provider,
            "model": generated["model"],
            "retrieval_mode": retrieval.get("selected_mode", mode),
            "graph_backend": retrieval.get("graph_backend"),
            "sources": sources,
            "avoid_exercises": avoid,
            "usage": generated["usage"],
            "retrieval_latency_ms": retrieval.get("total_latency_ms"),
            "llm_latency_ms": llm_latency_ms,
            "total_latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
