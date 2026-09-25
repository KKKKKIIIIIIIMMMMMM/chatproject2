import sys
import os
import pymupdf as fitz

sys.stdout.reconfigure(encoding='utf-8')
pdf_path = "exercise/exercise.pdf"
doc = fitz.open(pdf_path)

print(f"Total pages: {len(doc)}")

for page_idx in range(len(doc)):
    page = doc[page_idx]
    image_list = page.get_images(full=True)
    text = page.get_text()
    first_line = text.strip().split("\n")[0] if text.strip() else "(No text)"
    print(f"Page {page_idx+1}: {len(image_list)} images, First line: {first_line[:60]}")
