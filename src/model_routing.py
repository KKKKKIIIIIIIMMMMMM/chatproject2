"""Conservative, evidence-aware LLM routing for LINE questions.

This is a transparent heuristic, not a claim to measure true question difficulty.
It never uses model-generated text or raw conversation history as routing evidence.
"""

from __future__ import annotations

import re
from typing import Any


COMPARISON_CUES = (
    "เปรียบเทียบ", "แตกต่าง", "ต่างกัน", "ข้อดีข้อเสีย", "เทียบกับ",
    "แบบไหนดีกว่า", "ท่าไหนเหมาะกว่า", "compare", "difference", "versus",
)
SYNTHESIS_CUES = (
    "หลายท่า", "หลายแบบ", "สรุปภาพรวม", "จัดลำดับ", "เชื่อมโยง", "ร่วมกัน",
)
MULTIPART_CUES = ("และ", "พร้อมกับ", "รวมทั้ง", "อีกทั้ง", "จากนั้น", "รวมถึง")
# Do not automatically transmit questions containing likely personal health details.
PRIVATE_HEALTH_CUES = (
    "ปวด", "เจ็บ", "บาดเจ็บ", "โรค", "รักษา", "วินิจฉัย", "ตั้งครรภ์",
    "อายุ", "น้ำหนักตัว", "แพ้ยา", "ไม่สบาย", "เข่าเสื่อม", "เบาหวาน",
)


def is_complex_query(query: str) -> bool:
    """Identify multi-part or comparative requests before menu/name shortcuts."""
    text = re.sub(r"\s+", "", query).casefold()
    if any(cue in text for cue in COMPARISON_CUES + SYNTHESIS_CUES):
        return True
    if text.count("?") + text.count("？") >= 2:
        return True
    return len(text) >= 220 and any(cue in text for cue in MULTIPART_CUES)


def choose_auto_provider(
    query: str, safe_items: list[dict[str, Any]], *, api_available: bool,
) -> tuple[str, str]:
    """Route only evidence-backed, multi-source complex queries to OpenRouter."""
    text = re.sub(r"\s+", "", query).casefold()
    if any(cue in text for cue in PRIVATE_HEALTH_CUES):
        return "local", "private_health_question"
    if not api_available:
        return "local", "api_unavailable"
    sources = {
        (item.get("page_number"), item.get("title")) for item in safe_items
        if item.get("page_number") is not None or item.get("title")
    }
    if len(sources) < 2:
        return "local", "single_source"
    if any(cue in text for cue in COMPARISON_CUES + SYNTHESIS_CUES):
        return "openrouter", "multi_source_synthesis"
    if text.count("?") + text.count("？") >= 2:
        return "openrouter", "multiple_questions"
    if len(text) >= 220 and any(cue in text for cue in MULTIPART_CUES):
        return "openrouter", "long_multi_part_question"
    return "local", "simple_question"
