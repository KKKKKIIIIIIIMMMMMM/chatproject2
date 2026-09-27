"""Build a factual Thai project report from evaluation outputs (no invented scores)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def load_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def human_review_stats(path: Path) -> tuple[int, int, dict]:
    if not path.is_file():
        return 0, 0, {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    graded = [row for row in rows if all(row.get(f"human_{name}_0_2", "").strip() in ("0", "1", "2")
                                     for name in ("accuracy", "grounding", "safety"))]
    averages = {}
    if graded:
        for name in ("accuracy", "grounding", "safety"):
            averages[name] = round(sum(int(row[f"human_{name}_0_2"]) for row in graded) / len(graded), 2)
    return len(rows), len(graded), averages


def fmt_number(value, digits=1):
    return "—" if value is None else f"{value:,.{digits}f}"


def fmt_percent(value):
    return "—" if value is None else f"{value * 100:.1f}%"


def build_report(results_dir: Path) -> str:
    questions = load_json(ROOT / "evaluation" / "questions.json", [])
    chunks = load_json(ROOT / "data" / "chunks.json", [])
    graph = load_json(ROOT / "data" / "knowledge_graph.json", {"nodes": {}, "edges": []})
    summary = load_json(results_dir / "summary.json", {"configurations": {}})
    rows = load_rows(results_dir / "results.jsonl")
    latest = {}
    for row in rows:
        if row.get("status") == "ok":
            latest[(row["question_id"], row["provider"], row["mode"])] = row
    success = list(latest.values())
    backends = Counter(row.get("graph_backend") for row in success if row.get("graph_backend"))
    total_review, graded_review, review_avg = human_review_stats(results_dir / "human_review.csv")
    counts = Counter(item.get("category") for item in questions)
    full = len(success) >= len(questions) * 6
    status = "ครบ 6 รูปแบบ" if full else "ยังไม่ครบ 6 รูปแบบ"

    lines = [
        "# รายงาน Final Project: ผู้ช่วยการออกกำลังกายด้วย Hybrid RAG",
        "",
        f"สร้างรายงาน: {datetime.now().strftime('%d/%m/%Y %H:%M')} | สถานะผลทดลอง: **{status}**",
        "",
        "## 1. วัตถุประสงค์และขอบเขต",
        "",
        "ระบบตอบคำถามการใช้เครื่องและท่าออกกำลังกายจากคู่มือสถานกีฬาและสุขภาพ โดยแสดงชื่อท่า เลขหน้า และรูปประกอบที่ค้นพบ ระบบไม่ใช่เครื่องมือวินิจฉัยโรคหรือให้คำแนะนำทางการแพทย์",
        "",
        "## 2. ข้อมูลและสถาปัตยกรรม",
        "",
        f"- เอกสารต้นทาง: `exercise/exercise.pdf`; แบ่งเป็น {len(chunks)} chunks, ภาพ {len(list((ROOT / 'data' / 'images').glob('*.jpg')))} ภาพ",
        f"- กราฟต้นแบบ: {len(graph.get('nodes', {}))} nodes, {len(graph.get('edges', []))} relationships",
        "- Dense Retrieval: multilingual-e5-small กับ ChromaDB; Graph Retrieval: Cypher บน Neo4j เมื่อพร้อมใช้งาน และ JSON fallback เมื่อไม่พร้อม",
        "- Hybrid Retrieval: จัดอันดับร่วมด้วย Reciprocal Rank Fusion (RRF); ตัวตอบคัดท่าที่มี AVOID ออกจากรายการอ้างอิงก่อนส่งให้ LLM",
        "- LLM: Ollama `qwen2.5:3b` ในเครื่อง หรือ OpenRouter API; หน้า Streamlit เลือก Retrieval และ LLM ได้",
        "",
        "## 3. วิธีประเมิน",
        "",
        f"ชุดคำถาม {len(questions)} ข้อ: ขั้นตอน {counts['procedural']}, ความสัมพันธ์ {counts['relational']}, ซับซ้อน {counts['complex']}. ทดสอบ Dense, Graph, Hybrid ร่วมกับ Local และ API รวม 6 รูปแบบเมื่อมี OpenRouter key",
        "",
        "ตัวชี้วัดอัตโนมัติ: source-page coverage, avoid recall, จำนวนกรณีที่หน้าแหล่งข้อมูลทับซ้อนกับหน้าท่า AVOID, หน้าอ้างอิงที่ไม่อยู่ในหลักฐาน, latency, token และต้นทุนที่ API รายงานจริง การทับซ้อนระดับหน้าไม่พิสูจน์ว่าระบบแนะนำท่าที่ควรหลีกเลี่ยง ตัวชี้วัดเหล่านี้ไม่แทนคะแนนความถูกต้องของข้อความคำตอบ จึงมี `human_review.csv` สำหรับให้คนตรวจ 0–2 คะแนนด้านความถูกต้อง การยึดหลักฐาน และความปลอดภัย",
        "",
        "## 4. ผลการทดลองที่บันทึกได้",
        "",
        "| รูปแบบ | สำเร็จ / 20 | เวลาเฉลี่ย (s) | P95 (s) | Source coverage | Avoid recall | หน้าอ้างอิงทับกับ AVOID (กรณี) | Token input/output | API cost (USD) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for provider in ("local", "openrouter"):
        for mode in ("dense", "graph", "hybrid"):
            item = summary.get("configurations", {}).get(f"{provider}+{mode}", {})
            mean_ms = item.get("mean_latency_ms")
            p95_ms = item.get("p95_latency_ms")
            lines.append(
                f"| {provider} + {mode} | {item.get('completed_questions', 0)} / 20 | "
                f"{fmt_number(mean_ms / 1000 if mean_ms is not None else None, 2)} | "
                f"{fmt_number(p95_ms / 1000 if p95_ms is not None else None, 2)} | "
                f"{fmt_percent(item.get('mean_retrieval_coverage'))} | "
                f"{fmt_percent(item.get('mean_avoid_recall'))} | "
                f"{item.get('cases_with_avoid_page_overlap', '—')} | "
                f"{item.get('prompt_tokens', '—')}/{item.get('completion_tokens', '—')} | "
                f"{fmt_number(item.get('reported_api_cost_usd'), 4)} |"
            )
    lines.extend([
        "",
        f"บันทึกสำเร็จ {len(success)} จาก {len(questions) * 6} คู่คำถาม-รูปแบบ; สัดส่วนนี้บอกความครบของการทดลอง ไม่ใช่คะแนนคุณภาพ",
        f"ค่าใช้จ่าย OpenRouter รวมจากตัวเลขที่ API รายงาน: ${sum((summary.get('configurations', {}).get(f'openrouter+{mode}', {}).get('reported_api_cost_usd') or 0) for mode in ('dense', 'graph', 'hybrid')):.4f}",
        "จำนวนกรณีที่คำตอบอ้างเลขหน้าแต่ไม่อยู่ในรายการ sources/AVOID ที่แสดง: "
        + ", ".join(f"{provider}+{mode} {summary.get('configurations', {}).get(f'{provider}+{mode}', {}).get('cases_with_unsupported_page', 0)}"
                    for provider in ("local", "openrouter") for mode in ("dense", "graph", "hybrid"))
        + " (ต้องอ่านเนื้อหาเอง เพราะกราฟสรุปอาจมีหลักฐานเพิ่มเติม)",
        f"แหล่งกราฟที่บันทึกในผลจริง: {dict(backends) if backends else 'ยังไม่มีผล Graph/Hybrid'}",
        f"ผลตรวจโดยคน: {graded_review}/{total_review} คำตอบ" + (f"; ค่าเฉลี่ยจากคะแนน 0–2: {review_avg}" if review_avg else " (ยังไม่ตรวจครบ)"),
        "",
        "## 5. การตีความและข้อจำกัด",
        "",
        "- กราฟ AVOID/RECOMMEND เป็นความสัมพันธ์ในชุดข้อมูลโครงงาน ต้องให้ผู้เชี่ยวชาญตรวจสอบก่อนใช้เป็นคำแนะนำสุขภาพจริง",
        "- JSON fallback ทำให้สาธิตได้เมื่อ Neo4j ไม่พร้อม แต่การอ้างว่าใช้ Neo4j ต้องแสดงผล `graph_backend=neo4j` จากการรันจริง",
        "- ค่า GPU memory ที่เก็บเป็นภาพรวมของเครื่องก่อน/หลังคำถาม ไม่ใช่ VRAM เฉพาะโมเดล; ค่า API cost แสดงเฉพาะเมื่อผู้ให้บริการส่งตัวเลขกลับมา",
        "- การอ้างเลขหน้าที่พบในคำตอบเป็นเพียงการตรวจรูปแบบ ไม่พิสูจน์ว่าทุกข้อความถูกต้อง ต้องใช้คะแนน human review",
        "- ผลที่ยังไม่ครบ ห้ามสรุปว่า Hybrid หรือโมเดลใดเหนือกว่าแบบมีนัยสำคัญ",
        "",
        "## 6. วิธีสาธิตและหลักฐานส่งงาน",
        "",
        "เปิด `app.py` ถามหนึ่งคำถามเชิงขั้นตอนและหนึ่งคำถามที่มีเงื่อนไข AVOID สลับ Dense/Graph/Hybrid แล้วชี้ให้เห็นแหล่งข้อมูล เลขหน้า ภาพ และเวลาที่แสดง เปิด `results.jsonl`, `summary.json`, `human_review.csv` เพื่อประกอบการอธิบายผล ไม่แสดง API key ในสไลด์หรือวิดีโอ",
        "",
        "อ้างอิงภายในโครงงาน: `exercise/exercise.pdf`, `data/chunks.json`, `data/knowledge_graph.json`, `evaluation/questions.json`, `src/`, `results/final_project/`",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results" / "final_project")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "FINAL_REPORT_TH.md")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_report(args.results_dir), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
