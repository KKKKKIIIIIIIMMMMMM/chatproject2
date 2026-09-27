# 🏋️ Workflow: ระบบผู้ช่วยอัจฉริยะ GraphRAG & LLMs สำหรับคู่มือการออกกำลังกาย
### อ้างอิงจากเอกสาร: `exercise.pdf` (คู่มือสถานกีฬาและสุขภาพ มทส. 46 หน้า, 35 ท่า/เครื่อง)
### เกณฑ์การประเมิน: Rubric ระดับคุณภาพ Final Project (เป้าหมาย Level 5 เต็ม 100 คะแนน)

---

## 📌 Phase 1: เตรียมข้อมูลและสกัด Asset (Data & Asset Preparation)

* **ขั้นตอนที่ 1.1: แหล่งข้อมูลต้นฉบับ (Source File)**
  * **ไฟล์:** `exercise/exercise.pdf` (46 หน้า ครอบคลุม 4 Aerobic, 17 Weight Machines, 14 Free Weights และตาราง 1RM)
* **ขั้นตอนที่ 1.2: คลีนข้อความ (Text Cleaning & Extraction)**
  * **ทำอะไร:** แปลง PDF เป็นข้อความ Text สะอาด ลบเลขหน้า หัวกระดาษ และสัญลักษณ์แปลกปลอม แยกเนื้อหาตาม 35 ท่า/เครื่อง
* **ขั้นตอนที่ 1.3: สกัดรูปภาพและจัดเก็บแยก (Image Extraction & Asset Management)**
  * **ทำอะไร:** เขียนสคริปต์สกัดรูปถ่ายสาธิตท่าทางจริงจาก PDF บันทึกลงในโฟลเดอร์ `images/` แยกตามชื่อท่าอย่างเป็นระบบ
  * **ผลลัพธ์:** ได้ไฟล์รูปภาพ เช่น `images/01_bike.jpg`, `images/12_leg_press.jpg`, `images/24_seated_row.jpg` เพื่อนำไปใช้เป็น Visual Metadata
* **ขั้นตอนที่ 1.4: แตกข้อมูลเป็น Chunks สำหรับ Vector (ChromaDB) พร้อมผูกรูปภาพ**
  * **ทำอะไร:** หั่นเนื้อหาขั้นตอนการเล่น, การปรับเบาะ, จังหวะหายใจ และข้อควรระวังออกเป็น Chunks ละ ~400 ตัวอักษร
  * **ผลลัพธ์:** ได้ไฟล์ `chunks.json` โดยแต่ละ Chunk มีฟิลด์ Metadata ครบถ้วน:
    * `exercise_name`: "Leg press"
    * `zone`: "Weight Machine Zone"
    * `target_muscles`: "ต้นขาด้านหน้าและสะโพก (Quadriceps & Gluteus)"
    * `image_path`: "images/12_leg_press.jpg" (ผูก Path รูปภาพไว้สำหรับแสดงผล)
    * `text`: "วิธีการใช้งาน 1. ปรับเบาะให้เหมาะสมกับสรีระ..."
* **ขั้นตอนที่ 1.5: สกัดความสัมพันธ์สำหรับ Graph (Neo4j) พร้อมผูกรูปภาพ**
  * **ทำอะไร:** สกัดความสัมพันธ์ระดับ Entity เป็นตาราง CSV หรือ JSON
  * **ผลลัพธ์:** ได้ไฟล์ `graph_data.csv` ประกอบด้วย:
    * **Nodes:** `Exercise` (มี Property: `name`, `zone`, `image_path`), `Muscle`, `MuscleGroup`, `Caution`, `Objective`
    * **Relationships:**
      * `(:Exercise {name: 'Leg press', image_path: 'images/12_leg_press.jpg'}) -[:TARGETS]-> (:Muscle {name: 'Quadriceps'})`
      * `(:Muscle {name: 'Quadriceps'}) -[:PART_OF]-> (:MuscleGroup {name: 'ขา'})`
      * `(:Condition {name: 'ปวดหลังล่าง'}) -[:AVOID]-> (:Exercise {name: 'Hyper Extension'})`
      * `(:Condition {name: 'ปวดหลังล่าง'}) -[:RECOMMEND]-> (:Exercise {name: 'Seated Row'})`

---

## 📌 Phase 2: บันทึกข้อมูลลง 2 ฐานข้อมูล (Dual Databases Setup)

* **ขั้นตอนที่ 2.1: บันทึกลง ChromaDB (ฝั่ง Dense)**
  * **ทำอะไร:** โหลด `chunks.json` แปลงข้อความเป็น Vector ด้วย Embedding Model (เช่น `sentence-transformers` หรือ OpenAI) เซฟลง ChromaDB พร้อม Metadata (รวมถึง `image_path`)
* **ขั้นตอนที่ 2.2: บันทึกลง Neo4j (ฝั่ง Graph)**
  * **ทำอะไร:** รัน Cypher Script นำเข้า `graph_data.csv` เข้า Neo4j (Desktop หรือ AuraDB Cloud) สร้างโครงข่ายความรู้ Node และ Relationship ครบถ้วน รวมถึงใส่ Property `image_path` ให้ Node

---

## 📌 Phase 3: เขียนฟังก์ชันค้นหาข้อมูลของแต่ละฝั่ง (Retrieval Implementation)

* **ขั้นตอนที่ 3.1: ฟังก์ชันค้นหา Vector (`search_dense`)**
  * **ทำอะไร:** รับคำถาม ค้นหาท่อนข้อความที่คล้ายคลึงที่สุด (Top-K = 3) พร้อมดึงข้อความอธิบายและ `image_path`
* **ขั้นตอนที่ 3.2: ฟังก์ชันค้นหา Graph (`search_graph`)**
  * **ทำอะไร:** วิเคราะห์ Entity จากคำถาม เขียน Cypher Query ดึงความสัมพันธ์ (เช่น ท่าห้ามเล่น, ท่าแนะนำ, กล้ามเนื้อเป้าหมาย) ออกมาเป็นโครงสร้างความรู้พร้อม `image_path`

---

## 📌 Phase 4: รวมพลังเป็น Hybrid RAG ด้วย RRF (หัวใจสำคัญ 20 คะแนน)

* **ขั้นตอนที่ 4.1: ค้นหาคู่ขนาน (Parallel Retrieval)**
  * **ทำอะไร:** ส่งคำถามไปค้นทั้ง `search_dense` และ `search_graph` พร้อมกัน
* **ขั้นตอนที่ 4.2: รวมและจัดอันดับด้วยสูตร RRF (Reciprocal Rank Fusion)**
  * **ทำอะไร:** คำนวณคะแนน $Score = \sum \frac{1}{60 + Rank}$ เพื่อผสานผลลัพธ์จาก Vector และ Graph
  * **ผลลัพธ์:** ได้ Context คุณภาพสูง 3–5 อันดับแรกที่รวมทั้ง "ความถูกต้องเชิงความสัมพันธ์", "ขั้นตอนวิธีทำ" และ "รูปภาพอ้างอิง"

---

## 📌 Phase 5: เชื่อมต่อสมอง LLM (Local Ollama + Cloud API)

* **ขั้นตอนที่ 5.1: ประกอบ Prompt Template**
  * **ทำอะไร:** รวม Context จาก Hybrid RAG เข้ากับคำถามของผู้ใช้
* **ขั้นตอนที่ 5.2: สร้างท่อส่ง 2 ขา (Dual-Engine LLM)**
  * **ขา A (Local LLM):** ส่งเข้า **Ollama `qwen2.5:3b`** ในเครื่อง วัด VRAM และ Latency
  * **ขา B (API LLM):** ส่งข้ามเน็ตไปที่ **OpenRouter** วัด Token, Cost และ Latency
* **ขั้นตอนที่ 5.3: สรุปคำตอบแบบ Multi-modal Response (ตอบข้อความ + แนบรูปภาพ)**
  * **ทำอะไร:** ระบบส่งคำตอบเป็นภาษาไทยที่ถูกต้อง พร้อมแนบ **รูปภาพท่าทางจริงจากคู่มือ (`image_path`)** ส่งกลับให้ผู้ใช้ดูท่าทางประกอบได้ทันที

---

## 📌 Phase 6: รวมระบบและหน้าแชต

* Streamlit `app.py` เชื่อม User → Query Router → Dense/Graph/Hybrid → Local/OpenRouter LLM → Answer
* แสดงหน้าอ้างอิง ภาพจาก PDF กฎ AVOID และเวลาในแต่ละขั้น
* รักษา API key ใน `.env` ที่ Git ignore และแสดงข้อผิดพลาดที่ไม่เปิดเผย key

---

## 📌 Phase 7: การทดลองและวัดผล (Evaluation & Analysis - 10 คะแนน)

* **ขั้นตอนที่ 7.1: ออกแบบชุดคำถามทดสอบ 20 ข้อ (Evaluation Dataset)**
  * คำถามขั้นตอน 5 ข้อ, ความสัมพันธ์ 5 ข้อ, ซับซ้อน/ข้ามเงื่อนไข 10 ข้อ ใน `evaluation/questions.json`
* **ขั้นตอนที่ 7.2: รันเปรียบเทียบข้าม 6 Configurations**
  1. Dense RAG + Local LLM
  2. Dense RAG + API LLM
  3. Graph RAG + Local LLM
  4. Graph RAG + API LLM
  5. Hybrid RAG + Local LLM
  6. Hybrid RAG + API LLM
* **ขั้นตอนที่ 7.3: บันทึกผลลัพธ์และตรวจด้วยคน**
  * วัด Latency, Token, GPU memory ทั้งระบบ, Cost ที่ API รายงาน, source-page coverage และข้อผิดพลาดด้าน AVOID
  * ให้คนตรวจ Accuracy/Grounding/Safety 0–2 คะแนนใน `human_review.csv`; ห้ามอนุมาน Accuracy จาก retrieval metric
* **ขั้นตอนที่ 7.4: วิเคราะห์สาเหตุ**
  * เปรียบเทียบจากตัวเลขจริงและตัวอย่างคำตอบ ไม่สรุปว่า Hybrid ดีกว่าโดยไม่มีผลรองรับ

---

## 📌 Phase 8: รายงานและนำเสนอ

* สร้างรายงานจาก `results/final_project/summary.json` และผลตรวจด้วยคน โดยระบุช่องที่ยังไม่มีผล
* สร้างสไลด์ที่มีสถาปัตยกรรม กราฟตัวอย่าง ผลทดลอง 6 รูปแบบ และข้อจำกัดที่ตรวจสอบได้
* ซ้อม Live Demo ก่อนนำเสนอวันพุธที่ 30 ก.ย. 2569 (9.00 - 12.00 น.)
