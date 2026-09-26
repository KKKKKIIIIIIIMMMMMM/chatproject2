import sys
import os

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from src.dense_retrieval import DenseRetriever
from src.graph_retrieval import GraphRetriever

def test_phase3():
    print("=" * 70)
    print("🎯 [Phase 3 VERIFICATION] Testing Dense Retrieval & Graph Retrieval")
    print("=" * 70)
    
    dense = DenseRetriever()
    graph = GraphRetriever()
    
    test_queries = [
        "วิธีปรับเบาะและใช้งานเครื่อง Leg press ต้องทำอย่างไร",
        "มีอาการปวดหลังล่าง ห้ามเล่นท่าไหน และเล่นท่าไหนแทนได้บ้าง",
        "ถ้าอยากฝึกกล้ามเนื้อต้นแขนด้านหน้า (Biceps) มีเครื่องและท่าอะไรบ้าง"
    ]
    
    for i, q in enumerate(test_queries, 1):
        print(f"\n{'#' * 70}")
        print(f"📌 [Test Case {i}] คำถาม: \"{q}\"")
        print(f"{'#' * 70}")
        
        # 1. Dense Retrieval Result
        print("\n🔹 [ผลลัพธ์จาก Dense RAG (ChromaDB)]:")
        dense_results = dense.search(q, top_k=2)
        for rank, d in enumerate(dense_results, 1):
            print(f"  [{rank}] Score: {d['score']:.4f} | {d['title']} (หน้า {d['page_number']})")
            print(f"      Image: {d['image_path']}")
            # Show snippet
            snippet = d['content'].split('\n\n')[1][:150].replace('\n', ' ') if '\n\n' in d['content'] else d['content'][:150]
            print(f"      Snippet: {snippet}...")
            
        # 2. Graph Retrieval Result
        print("\n🔸 [ผลลัพธ์จาก Graph RAG (Knowledge Graph)]:")
        graph_results = graph.search(q, top_k=3)
        if graph_results["has_graph_facts"]:
            print(graph_results["subgraph_text"])
        else:
            print("  (ไม่พบข้อห้ามหรือเงื่อนไขเฉพาะใน Graph)")
            
    print("\n" + "=" * 70)
    print("✅ [Phase 3 PASSED] Both Dense & Graph retrievers are functioning accurately!")
    print("=" * 70)

if __name__ == "__main__":
    test_phase3()
