# 🏋️ AI Fitness Assistant (GraphRAG & LLMs)
> **Final Project:** การพัฒนาระบบผู้ช่วยอัจฉริยะด้วย GraphRAG และ LLMs สำหรับคู่มือการออกกำลังกายและใช้อุปกรณ์สถานกีฬาและสุขภาพ (Development of a GraphRAG-Powered Intelligent Fitness Assistant)  
> **กำหนดนำเสนอ:** วันพุธที่ 30 กันยายน 2569 เวลา 9:00 - 12:00 น.  
> **เกณฑ์การประเมิน:** [Rubric ระดับคุณภาพ Final Project (เป้าหมาย Level 5)](./exercise/Rubric%20ระดับคุณภาพสำหรับประเมิน%20Final%20Project.md)

---

## 📌 ภาพรวมโครงการ (Project Overview)
โครงการนี้พัฒนาระบบผู้ช่วยอัจฉริยะ (Interactive Assistant / AI Copilot) ให้คำแนะนำการใช้เครื่องมือออกกำลังกายและจัดท่าทางในฟิตเนสอย่างถูกต้อง ปลอดภัย และตรงเป้าหมาย โดยบูรณาการเทคโนโลยี:
1. **Dense RAG (ChromaDB):** ค้นหาขั้นตอนวิธีใช้งาน, การปรับเบาะ, และจังหวะการหายใจ (Semantic Search)
2. **Graph RAG (Neo4j):** ค้นหาโครงสร้างความสัมพันธ์ข้ามมิติ เช่น `(ท่า) -> (กล้ามเนื้อ) -> (ข้อห้าม/อาการบาดเจ็บ) -> (เป้าหมาย 1RM)`
3. **Hybrid RAG (RRF Fusion):** รวมพลังผลการค้นหาจาก Dense + Graph ด้วยสูตร Reciprocal Rank Fusion
4. **Dual-Engine LLM:** สลับใช้งานได้ทั้ง **Local LLM (Ollama `qwen2.5:3b`)** ในเครื่อง และ **Cloud API (OpenRouter)** เพื่อประเมินผลเปรียบเทียบความเร็ว, ค่าใช้จ่าย และทรัพยากร

---

## 📂 โครงสร้างโฟลเดอร์ (Directory Structure)
```
chatproject/
├── data/
│   ├── chunks.json          # 44 Chunks สำหรับ Vector DB (ChromaDB) พร้อม Metadata & Image Path
│   ├── graph_data.csv       # 221 ความสัมพันธ์ (Triples) สำหรับ Knowledge Graph
│   ├── init_neo4j.cypher    # สคริปต์ Cypher สร้าง Nodes & Relationships ใน Neo4j
│   └── images/              # รูปภาพสาธิตท่าทางจริง 40 รูป (ผสานภาพคู่แบบ Side-by-Side)
├── exercise/
│   ├── exercise.pdf         # คู่มือการใช้เครื่องมือสถานกีฬาและสุขภาพ มทส. (46 หน้า)
│   └── Rubric...md          # เกณฑ์การประเมินโครงการระดับ Level 5
├── scripts/
│   ├── run_phase1.py        # สคริปต์ประมวลผล PDF, ตัดภาพ, สร้าง chunks และ graph
│   └── ...                  # สคริปต์ตรวจสอบข้อมูล
├── workflow.md              # แผนการดำเนินงาน 7 ขั้นตอนโดยละเอียด
├── PROJECT_PROGRESS_REPORT.md # บันทึกความคืบหน้าและประวัติการทำงานทุกก้าว
└── README.md                # เอกสารแนะนำโปรเจกต์
```

---

## 🚀 คำแนะนำสำหรับเพื่อนร่วมทีม (Quick Start for Collaborator)

### 1. ติดตั้ง Library พื้นฐาน
```bash
pip install -r requirements.txt
```

### 2. สถานะปัจจุบัน (Current Progress)
* **Phase 1: Data Preparation:** ✅ **เสร็จสมบูรณ์ 100%**
  * สกัดรูปภาพ 40 รูปเก็บไว้ใน `data/images/`
  * สร้าง `data/chunks.json` (44 chunks) พร้อม Metadata
  * สร้าง `data/graph_data.csv` (221 relations) และ `data/init_neo4j.cypher`
* **Phase 2: Dual Database Setup:** ✅ **เสร็จสมบูรณ์ 100%**
  * Vector: ChromaDB เก็บ Persistent Vector Indexing ไว้ใน `data/chroma_db/`
  * Graph: นำข้อมูลเข้า Neo4j พร้อมไฟล์ In-Memory Fallback `data/knowledge_graph.json` (145 nodes, 221 edges)
* **Phase 3: Retrieval Implementation:** ✅ **เสร็จสมบูรณ์ 100%**
  * `src/dense_retrieval.py` (`DenseRetriever`) ค้นหาเวกเตอร์ Cosine Similarity + Threshold Cutoff
  * `src/graph_retrieval.py` (`GraphRetriever`) Multi-hop traversal ตรวจสอบข้อห้าม AVOID และท่าทดแทน
* **Phase 4: Hybrid RAG Core (20 คะแนนเต็ม):** ✅ **เสร็จสมบูรณ์ 100%**
  * `src/hybrid_rag.py` (`HybridRAG`): รวม QueryRouter, Reciprocal Rank Fusion (RRF), Safety Filtering, และ Context Aggregator
  * รันสคริปต์ทดสอบ: `python scripts/test_phase4_hybrid.py`
* **Phase 5: Dual LLM Engine:** ✅ **Local และ OpenRouter ผ่านการทดลองจริงครบอย่างละ 60 คู่คำถาม-รูปแบบ**
  * `src/llm_engine.py` ส่ง Context จาก HybridRAG ไปยัง Ollama `qwen2.5:3b` หรือ OpenRouter
  * `scripts/chat_phase5.py` เป็นหน้าแชตบน Terminal เลือก Local / API และโหมด Retrieval ได้
  * `.env.example` เป็นตัวอย่างการตั้งค่า; `.env` ถูก Git ignore และต้องไม่ commit API key

---

## 🧪 คำสั่งทดสอบระบบ (How to Run Tests)

```bash
# 1. ทดสอบการค้นหาแยกสาย (Dense Vector vs Graph)
python scripts/test_phase3_retrieval.py

# 2. ทดสอบระบบรวมพลัง Hybrid RAG (RRF + Safety Filter + Auto Attached Images)
python scripts/test_phase4_hybrid.py
```

### Phase 5: ถาม–ตอบผ่าน LLM

1. เปิด Ollama และดาวน์โหลดโมเดลด้วย `ollama pull qwen2.5:3b` (Local ไม่ใช้ API key)
2. ถ้าจะใช้ OpenRouter ให้คัดลอก `.env.example` เป็น `.env` แล้วใส่ `OPENROUTER_API_KEY` ของตัวเองในไฟล์นี้ **อย่าส่ง key เข้า Git หรือแชต** เปลี่ยน `OPENROUTER_MODEL` ได้ตามบัญชีและโควตา; ค่าเริ่มต้นเป็นโมเดลตัวอย่างฟรีซึ่งอาจติด rate limit
3. รันจากโฟลเดอร์หลักของ repo:

```powershell
python -m unittest discover -s tests -v
python scripts/chat_phase5.py --provider local --query "ปวดเข่าควรหลีกเลี่ยงท่าไหน"
python scripts/chat_phase5.py --provider openrouter --query "วิธีเล่น Leg press"
```

ไม่ใส่ `--query` จะเข้าสู่โหมดถามต่อเนื่องบน Terminal; ใช้ `--mode dense`, `graph` หรือ `hybrid` เพื่อเปรียบเทียบการค้นหาได้ ระบบคืนคำตอบพร้อมรายชื่อแหล่งข้อมูล เลขหน้า โทเคน (เมื่อผู้ให้บริการส่งมา) และเวลาในการค้น/ตอบ ทั้งสอง provider ผ่านการทดสอบจริงตามชุดคำถาม 20 ข้อแล้ว

### Phase 6: หน้าแชต

```powershell
python -m streamlit run app.py
# ถ้าใช้ Docker container ชื่อ hybrid-rag-neo4j ในเครื่องนี้:
python scripts/run_with_neo4j.py
```

หน้าเว็บเลือก Local/OpenRouter และ Auto/Dense/Graph/Hybrid ได้ แสดงแหล่งอ้างอิง เลขหน้า ภาพประกอบ ข้อควรหลีกเลี่ยง และเวลาในการทำงาน API key อ่านจาก `.env` เท่านั้น หน้าเว็บไม่แสดงค่า key

### Phase 7: ประเมิน 20 คำถาม

```powershell
python scripts/evaluate_phase7.py --providers local
# หลังใส่ key ใน .env แล้ว และยอมรับการใช้โควตา API:
python scripts/evaluate_phase7.py --providers local openrouter --allow-api
```

ผลบันทึกต่อเนื่องใน `results/final_project/` และรันคำสั่งเดิมซ้ำเพื่อทำต่อได้ รายละเอียดเกณฑ์ตรวจด้วยคนอยู่ที่ `evaluation/README.md` **คะแนนความถูกต้องของคำตอบต้องให้คนตรวจ**; เมตริกค้นหาอัตโนมัติไม่ใช่คำตอบว่า LLM ถูกต้องทั้งหมด

### Phase 8: รายงานและสไลด์

```powershell
python scripts/build_final_report.py
```

รายงาน Markdown อยู่ใน `reports/FINAL_REPORT_TH.md`; สไลด์ฉบับตรวจภาพและโครงสร้างแล้วอยู่ใน `reports/FINAL_PRESENTATION_TH_v5.pptx` ผลที่บันทึก ณ 27 ก.ย. 2569 คือ Local 60/60, OpenRouter 60/60 รวม 120/120 คู่คำถาม-รูปแบบ Graph/Hybrid ทั้ง 80 คู่ใช้ Neo4j สด ค่าใช้จ่าย OpenRouter ตามที่ API รายงานรวม $0.0721 ยังไม่มีคะแนน human review (0/120) จึงห้ามเรียกค่า source coverage ว่าความแม่นยำของคำตอบ

กราฟใน Neo4j ใช้ label `FitnessEntity` พร้อม `project_id=fitness_rag_final_2026` เพื่อแยกจากโปรเจกต์อื่น คำสั่ง `python scripts/run_with_neo4j.py` อ่าน credential จาก Docker container ในหน่วยความจำเพื่อเปิดหน้าแชตโดยไม่ต้องบันทึกรหัสผ่านลงไฟล์ หากใช้ Neo4j ตัวอื่น ให้กำหนด `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` ใน environment หรือ `.env` เอง; ถ้าไม่พร้อม ระบบใช้ `json_fallback` และแสดง backend จริง
