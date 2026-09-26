import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
JSON_PATH = os.path.join(DATA_DIR, "knowledge_graph.json")
HTML_PATH = os.path.join(DATA_DIR, "graph_visualization.html")

def generate_interactive_graph():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        graph = json.load(f)
        
    nodes_data = graph["nodes"]
    edges_data = graph["edges"]
    
    # Color palette by label
    color_map = {
        "Exercise": {"background": "#3b82f6", "border": "#1d4ed8", "highlight": "#60a5fa"}, # Blue
        "Muscle": {"background": "#10b981", "border": "#047857", "highlight": "#34d399"},   # Green
        "MuscleGroup": {"background": "#059669", "border": "#065f46", "highlight": "#10b981"},# Dark Green
        "Zone": {"background": "#8b5cf6", "border": "#6d28d9", "highlight": "#a78bfa"},       # Purple
        "Equipment": {"background": "#f59e0b", "border": "#d97706", "highlight": "#fbbf24"},  # Amber
        "Condition": {"background": "#ef4444", "border": "#b91c1c", "highlight": "#f87171"},  # Red
        "Caution": {"background": "#f97316", "border": "#c2410c", "highlight": "#fb923c"}     # Orange
    }
    
    vis_nodes = []
    for name, info in nodes_data.items():
        lbl = info.get("label", "Node")
        c = color_map.get(lbl, {"background": "#9ca3af", "border": "#4b5563", "highlight": "#d1d5db"})
        
        # Display short label
        display_label = name
        if len(display_label) > 25:
            display_label = display_label[:22] + "..."
            
        vis_nodes.append({
            "id": name,
            "label": display_label,
            "title": f"<b>{name}</b><br>Type: {lbl}",
            "color": {
                "background": c["background"],
                "border": c["border"],
                "highlight": {"background": c["highlight"], "border": c["border"]}
            },
            "shape": "dot" if lbl != "Condition" else "diamond",
            "size": 25 if lbl in ["Condition", "Zone", "MuscleGroup"] else 18,
            "font": {"color": "#1f2937", "size": 13, "face": "Sarabun, sans-serif"}
        })
        
    vis_edges = []
    edge_color_map = {
        "AVOID": "#ef4444",        # Red
        "RECOMMEND": "#10b981",    # Green
        "TARGETS": "#3b82f6",      # Blue
        "TARGETS_GROUP": "#059669",# Dark Green
        "LOCATED_IN": "#8b5cf6",   # Purple
        "USES_EQUIPMENT": "#f59e0b",
        "HAS_CAUTION": "#f97316"
    }
    
    for e in edges_data:
        rel = e["relation"]
        c = edge_color_map.get(rel, "#9ca3af")
        vis_edges.append({
            "from": e["source"],
            "to": e["target"],
            "label": rel,
            "arrows": "to",
            "color": {"color": c, "highlight": c},
            "font": {"size": 9, "align": "middle", "color": "#4b5563"},
            "width": 2 if rel in ["AVOID", "RECOMMEND"] else 1
        })
        
    html_content = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <title>Fitness Knowledge Graph Visualization (Neo4j)</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{
      font-family: 'Sarabun', sans-serif;
      margin: 0;
      padding: 0;
      background: #0f172a;
      color: #f8fafc;
      overflow: hidden;
    }}
    #header {{
      background: #1e293b;
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #334155;
    }}
    #header h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      color: #38bdf8;
    }}
    #stats {{
      font-size: 13px;
      color: #94a3b8;
    }}
    #network {{
      width: 100vw;
      height: calc(100vh - 58px);
    }}
    .legend {{
      position: absolute;
      bottom: 20px;
      left: 20px;
      background: rgba(30, 41, 59, 0.9);
      backdrop-filter: blur(8px);
      padding: 12px 18px;
      border-radius: 8px;
      border: 1px solid #334155;
      font-size: 12px;
      z-index: 10;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      margin-bottom: 6px;
    }}
    .legend-color {{
      width: 14px;
      height: 14px;
      border-radius: 50%;
      margin-right: 8px;
      border: 1px solid rgba(255,255,255,0.2);
    }}
    .instructions {{
      position: absolute;
      top: 70px;
      right: 20px;
      background: rgba(30, 41, 59, 0.9);
      padding: 10px 16px;
      border-radius: 8px;
      border: 1px solid #334155;
      font-size: 12px;
      color: #cbd5e1;
      z-index: 10;
    }}
  </style>
</head>
<body>
  <div id="header">
    <h1>🏋️ Neo4j Knowledge Graph: คู่มือออกกำลังกายและใช้อุปกรณ์สถานกีฬาและสุขภาพ</h1>
    <div id="stats">
      📊 โหนดทั้งหมด: <b>{len(vis_nodes)} Nodes</b> | เส้นความสัมพันธ์: <b>{len(vis_edges)} Relationships</b>
    </div>
  </div>

  <div class="instructions">
    💡 <b>วิธีใช้งาน:</b> คลิก ลาก ซูมดูโหนดได้อิสระ | คลิกที่โหนดเพื่อดูจุดเชื่อมโยง
  </div>

  <div class="legend">
    <div style="font-weight: 700; margin-bottom: 8px; color: #38bdf8;">🏷️ ประเภทโหนด (Labels)</div>
    <div class="legend-item"><div class="legend-color" style="background: #3b82f6;"></div> Exercise (ท่า/เครื่อง)</div>
    <div class="legend-item"><div class="legend-color" style="background: #ef4444; border-radius: 2px;"></div> Condition (อาการบาดเจ็บ / ข้อห้าม)</div>
    <div class="legend-item"><div class="legend-color" style="background: #10b981;"></div> Muscle (กล้ามเนื้อมัดเฉพาะ)</div>
    <div class="legend-item"><div class="legend-color" style="background: #059669;"></div> MuscleGroup (กลุ่มกล้ามเนื้อหลัก)</div>
    <div class="legend-item"><div class="legend-color" style="background: #8b5cf6;"></div> Zone (โซนอุปกรณ์)</div>
    <div class="legend-item"><div class="legend-color" style="background: #f59e0b;"></div> Equipment (ชนิดอุปกรณ์)</div>
    <div class="legend-item"><div class="legend-color" style="background: #f97316;"></div> Caution (ข้อควรระวัง)</div>
  </div>

  <div id="network"></div>

  <script type="text/javascript">
    const nodes = new vis.DataSet({json.dumps(vis_nodes, ensure_ascii=False)});
    const edges = new vis.DataSet({json.dumps(vis_edges, ensure_ascii=False)});

    const container = document.getElementById('network');
    const data = {{ nodes: nodes, edges: edges }};
    const options = {{
      physics: {{
        barnesHut: {{
          gravitationalConstant: -3500,
          centralGravity: 0.3,
          springLength: 95,
          springConstant: 0.04,
          damping: 0.09,
          avoidOverlap: 0.2
        }},
        maxVelocity: 50,
        minVelocity: 0.1,
        stabilization: {{ iterations: 150 }}
      }},
      interaction: {{
        hover: true,
        tooltipDelay: 100,
        zoomView: true,
        navigationButtons: true
      }},
      edges: {{
        smooth: {{ type: 'continuous' }}
      }}
    }};

    const network = new vis.Network(container, data, options);
  </script>
</body>
</html>
"""
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f" [SUCCESS] Generated Interactive Knowledge Graph HTML at: {HTML_PATH}")
    return HTML_PATH

if __name__ == "__main__":
    generate_interactive_graph()
