import os
import sys
import json
import re
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

class GraphRetriever:
    """
    โมดูล Graph Retrieval (Knowledge Graph Search)
    ค้นหาความสัมพันธ์เชิงโครงสร้าง เงื่อนไข อาการบาดเจ็บ และการจับคู่ทดแทน
    รองรับทั้งการเชื่อมต่อ Neo4j สด และ Fallback จาก knowledge_graph.json
    """
    def __init__(self, neo4j_uri=None, neo4j_user=None, neo4j_password=None, json_path=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Try Docker port 8687 first, fallback to standard 7687
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:8687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password123")

        
        self.json_path = json_path or os.path.join(base_dir, "data", "knowledge_graph.json")
        self.chunks_path = os.path.join(base_dir, "data", "chunks.json")
        
        # Load chunks to map exercise titles to image_path and page
        self.exercise_metadata = {}
        if os.path.exists(self.chunks_path):
            with open(self.chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                for c in chunks:
                    self.exercise_metadata[c["title"]] = {
                        "image_path": c.get("image_path", ""),
                        "page_number": c.get("page_number", 0),
                        "zone": c.get("zone", ""),
                        "muscle_group": c.get("muscle_group", "")
                    }
                    
        # Check Neo4j connection
        self.driver = None
        self.neo4j_active = False
        try:
            self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
            with self.driver.session() as s:
                s.run("RETURN 1 AS test")
            self.neo4j_active = True
        except Exception:
            self.neo4j_active = False
            
        # Load local In-Memory graph
        self.local_graph = {"nodes": {}, "edges": []}
        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.local_graph = json.load(f)
                
    def extract_entities_from_query(self, query: str):
        """วิเคราะห์สกัด Entity และคำสำคัญจากคำถามของผู้ใช้"""
        q_lower = query.lower()
        matched = {
            "conditions": [],
            "muscles": [],
            "zones": [],
            "exercises": []
        }
        
        # 1. Condition & Pain Keywords
        condition_rules = {
            "ปวดหลังล่าง (Lower Back Pain)": ["ปวดหลัง", "เจ็บหลัง", "หลังล่าง", "หลังแอ่น", "back pain", "lower back"],
            "ปวดข้อเข่า (Knee Pain)": ["ปวดเข่า", "เจ็บเข่า", "ข้อเข่า", "เข่าตึง", "knee pain"],
            "ปวดหัวไหล่ / ข้อต่อไหล่ติด (Shoulder Impingement)": ["ปวดไหล่", "เจ็บไหล่", "หัวไหล่ติด", "กระตุกข้อต่อ", "shoulder pain"],
            "ผู้เริ่มต้นฝึกออกกำลังกาย (Beginner)": ["ผู้เริ่มต้น", "มือใหม่", "เพิ่งเริ่ม", "ไม่เคยเล่น", "beginner"]
        }
        for cond, keywords in condition_rules.items():
            if any(k in q_lower for k in keywords):
                matched["conditions"].append(cond)
                
        # 2. Muscle & Muscle Group Keywords
        muscle_rules = {
            "กลุ่มกล้ามเนื้อขา (Leg Group)": ["ขา", "ต้นขา", "น่อง", "สะโพก", "leg", "quadriceps", "hamstring", "glute"],
            "กลุ่มกล้ามเนื้ออก (Chest Group)": ["อก", "หน้าอก", "อกบน", "อกล่าง", "อกใน", "อกกลาง", "chest", "pectoral"],
            "กลุ่มกล้ามเนื้อปีกและหลัง (Back Group)": ["หลัง", "ปีก", "สะบัก", "หลังบน", "back", "latissimus", "seated row", "lat pulldown"],
            "กลุ่มกล้ามเนื้อหัวไหล่ (Shoulder Group)": ["ไหล่", "หัวไหล่", "shoulder", "deltoid"],
            "กลุ่มกล้ามเนื้อแขน (Biceps Group)": ["หน้าแขน", "ต้นแขนด้านหน้า", "biceps", "arm curl", "dumbbell curl"],
            "กลุ่มกล้ามเนื้อแขน (Triceps Group)": ["หลังแขน", "ต้นแขนด้านหลัง", "triceps", "kick back", "press down"],
            "หน้าท้องและลำตัว (Abdominal & Obliques)": ["ท้อง", "หน้าท้อง", "ลำตัว", "เอว", "sit up", "abdominal", "oblique", "core"],
            "หัวใจและหลอดเลือด (Cardio)": ["คาร์ดิโอ", "วิ่ง", "ปั่นจักรยาน", "หัวใจ", "cardio", "treadmill", "bike", "rower"]
        }
        for m_group, keywords in muscle_rules.items():
            if any(k in q_lower for k in keywords):
                matched["muscles"].append(m_group)
                
        # 3. Zone / Equipment Keywords
        if any(k in q_lower for k in ["ดัมเบล", "dumbbell", "free weight", "ฟรีเวท"]):
            matched["zones"].append("Free Weight Zone")
        if any(k in q_lower for k in ["เครื่อง", "machine", "แมชชีน"]):
            matched["zones"].append("Weight Machine Zone")
        if any(k in q_lower for k in ["คาร์ดิโอ", "aerobic", "วิ่ง", "จักรยาน"]):
            matched["zones"].append("Aerobic Exercise Group")
            
        # 4. Exercise Match
        for node_name in self.local_graph.get("nodes", {}):
            clean_node = re.sub(r'^\d+\.\s*', '', node_name).lower()
            # If significant keyword of exercise appears in query
            en_match = re.search(r'\((.*?)\)', clean_node)
            if en_match:
                en_name = en_match.group(1).lower()
                if en_name in q_lower and len(en_name) > 3:
                    matched["exercises"].append(node_name)
                    
        return matched

    def search(self, query: str, top_k: int = 5):
        """
        ค้นหาความสัมพันธ์ใน Knowledge Graph
        คืนค่าโครงสร้างความสัมพันธ์ และข้อความสรุป Subgraph Fact
        """
        entities = self.extract_entities_from_query(query)
        
        avoid_list = []
        recommend_list = []
        target_exercises = []
        cautions_found = []
        
        edges = self.local_graph.get("edges", [])
        
        # 1. Traverse Condition Relationships (AVOID & RECOMMEND)
        for cond in entities["conditions"]:
            for e in edges:
                if e["source"] == cond:
                    if e["relation"] == "AVOID":
                        avoid_list.append({
                            "exercise": e["target"],
                            "condition": cond,
                            "reason": "เสี่ยงต่อการบาดเจ็บซ้ำหรืออาการรุนแรงขึ้น",
                            "metadata": self.exercise_metadata.get(e["target"], {})
                        })
                    elif e["relation"] == "RECOMMEND":
                        recommend_list.append({
                            "exercise": e["target"],
                            "condition": cond,
                            "reason": "ปลอดภัยและช่วยฟื้นฟูหรือฝึกทดแทนได้โดยไม่กระทบจุดบาดเจ็บ",
                            "metadata": self.exercise_metadata.get(e["target"], {})
                        })
                        
        # 2. Traverse Muscle Group Relationships
        for m_grp in entities["muscles"]:
            for e in edges:
                if e["target"] == m_grp and e["relation"] == "TARGETS_GROUP":
                    ex_name = e["source"]
                    # กรองเฉพาะท่าที่ไม่อยู่ใน avoid_list
                    if not any(a["exercise"] == ex_name for a in avoid_list):
                        target_exercises.append({
                            "exercise": ex_name,
                            "muscle_group": m_grp,
                            "metadata": self.exercise_metadata.get(ex_name, {})
                        })
                        
        # 3. Traverse Exercise Cautions
        for ex in entities["exercises"]:
            for e in edges:
                if e["source"] == ex and e["relation"] == "HAS_CAUTION":
                    cautions_found.append({
                        "exercise": ex,
                        "caution": e["target"]
                    })
                    
        # 4. Synthesize Subgraph Knowledge Text
        fact_lines = []
        
        if avoid_list:
            fact_lines.append("🚫 ข้อห้ามและท่าที่ควรหลีกเลี่ยง (จาก Knowledge Graph):")
            for item in avoid_list:
                fact_lines.append(f"  • หลีกเลี่ยงท่า: {item['exercise']} (เนื่องจากมีอาการ: {item['condition']})")
                
        if recommend_list:
            fact_lines.append(" ท่าที่แนะนำให้ฝึกทดแทน (จาก Knowledge Graph):")
            for item in recommend_list[:top_k]:
                pg = item['metadata'].get('page_number', '')
                img = item['metadata'].get('image_path', '')
                fact_lines.append(f"  • แนะนำท่า: {item['exercise']} (หน้า {pg}) [{item['reason']}] (รูป: {img})")
                
        if not avoid_list and not recommend_list and target_exercises:
            fact_lines.append(f"💪 ท่าออกกำลังกายที่บริหารกลุ่มเป้าหมาย (จาก Knowledge Graph):")
            for item in target_exercises[:top_k]:
                pg = item['metadata'].get('page_number', '')
                img = item['metadata'].get('image_path', '')
                fact_lines.append(f"  • {item['exercise']} (กลุ่ม: {item['muscle_group']}, หน้า {pg}) (รูป: {img})")
                
        if cautions_found:
            fact_lines.append("⚠️ ข้อควรระวังความปลอดภัย:")
            for item in cautions_found:
                fact_lines.append(f"  • {item['exercise']}: {item['caution']}")
                
        subgraph_text = "\n".join(fact_lines) if fact_lines else ""
        
        return {
            "entities": entities,
            "avoid_exercises": avoid_list,
            "recommend_exercises": recommend_list,
            "target_exercises": target_exercises[:top_k],
            "cautions": cautions_found,
            "subgraph_text": subgraph_text,
            "has_graph_facts": len(fact_lines) > 0,
            "source": "knowledge_graph"
        }

if __name__ == "__main__":
    retriever = GraphRetriever()
    test_queries = [
        "มีอาการปวดหลังล่าง ห้ามเล่นท่าไหน และเล่นท่าไหนแทนได้บ้าง",
        "อยากเล่นกล้ามเนื้อปีกและหลัง มีท่าไหนบ้าง",
        "ผู้เริ่มต้นฝึกออกกำลังกาย แนะนำเครื่องไหน"
    ]
    for q in test_queries:
        print(f"\n{'='*60}\nQuery: '{q}'")
        res = retriever.search(q, top_k=3)
        print(f"Entities Detected: {res['entities']}")
        print(res["subgraph_text"])
