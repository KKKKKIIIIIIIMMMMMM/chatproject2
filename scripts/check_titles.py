import sys
import pymupdf as fitz

sys.stdout.reconfigure(encoding='utf-8')
doc = fitz.open("exercise/exercise.pdf")

print("Checking content pages 6 to 46:")
for page_idx in range(5, 46):
    text = doc[page_idx].get_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    header_candidate = ""
    for l in lines:
        if any(keyword in l for keyword in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "11.", "12.", "13.", "14.", "15.", "16.", "17.", "18.", "19.", "20.", "21.", "ตารางจุดมุ่งหมาย"]):
            header_candidate = l
            break
    print(f"Page {page_idx+1:2d}: {header_candidate}")
