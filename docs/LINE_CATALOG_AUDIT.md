# LINE exercise catalogue: source audit

The LINE UI uses `data/chunks.json` as its source of page numbers, exercise IDs,
titles, text and image paths. `src/line_catalog.py` supplies the eight navigation
groups and optional subgroup filters. A menu selection never lets an LLM invent
an exercise ID or image filename.

| Group | Manual pages | Pictured exercises |
| --- | --- | ---: |
| Legs and glutes | 12–18 | 7 |
| Chest | 19–21, 42–45 | 7 |
| Back | 23–25, 40–41 | 5 |
| Shoulders | 22, 37–39 | 4 |
| Biceps | 26, 31–33 | 4 |
| Triceps | 27–28, 34–36 | 5 |
| Abdominals and core | 10–11, 29–30 | 4 |
| Cardio | 6–9 | 4 |
| **Total** | **6–45** | **40** |

All 40 exercise chunks have distinct IDs, distinct pages and an existing JPEG
in `data/images/`. Page 46 has four text-only training-goal chunks and no image;
ordinary RAG can answer from them but should not attach an exercise photo.

`C:/Users/lenovo/Downloads/checklist.md` is a useful classification draft,
but it conflicts with the current indexed data in several places:

- It says 39 exercises while its detailed rows sum to 40; the indexed PDF has 40.
- It lists page 11 as Multi Hip in the legs section; the indexed manual has
  Abdominal Machine on page 11. Thus legs have seven pictured exercises and
  core has four, not eight and three.
- The triceps summary says six but its detailed table and indexed manual have five.
- Page 42 is a general Dumbbell Bench Press, not specifically “middle chest.”
  Page 11 is general abdominal work, not specifically “upper abs.” Subgroup
  menus do not make those stronger claims.
- Some checklist injury AVOID/RECOMMEND statements are not verbatim in the
  exercise chunks. The existing knowledge graph contains curated condition
  relations, but the LINE menu does not promote those statements to PDF facts
  or label any substitute exercise as medically safe. Injury questions stay
  with the safety-aware RAG path, without a photo carousel.

Before changing taxonomy or medical claims, compare the exact PDF passage,
`chunks.json` entry and knowledge-graph provenance, then update tests.
