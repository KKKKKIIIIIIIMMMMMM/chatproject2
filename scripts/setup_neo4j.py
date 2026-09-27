import os
import sys
import json
import csv
from collections import defaultdict
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from src.llm_engine import load_project_env
load_project_env()
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "graph_data.csv")
JSON_GRAPH_PATH = os.path.join(DATA_DIR, "knowledge_graph.json")

# This Neo4j instance also contains other projects. Keep this graph isolated.
PROJECT_ID = os.getenv("NEO4J_PROJECT_ID", "fitness_rag_final_2026")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
ALLOWED_KINDS = {"Caution", "Condition", "Equipment", "Exercise", "Muscle", "MuscleGroup", "Zone"}
ALLOWED_RELATIONS = {"LOCATED_IN", "TARGETS_GROUP", "USES_EQUIPMENT", "TARGETS", "HAS_CAUTION", "AVOID", "RECOMMEND"}


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

def _write_graph(tx, nodes, edges, project_id):
    by_kind = defaultdict(list)
    for node in nodes.values():
        by_kind[node["label"]].append(node)
    for kind, rows in by_kind.items():
        # Labels are interpolated only after validating against a fixed allowlist.
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"Unexpected graph node type: {kind}")
        tx.run(
            f"""UNWIND $rows AS row
            MERGE (n:FitnessEntity {{project_id: $project_id, name: row.name}})
            SET n:Fitness{kind}, n.kind = $kind, n.source_file = 'exercise/exercise.pdf',
                n.page = row.page, n.image_path = row.image_path""",
            rows=rows, project_id=project_id, kind=kind,
        ).consume()

    by_relation = defaultdict(list)
    for edge in edges:
        by_relation[edge["relation"]].append(edge)
    for relation, rows in by_relation.items():
        if relation not in ALLOWED_RELATIONS:
            raise ValueError(f"Unexpected relationship type: {relation}")
        tx.run(
            f"""UNWIND $rows AS row
            MATCH (a:FitnessEntity {{project_id: $project_id, name: row.source}})
            MATCH (b:FitnessEntity {{project_id: $project_id, name: row.target}})
            MERGE (a)-[r:{relation}]->(b)
            SET r.project_id = $project_id, r.source_file = 'exercise/exercise.pdf'""",
            rows=rows, project_id=project_id,
        ).consume()


def import_to_neo4j(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD):
    print("=" * 60)
    print("🚀 [Phase 2.2] Connecting to Neo4j Database")
    print(f"Target URI: {uri} (User: {user})")
    print("=" * 60)
    
    # Import from the checked-in JSON/CSV facts; do not touch unrelated nodes.
    if not os.path.exists(JSON_GRAPH_PATH):
        build_local_graph_json()
    with open(JSON_GRAPH_PATH, "r", encoding="utf-8") as handle:
        graph = json.load(handle)
    with open(os.path.join(DATA_DIR, "chunks.json"), "r", encoding="utf-8") as handle:
        chunk_metadata = {item["title"]: item for item in json.load(handle)}
    nodes = {}
    for name, item in graph["nodes"].items():
        metadata = chunk_metadata.get(name, {})
        nodes[name] = {
            "name": name, "label": item["label"],
            "page": metadata.get("page_number"),
            "image_path": metadata.get("image_path"),
        }
    edges = graph["edges"]
    if len(nodes) != 145 or len(edges) != 221:
        raise ValueError("Source graph counts changed; inspect the files before importing")
    if {item["label"] for item in nodes.values()} - ALLOWED_KINDS:
        raise ValueError("Unexpected node kinds in graph")
    if {item["relation"] for item in edges} - ALLOWED_RELATIONS:
        raise ValueError("Unexpected relationship kinds in graph")
    
    # 2. Try connecting to Neo4j instance
    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            driver.verify_connectivity()
            with driver.session() as session:
                session.run(
                    "CREATE CONSTRAINT fitness_entity_project_name IF NOT EXISTS "
                    "FOR (n:FitnessEntity) REQUIRE (n.project_id, n.name) IS UNIQUE"
                ).consume()
                session.execute_write(_write_graph, nodes, edges, PROJECT_ID)
                total_nodes = session.run(
                    "MATCH (n:FitnessEntity {project_id: $project_id}) RETURN count(n) AS count",
                    project_id=PROJECT_ID,
                ).single()["count"]
                total_rels = session.run(
                    "MATCH (a:FitnessEntity {project_id: $project_id})-[r]->"
                    "(b:FitnessEntity {project_id: $project_id}) RETURN count(r) AS count",
                    project_id=PROJECT_ID,
                ).single()["count"]
        if (total_nodes, total_rels) != (len(nodes), len(edges)):
            raise RuntimeError(f"Scoped graph mismatch: {total_nodes} nodes, {total_rels} relationships")
        print(f" [SUCCESS] Project {PROJECT_ID}: {total_nodes} nodes, {total_rels} relationships")
        return True
    except Exception as e:
        print(f"⚠️ [Notice] Could not connect to Neo4j server at {uri}: {e}")
        print("💡 [Solution] You can start Neo4j Desktop or Neo4j AuraDB whenever convenient.")
        print(f"Local fallback remains available at '{JSON_GRAPH_PATH}'.")
        return False

if __name__ == "__main__":
    import_to_neo4j()
