# 📋 บันทึกความคืบหน้าและการดำเนินงาน (Project Progress Report)
## การพัฒนาระบบผู้ช่วยอัจฉริยะด้วย GraphRAG และ LLMs สำหรับคู่มือการออกกำลังกายและใช้อุปกรณ์สถานกีฬาและสุขภาพ
### (Development of a GraphRAG-Powered Intelligent Fitness Assistant)

---

> **กำหนดการนำเสนอ:** วันพุธที่ 30 กันยายน 2569 เวลา 9:00 – 12:00 น.  
> **เกณฑ์การประเมิน:** [Rubric ระดับคุณภาพสำหรับประเมิน Final Project (ระดับ Level 5)](file:///d:/3term1/a.kit/finalproject/exercise/Rubric%20%E0%B8%A3%E0%B8%B0%E0%B8%94%E0%B8%B1%E0%B8%9A%E0%B8%84%E0%B8%B8%E0%B8%93%E0%B8%A0%E0%B8%B2%E0%B8%9E%E0%B8%AA%E0%B8%B3%E0%B8%AB%E0%B8%A3%E0%B8%B1%E0%B8%9A%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B9%80%E0%B8%A1%E0%B8%B4%E0%B8%99%20Final%20Project.md)  
> **แหล่งข้อมูลหลัก:** [exercise.pdf](file:///d:/3term1/a.kit/finalproject/exercise/exercise.pdf) (คู่มือการใช้เครื่องมือออกกำลังกายสถานกีฬาและสุขภาพ มทส. 46 หน้า)

---

## 1. ข้อมูลหัวข้อและขอบเขตของโครงการ (Project Domain)

### 1.1 หัวข้อที่ทำ
ระบบผู้ช่วยอัจฉริยะ (AI Copilot / Interactive Fitness Assistant) ที่ให้คำแนะนำการออกกำลังกาย การเลือกใช้เครื่องมือ และการจัดท่าทางอย่างถูกต้อง ปลอดภัย และตรงตามเป้าหมาย

### 1.2 แหล่งข้อมูลที่นำมาใช้
เนื้อหาจากเอกสารคู่มือสถานกีฬาและสุขภาพ มหาวิทยาลัยเทคโนโลยีสุรนารี จำนวน 46 หน้า ประกอบด้วย:
1. **Aerobic Exercise Group (4 เครื่อง):** จักรยาน (Bike), ลู่วิ่ง (Treadmill), เครื่องเดินวงรี (Elliptical), กรรเชียงบก (Rower)
2. **Weight Machine Zone (17 เครื่อง):** เครื่องออกกำลังกายกลุ่มขา, อก, หัวไหล่, ปีก/หลัง, แขน และหน้าท้อง
3. **Free Weight Zone (14 ท่าดัมเบล):** ท่าบริหารแขนด้านหน้า (Biceps), แขนด้านหลัง (Triceps), ไหล่ (Shoulders), ปีก/หลัง, และหน้าอก (Chest)
4. **ตารางจุดมุ่งหมายในการฝึก (Training Objectives):** สูตรจำนวนครั้ง เซต และ % 1RM สำหรับ Endurance, Strength, Power, และ Cardiovascular

---

## 2. พิมพ์เขียวการนำเนื้อหาไปใช้ในระบบ RAG (Data & Architecture Plan)

```
                       [exercise.pdf (46 หน้า)]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[ฝั่ง Dense RAG (ChromaDB)]                       [ฝั่ง Graph RAG (Neo4j)]
• ขั้นตอนการใช้เครื่องมือแบบ Step-by-step         • Nodes: Exercise (35 ท่า/เครื่อง)
• วิธีการปรับเบาะ / สรีระร่างกาย                   • Nodes: Muscle (กล้ามเนื้อมัดย่อย)
• จังหวะการหายใจเข้า-ออก                         • Nodes: MuscleGroup (กลุ่มกล้ามเนื้อหลัก)
• ข้อควรระวังด้านความปลอดภัย                     • Nodes: Zone (Aerobic, Machine, FreeWeight)
                                                 • Nodes: Objective (สูตร 1RM / Reps / Sets)
                                                 • Nodes: Caution (ข้อห้าม / เสี่ยงบาดเจ็บ)
         │                                                 │
         └────────────────────────┬────────────────────────┘
                                  ▼
                    [Hybrid RAG Engine (RRF Fusion)]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[Local LLM (Ollama)]                               [API LLM (Groq / Gemini)]
• รันโมเดลในเครื่อง (Llama-3 / Qwen)               • ยิงผ่าน Cloud API
• บันทึก VRAM, Latency, Resource                  • บันทึก Token, Latency, Cost
```

---

## 3. สรุปสิ่งที่ต้องทำให้ครบตาม Rubric (เป้าหมาย 100 คะแนนเต็ม)

| องค์ประกอบ | น้ำหนัก | สิ่งที่ต้องส่งมอบในระบบ |
| :--- | :---: | :--- |
| **1. Data & Knowledge Base** | 10 | Clean Text, ทำ Chunking ใส่ Metadata, สกัดความสัมพันธ์สร้างตาราง Graph |
| **2. Dense RAG** | 15 | ระบบค้นหา Vector ผ่าน ChromaDB, ปรับ Top-K, และวัดค่า Similarity |
| **3. Graph RAG** | 15 | โครงสร้าง Neo4j เชื่อมโยง ท่า-กล้ามเนื้อ-ข้อควรระวัง พร้อมฟังก์ชัน Cypher Query |
| **4. Hybrid RAG (หัวใจสำคัญ)** | 20 | รวมผลลัพธ์ Dense + Graph ด้วยสูตร RRF (Reciprocal Rank Fusion) |
| **5. Local LLM** | 7.5 | ต่อ Ollama ในเครื่อง, ปรับ Prompt, วัดการกิน VRAM และเวลาตอบ |
| **6. API LLM** | 7.5 | ต่อ Cloud API (Groq/Gemini), จัดการ Token, วัดค่าใช้จ่ายและเวลาตอบ |
| **7. System Integration** | 10 | รวมระบบเป็นท่อเดียวกัน (Pipeline) มี Architecture ชัดเจน และ Error Handling |
| **8. Evaluation & Analysis** | 10 | ชุดคำถาม 20 ข้อ รันเทียบ 6 Configurations พร้อมตารางและบทวิเคราะห์ |
| **Documentation & Presentation** | 5 | รายงานสรุปผลเชิงเทคนิค และสไลด์นำเสนอสำหรับวันพุธที่ 30 ก.ย. |

---

## 4. ตารางติดตามสถานะการดำเนินงาน (Execution Status Checklist)

| Phase | กิจกรรมที่ต้องทำ | ผู้รับผิดชอบหลัก | สถานะ |
| :---: | :--- | :---: | :---: |
| **0** | **ศึกษาโจทย์, วิเคราะห์ Rubric, และอ่านไฟล์ PDF ต้นฉบับ** | ทั้งสองคน | ✅ **เสร็จสิ้น** |
| **1** | **Data Preparation:** Clean ข้อมูล, ตัด Chunks (Vector), สกัด Relation (Graph), และสกัดรูปภาพ | ร่วมกัน | ✅ **เสร็จสมบูรณ์ (100%)** |
| **2** | **Dual Database Setup:** สร้าง ChromaDB Indexing และเชื่อมต่อ Neo4j / Graph Engine | เพื่อน (Chroma) / เรา (Neo4j) | ✅ **เสร็จสมบูรณ์ (100%)** |
| **3** | **Retrieval Implementation:** พัฒนาฟังก์ชันค้นหา Dense Vector และ Graph Retrieval | เพื่อน (Vector) / เรา (Graph) | ✅ **เสร็จสมบูรณ์ (100%)** |
| **4** | **Hybrid RAG Core:** เขียนระบบ RRF (Reciprocal Rank Fusion) ผสาน 2 แหล่ง | ร่วมกัน | ✅ **เสร็จสมบูรณ์ (100%)** |
| **5** | **LLM Engine:** เชื่อมต่อ Ollama (Local) และ Cloud API (Groq) พร้อม Prompt | เพื่อน (Local) / เรา (API) | ⏳ พร้อมเริ่มต่อ |
| **6** | **System Integration & UI:** รวมระบบเป็นท่อเดียว มีสวิตช์สลับโหมด | ร่วมกัน | ⏳ รอเริ่ม |
| **7** | **Evaluation & Benchmark:** รันชุดคำถาม 20 ข้อ บันทึกผลเปรียบเทียบ 6 แบบ | ร่วมกัน | ⏳ รอเริ่ม |
| **8** | **Final Report & Slides:** จัดทำสไลด์และเอกสารเตรียมนำเสนอ 30 ก.ย. | ร่วมกัน | ⏳ รอเริ่ม |

---

## 5. บันทึกประวัติการทำงาน (Activity Log)

* **26 ก.ย. 2569 (00:25 น.) - Phase 0 เสร็จสมบูรณ์:**
  * ศึกษาเกณฑ์การให้คะแนนอย่างละเอียดจาก [Rubric ระดับคุณภาพสำหรับประเมิน Final Project.md](file:///d:/3term1/a.kit/finalproject/exercise/Rubric%20%E0%B8%A3%E0%B8%B0%E0%B8%94%E0%B8%B1%E0%B8%9A%E0%B8%84%E0%B8%B8%E0%B8%93%E0%B8%A0%E0%B8%B2%E0%B8%9E%E0%B8%AA%E0%B8%B3%E0%B8%AB%E0%B8%A3%E0%B8%B1%E0%B8%9A%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B9%80%E0%B8%A1%E0%B8%B4%E0%B8%99%20Final%20Project.md)
  * อ่านและวิเคราะห์เนื้อหาครบทั้ง 46 หน้าของเอกสาร [exercise.pdf](file:///d:/3term1/a.kit/finalproject/exercise/exercise.pdf) (มทส.)
  * สร้างเอกสารติดตามความคืบหน้าฉบับนี้ (`PROJECT_PROGRESS_REPORT.md`) เพื่อใช้เป็นบันทึกกลางของการพัฒนาทุกขั้นตอน
* **26 ก.ย. 2569 (00:38 น.) - ปรับปรุง Workflow ผนวก Image Extraction:**
  * ปรับปรุงไฟล์ [workflow.md](file:///d:/3term1/a.kit/finalproject/workflow.md) เพิ่มขั้นตอน **1.3 สกัดรูปภาพ (Image Extraction)** เพื่อเก็บรูปถ่ายสาธิตท่าทางลงโฟลเดอร์ `images/`
  * ผูก `image_path` เข้าเป็น Metadata ของ Chunks ใน ChromaDB และ Property ของ Node ใน Neo4j
* **26 ก.ย. 2569 (00:52 น.) - Phase 1 ดำเนินการเสร็จสมบูรณ์ 100% (หลักฐานเชิงประจักษ์):**
  * พัฒนาสคริปต์สกัดข้อมูลอัตโนมัติ [run_phase1.py](file:///d:/3term1/a.kit/finalproject/scripts/run_phase1.py)
  * **หลักฐานที่ 1 (Assets รูปภาพ):** สกัดรูปถ่ายท่าออกกำลังกายจริงได้ **40 ไฟล์** คุณภาพสูง (รวมภาพ Side-by-side ท่าเริ่มต้น+ท่าออกแรง) เซฟลงใน [data/images/](file:///d:/3term1/a.kit/finalproject/data/images)
  * **หลักฐานที่ 2 (Vector Chunks):** สร้างไฟล์ [data/chunks.json](file:///d:/3term1/a.kit/finalproject/data/chunks.json) จำนวน **44 Chunks** ครบทั้ง 39 ท่า/เครื่อง และ 4 กฎเป้าหมายการฝึก 1RM พร้อม Metadata และ Image Path
  * **หลักฐานที่ 3 (Graph Triples):** สร้างตารางความสัมพันธ์ [data/graph_data.csv](file:///d:/3term1/a.kit/finalproject/data/graph_data.csv) จำนวน **221 ความสัมพันธ์ (Triples)** ครอบคลุม Exercise, Muscle, MuscleGroup, Zone, Equipment, Caution, และเงื่อนไขข้อห้ามทางการแพทย์ (Avoid/Recommend)
* **26 ก.ย. 2569 (02:20 น.) - นำโปรเจกต์ขึ้น GitHub Repository:**
  * ทำการ Initialize Git Repository และกำหนดโครงสร้างโปรเจกต์พร้อมไฟล์ `.gitignore` และ `README.md`
  * อัปโหลดไฟล์ทั้งหมดขึ้น GitHub: https://github.com/buzziezylovemelon/chatproject (Branch: `main`)
* **26 ก.ย. 2569 (22:45 น.) - Phase 2 Dual Database Setup เสร็จสมบูรณ์ 100%:**
  * **ฝั่ง Dense RAG:** พัฒนา [scripts/setup_chromadb.py](file:///d:/3term1/a.kit/finalproject/scripts/setup_chromadb.py) ใช้โมเดล `intfloat/multilingual-e5-small` แปลง 44 Chunks เป็น Vector บันทึกลง Persistent ChromaDB สำเร็จ
  * **ฝั่ง Graph RAG:** พัฒนา [scripts/setup_neo4j.py](file:///d:/3term1/a.kit/finalproject/scripts/setup_neo4j.py) เชื่อมต่อ Neo4j พร้อมสคริปต์ Cypher และสร้าง In-Memory Graph Fallback [data/knowledge_graph.json](file:///d:/3term1/a.kit/finalproject/data/knowledge_graph.json) ขนาด 145 Nodes และ 221 Edges
* **26 ก.ย. 2569 (22:55 น.) - Phase 3 Retrieval Implementation เสร็จสมบูรณ์ 100%:**
  * พัฒนา [src/dense_retrieval.py](file:///d:/3term1/a.kit/finalproject/src/dense_retrieval.py) (`DenseRetriever`): ค้นหา Vector Similarity และรองรับ Score Threshold Filtering
  * พัฒนา [src/graph_retrieval.py](file:///d:/3term1/a.kit/finalproject/src/graph_retrieval.py) (`GraphRetriever`): ดึงความสัมพันธ์ Multi-hop ระบุข้อห้าม (Avoid) และท่าแนะนำ (Recommend)
  * พัฒนา [scripts/test_phase3_retrieval.py](file:///d:/3term1/a.kit/finalproject/scripts/test_phase3_retrieval.py): รันการทดสอบ 3 รูปแบบ (ขั้นตอนใช้งาน, อาการบาดเจ็บ, และกลุ่มกล้ามเนื้อ) ผลลัพธ์ถูกต้องแม่นยำ 100%
* **26 ก.ย. 2569 (23:18 น.) - Phase 4 Hybrid RAG Core เสร็จสมบูรณ์ 100% (หัวใจสำคัญ 20 คะแนน Rubric):**
  * พัฒนา [src/hybrid_rag.py](file:///d:/3term1/a.kit/finalproject/src/hybrid_rag.py) บูรณาการ 3 กลไกระดับสูง:
    1. **Query Router:** จำแนกเจตนาคำถาม (Procedural / Relational / Hybrid) อัตโนมัติ
    2. **Reciprocal Rank Fusion (RRF):** อัลกอริทึมจัดอันดับคะแนนผสมผสาน $RRF(d) = \sum \frac{w}{60 + rank}$
    3. **Safety Filtering:** สกัดและกรองข้อห้าม AVOID ออกจากคำแนะนำเพื่อความปลอดภัยสูงสุด
    4. **Context Aggregator & Multimodal Asset Binding:** สรุปโครงสร้างบริบทพร้อมผูกรูปภาพสาธิตท่าทางจริง
  * พัฒนาและรันชุดทดสอบเปรียบเทียบ [scripts/test_phase4_hybrid.py](file:///d:/3term1/a.kit/finalproject/scripts/test_phase4_hybrid.py) เปรียบเทียบ Dense vs Graph vs Hybrid ใน 3 สถานการณ์จริง ผลลัพธ์ยืนยันว่า Hybrid RAG ป้องกันข้อห้ามทางการแพทย์ได้ 100% และดึงขั้นตอนการเล่นได้สมบูรณ์ที่สุด





