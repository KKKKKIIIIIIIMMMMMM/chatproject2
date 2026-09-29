"""Render a screenshot-friendly, evidence-labelled comparison from evaluation JSONL."""

from __future__ import annotations

import argparse
import html
import json
import statistics
from pathlib import Path

try:
    import mistune
except ImportError:
    mistune = None


ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ("local", "openrouter")


def latest_rows(path: Path) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("mode") == "hybrid":
                latest[(row["question_id"], row["provider"])] = row
    return latest


def seconds(row: dict | None) -> str:
    value = row.get("total_latency_ms") if row else None
    return f"{value / 1000:.2f} วินาที" if isinstance(value, (int, float)) else "—"


def coverage(row: dict | None) -> str:
    value = row.get("retrieval_coverage") if row else None
    return f"{value * 100:.0f}%" if isinstance(value, (int, float)) else "—"


def source_pages(row: dict | None) -> str:
    pages = row.get("source_pages", []) if row else []
    return ", ".join(str(page) for page in pages) or "ไม่มี"


def model(row: dict | None) -> str:
    return str(row.get("model") or "—") if row else "—"


def average_seconds(rows: list[dict]) -> str:
    values = [row["total_latency_ms"] / 1000 for row in rows
              if row.get("status") == "ok" and isinstance(row.get("total_latency_ms"), (int, float))]
    return f"{statistics.mean(values):.2f}" if values else "—"


def average_coverage(rows: list[dict]) -> str:
    values = [row["retrieval_coverage"] for row in rows
              if row.get("status") == "ok" and isinstance(row.get("retrieval_coverage"), (int, float))]
    return f"{statistics.mean(values) * 100:.1f}%" if values else "—"


def render_answer(answer: str) -> str:
    if mistune is not None:
        return mistune.create_markdown(escape=True)(answer)
    return html.escape(answer).replace("\n", "<br>")


def card(row: dict | None, label: str) -> str:
    if not row:
        return f'<article class="answer"><h3>{html.escape(label)}</h3><p>ไม่มีผลการทดลอง</p></article>'
    ok = row.get("status") == "ok"
    answer = row.get("answer", "") if ok else f"รันไม่สำเร็จ: {row.get('error_type', 'unknown')}"
    flagged = row.get("unsupported_cited_pages") or []
    flag_html = (f'<p class="flag">ควรตรวจเลขหน้าที่โมเดลอ้าง: {html.escape(", ".join(map(str, flagged)))}</p>'
                 if flagged else "")
    return (
        '<article class="answer">'
        f'<h3>{html.escape(label)} <small>{html.escape(model(row))}</small></h3>'
        f'<p class="metrics">เวลา {seconds(row)} · พบหน้าที่คาดหวัง {coverage(row)}'
        f' · หน้าที่ค้นได้ {html.escape(source_pages(row))}</p>'
        f'{flag_html}<div class="response">{render_answer(str(answer))}</div>'
        '</article>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    result_dir = args.result_dir.resolve()
    rows = latest_rows(result_dir / "results.jsonl")
    questions = json.loads((ROOT / "evaluation" / "questions.json").read_text(encoding="utf-8"))
    question_rows = [(question, rows.get((question["id"], "local")),
                      rows.get((question["id"], "openrouter"))) for question in questions]
    by_provider = {provider: [row for (qid, p), row in rows.items() if p == provider]
                   for provider in PROVIDERS}
    models = {provider: sorted({model(row) for row in by_provider[provider] if row.get("status") == "ok"})
              for provider in PROVIDERS}
    backends = sorted({str(row.get("graph_backend") or "none") for row in rows.values()
                       if row.get("status") == "ok"})
    costs = [(row.get("usage") or {}).get("cost") for row in by_provider["openrouter"]
             if row.get("status") == "ok"]
    reported_costs = [float(cost) for cost in costs if isinstance(cost, (int, float))]
    cost_text = f"${sum(reported_costs):.4f}" if reported_costs else "API ไม่รายงาน"
    local_flags = sum(bool(row.get("unsupported_cited_pages")) for row in by_provider["local"])
    api_flags = sum(bool(row.get("unsupported_cited_pages")) for row in by_provider["openrouter"])

    summary_rows = []
    sections = []
    for question, local, api in question_rows:
        qid = question["id"]
        summary_rows.append(
            f'<tr><td><a href="#{qid}">{qid}</a></td><td>{html.escape(question["category"])}</td>'
            f'<td>{seconds(local)}</td><td>{seconds(api)}</td>'
            f'<td>{coverage(local)}</td><td>{coverage(api)}</td></tr>'
        )
        sections.append(
            f'<section class="question" id="{qid}"><div class="question-head">'
            f'<span class="qid">{qid}</span><h2>{html.escape(question["question"])}</h2></div>'
            f'<p class="expected">หน้าคู่มือที่คาดหวัง: '
            f'{html.escape(", ".join(map(str, question.get("expected_source_pages", []))) or "ไม่มี")}'
            f' · Graph backend: {html.escape(str(local.get("graph_backend") if local else "—"))}</p>'
            f'<div class="columns">{card(local, "Local")}{card(api, "API")}</div></section>'
        )

    style = """
    :root{font-family:Arial,'Noto Sans Thai',sans-serif;color:#17212b;background:#f2f5f8}
    body{margin:0 auto;max-width:1450px;padding:30px 24px 80px}
    h1{font-size:2rem;margin:0 0 8px}h2{font-size:1.13rem;margin:0}h3{margin:0;font-size:1.12rem}
    small{font-size:.78rem;font-weight:400;color:#536475;display:block;margin-top:5px}
    .subtitle,.note,.expected,.metrics{color:#526476}.note{background:#fff1d4;padding:14px 18px;border-radius:10px}
    .stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:22px 0}
    .stat,.question{background:white;border:1px solid #dce4ed;border-radius:14px;padding:20px}
    .stat strong{font-size:1.3rem;display:block;margin:8px 0}.stat span{color:#536475}
    table{border-collapse:collapse;width:100%;background:white;font-size:.9rem}
    th,td{padding:9px 11px;text-align:left;border-bottom:1px solid #e3e8ee}th{background:#dfe8f2;position:sticky;top:0}
    a{color:#1258a4}.question{margin-top:24px;scroll-margin-top:20px;break-inside:avoid}
    .question-head{display:flex;gap:10px;align-items:flex-start}.qid{background:#173b63;color:white;border-radius:6px;padding:4px 8px;font-weight:bold}
    .columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
    .answer{border:1px solid #dce4ed;border-radius:10px;padding:16px;min-width:0}
    .answer:nth-child(1){border-top:5px solid #229d77}.answer:nth-child(2){border-top:5px solid #4774ca}
    .metrics{font-size:.86rem}.flag{color:#8c351e;background:#fff0e8;border-radius:6px;padding:8px 10px;font-size:.85rem}
    .response{overflow-wrap:anywhere;line-height:1.58}.response p{margin:0 0 .75em}.response ul,.response ol{padding-left:1.5em}
    @media(max-width:800px){.columns,.stats{grid-template-columns:1fr}body{padding:18px 12px}table{font-size:.76rem}}
    @media print{body{background:white;max-width:none;padding:0}.question{box-shadow:none}.note{background:#fff5dc}th{position:static}}
    """
    page = f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>Local 9B vs API — 20 คำถาม</title>
    <style>{style}</style></head><body><h1>เปรียบเทียบ Local 9B กับ API: 20 คำถาม</h1>
    <p class="subtitle">คำถามชุดเดียวกัน · Hybrid Retrieval · top-k 4 · Local: {html.escape(', '.join(models['local']))}
    · API: {html.escape(', '.join(models['openrouter']))} · Backend: {html.escape(', '.join(backends))}</p>
    <div class="stats"><div class="stat"><span>Local</span><strong>{average_seconds(by_provider['local'])} วินาทีเฉลี่ย</strong>
    พบหน้าที่คาดหวังเฉลี่ย {average_coverage(by_provider['local'])} · สำเร็จ {sum(r.get('status') == 'ok' for r in by_provider['local'])}/20
    · ควรตรวจเลขหน้าที่อ้าง {local_flags} กรณี</div>
    <div class="stat"><span>API</span><strong>{average_seconds(by_provider['openrouter'])} วินาทีเฉลี่ย</strong>
    พบหน้าที่คาดหวังเฉลี่ย {average_coverage(by_provider['openrouter'])} · สำเร็จ {sum(r.get('status') == 'ok' for r in by_provider['openrouter'])}/20
    · ควรตรวจเลขหน้าที่อ้าง {api_flags} กรณี · ค่าใช้จ่ายที่ API รายงาน {cost_text}</div></div>
    <p class="note">ตัวเลข “พบหน้าที่คาดหวัง” เป็นผลการค้นเอกสาร ไม่ใช่คะแนนความถูกต้องของคำตอบหรือการตัดสินว่าโมเดลใดดีกว่า
    ตัวตรวจเลขหน้าเป็นกฎอัตโนมัติ อาจมีทั้งผลบวกลวงและข้อผิดพลาดที่ตรวจไม่พบ
    ควรอ่านคำตอบคู่กันและให้คนตรวจความถูกต้อง การอ้างหลักฐาน และความปลอดภัยก่อนสรุปคุณภาพ</p>
    <h2>ภาพรวม 20 คำถาม</h2><table><thead><tr><th>ID</th><th>ประเภท</th><th>Local</th><th>API</th>
    <th>พบหน้า Local</th><th>พบหน้า API</th></tr></thead><tbody>{''.join(summary_rows)}</tbody></table>
    {''.join(sections)}</body></html>"""
    output = result_dir / "comparison.html"
    output.write_text(page, encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
