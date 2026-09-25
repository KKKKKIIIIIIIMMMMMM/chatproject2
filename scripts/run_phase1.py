import os
import sys
import json
import re
import csv
import io
import pymupdf as fitz
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

# 1. Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(BASE_DIR, "exercise", "exercise.pdf")
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# 2. Text Normalization
def clean_thai_text(text: str) -> str:
    """แก้สระอำและวรรณยุกต์ลอยที่เกิดจากการแปลง PDF ภาษาไทยแบบแม่นยำ"""
    # คำเฉพาะที่มักผิดเพี้ยนจากการแปลง PDF
    text = text.replace("ก้าลังกาย", "กำลังกาย")
    text = text.replace("ล้าตัว", "ลำตัว")
    text = text.replace("น้าหนัก", "น้ำหนัก")
    text = text.replace("กล้าเนื้อ", "กล้ามเนื้อ")
    text = text.replace("หน้ำอก", "หน้าอก")
    text = text.replace("หน้ำท้อง", "หน้าท้อง")
    text = text.replace("ด้านหน้ำ", "ด้านหน้า")
    
    # สระอำที่แยกช่องว่าง
    text = text.replace("ก า", "กำ")
    text = text.replace("น้ า", "น้ำ")
    text = text.replace("ท า", "ทำ")
    text = text.replace("ค า", "คำ")
    text = text.replace("ซ้ า", "ซ้ำ")
    text = text.replace("จ า", "จำ")
    text = text.replace("ล า", "ลำ")
    text = text.replace("ต า", "ตำ")
    text = text.replace("ย า", "ยำ")
    text = text.replace("อ า", "อำ")
    text = text.replace("ล๊อด", "ล็อค").replace("ล๊อก", "ล็อค")
    
    # ลบ Header คู่มือการใช้เครื่องมือ...
    text = re.sub(r'คู่\s*มือ\s*การ\s*ใช้\s*เครื่อง\s*มือ\s*ออก\s*กำ\s*ลัง\s*กาย[^\n]*', '', text)
    text = re.sub(r'คู่\s*มื\s*อ\s*ก\s*า\s*ร\s*ใ\s*ช้[^\n]*', '', text)
    return text.strip()


# 3. Open PDF
doc = fitz.open(PDF_PATH)
print(f"[Phase 1] Opened PDF: {PDF_PATH} ({len(doc)} pages)")

# 4. Define exercise page metadata
pages_meta = [
    # Aerobic (Pages 6-9)
    {"page": 6, "slug": "01_bike", "zone": "Aerobic Exercise Group", "muscle_group": "หัวใจและหลอดเลือด (Cardio)", "equipment": "จักรยานฟิตเนส (Stationary Bike)"},
    {"page": 7, "slug": "02_treadmill", "zone": "Aerobic Exercise Group", "muscle_group": "หัวใจและหลอดเลือด (Cardio)", "equipment": "ลู่วิ่งไฟฟ้า (Treadmill)"},
    {"page": 8, "slug": "03_elliptical", "zone": "Aerobic Exercise Group", "muscle_group": "หัวใจและหลอดเลือด (Cardio)", "equipment": "เครื่องเดินวงรี (Elliptical)"},
    {"page": 9, "slug": "04_rower", "zone": "Aerobic Exercise Group", "muscle_group": "หัวใจและหลอดเลือด (Cardio)", "equipment": "เครื่องกรรเชียงบก (Rowing Machine)"},
    
    # Weight Machine (Pages 10-30)
    {"page": 10, "slug": "05_torso_twist", "zone": "Weight Machine Zone", "muscle_group": "หน้าท้องและลำตัว (Abdominal & Obliques)", "equipment": "Machine (Torso Twist)"},
    {"page": 11, "slug": "06_abdominal_machine", "zone": "Weight Machine Zone", "muscle_group": "หน้าท้องและลำตัว (Abdominal)", "equipment": "Machine (Abdominal)"},
    {"page": 12, "slug": "07_leg_press", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Leg Press)"},
    {"page": 13, "slug": "08_leg_extension", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Leg Extension)"},
    {"page": 14, "slug": "09_leg_curl", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Leg Curl)"},
    {"page": 15, "slug": "10_calf_raise", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Calf Raise)"},
    {"page": 16, "slug": "11_inner_outer_thigh", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Thigh Machine)"},
    {"page": 17, "slug": "12_inner_thigh", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Inner Thigh)"},
    {"page": 18, "slug": "13_outer_thigh", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อขา (Leg Group)", "equipment": "Machine (Outer Thigh)"},
    {"page": 19, "slug": "14_pec_dek", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Machine (Pec Dek Fly)"},
    {"page": 20, "slug": "15_incline_press", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Machine (Incline Chest Press)"},
    {"page": 21, "slug": "16_chest_press", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Machine (Chest Press)"},
    {"page": 22, "slug": "17_shoulder_press", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อหัวไหล่ (Shoulder Group)", "equipment": "Machine (Shoulder Press)"},
    {"page": 23, "slug": "18_lat_pulldown", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อปีกและหลัง (Back Group)", "equipment": "Machine (Lat Pulldown)"},
    {"page": 24, "slug": "19_seated_row", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อปีกและหลัง (Back Group)", "equipment": "Machine (Seated Cable Row)"},
    {"page": 25, "slug": "20_hyper_extension", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อปีกและหลัง (Back Group)", "equipment": "Roman Chair (Hyper Extension)"},
    {"page": 26, "slug": "21_arms_curl", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Biceps Group)", "equipment": "Machine (Arm Curl)"},
    {"page": 27, "slug": "22_triceps_extension", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Triceps Group)", "equipment": "Machine (Triceps Extension)"},
    {"page": 28, "slug": "23_triceps_press_down", "zone": "Weight Machine Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Triceps Group)", "equipment": "Cable Machine (Triceps Press Down)"},
    {"page": 29, "slug": "24_sit_up", "zone": "Weight Machine Zone", "muscle_group": "หน้าท้องและลำตัว (Abdominal)", "equipment": "Abdominal Bench (Sit Up Bench)"},
    {"page": 30, "slug": "25_verticals_knee_raise", "zone": "Weight Machine Zone", "muscle_group": "หน้าท้องและลำตัว (Abdominal)", "equipment": "Captain's Chair (Knee Raise Station)"},

    # Free Weight Zone (Pages 31-45)
    {"page": 31, "slug": "26_alt_dumbbell_curl", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Biceps Group)", "equipment": "Dumbbell"},
    {"page": 32, "slug": "27_dumbbell_curl", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Biceps Group)", "equipment": "Dumbbell"},
    {"page": 33, "slug": "28_dumbbell_conc_curl", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Biceps Group)", "equipment": "Dumbbell"},
    {"page": 34, "slug": "29_dumbbell_french_press", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Triceps Group)", "equipment": "Dumbbell"},
    {"page": 35, "slug": "30_two_arm_ext", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Triceps Group)", "equipment": "Dumbbell"},
    {"page": 36, "slug": "31_kick_back", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อแขน (Triceps Group)", "equipment": "Dumbbell & Bench"},
    {"page": 37, "slug": "32_dumbbell_press", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อหัวไหล่ (Shoulder Group)", "equipment": "Dumbbell"},
    {"page": 38, "slug": "33_dumbbell_raise_front", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อหัวไหล่ (Shoulder Group)", "equipment": "Dumbbell"},
    {"page": 39, "slug": "34_dumbbell_lateral_raise", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อหัวไหล่ (Shoulder Group)", "equipment": "Dumbbell"},
    {"page": 40, "slug": "35_dumbbell_row", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อปีกและหลัง (Back Group)", "equipment": "Dumbbell & Bench"},
    {"page": 41, "slug": "36_two_arm_dumbbell_row", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้อปีกและหลัง (Back Group)", "equipment": "Dumbbell"},
    {"page": 42, "slug": "37_dumbbell_bench_press", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Dumbbell & Flat Bench"},
    {"page": 43, "slug": "38_dumbbell_flies", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Dumbbell & Flat Bench"},
    {"page": 44, "slug": "39_pullovers", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Dumbbell & Bench"},
    {"page": 45, "slug": "40_decline_dumbbell_press", "zone": "Free Weight Zone", "muscle_group": "กลุ่มกล้ามเนื้ออก (Chest Group)", "equipment": "Dumbbell & Decline Bench"}
]

# 5. Extract Images and Clean Text
exercises_data = []

print("\n--- Extracting Images & Parsing Text ---")
for meta in pages_meta:
    page_num = meta["page"]
    slug = meta["slug"]
    page = doc[page_num - 1]
    
    # 5.1 Extract Photos (JPEG > 20KB)
    image_list = page.get_images(full=True)
    photo_images = []
    
    for img in image_list:
        xref = img[0]
        base_image = doc.extract_image(xref)
        # กรองเฉพาะ JPEG ที่เป็นรูปถ่ายจริง (ไม่ใช่ขอบ PNG เล็กๆ)
        if base_image["ext"] in ["jpeg", "jpg"] and len(base_image["image"]) > 10000:
            photo_images.append(Image.open(io.BytesIO(base_image["image"])))
            
    img_filename = f"{slug}.jpg"
    img_filepath = os.path.join(IMAGES_DIR, img_filename)
    relative_img_path = f"data/images/{img_filename}"
    
    if len(photo_images) == 1:
        photo_images[0].convert("RGB").save(img_filepath, "JPEG", quality=90)
    elif len(photo_images) >= 2:
        # รวม 2 รูปแบบ Side-by-Side (ท่าเริ่มต้น + ท่าสิ้นสุด)
        img1 = photo_images[0]
        img2 = photo_images[1]
        target_height = min(img1.height, img2.height)
        img1_resized = img1.resize((int(img1.width * target_height / img1.height), target_height))
        img2_resized = img2.resize((int(img2.width * target_height / img2.height), target_height))
        
        combined_width = img1_resized.width + img2_resized.width + 10
        combined_img = Image.new("RGB", (combined_width, target_height), (255, 255, 255))
        combined_img.paste(img1_resized, (0, 0))
        combined_img.paste(img2_resized, (img1_resized.width + 10, 0))
        combined_img.save(img_filepath, "JPEG", quality=90)
    else:
        # Fallback: render page clip as image if no raw jpeg found
        pix = page.get_pixmap(dpi=150)
        pix.save(img_filepath)
        
    # 5.2 Parse Text
    raw_text = clean_thai_text(page.get_text())
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    
    # Extract Title
    title = lines[0] if lines else slug
    # If first line was zone name, pick second line
    if any(z in title for z in ["Aerobic Exercise Group", "การออกก", "Weight Machine Zone", "Free Weight Zone", "กลุ่มกล้าม"]):
        if len(lines) > 1:
            title = lines[1]
            
    # Parse Sections
    text_content = "\n".join(lines)
    
    # Extract Muscle
    muscle_match = re.search(r'กล้ามเนื้อที่ใช้\s*([^\n]+)', text_content)
    target_muscle = muscle_match.group(1).strip() if muscle_match else meta["muscle_group"]
    
    # Extract Cautions / Notes
    cautions = []
    for idx_l, line in enumerate(lines):
        if any(k in line for k in ["ระวัง", "ห้าม"]):
            cautions.append(line)
        elif "หมายเหตุ" in line:
            if len(line) <= 15 and idx_l + 1 < len(lines):
                cautions.append(f"{line}: {lines[idx_l+1]}")
            else:
                cautions.append(line)

                
    exercise_entry = {
        "id": slug,
        "page": page_num,
        "title": title,
        "zone": meta["zone"],
        "muscle_group": meta["muscle_group"],
        "equipment": meta["equipment"],
        "target_muscles": target_muscle,
        "cautions": cautions,
        "image_path": relative_img_path,
        "full_text": text_content
    }
    exercises_data.append(exercise_entry)
    print(f"  [OK] Page {page_num:2d} -> {title} (Saved image: {img_filename})")

# 6. Parse Page 46: Objective Table (ตารางจุดมุ่งหมายในการฝึก)
page_46_text = clean_thai_text(doc[45].get_text())
objectives_data = [
    {
        "id": "obj_endurance",
        "name": "ความทนทานของกล้ามเนื้อ (Endurance)",
        "one_rep_max": "30 – 50% of 1RM",
        "repetitions": "12 – 15 ครั้ง",
        "sets": "3 – 5 เซต",
        "description": "เน้นเพิ่มความทนทาน กล้ามเนื้อทำงานได้ยาวนาน ไม่เมื่อยล้าง่าย เหมาะสำหรับผู้เริ่มต้นและกระชับสัดส่วน"
    },
    {
        "id": "obj_strength",
        "name": "ความแข็งแรงของกล้ามเนื้อ (Strength)",
        "one_rep_max": "70 – 90% of 1RM",
        "repetitions": "6 – 8 ครั้ง",
        "sets": "4 – 5 เซต",
        "description": "เน้นสร้างความแข็งแรงและขนาดกล้ามเนื้อ (Hypertrophy/Strength) ใช้น้ำหนักมาก จำนวนครั้งน้อย"
    },
    {
        "id": "obj_power",
        "name": "กำลังและความเร็ว (Power)",
        "one_rep_max": "50 – 70% of 1RM",
        "repetitions": "8 – 10 ครั้ง",
        "sets": "3 – 4 เซต",
        "description": "เน้นสร้างพลังระเบิดและความเร็วในการออกแรง (Explosive Power) ของกล้ามเนื้อ"
    },
    {
        "id": "obj_cardio",
        "name": "ระบบไหลเวียนเลือดและหัวใจ (Cardiovascular)",
        "one_rep_max": "20 – 30% of 1RM",
        "repetitions": "15 – 20 ครั้ง",
        "sets": "3 – 5 เซต",
        "description": "เน้นพัฒนาการทำงานของหัวใจและปอด เผาผลาญพลังงาน และกระตุ้นการไหลเวียนโลหิต"
    }
]

# 7. Generate chunks.json for ChromaDB (Dense RAG)
chunks = []
chunk_counter = 1

for ex in exercises_data:
    # Formulate rich descriptive chunk text
    chunk_text = (
        f"ชื่อท่า/เครื่องออกกำลังกาย: {ex['title']}\n"
        f"โซนอุปกรณ์: {ex['zone']}\n"
        f"กลุ่มกล้ามเนื้อหลัก: {ex['muscle_group']}\n"
        f"กล้ามเนื้อที่บริหาร: {ex['target_muscles']}\n"
        f"อุปกรณ์ที่ใช้: {ex['equipment']}\n\n"
        f"รายละเอียดและวิธีการฝึก:\n{ex['full_text']}\n"
    )
    if ex['cautions']:
        chunk_text += f"\nข้อควรระวังและความปลอดภัย:\n" + "\n".join(ex['cautions'])
        
    chunk_item = {
        "chunk_id": f"chunk_{chunk_counter:03d}",
        "exercise_id": ex["id"],
        "title": ex["title"],
        "zone": ex["zone"],
        "muscle_group": ex["muscle_group"],
        "target_muscles": ex["target_muscles"],
        "equipment": ex["equipment"],
        "page_number": ex["page"],
        "image_path": ex["image_path"],
        "has_cautions": len(ex["cautions"]) > 0,
        "content_type": "exercise_guide",
        "content": chunk_text
    }
    chunks.append(chunk_item)
    chunk_counter += 1

# Add objective table chunks
for obj in objectives_data:
    obj_text = (
        f"เป้าหมายการฝึก: {obj['name']}\n"
        f"ความหนักสูงสุด (% of 1RM): {obj['one_rep_max']}\n"
        f"จำนวนครั้งต่อเซต (Repetitions): {obj['repetitions']}\n"
        f"จำนวนเซต (Sets): {obj['sets']}\n"
        f"คำอธิบายและแนวทางการฝึก: {obj['description']}\n"
    )
    chunks.append({
        "chunk_id": f"chunk_{chunk_counter:03d}",
        "exercise_id": obj["id"],
        "title": obj["name"],
        "zone": "Training Principle",
        "muscle_group": "General Fitness",
        "target_muscles": "All Muscles",
        "equipment": "All Equipment",
        "page_number": 46,
        "image_path": "",
        "has_cautions": False,
        "content_type": "training_objective",
        "content": obj_text
    })
    chunk_counter += 1

chunks_path = os.path.join(DATA_DIR, "chunks.json")
with open(chunks_path, "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)
print(f"\n[OK] Generated {len(chunks)} chunks in {chunks_path}")

# 8. Generate Graph Data (Neo4j Entities & Relationships)
graph_triples = []

# Rules for condition-based avoidance & recommendations
conditions_rules = [
    {
        "condition": "ปวดหลังล่าง (Lower Back Pain)",
        "avoid": ["20_hyper_extension", "35_dumbbell_row"],
        "recommend": ["18_lat_pulldown", "19_seated_row", "03_elliptical"],
        "reason": "ควรหลีกเลี่ยงท่าที่แอ่นหลังหรือก้มยกน้ำหนักที่เสี่ยงกดทับกระดูกสันหลัง ให้ใช้ท่าที่มีเบาะรองหลังและดึงในแนวระนาบแทน"
    },
    {
        "condition": "ปวดข้อเข่า (Knee Pain)",
        "avoid": ["07_leg_press", "08_leg_extension", "02_treadmill"],
        "recommend": ["01_bike", "03_elliptical", "10_calf_raise"],
        "reason": "หลีกเลี่ยงแรงกระแทกจากลู่วิ่งและแรงกดที่ข้อต่อเข่าในท่าเหยียดขาหนักๆ แนะนำให้ปั่นจักรยานหรือเดินวงรีแบบไร้แรงกระแทกแทน"
    },
    {
        "condition": "ปวดหัวไหล่ / ข้อต่อไหล่ติด (Shoulder Impingement)",
        "avoid": ["17_shoulder_press", "32_dumbbell_press"],
        "recommend": ["16_chest_press", "21_arms_curl"],
        "reason": "หลีกเลี่ยงการดันน้ำหนักขึ้นเหนือศีรษะที่อาจทำให้ข้อต่อไหล่ถูกกดทับหรือเสียดสี"
    },
    {
        "condition": "ผู้เริ่มต้นฝึกออกกำลังกาย (Beginner)",
        "avoid": ["34_dumbbell_lateral_raise", "40_decline_dumbbell_press"],
        "recommend": ["01_bike", "07_leg_press", "16_chest_press", "18_lat_pulldown"],
        "reason": "ผู้เริ่มต้นควรฝึกด้วยเครื่อง Weight Machine ที่มีวิถีการเคลื่อนที่แน่นอนเพื่อความปลอดภัยและโฟกัสกล้ามเนื้อได้ถูกต้อง"
    }
]

for ex in exercises_data:
    ex_name = ex["title"]
    # Exercise -> Zone
    graph_triples.append({"source": ex_name, "source_label": "Exercise", "relation": "LOCATED_IN", "target": ex["zone"], "target_label": "Zone"})
    
    # Exercise -> MuscleGroup
    graph_triples.append({"source": ex_name, "source_label": "Exercise", "relation": "TARGETS_GROUP", "target": ex["muscle_group"], "target_label": "MuscleGroup"})
    
    # Exercise -> Equipment
    graph_triples.append({"source": ex_name, "source_label": "Exercise", "relation": "USES_EQUIPMENT", "target": ex["equipment"], "target_label": "Equipment"})
    
    # Exercise -> Specific Muscles
    # Parse individual muscles
    muscles_raw = ex["target_muscles"]
    muscles_found = re.findall(r'([A-Za-z\s]+|กล้ามเนื้อ[ก-๙]+|ต้นขา[ก-๙]+|หัวใจ|ปีก|สะบัก|น่อง|หน้าท้อง)', muscles_raw)
    for m in set(muscles_found):
        m = m.strip()
        if len(m) > 2 and m not in ["and", "of"]:
            graph_triples.append({"source": ex_name, "source_label": "Exercise", "relation": "TARGETS", "target": m, "target_label": "Muscle"})

    # Cautions
    for c in ex["cautions"]:
        graph_triples.append({"source": ex_name, "source_label": "Exercise", "relation": "HAS_CAUTION", "target": c, "target_label": "Caution"})

# Add Condition Triples
for cr in conditions_rules:
    cond_name = cr["condition"]
    for ex_id in cr["avoid"]:
        matching_ex = next((e["title"] for e in exercises_data if e["id"] == ex_id), None)
        if matching_ex:
            graph_triples.append({"source": cond_name, "source_label": "Condition", "relation": "AVOID", "target": matching_ex, "target_label": "Exercise"})
    for ex_id in cr["recommend"]:
        matching_ex = next((e["title"] for e in exercises_data if e["id"] == ex_id), None)
        if matching_ex:
            graph_triples.append({"source": cond_name, "source_label": "Condition", "relation": "RECOMMEND", "target": matching_ex, "target_label": "Exercise"})

# Save graph_data.csv
csv_path = os.path.join(DATA_DIR, "graph_data.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["source", "source_label", "relation", "target", "target_label"])
    writer.writeheader()
    writer.writerows(graph_triples)
print(f"[OK] Generated {len(graph_triples)} graph triples in {csv_path}")

# 9. Generate Cypher Script (init_neo4j.cypher)
cypher_lines = [
    "// ==========================================",
    "// Neo4j Initialization Script: Fitness Graph",
    "// Generated automatically for Final Project",
    "// ==========================================\n",
    "// 1. Create Constraints",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Exercise) REQUIRE e.name IS UNIQUE;",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Muscle) REQUIRE m.name IS UNIQUE;",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (mg:MuscleGroup) REQUIRE mg.name IS UNIQUE;",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (z:Zone) REQUIRE z.name IS UNIQUE;",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Condition) REQUIRE c.name IS UNIQUE;\n",
    "// 2. Clear Existing Data (Optional)",
    "// MATCH (n) DETACH DELETE n;\n",
    "// 3. Create Nodes & Relationships"
]

# Create Nodes
for ex in exercises_data:
    c_title = ex["title"].replace("'", "\\'")
    c_zone = ex["zone"].replace("'", "\\'")
    c_grp = ex["muscle_group"].replace("'", "\\'")
    c_img = ex["image_path"].replace("'", "\\'")
    c_eq = ex["equipment"].replace("'", "\\'")
    cypher_lines.append(f"MERGE (e:Exercise {{name: '{c_title}'}}) SET e.zone = '{c_zone}', e.image_path = '{c_img}', e.equipment = '{c_eq}', e.page = {ex['page']};")

for t in graph_triples:
    s = t["source"].replace("'", "\\'")
    s_label = t["source_label"]
    rel = t["relation"]
    tgt = t["target"].replace("'", "\\'")
    t_label = t["target_label"]
    cypher_lines.append(f"MERGE (a:{s_label} {{name: '{s}'}}) MERGE (b:{t_label} {{name: '{tgt}'}}) MERGE (a)-[:{rel}]->(b);")

cypher_path = os.path.join(DATA_DIR, "init_neo4j.cypher")
with open(cypher_path, "w", encoding="utf-8") as f:
    f.write("\n".join(cypher_lines))
print(f"[OK] Generated Cypher script ({len(cypher_lines)} lines) in {cypher_path}")

print("\n" + "="*50)
print("🎯 [Phase 1 COMPLETE] All assets and datasets ready!")
print(f"1. Extracted Images: {len(os.listdir(IMAGES_DIR))} files in {IMAGES_DIR}")
print(f"2. Vector Chunks: {len(chunks)} items in {chunks_path}")
print(f"3. Graph Triples: {len(graph_triples)} relationships in {csv_path}")
print(f"4. Neo4j Cypher: {cypher_path}")
print("="*50)
