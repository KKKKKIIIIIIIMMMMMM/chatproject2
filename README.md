# AI Fitness Assistant — Hybrid Graph RAG

ผู้ช่วยถาม–ตอบจากคู่มือการใช้เครื่องออกกำลังกายของสถานกีฬาและสุขภาพ มทส. มีหน้าเว็บ Streamlit และบอต LINE ใช้ Dense Retrieval (ChromaDB) ร่วมกับ Graph Retrieval (Neo4j) ก่อนส่งบริบทให้ Ollama ในเครื่องหรือ OpenRouter API คำตอบแสดงชื่อท่า เลขหน้า และภาพจากคู่มือเมื่อค้นพบ ระบบนี้เป็นโครงงานเพื่อการเรียน **ไม่ใช่คำวินิจฉัยหรือคำแนะนำทางการแพทย์**

## เริ่มต้นสำหรับเพื่อนร่วมทีม

โค้ดทดสอบบน Windows; ต้องมี Python 3.10+, Ollama และ (หากต้องการใช้กราฟสด) Docker Desktop ข้อมูล PDF, chunks, JSON graph และดัชนี ChromaDB มีอยู่ใน repo แล้ว แต่ควรเตรียมฐานข้อมูล Neo4j ของเครื่องตัวเองก่อนใช้กราฟสด `cloudflared` และบัญชี LINE Messaging API จำเป็นเฉพาะเมื่อต้องการถามผ่าน LINE

```powershell
git clone https://github.com/KKKKKIIIIIIIMMMMMM/chatproject2.git
cd chatproject2
python -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull qwen2.5:3b
# ทางเลือก Local 9B; ดาวน์โหลดเฉพาะเมื่อจะใช้
ollama pull qwen3.5:9b-q4_K_M
python -m unittest discover -s tests -v
```

เติมคีย์ใน `.env` เฉพาะบริการที่ต้องใช้: `OPENROUTER_API_KEY` สำหรับ API; `LINE_CHANNEL_SECRET` และ `LINE_CHANNEL_ACCESS_TOKEN` สำหรับ LINE ส่วน `OLLAMA_MODEL=qwen2.5:3b` เป็นค่าเริ่มต้นของ LINE และการรัน CLI ที่ไม่ได้ระบุโมเดล ค่าใน `.env` เป็นข้อมูลส่วนตัวและถูก Git ignore — **ห้ามคัดลอกคีย์จริงไป `.env.example`, README, log หรือ commit**

### เปิดหน้าเว็บโดยไม่ใช้ LINE

```powershell
python -m streamlit run app.py
```

เปิด `http://127.0.0.1:8501` เลือก Local Qwen2.5 3B, Local Qwen3.5 9B (Q4_K_M) หรือ API OpenRouter ได้ รวมทั้งเลือก `auto`, `dense`, `graph`, `hybrid` และจำนวนแหล่งข้อมูล หาก Neo4j ไม่พร้อม Graph Retriever ใช้ `data/knowledge_graph.json` เป็น fallback และแสดง backend จริงใน “ข้อมูลการทำงาน” การเลือกโมเดลบนเว็บ **ไม่เปลี่ยนโมเดลของ LINE**

### เปิด Neo4j สดบนเครื่องใหม่

ถ้ายังไม่มี container ให้สร้างครั้งเดียวหลังเปิด Docker Desktop (เปลี่ยนรหัสผ่านตัวอย่างก่อนรัน):

```powershell
docker run -d --name hybrid-rag-neo4j -p 7474:7474 -p 7687:7687 -e "NEO4J_AUTH=neo4j/replace-with-strong-password" neo4j:5
python scripts/run_with_neo4j.py -- python scripts/setup_neo4j.py
python scripts/run_with_neo4j.py
```

`run_with_neo4j.py` อ่าน credential จาก container ในหน่วยความจำ ไม่บันทึกรหัสผ่านลง repo กราฟของโครงงานถูกแยกด้วย `project_id=fitness_rag_final_2026`; หน้า Neo4j Browser อยู่ที่ `http://127.0.0.1:7474` หากใช้ Neo4j ที่ไม่ได้อยู่ใน container ชื่อนี้ ให้กำหนด `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` ใน environment หรือ `.env` แล้วรัน `python scripts/setup_neo4j.py` และ `python -m streamlit run app.py` แทน

ดัชนี ChromaDB ถูกเก็บไว้ใน `data/chroma_db/` แล้ว ถ้าต้องสร้างใหม่ให้รัน `python scripts/setup_chromadb.py` ซึ่งจะสร้าง embedding จาก `data/chunks.json` และเขียนทับ collection เดิม; ไฟล์ฐานข้อมูลที่เปลี่ยนจากการรันเป็น runtime data อย่า commit โดยไม่ได้ตั้งใจ

### เปิด LINE bot บน Windows

หลังใส่ LINE credentials ใน `.env` และเตรียม container `hybrid-rag-neo4j` แล้ว ดับเบิลคลิก `START_PROJECT.cmd` หรือรัน:

```powershell
python scripts/project_launcher.py start
```

ไฟล์เปิดระบบตรวจ/เปิด Docker Desktop, container Neo4j ที่มีอยู่, Ollama, Streamlit, LINE webhook และ Cloudflare Quick Tunnel โดยไม่สร้างฐานข้อมูลหรือดาวน์โหลดโมเดลให้อัตโนมัติ เมื่อ tunnel ใช้ได้จะทดสอบ webhook แล้วจึงตั้ง endpoint ใหม่บน LINE ข้อมูลสถานะและ log อยู่ใน `.runtime/` ซึ่ง Git ignore ถ้าต้องการหยุดเฉพาะโปรเซสที่ไฟล์นี้เปิด ให้ใช้ `STOP_PROJECT.cmd` หรือ `python scripts/project_launcher.py stop`; Docker Desktop และ Neo4j จะยังทำงานต่อ

ค่าเริ่มต้น LINE คือ `LINE_PROVIDER=local`, `LINE_RETRIEVAL_MODE=auto`, `LINE_TOP_K=4`, `LINE_PORT=8000` และ Ollama `qwen2.5:3b` เปลี่ยนเป็น API ได้ด้วย `LINE_PROVIDER=openrouter` (ต้องมี API key) หรือเปลี่ยน Local model ด้วย `OLLAMA_MODEL=qwen3.5:9b-q4_K_M` ใน `.env` แล้วรีสตาร์ตบอต Qwen3.5 ถูกส่ง `think: false` เพื่อปิด thinking mode

### LINE: ถามได้ทุกหมวดและดูรูปจากคู่มือ

พิมพ์ `เมนู` เพื่อดู Flex Carousel ของ 8 หมวด หรือพิมพ์ตรง ๆ เช่น `อยากเล่นขา`, `อยากเล่นอก`, `อยากเล่นหลัง`, `อยากเล่นไหล่`, `อยากเล่นหน้าแขน`, `อยากเล่นหลังแขน`, `อยากเล่นท้อง`, `อยากเล่นคาร์ดิโอ` บอตสรุปภาพรวมจากรายชื่อท่าในหมวดและแสดง Carousel ของท่าที่มีในคู่มือ แต่ละการ์ดมีรูป เลขหน้า และปุ่ม `ดูวิธีฝึก` กดแล้วบอตให้ LLM อธิบายโดยใช้ chunk ของท่านั้นเท่านั้น พร้อมการ์ดรูปและปุ่มกลับไปเลือกท่าอื่น เมื่อพิมพ์ชื่อท่าอังกฤษชัดเจน เช่น `วิธีเล่น Leg Extension` ระบบก็เลือก chunk เดียวและรูปเดียวโดยตรง เพื่อไม่ให้ผลค้นคืนของท่าอื่นมาปน ส่วนคำถามที่ไม่ระบุท่าชัดเจนยังใช้ RAG เดิมและตอบเป็นข้อความ โดยไม่แนบรูปที่อาจไม่ตรงคำถาม

บนมือถือมี Quick Reply สำหรับเลือกหมวดหรือหมวดย่อย เช่น `ต้นขาด้านหน้า` / `น่อง` และ `อกบน` / `อกล่าง` ส่วน LINE PC อาจไม่แสดง Quick Reply จึงมีปุ่มอยู่บน Flex Card ด้วย ข้อมูลรูป/หน้ามาจาก `data/chunks.json` โดยตรง: ท่าออกกำลังกาย 40 รายการ หน้า 6–45 พร้อมรูป 40 รูป ส่วนหัวข้อความรู้หน้า 46 มีแต่ข้อความและไม่แนบรูป อย่านำตัวเลขหรือข้อห้ามจาก checklist ภายนอกมาเขียนทับข้อมูลนี้โดยไม่ตรวจหลักฐาน (ดู `docs/LINE_CATALOG_AUDIT.md`)

รูปถูกเสิร์ฟที่ `https://<LINE webhook host>/images/<ชื่อรูป>.jpg` และจำกัดเฉพาะ 40 ภาพใน catalogue URL ต้องเป็น HTTPS ที่ LINE เข้าถึงได้ เมื่อรัน `START_PROJECT.cmd` ตัวเปิดระบบจะบันทึก tunnel URL ปัจจุบันไว้ใน `.runtime/line_public_base_url.txt` ให้อัตโนมัติ (ไฟล์นี้ถูก Git ignore) ถ้ารัน webhook/tunnel แยกเอง ให้กำหนด `LINE_PUBLIC_BASE_URL=https://<host>` ใน `.env` โดยไม่ใส่ `/webhook` หากยังไม่มี URL สาธารณะ บอตจะส่งคำตอบข้อความกับปุ่ม แต่จะไม่ส่งการ์ดรูป หากโมเดลสรุปไม่สำเร็จ บอตจะบอกข้อผิดพลาดโดยไม่แต่งขั้นตอนฝึกขึ้นเอง

Quick Tunnel ใช้สำหรับสาธิตเท่านั้น URL เปลี่ยนเมื่อเปิดใหม่และอาจหลุดเมื่อเครือข่ายขัดข้อง ถ้าเปิดระบบแล้ว LINE ไม่ตอบ ให้ดู `.runtime/cloudflared.err.log`, ตรวจ `http://127.0.0.1:8000/healthz` และตรวจว่า LINE Developers เปิด **Use webhook** อยู่ ไฟล์เปิดระบบจะพยายามเริ่ม tunnel ของโครงงานใหม่หากตัวเดิมค้างแต่ไม่พร้อมใช้งาน สำหรับงานที่ต้องออนไลน์ต่อเนื่องควรใช้ endpoint ถาวรและคิวงานที่เก็บสถานะข้ามการรีสตาร์ต

ไม่ต้องใช้ launcher หากจะรันแยกเอง: `python scripts/run_with_neo4j.py -- python scripts/line_webhook.py` แล้วเปิด tunnel `cloudflared tunnel --url http://127.0.0.1:8000` และตั้ง `https://<tunnel>.trycloudflare.com/webhook` ใน LINE Developers บอตตรวจลายเซ็น `x-line-signature` ก่อนอ่าน JSON รับข้อความตัวอักษรและ postback ที่รู้จัก กัน event ซ้ำในหน่วยความจำ คำถามทั่วไปตอบจาก RAG เดียวกับเว็บ ส่วนเมนูการ์ดใช้รายการที่ตรวจหน้า/รูปแล้ว

## สิ่งที่ทำเสร็จแล้วและสิ่งที่เพิ่มจาก repo เดิม

| ส่วน | สถานะและไฟล์หลัก |
|---|---|
| เตรียมข้อมูล | `scripts/run_phase1.py` ดึงข้อความจาก `exercise/exercise.pdf` 46 หน้า แก้คำไทยบางคำที่เพี้ยน แยก 44 chunks พร้อมหน้า/ภาพ 40 ภาพ และสร้าง triples สำหรับกราฟ |
| Dense RAG | `src/dense_retrieval.py` ใช้ `intfloat/multilingual-e5-small`, ChromaDB, top-k และ similarity threshold 0.5 |
| Graph RAG | `src/graph_retrieval.py`, `scripts/setup_neo4j.py` ใช้กราฟ 145 nodes / 221 relationships พร้อม JSON fallback; ความสัมพันธ์หลักได้แก่ `TARGETS_GROUP`, `HAS_CAUTION`, `AVOID`, `RECOMMEND` |
| Hybrid RAG | `src/hybrid_rag.py` มี Query Router, weighted Reciprocal Rank Fusion, safety filtering และ context aggregation |
| LLM และ UI | `src/llm_engine.py`, `app.py`, `scripts/chat_phase5.py` เพิ่ม Ollama/OpenRouter, แหล่งอ้างอิง, เวลา, token และตัวเลือก Local Qwen3.5 9B ที่ปิด thinking โดย Qwen2.5 3B ยังเป็นค่าเริ่มต้น |
| LINE และตัวเปิดระบบ | `scripts/line_webhook.py`, `scripts/project_launcher.py`, `START_PROJECT.cmd`, `STOP_PROJECT.cmd`; อ่าน credentials จาก `.env` และไม่ส่งคีย์เข้า Git |
| ทดสอบและรายงาน | `tests/`, `evaluation/`, `results/final_project/`, `reports/FINAL_REPORT_TH.md` และสไลด์ `reports/FINAL_PRESENTATION_TH_v5.pptx` |

งานที่เพิ่มหลังโครงหลัก Phase 1–4 ได้แก่ ระบบตอบ Local/API (Phase 5), เว็บแชตพร้อมการอ้างอิง (Phase 6), ชุดประเมินและรายงาน (Phase 7–8), LINE webhook, ไฟล์เปิด/ปิดระบบบน Windows และตัวเลือก Qwen3.5 9B พร้อม `think: false` นอกจากนี้แก้การอ่าน LINE credentials ให้ค่าใน `.env` ชนะค่าเก่าที่ตกค้างใน environment และแก้ไฟล์เปิดระบบให้โหลดโมดูล Neo4j ได้เมื่อเรียกผ่าน `python scripts/project_launcher.py`

ระบบตอบใช้ลำดับ **คำถาม → Router → Dense/Graph → Fusion (เมื่อเป็น Hybrid) → กรองท่า AVOID → สร้าง context → Local/API LLM → คำตอบพร้อมหลักฐาน** ถ้าไม่มีหลักฐานที่ค้นได้จะตอบว่าไม่พบข้อมูล แต่คำถามไร้ความหมายบางแบบยังอาจดึง chunk ที่ไม่เกี่ยวข้องแล้วทำให้ Local ตอบผิดประเด็นได้

## วิธีทดสอบและผลที่มีอยู่

```powershell
python -m unittest discover -s tests -v
python scripts/chat_phase5.py --provider local --query "วิธีเล่น Leg press"
python scripts/chat_phase5.py --provider local --local-model qwen3.5:9b-q4_K_M --query "วิธีเล่น Leg press"
# มีการใช้โควตา/อาจมีค่าใช้จ่าย API; ใส่ key ใน .env ก่อน
python scripts/evaluate_phase7.py --providers local openrouter --allow-api
```

ชุดประเมินใน `evaluation/questions.json` มี 20 คำถาม: ขั้นตอน 5, ความสัมพันธ์ 5, ซับซ้อน 10 ผลเดิมทดสอบ Dense/Graph/Hybrid × Qwen2.5 3B/OpenRouter ครบ **120 คู่คำถาม–รูปแบบ** (Qwen3.5 9B เป็นตัวเลือกใหม่และ **ยังไม่อยู่ในผลเปรียบเทียบเดิม**) ผลสรุปใน `results/final_project/summary.json` แสดง source-page coverage ของ Dense 68.7%, Graph 87.8%, Hybrid 95.5%; Graph และ Hybrid พบหน้า AVOID ที่ระบุไว้ครบในชุดนี้ ค่าใช้จ่าย OpenRouter ที่ API รายงานรวมประมาณ $0.0721 ผลเหล่านี้เป็นเมตริกการค้นหาและความครบของการรัน **ไม่ใช่คะแนนความถูกต้องของคำตอบ** ปัจจุบัน `results/final_project/human_review.csv` ยังไม่ได้ให้คะแนนโดยคน (0/120) อ่านข้อจำกัดที่ `evaluation/README.md` และ `reports/FINAL_REPORT_TH.md` ก่อนนำตัวเลขไปนำเสนอ

## งานที่ควรทำต่อ

1. ให้สมาชิกทีมตรวจคำตอบใน `results/final_project/human_review.csv` ด้านความถูกต้อง การยึดหลักฐาน และความปลอดภัย แล้วสรุปใหม่ด้วย `python scripts/evaluate_phase7.py --summarize-only`
2. เพิ่มการตรวจคำถามนอกขอบเขต/ไร้ความหมายและเกณฑ์ปฏิเสธเมื่อแหล่งข้อมูลไม่เกี่ยวข้อง เพื่อลดคำตอบผิดประเด็นของ Local LLM
3. ตรวจสอบกฎ `AVOID/RECOMMEND` ใน `scripts/run_phase1.py` กับเอกสารต้นทางและผู้เชี่ยวชาญก่อนนำไปให้คำแนะนำด้านสุขภาพจริง; กฎบางส่วนเป็นการกำหนดโดยโครงงาน ไม่ใช่ผลวินิจฉัย
4. หากจะอ้างว่า Qwen3.5 9B ดีกว่า ให้รันชุดคำถามและ human review ด้วยเงื่อนไขเดียวกับ Qwen2.5 3B; ผลเดิมยังใช้สรุปแทน 9B ไม่ได้
5. ถ้าต้องเปิด LINE ระยะยาว ให้เปลี่ยน Quick Tunnel ชั่วคราวเป็น HTTPS endpoint ถาวร และเปลี่ยนการกันซ้ำ/คิวงานในหน่วยความจำเป็นระบบที่ทนต่อการรีสตาร์ต

ไฟล์หลักสำหรับอ่านต่อ: `workflow.md` (ภาพรวมงาน), `PROJECT_PROGRESS_REPORT.md` (ประวัติ), `data/chunks.json` (ข้อความ/metadata), `data/knowledge_graph.json` (กราฟ), `src/` (retrieval และ LLM), `app.py` (หน้าเว็บ), `scripts/line_webhook.py` (LINE), `evaluation/README.md` (การให้คะแนน)
