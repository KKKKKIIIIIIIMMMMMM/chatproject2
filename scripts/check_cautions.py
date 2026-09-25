import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("data/chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

for c in chunks:
    if c["has_cautions"]:
        print(f"[{c['exercise_id']}] {c['title']}:")
        for line in c["content"].split("\n"):
            if "ข้อควรระวังและความปลอดภัย:" in line or any(k in line for k in ["ระวัง", "ห้าม", "หมายเหตุ"]):
                print(f"   -> {line}")
