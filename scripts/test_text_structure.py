import sys
import os
import pymupdf as fitz
import re

sys.stdout.reconfigure(encoding='utf-8')
doc = fitz.open("exercise/exercise.pdf")

pages_data = []

for idx in range(5, 46): # pages 6 to 46
    page = doc[idx]
    text = page.get_text()
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    pages_data.append({
        "page_number": idx + 1,
        "raw_text": text,
        "lines": lines
    })

print(f"Read {len(pages_data)} content pages.")
for p in pages_data[:5]:
    print(f"\nPage {p['page_number']}:")
    for l in p['lines'][:6]:
        print(f"  {l}")
