"""Evidence-checked exercise catalogue for LINE menus and manual images.

The checklist is useful as a taxonomy draft, but the actual page, title and
image always come from chunks.json.  Page 11 is an abdominal machine (not
Multi Hip), and the current manual has 40 pictured exercises on pages 6-45.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "data" / "images"
CHUNKS_PATH = ROOT / "data" / "chunks.json"

# Page ownership is reviewed against chunks.json, not copied from checklist.md.
GROUPS = {
    "legs": ("ขาและสะโพก", (12, 13, 14, 15, 16, 17, 18), ("ขา", "ต้นขา", "สะโพก", "น่อง", "legs", "leg", "glute", "calf")),
    "chest": ("หน้าอก", (19, 20, 21, 42, 43, 44, 45), ("หน้าอก", "อก", "chest", "pectoral")),
    "back": ("ปีกและหลัง", (23, 24, 25, 40, 41), ("ปีก", "หลัง", "back", "lat", "row")),
    "shoulders": ("หัวไหล่", (22, 37, 38, 39), ("หัวไหล่", "ไหล่", "shoulder", "deltoid")),
    "biceps": ("แขนด้านหน้า", (26, 31, 32, 33), ("หน้าแขน", "แขนหน้า", "แขนด้านหน้า", "biceps")),
    "triceps": ("แขนด้านหลัง", (27, 28, 34, 35, 36), ("หลังแขน", "แขนหลัง", "แขนด้านหลัง", "triceps")),
    "core": ("หน้าท้องและเอว", (10, 11, 29, 30), ("ท้อง", "หน้าท้อง", "เอว", "แกนกลาง", "core", "abs", "abdominal")),
    "cardio": ("คาร์ดิโอ", (6, 7, 8, 9), ("คาร์ดิโอ", "หัวใจ", "แอโรบิก", "cardio", "aerobic")),
}

# Optional filters for follow-up buttons. Every page stays in its source group.
SUBGROUPS = {
    "legs": {
        "front": ("ต้นขาด้านหน้า", (12, 13), ("ต้นขาหน้า", "ต้นขาด้านหน้า", "หน้าขา")),
        "back": ("ต้นขาด้านหลัง", (14,), ("ต้นขาหลัง", "ต้นขาด้านหลัง", "หลังขา")),
        "calf": ("น่อง", (15,), ("น่อง", "calf")),
        "inner": ("ต้นขาด้านใน", (16, 17), ("ขาด้านใน", "ต้นขาด้านใน", "ขาใน")),
        "outer": ("ต้นขาด้านนอก", (16, 18), ("ขาด้านนอก", "ต้นขาด้านนอก", "ขานอก")),
        "hip": ("สะโพก", (12, 18), ("สะโพก", "glute")),
    },
    "chest": {
        "upper": ("อกบน", (20,), ("อกบน", "หน้าอกบน")),
        "middle": ("อกกลาง", (21,), ("อกกลาง", "หน้าอกกลาง")),
        "lower": ("อกล่าง", (44, 45), ("อกล่าง", "หน้าอกล่าง")),
        "inner": ("อกด้านใน", (19, 43), ("อกใน", "อกด้านใน", "หน้าอกใน")),
    },
    "back": {
        "wings": ("ปีกและสะบัก", (23, 40, 41), ("ปีก", "สะบัก")),
        "upper": ("หลังส่วนบน", (24,), ("หลังบน", "หลังส่วนบน")),
        "lower": ("หลังส่วนล่าง", (25,), ("หลังล่าง", "หลังส่วนล่าง")),
    },
    "shoulders": {
        "front": ("ไหล่ด้านหน้า", (38,), ("ไหล่หน้า", "ไหล่ด้านหน้า")),
        "side": ("ไหล่ด้านข้าง", (39,), ("ไหล่ข้าง", "ไหล่ด้านข้าง")),
        "all": ("ไหล่รวม", (22, 37), ("ไหล่รวม",)),
    },
    "core": {
        "waist": ("เอวและลำตัวด้านข้าง", (10,), ("เอว", "ลำตัวด้านข้าง")),
        "upper": ("หน้าท้องส่วนบน", (29,), ("ท้องบน", "หน้าท้องบน")),
        "lower": ("หน้าท้องส่วนล่าง", (30,), ("ท้องล่าง", "หน้าท้องล่าง")),
    },
}

EXERCISE_ALIASES = {
    19: ("pec deck",),
    31: ("alternate dumbbell curl", "biceps alternate curl"),
    34: ("dumbbell triceps extension",),
    35: ("two arm extension",),
    36: ("kickback",),
    39: ("lateral raise", "side lateral raise"),
    45: ("decline dumbbell bench press",),
}


@dataclass(frozen=True)
class Exercise:
    exercise_id: str
    group: str
    label: str
    title: str
    page: int
    image_name: str
    content: str
    target_muscles: str
    equipment: str


class ExerciseCatalog:
    def __init__(self, chunks_path: Path = CHUNKS_PATH):
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        if not isinstance(chunks, list):
            raise ValueError("chunks.json must contain a list")
        by_page = {}
        by_id = {}
        grouped_pages = [(page, key) for key, (_, pages, _) in GROUPS.items() for page in pages]
        group_by_page = dict(grouped_pages)
        if len(grouped_pages) != 40 or set(group_by_page) != set(range(6, 46)):
            raise ValueError("LINE group map must cover each pictured manual page exactly once")
        image_names = set()
        for chunk in chunks:
            if chunk.get("content_type") != "exercise_guide":
                continue
            page = chunk.get("page_number")
            if page not in group_by_page or page in by_page:
                raise ValueError(f"Unmapped or duplicate exercise page: {page}")
            image = chunk.get("image_path", "")
            image_name = Path(image).name
            if (image != f"data/images/{image_name}" or image_name in image_names
                    or not (IMAGES_DIR / image_name).is_file()):
                raise ValueError(f"Missing or invalid manual image on page {page}")
            image_names.add(image_name)
            exercise_id = str(chunk.get("exercise_id", ""))
            if not re.fullmatch(r"[a-z0-9_]+", exercise_id) or exercise_id in by_id:
                raise ValueError(f"Missing or duplicate exercise ID on page {page}")
            group = group_by_page[page]
            item = Exercise(
                exercise_id=exercise_id, group=group, label=GROUPS[group][0],
                title=str(chunk.get("title", "")).strip(), page=page,
                image_name=image_name, content=str(chunk.get("content", "")).strip(),
                target_muscles=str(chunk.get("target_muscles", "")).strip(),
                equipment=str(chunk.get("equipment", "")).strip(),
            )
            if not item.title or not item.content:
                raise ValueError(f"Incomplete manual source on page {page}")
            by_page[page] = item
            by_id[exercise_id] = item
        if set(by_page) != set(group_by_page) or len(by_id) != 40:
            raise ValueError("LINE catalogue needs all 40 pictured exercise chunks")
        self.by_page: dict[int, Exercise] = by_page
        self.by_id: dict[str, Exercise] = by_id

    def group(self, key: str) -> list[Exercise]:
        return [self.by_page[page] for page in GROUPS[key][1]]

    def subgroup(self, group: str, key: str) -> list[Exercise]:
        return [self.by_page[page] for page in SUBGROUPS[group][key][1]]

    def image_path(self, filename: str) -> Path | None:
        if filename not in {item.image_name for item in self.by_id.values()}:
            return None
        path = (IMAGES_DIR / filename).resolve()
        if path.parent != IMAGES_DIR.resolve() or not path.is_file():
            return None
        return path

    def named_exercise(self, question: str) -> Exercise | None:
        """Resolve an explicitly named exercise; ties stay unresolved."""
        normalized = " " + re.sub(r"[^a-z0-9]+", " ", question.casefold()).strip() + " "
        thai_question = re.sub(r"[^\u0e00-\u0e7f]+", "", question.casefold())
        candidates = []
        for item in self.by_id.values():
            canonical = " ".join(item.exercise_id.split("_")[1:])
            for alias in (canonical, *EXERCISE_ALIASES.get(item.page, ())):
                if len(alias) >= 4 and f" {alias} " in normalized:
                    candidates.append((len(alias), item))
            # The Thai title is an exact manual label, unlike a broad muscle
            # name. Skip pages whose titles are just generic arm headings.
            if item.page not in {31, 34, 35, 36}:
                thai_title = re.sub(r"[A-Za-z].*$", "", item.title.split("(")[0])
                thai_alias = re.sub(r"[^\u0e00-\u0e7f]+", "", thai_title)
                if len(thai_alias) >= 12 and thai_alias in thai_question:
                    candidates.append((len(thai_alias), item))
        if not candidates:
            return None
        strongest = max(length for length, _item in candidates)
        winners = {item for length, item in candidates if length == strongest}
        return next(iter(winners)) if len(winners) == 1 else None


def text_action(text: str) -> str | None:
    """Recognize browsing requests only; symptom questions stay with safety RAG."""
    compact = re.sub(r"\s+", "", text).casefold()
    if safety_sensitive(compact):
        return None
    if compact in ("เมนู", "ดูเมนู", "ดูทั้งหมด", "เลือกหมวด", "เล่นอะไรดี", "ออกกำลังกายอะไรดี"):
        return "menu:groups"
    if compact in ("แขน", "เล่นแขน", "อยากเล่นแขน", "ฝึกแขน"):
        return "menu:arms"
    # Prefer specific subgroup names over the broad group alias.
    sub_matches = []
    for group, subgroups in SUBGROUPS.items():
        for subkey, (_label, _pages, aliases) in subgroups.items():
            for alias in aliases:
                if alias.casefold() in compact:
                    sub_matches.append((len(alias), group, subkey))
    if sub_matches:
        _length, group, subkey = max(sub_matches)
        return f"sub:{group}:{subkey}"
    group_matches = []
    for group, (_label, _pages, aliases) in GROUPS.items():
        for alias in aliases:
            if alias.casefold() in compact:
                group_matches.append((len(alias), group))
    if not group_matches:
        return None
    # Avoid hijacking detailed questions; those go through retrieval + image sources.
    if any(term in compact for term in ("วิธี", "หายใจ", "ระวัง", "อุปกรณ์", "กี่ครั้ง", "กี่เซต")):
        return None
    if len(compact) <= 20 or any(term in compact for term in ("อยากเล่น", "ขอดู", "ขอท่า", "แนะนำท่า", "ฝึก")):
        return f"group:{max(group_matches)[1]}"
    return None


def safety_sensitive(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).casefold()
    return any(term in compact for term in (
        "ปวด", "เจ็บ", "บาดเจ็บ", "แน่นหน้าอก", "ห้าม", "ข้อห้าม", "ไม่สบาย",
        "มือใหม่", "ผู้เริ่มต้น", "beginner",
    ))


def unsupported_topic(text: str) -> str | None:
    """Reject only clearly out-of-manual requests, not incidental body words."""
    compact = re.sub(r"\s+", "", text).casefold()
    if any(term in compact for term in (
        "อาหารเสริม", "เวย์", "ยี่ห้อโปรตีน", "เมนูอาหาร", "โภชนาการ", "ยาแก้", "กินยา",
    )):
        return "คู่มือสถานกีฬาและสุขภาพไม่มีข้อมูลเรื่องอาหารเสริม โภชนาการหรือยา จึงไม่ควรเดาคำตอบจากคู่มือนี้"
    if any(term in compact for term in (
        "บริหารคอ", "เล่นคอ", "ฝึกคอ", "กล้ามเนื้อคอ", "บริหารข้อมือ", "ฝึกข้อมือ",
        "บริหารข้อเท้า", "ฝึกข้อเท้า",
    )):
        return "ไม่พบท่าบริหารเฉพาะส่วนนั้นในคู่มือสถานกีฬาและสุขภาพ กรุณาถามหมวดที่มีในคู่มือ เช่น ขา อก หลัง ไหล่ แขน ท้อง หรือคาร์ดิโอ"
    return None


def overview_prompt(label: str, exercises: list[Exercise]) -> list[dict[str, str]]:
    facts = "\n".join(
        f"- {item.title} (หน้า {item.page}); กล้ามเนื้อ: {item.target_muscles}; อุปกรณ์: {item.equipment}"
        for item in exercises
    )
    return [
        {"role": "system", "content": (
            "คุณช่วยอธิบายหมวดท่าออกกำลังกายจากคู่มือ ตอบภาษาไทยไม่เกิน 3 ประโยค "
            "ใช้เฉพาะรายการใน CONTEXT ห้ามแต่งท่า วิธีทำ ความปลอดภัย จำนวนเซต หรือเลขหน้าเพิ่ม "
            "ให้ผู้ใช้เลือกการ์ดเพื่อดูวิธีฝึกของแต่ละท่า"
        )},
        {"role": "user", "content": f"สรุปหมวด {label} จากรายการต่อไปนี้\nCONTEXT:\n{facts}"},
    ]
