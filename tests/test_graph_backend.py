"""Check that GraphRetriever actually reads Neo4j when available."""

import unittest
from unittest.mock import patch

from src.graph_retrieval import GraphRetriever


class FakeSession:
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, **parameters):
        self.queries.append((query, parameters))
        if "RETURN 1" in query:
            return [{"test": 1}]
        return [{
            "source": "ปวดข้อเข่า (Knee Pain)",
            "relation": "AVOID",
            "target": "3. เครื่องบริหารต้นขาด้านหน้าและสะโพก (Leg press)",
        }]


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


class GraphBackendTests(unittest.TestCase):
    def test_cypher_is_used_when_neo4j_is_available(self):
        session = FakeSession()
        with patch("src.graph_retrieval.GraphDatabase.driver", return_value=FakeDriver(session)):
            graph = GraphRetriever()
            result = graph.search("ปวดเข่า ควรหลีกเลี่ยงท่าไหน")
        self.assertEqual(result["source"], "neo4j")
        self.assertEqual(len(result["avoid_exercises"]), 1)
        self.assertIn("$conditions", session.queries[-1][0])
        self.assertIn("FitnessEntity", session.queries[-1][0])
        self.assertEqual(session.queries[-1][1]["project_id"], "fitness_rag_final_2026")
        self.assertIn("ปวดข้อเข่า (Knee Pain)", session.queries[-1][1]["conditions"])

    def test_local_json_is_explicit_fallback(self):
        with patch("src.graph_retrieval.GraphDatabase.driver", side_effect=OSError("offline")):
            result = GraphRetriever().search("ปวดเข่า ควรหลีกเลี่ยงท่าไหน")
        self.assertEqual(result["source"], "json_fallback")
        self.assertGreater(len(result["avoid_exercises"]), 0)

    def test_shoulder_pain_wording_matches_condition(self):
        with patch("src.graph_retrieval.GraphDatabase.driver", side_effect=OSError("offline")):
            graph = GraphRetriever()
        entities = graph.extract_entities_from_query("ปวดหัวไหล่ ควรหลีกเลี่ยงอะไร")
        self.assertIn("ปวดหัวไหล่ / ข้อต่อไหล่ติด (Shoulder Impingement)", entities["conditions"])


if __name__ == "__main__":
    unittest.main()
