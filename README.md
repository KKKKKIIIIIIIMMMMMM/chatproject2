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
4. **Dual-Engine LLM:** สลับใช้งานได้ทั้ง **Local LLM (Ollama)** ในเครื่อง และ **Cloud API (Groq/Gemini)** เพื่อประเมินผลเปรียบเทียบความเร็ว, ค่าใช้จ่าย และทรัพยากร

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
pip install pymupdf pillow
```

### 2. สถานะปัจจุบัน (Current Progress)
* **Phase 1: Data Preparation:** ✅ **เสร็จสมบูรณ์ 100%**
  * สกัดรูปภาพ 40 รูปเก็บไว้ใน `data/images/`
  * สร้าง `data/chunks.json` (44 chunks) พร้อม Metadata
  * สร้าง `data/graph_data.csv` (221 relations) และ `data/init_neo4j.cypher`
* **Phase 2: Dual Database Setup:** ⏳ **เตรียมเริ่มต่อ**
  * ฝั่ง Vector: นำ `data/chunks.json` เข้าสู่ ChromaDB
  * ฝั่ง Graph: นำ `data/init_neo4j.cypher` เข้าสู่ Neo4j
