import pymupdf as fitz
import sys

sys.stdout.reconfigure(encoding='utf-8')
doc = fitz.open("exercise/exercise.pdf")
text = doc[6].get_text() # Page 7
print("Page 7 raw text sample:")
for l in text.split("\n")[:10]:
    if "หนัก" in l or "หน้า" in l:
        print(repr(l))
