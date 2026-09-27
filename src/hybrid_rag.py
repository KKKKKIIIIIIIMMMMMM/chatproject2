import os
import sys
import time
import json
import re
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Ensure parent directory is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.dense_retrieval import DenseRetriever
from src.graph_retrieval import GraphRetriever

class QueryRouter:
    """
    Query Router สำหรับจำแนกประเภทเจตนาของคำถาม (Query Intent)
    เพื่อเลือกกลยุทธ์การค้นหาที่เหมาะสมที่สุด (Dense, Graph, หรือ Hybrid)
    """
    # คำบ่งชี้ขั้นตอน วิธีการปฏิบัติ การจัดท่าทาง และสรีระ (Procedural Keywords)
    PROCEDURAL_KEYWORDS = [
        "วิธีเล่น", "วิธีใช้", "ขั้นตอน", "ปรับเบาะ", "วางเท้า", "จับบาร์",
        "หายใจ", "จังหวะ", "ท่าทาง", "ท่าเริ่มต้น", "ท่าสิ้นสุด", "แอ่นหลัง",
        "เกร็ง", "บีบสะบัก", "เซตละ", "กี่ครั้ง", "1rm", "กี่เซต", "หนักเท่าไหร่"
    ]
    
    # คำบ่งชี้ความสัมพันธ์ โครงสร้างกล้ามเนื้อ และข้อห้ามทางการแพทย์ (Relational Keywords)
    RELATIONAL_KEYWORDS = [
        "ปวด", "เจ็บ", "บาดเจ็บ", "ห้ามเล่น", "เลี่ยง", "ข้อห้าม", "ระวัง",
        "กล้ามเนื้อส่วนไหน", "โดนส่วนไหน", "มัดไหน", "กลุ่มกล้ามเนื้อ",
        "มือใหม่", "ผู้เริ่มต้น", "แทนได้", "ท่าไหนบ้าง", "เครื่องไหนบ้าง", "โซนไหน"
    ]

    @classmethod
    def route_query(cls, query: str) -> Dict[str, Any]:
        """
        วิเคราะห์คำถามและตัดสินใจเลือกลักษณะการค้นหา (Query Routing)
        """
        q_lower = query.lower()
        
        proc_hits = [k for k in cls.PROCEDURAL_KEYWORDS if k in q_lower]
        rel_hits = [k for k in cls.RELATIONAL_KEYWORDS if k in q_lower]
        
        proc_score = len(proc_hits)
        rel_score = len(rel_hits)
        
        # กฎการตัดสินใจ
        if proc_score > 0 and rel_score > 0:
            route = "hybrid"
            rationale = "คำถามมีทั้งความต้องการเชิงขั้นตอน (Procedural) และความสัมพันธ์/เงื่อนไข (Relational)"
        elif proc_score > 0:
            route = "dense"
            rationale = "คำถามเน้นขั้นตอนการปฏิบัติ ท่าทาง หรือวิธีการปรับอุปกรณ์ (Dense Vector เหมาะสมที่สุด)"
        elif rel_score > 0:
            route = "graph"
            rationale = "คำถามเน้นความสัมพันธ์ของกล้ามเนื้อ ข้อควรระวัง หรือเงื่อนไขการบาดเจ็บ (Knowledge Graph เหมาะสมที่สุด)"
        else:
            # ค่าตั้งต้นหากไม่เจอคีย์เวิร์ดชัดเจน ให้ใช้ Hybrid เพื่อความครบถ้วน
            route = "hybrid"
            rationale = "คำถามทั่วไป ใช้กลยุทธ์ Hybrid RAG เพื่อดึงความรู้ทั้งสองด้านมาผสมผสาน"
            
        return {
            "route": route,
            "procedural_keywords": proc_hits,
            "relational_keywords": rel_hits,
            "rationale": rationale
        }


class HybridRAG:
    """
    ระบบ Hybrid RAG Core ที่รวม Dense Vector Search และ Knowledge Graph เข้าด้วยกัน
    ผ่านอัลกอริทึม Reciprocal Rank Fusion (RRF) พร้อมระบบความปลอดภัย (Safety Filtering)
    และตัวจัดเตรียมบริบท (Context Aggregator) สำหรับส่งให้ LLM
    """
    def __init__(self, dense_retriever: Optional[DenseRetriever] = None, 
                 graph_retriever: Optional[GraphRetriever] = None,
                 rrf_k: int = 60,
                 dense_weight: float = 1.0,
                 graph_weight: float = 1.2):
        
        self.dense_retriever = dense_retriever or DenseRetriever()
        self.graph_retriever = graph_retriever or GraphRetriever()
        
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.graph_weight = graph_weight
        
        # Load all chunks for quick lookups
        self.chunks_path = os.path.join(BASE_DIR, "data", "chunks.json")
        self.chunks_by_title = {}
        if os.path.exists(self.chunks_path):
            with open(self.chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)
                for c in all_chunks:
                    self.chunks_by_title[c["title"]] = c

    def normalize_title(self, title: str) -> str:
        """ทำความสะอาดชื่อท่าออกกำลังกายเพื่อใช้เชื่อมต่อระหว่าง Vector และ Graph"""
        clean = re.sub(r'^\d+\.\s*', '', title)
        return clean.strip().lower()

    def reciprocal_rank_fusion(self, dense_results: List[Dict[str, Any]], 
                               graph_results: Dict[str, Any], 
                               top_k: int = 5) -> List[Dict[str, Any]]:
        """
        ผสานผลลัพธ์ของ Dense Retrieval และ Graph Retrieval ด้วย Reciprocal Rank Fusion (RRF)
        
        สูตรคำนวณ:
            RRF_score(d) = SUM_{m in Models} [ Weight_m / (k + Rank_m(d)) ]
        """
        fused_scores = {}
        item_details = {}
        
        # 1. ให้คะแนนจาก Dense Vector Results
        for rank, d_item in enumerate(dense_results, 1):
            key = d_item["title"]
            score = self.dense_weight / (self.rrf_k + rank)
            
            fused_scores[key] = fused_scores.get(key, 0.0) + score
            if key not in item_details:
                item_details[key] = {
                    "title": d_item["title"],
                    "chunk_id": d_item.get("chunk_id"),
                    "content": d_item.get("content", ""),
                    "image_path": d_item.get("image_path", ""),
                    "page_number": d_item.get("page_number", 0),
                    "zone": d_item.get("zone", ""),
                    "muscle_group": d_item.get("muscle_group", ""),
                    "target_muscles": d_item.get("target_muscles", ""),
                    "dense_rank": rank,
                    "dense_score": d_item.get("score", 0.0),
                    "graph_rank": None,
                    "sources": ["dense_vector"]
                }
            else:
                item_details[key]["dense_rank"] = rank
                item_details[key]["dense_score"] = d_item.get("score", 0.0)
                if "dense_vector" not in item_details[key]["sources"]:
                    item_details[key]["sources"].append("dense_vector")

        # 2. ให้คะแนนจาก Graph Results (Recommended / Target Exercises)
        graph_candidates = []
        # ท่าที่ Graph แนะนำจากอาการ/เงื่อนไข
        for item in graph_results.get("recommend_exercises", []):
            graph_candidates.append({
                "title": item["exercise"],
                "reason": item.get("reason", ""),
                "condition": item.get("condition", "")
            })
        # ท่าที่ตรงกับกลุ่มกล้ามเนื้อเป้าหมาย
        for item in graph_results.get("target_exercises", []):
            if not any(c["title"] == item["exercise"] for c in graph_candidates):
                graph_candidates.append({
                    "title": item["exercise"],
                    "reason": f"บริหารกล้ามเนื้อกลุ่ม {item.get('muscle_group', '')}",
                    "condition": ""
                })

        for rank, g_item in enumerate(graph_candidates, 1):
            key = g_item["title"]
            score = self.graph_weight / (self.rrf_k + rank)
            fused_scores[key] = fused_scores.get(key, 0.0) + score
            
            if key not in item_details:
                # ดึง metadata เพิ่มเติมจาก chunks.json
                chunk_info = self.chunks_by_title.get(key, {})
                item_details[key] = {
                    "title": key,
                    "chunk_id": chunk_info.get("id"),
                    "content": chunk_info.get("content", ""),
                    "image_path": chunk_info.get("image_path", ""),
                    "page_number": chunk_info.get("page_number", 0),
                    "zone": chunk_info.get("zone", ""),
                    "muscle_group": chunk_info.get("muscle_group", ""),
                    "target_muscles": chunk_info.get("target_muscles", ""),
                    "dense_rank": None,
                    "dense_score": None,
                    "graph_rank": rank,
                    "graph_reason": g_item.get("reason", ""),
                    "sources": ["knowledge_graph"]
                }
            else:
                item_details[key]["graph_rank"] = rank
                item_details[key]["graph_reason"] = g_item.get("reason", "")
                if "knowledge_graph" not in item_details[key]["sources"]:
                    item_details[key]["sources"].append("knowledge_graph")

        # 3. จัดการ Safety Filter (ตรวจจับข้อห้าม AVOID จาก Knowledge Graph)
        avoid_titles = [a["exercise"] for a in graph_results.get("avoid_exercises", [])]
        for key in item_details:
            if key in avoid_titles:
                item_details[key]["safety_status"] = "AVOID_CONTRAINDICATION"
                # ลดคะแนน RRF ของท่าอันตรายเพื่อไม่ให้ถูกแนะนำเป็นอันดับแรก
                fused_scores[key] *= 0.1
            else:
                item_details[key]["safety_status"] = "SAFE"

        # 4. เรียงลำดับตามคะแนน RRF จากมากไปน้อย
        sorted_keys = sorted(fused_scores.keys(), key=lambda k: fused_scores[k], reverse=True)
        
        fused_items = []
        for rank, k in enumerate(sorted_keys[:top_k], 1):
            item = item_details[k]
            item["rrf_rank"] = rank
            item["rrf_score"] = round(float(fused_scores[k]), 5)
            fused_items.append(item)
            
        return fused_items

    def retrieve(self, query: str, mode: str = "auto", top_k: int = 4) -> Dict[str, Any]:
        """
        ฟังก์ชันหลักในการค้นหาแบบบูรณาการ
        
        Args:
            query: คำถามของผู้ใช้
            mode: รูปแบบการทำงาน ("auto", "dense", "graph", "hybrid")
            top_k: จำนวนผลลัพธ์ที่ต้องการนำมาจัดโครงสร้างบริบท
            
        Returns:
            Dict สรุปบริบท ผลการค้นหา เมทริกซ์เวลา และข้อมูลรูปภาพ
        """
        start_time = time.time()
        
        # 1. Routing
        routing_info = QueryRouter.route_query(query)
        selected_mode = mode if mode != "auto" else routing_info["route"]
        
        dense_results = []
        graph_results = {"entities": {}, "avoid_exercises": [], "recommend_exercises": [], 
                         "target_exercises": [], "cautions": [], "subgraph_text": ""}
        dense_time_ms = 0.0
        graph_time_ms = 0.0
        
        # 2. Execution ตามโหมดที่เลือก
        if selected_mode in ["dense", "hybrid"]:
            t0 = time.time()
            dense_results = self.dense_retriever.search(query, top_k=top_k * 2)
            dense_time_ms = round((time.time() - t0) * 1000, 2)
            
        if selected_mode in ["graph", "hybrid"]:
            t0 = time.time()
            graph_results = self.graph_retriever.search(query, top_k=top_k * 2)
            graph_time_ms = round((time.time() - t0) * 1000, 2)
            
        # 3. Fusion & Ranking
        t0 = time.time()
        if selected_mode == "hybrid":
            ranked_items = self.reciprocal_rank_fusion(dense_results, graph_results, top_k=top_k)
        elif selected_mode == "dense":
            ranked_items = []
            for rank, d in enumerate(dense_results[:top_k], 1):
                d_copy = dict(d)
                d_copy["rrf_rank"] = rank
                d_copy["rrf_score"] = d["score"]
                d_copy["safety_status"] = "SAFE"
                d_copy["sources"] = ["dense_vector"]
                ranked_items.append(d_copy)
        else: # graph only
            ranked_items = self.reciprocal_rank_fusion([], graph_results, top_k=top_k)
        fusion_time_ms = round((time.time() - t0) * 1000, 2)
        
        total_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # 4. Context Aggregator: ผสานข้อความและเตรียมโครงสร้างสำหรับ LLM
        aggregated_context, attached_images = self.build_augmented_context(
            query=query,
            ranked_items=ranked_items,
            graph_results=graph_results,
            selected_mode=selected_mode
        )
        
        return {
            "query": query,
            "selected_mode": selected_mode,
            "graph_backend": graph_results.get("source") if selected_mode in ["graph", "hybrid"] else None,
            "routing_info": routing_info,
            "total_latency_ms": total_time_ms,
            "latency_breakdown_ms": {
                "dense": dense_time_ms,
                "graph": graph_time_ms,
                "fusion": fusion_time_ms
            },
            "ranked_items": ranked_items,
            "graph_summary": graph_results.get("subgraph_text", ""),
            "avoid_exercises": graph_results.get("avoid_exercises", []),
            "recommend_exercises": graph_results.get("recommend_exercises", []),
            "attached_images": attached_images,
            "augmented_context": aggregated_context
        }

    def build_augmented_context(self, query: str, ranked_items: List[Dict[str, Any]], 
                                graph_results: Dict[str, Any], selected_mode: str) -> (str, List[Dict[str, Any]]):
        """
        จัดโครงสร้าง Context ให้สมบูรณ์แบบเพื่อส่งต่อให้ LLM ใน Phase 5
        พร้อมระบุข้อควรระวังความปลอดภัย และรูปภาพประกอบที่เกี่ยวข้อง
        """
        context_sections = []
        attached_images = []
        
        context_sections.append(f"=== [คลังข้อมูลอ้างอิงคู่มือสถานกีฬาและสุขภาพ มทส. (โหมด: {selected_mode.upper()})] ===")
        
        # ส่วนที่ 1: ข้อห้ามทางการแพทย์และอาการบาดเจ็บ (ถ้ามี - ดึงจาก Graph เสมอ)
        avoid_list = graph_results.get("avoid_exercises", [])
        if avoid_list:
            context_sections.append("\n🚫 [คำเตือนความปลอดภัยทางการแพทย์ (Safety Contraindications)]")
            for av in avoid_list:
                context_sections.append(f"- ห้าม/หลีกเลี่ยง: {av['exercise']} (สาเหตุ: ตรวจพบ {av['condition']} เสี่ยงบาดเจ็บ)")

        # ส่วนที่ 2: ท่าแนะนำและความรู้เชิงโครงสร้าง
        graph_text = graph_results.get("subgraph_text", "")
        if graph_text and selected_mode in ["graph", "hybrid"]:
            context_sections.append(f"\n🔗 [ความรู้เชิงโครงสร้าง (Knowledge Graph Facts)]\n{graph_text}")
            
        # ส่วนที่ 3: รายละเอียดท่า ขั้นตอนการปฏิบัติ และรูปภาพสาธิต
        if ranked_items:
            context_sections.append("\n📖 [รายละเอียดขั้นตอนการปฏิบัติและสรีระ (Step-by-Step Instructions)]")
            for idx, item in enumerate(ranked_items, 1):
                title = item.get("title", "")
                page = item.get("page_number", "")
                zone = item.get("zone", "")
                m_group = item.get("muscle_group", "")
                target_m = item.get("target_muscles", "")
                content = item.get("content", "").strip()
                img = item.get("image_path", "")
                
                header = f"\n--- ลำดับที่ {idx}: {title} (โซน: {zone}, กลุ่ม: {m_group}, หน้า {page}) ---"
                if target_m:
                    header += f"\nกล้ามเนื้อเป้าหมาย: {target_m}"
                context_sections.append(header)
                
                if content:
                    context_sections.append(content)
                    
                if img and os.path.exists(img):
                    attached_images.append({
                        "exercise": title,
                        "page": page,
                        "path": img
                    })
                    context_sections.append(f"[รูปภาพสาธิตประกอบ: มีภาพสาธิตแสดงท่าเริ่มต้นและท่าออกแรงพร้อมใช้งาน]")
                    
        full_context = "\n".join(context_sections)
        return full_context, attached_images


if __name__ == "__main__":
    rag = HybridRAG()
    test_query = "มีอาการปวดหลังล่าง ห้ามเล่นเครื่องไหน และแนะนำให้เล่นท่าไหนแทน พร้อมวิธีเล่น"
    print(f"Testing HybridRAG with query: '{test_query}'\n")
    res = rag.retrieve(test_query, mode="auto", top_k=3)
    
    print(f"Route: {res['selected_mode']} (Rationale: {res['routing_info']['rationale']})")
    print(f"Total Latency: {res['total_latency_ms']} ms")
    print("\n--- Fused Ranking Results ---")
    for item in res["ranked_items"]:
        print(f"Rank {item['rrf_rank']} | Score: {item['rrf_score']} | {item['title']} | Status: {item['safety_status']} | Sources: {item['sources']}")
        
    print("\n--- Attached Images ---")
    for img in res["attached_images"]:
        print(f"Image for: {img['exercise']} -> {img['path']}")
