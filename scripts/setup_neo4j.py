import os
import sys
import json
import csv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "graph_data.csv")
CYPHER_PATH = os.path.join(DATA_DIR, "init_neo4j.cypher")
JSON_GRAPH_PATH = os.path.join(DATA_DIR, "knowledge_graph.json")

# Default connection settings (supports user's Docker container on port 8687 or 7687)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:8687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")


def build_local_graph_json():
    """สร้างไฟล์ knowledge_graph.json สำหรับเป็น Fast In-Memory Graph Engine / Fallback"""
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        triples = list(reader)
        
    nodes = {}
    edges = []
    
    for t in triples:
        s = t["source"]
        s_lbl = t["source_label"]
        rel = t["relation"]
        tgt = t["target"]
        t_lbl = t["target_label"]
        
        if s not in nodes:
            nodes[s] = {"name": s, "label": s_lbl}
        if tgt not in nodes:
            nodes[tgt] = {"name": tgt, "label": t_lbl}
            
        edges.append({
            "source": s,
            "relation": rel,
            "target": tgt
        })
        
    graph_data = {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }
    
    with open(JSON_GRAPH_PATH, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    print(f" [OK] Built Local Graph Structure: {len(nodes)} nodes, {len(edges)} edges -> {JSON_GRAPH_PATH}")
    return graph_data

def import_to_neo4j(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD):
    print("=" * 60)
    print("🚀 [Phase 2.2] Connecting to Neo4j Database")
    print(f"Target URI: {uri} (User: {user})")
    print("=" * 60)
    
    # 1. Build local graph representation first (always available)
    build_local_graph_json()
    
    # 2. Try connecting to Neo4j instance
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Check connection
            session.run("RETURN 1 AS test")
            print(" Connected to Neo4j successfully!")
            
            # Read and execute Cypher script
            print(f"Executing Cypher script from {CYPHER_PATH} ...")
            with open(CYPHER_PATH, "r", encoding="utf-8") as f:
                cypher_content = f.read()
                
            statements = [stmt.strip() for stmt in cypher_content.split(";") if stmt.strip() and not stmt.strip().startswith("//")]
            for stmt in statements:
                session.run(stmt)
                
            total_nodes = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
            print(f" [SUCCESS] Neo4j populated with {total_nodes} nodes and {total_rels} relationships!")
        driver.close()
        return True
    except Exception as e:
        print(f"⚠️ [Notice] Could not connect to Neo4j server at {uri}: {e}")
        print("💡 [Solution] You can start Neo4j Desktop or Neo4j AuraDB whenever convenient.")
        print(f"✅ The system has generated '{JSON_GRAPH_PATH}' as an In-Memory Graph fallback so Graph RAG development and testing can proceed seamlessly without any downtime!")
        return False

if __name__ == "__main__":
    import_to_neo4j()
