import sys
import os
import pymupdf as fitz

sys.stdout.reconfigure(encoding='utf-8')
doc = fitz.open("exercise/exercise.pdf")

for page_idx in [15, 18, 19, 20]:  # Pages 16, 19, 20, 21
    page = doc[page_idx]
    image_list = page.get_images(full=True)
    print(f"\n--- Page {page_idx+1} ---")
    for img_idx, img in enumerate(image_list):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        w = base_image["width"]
        h = base_image["height"]
        print(f"  Img {img_idx+1}: xref={xref}, ext={image_ext}, size={w}x{h}, bytes={len(image_bytes)}")
