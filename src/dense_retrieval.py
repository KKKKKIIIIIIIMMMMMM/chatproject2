import os
import sys
import chromadb
from sentence_transformers import SentenceTransformer

# Reconfigure stdout for UTF-8
sys.stdout.reconfigure(encoding='utf-8')

class DenseRetriever:
    """
    โมดูล Dense Retrieval (Vector Search) สำหรับค้นหาข้อความตามความหมาย
    ผ่าน ChromaDB และ intfloat/multilingual-e5-small
    """
    def __init__(self, chroma_dir=None, model_name="intfloat/multilingual-e5-small", collection_name="fitness_knowledge"):
        if chroma_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            chroma_dir = os.path.join(base_dir, "data", "chroma_db")
            
        self.chroma_dir = chroma_dir
        self.model_name = model_name
        self.collection_name = collection_name
        
        # Load Embedding Model
        self.model = SentenceTransformer(self.model_name)
        
        # Connect to ChromaDB
        self.client = chromadb.PersistentClient(path=self.chroma_dir)
        self.collection = self.client.get_collection(self.collection_name)
        
    def search(self, query: str, top_k: int = 3, score_threshold: float = 0.5):
        """
        ค้นหาท่อนข้อความที่เกี่ยวข้องตามความหมาย (Cosine Similarity)
        
        Args:
            query: คำถามของผู้ใช้
            top_k: จำนวนผลลัพธ์สูงสุดที่ต้องการ
            score_threshold: ค่าความคล้ายคลึงขั้นต่ำ (0.0 - 1.0)
            
        Returns:
            list of dict: รายการผลลัพธ์พร้อมคะแนน similarity และ metadata
        """
        # Prefix "query: " for E5 embedding models
        query_text = "query: " + query
        q_emb = self.model.encode([query_text], normalize_embeddings=True)[0]
        
        results = self.collection.query(
            query_embeddings=[q_emb.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        formatted_results = []
        if not results["ids"] or not results["ids"][0]:
            return formatted_results
            
        for i in range(len(results["ids"][0])):
            dist = results["distances"][0][i]
            sim = 1.0 - dist  # Cosine Similarity score
            
            # Apply similarity threshold
            if sim < score_threshold:
                continue
                
            meta = results["metadatas"][0][i]
            doc_text = results["documents"][0][i]
            
            formatted_results.append({
                "chunk_id": results["ids"][0][i],
                "title": meta.get("title", ""),
                "score": round(float(sim), 4),
                "distance": round(float(dist), 4),
                "content": doc_text,
                "image_path": meta.get("image_path", ""),
                "zone": meta.get("zone", ""),
                "muscle_group": meta.get("muscle_group", ""),
                "target_muscles": meta.get("target_muscles", ""),
                "page_number": meta.get("page_number", 0),
                "content_type": meta.get("content_type", "exercise_guide"),
                "source": "dense_vector"
            })
            
        return formatted_results

if __name__ == "__main__":
    retriever = DenseRetriever()
    query = "วิธีเล่นเครื่อง Leg press ต้องวางเท้าและหายใจอย่างไร"
    print(f"Testing DenseRetriever with query: '{query}'")
    hits = retriever.search(query, top_k=2)
    for idx, h in enumerate(hits, 1):
        print(f"[{idx}] (Score: {h['score']}) {h['title']} (Page {h['page_number']})")
        print(f"     Image: {h['image_path']}")
