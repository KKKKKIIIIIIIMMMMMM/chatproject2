"""Verified chest-exercise choices for the LINE conversation.

Each option is tied to one exact chunk and its original manual image.  The
LLM may explain that chunk, but it never chooses the exercise or image.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = ROOT / "data" / "chunks.json"
IMAGES_DIR = ROOT / "data" / "images"


@dataclass(frozen=True)
class ChestExercise:
    region: str
    label: str
    title: str
    page: int
    image_name: str
    content: str


# The expected page and file are reviewed against the source PDF.  If the
# dataset changes, fail closed instead of showing a mismatched illustration.
CHEST_SPECS = {
    "upper": ("อกบน", 20, "15_incline_press.jpg"),
    "middle": ("อกกลาง", 21, "16_chest_press.jpg"),
    "lower": ("อกล่าง", 45, "40_decline_dumbbell_press.jpg"),
}


def load_chest_exercises(path: Path = CHUNKS_PATH) -> dict[str, ChestExercise]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(chunks, list):
        raise ValueError("chunks.json must contain a list")
    result = {}
    for region, (label, page, image_name) in CHEST_SPECS.items():
        matches = [
            chunk for chunk in chunks
            if chunk.get("page_number") == page
            and chunk.get("image_path") == f"data/images/{image_name}"
            and label in str(chunk.get("title", ""))
        ]
        if len(matches) != 1 or not (IMAGES_DIR / image_name).is_file():
            raise ValueError(f"Missing or ambiguous verified LINE chest source: {region}")
        chunk = matches[0]
        result[region] = ChestExercise(
            region=region,
            label=label,
            title=str(chunk["title"]).strip(),
            page=page,
            image_name=image_name,
            content=str(chunk["content"]).strip(),
        )
    return result


def chest_intent(text: str) -> str | None:
    """Only route explicit workout requests; symptoms go to the normal RAG path."""
    compact = re.sub(r"\s+", "", text).casefold()
    if any(word in compact for word in (
        "เจ็บอก", "เจ็บหน้าอก", "แน่นอก", "แน่นหน้าอก", "ปวดอก", "ปวดหน้าอก", "อกหัก"
    )):
        return None
    for region, (label, _, _) in CHEST_SPECS.items():
        if compact == label:
            return region
    if re.search(r"(?:อยาก|ขอ|แนะนำ|ฝึก|เล่น|บริหาร|ท่า).{0,15}(?:หน้า)?อก", compact):
        for region, (label, _, _) in CHEST_SPECS.items():
            if label in compact:
                return region
        return "menu"
    return None


def safe_image_path(filename: str, exercises: dict[str, ChestExercise]) -> Path | None:
    if filename not in {item.image_name for item in exercises.values()}:
        return None
    path = (IMAGES_DIR / filename).resolve()
    if path.parent != IMAGES_DIR.resolve() or not path.is_file():
        return None
    return path


def prompt_for_exercise(exercise: ChestExercise) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "คุณเป็นผู้ช่วยอธิบายการออกกำลังกาย ตอบภาษาไทยสั้น กระชับ "
                "ใช้เฉพาะ CONTEXT จากคู่มือที่ให้มา ห้ามเพิ่มท่า ขั้นตอน น้ำหนัก จำนวนเซต "
                "หรือคำแนะนำทางการแพทย์ที่ไม่มีใน CONTEXT ถ้าข้อมูลไม่พอให้บอกว่าไม่พบในคู่มือ "
                "ระบุชื่อท่าและหน้าคู่มืออย่างถูกต้อง"
            ),
        },
        {
            "role": "user",
            "content": (
                f"อธิบายวิธีฝึก {exercise.label} จากท่านี้เท่านั้น: {exercise.title} "
                "สรุปอุปกรณ์ วิธีทำ และการหายใจตามที่ระบุในคู่มือ\n\n"
                f"CONTEXT (หน้า {exercise.page}):\n{exercise.content}"
            ),
        },
    ]
