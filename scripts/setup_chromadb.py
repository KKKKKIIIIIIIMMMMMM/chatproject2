import os
import sys
import json
import chromadb
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHUNKS_PATH = os.path.join(DATA_DIR, "chunks.json")
CHROMA_PERSIST_DIR = os.path.join(DATA_DIR, "chroma_db")

COLLECTION_NAME = "fitness_knowledge"
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"

def build_chromadb():
    print("=" * 60)
    print("🚀 [Phase 2.1] Building ChromaDB Vector Index")
    print("=" * 60)
    
    # 1. Load Chunks
    if not os.path.exists(CHUNKS_PATH):
        raise FileNotFoundError(f"Missing {CHUNKS_PATH}. Run Phase 1 first!")
        
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks from {CHUNKS_PATH}")
    
    # 2. Load Embedding Model
    print(f"Loading Embedding Model: {EMBEDDING_MODEL_NAME} ...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    
    # 3. Initialize Persistent ChromaDB Client
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    # Reset / recreate collection if exists
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Cleared existing collection: {COLLECTION_NAME}")
    except Exception:
        pass
        
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "model": EMBEDDING_MODEL_NAME}
    )
    
    # 4. Prepare Embeddings and Metadata
    ids = []
    documents = []
    metadatas = []
    passages = []
    
    for c in chunks:
        ids.append(c["chunk_id"])
        documents.append(c["content"])
        passages.append("passage: " + c["content"])
        
        # Metadata for filtering and visual rendering
        meta = {
            "exercise_id": c.get("exercise_id", ""),
            "title": c.get("title", ""),
            "zone": c.get("zone", ""),
            "muscle_group": c.get("muscle_group", ""),
            "target_muscles": c.get("target_muscles", ""),
            "equipment": c.get("equipment", ""),
            "page_number": int(c.get("page_number", 0)),
            "image_path": c.get("image_path", ""),
            "has_cautions": bool(c.get("has_cautions", False)),
            "content_type": c.get("content_type", "exercise_guide")
        }
        metadatas.append(meta)
        
    # 5. Generate Vector Embeddings
    print("Generating dense vector embeddings for all passages...")
    embeddings = model.encode(passages, normalize_embeddings=True, show_progress_bar=True)
    
    # 6. Add to ChromaDB
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings.tolist(),
        metadatas=metadatas
    )
    print(f" Successfully indexed {collection.count()} chunks into ChromaDB at '{CHROMA_PERSIST_DIR}'")
    
    # 7. Verification Test Queries
    print("\n--- Running Verification Test Queries ---")
    test_queries = [
        "วิธีปรับเบาะและใช้งานเครื่อง Leg press",
        "มีปัญหาปวดหลังล่าง ห้ามทำท่าไหน",
        "เป้าหมายความแข็งแรง Strength ต้องฝึกกี่ครั้งกี่เซต"
    ]
    
    for q in test_queries:
        query_text = "query: " + q
        q_emb = model.encode([query_text], normalize_embeddings=True)[0]
        results = collection.query(
            query_embeddings=[q_emb.tolist()],
            n_results=2,
            include=["documents", "metadatas", "distances"]
        )
        print(f"\n🔍 Query: '{q}'")
        for i in range(len(results["ids"][0])):
            m = results["metadatas"][0][i]
            dist = results["distances"][0][i]
            sim = 1.0 - dist  # Cosine similarity
            print(f"   [Rank {i+1}] (Sim: {sim:.4f}) {m['title']} (Page {m['page_number']})")
            print(f"          Image: {m['image_path']}")
            print(f"          Zone : {m['zone']}")
            
    print("\n" + "=" * 60)
    print("🎯 [Phase 2.1 COMPLETE] ChromaDB Vector Database is ready!")
    print("=" * 60)

if __name__ == "__main__":
    build_chromadb()
