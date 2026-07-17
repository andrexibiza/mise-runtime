import json
import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).parents[1] / "hermes-plugin"
sys.path.insert(0, str(PLUGIN))

from mise.retrieval import build_search_query, decode_relation, parse_mcp_result, rank_rows, tokenize


class RetrievalTests(unittest.TestCase):
    def test_tokenize_is_bounded_and_literal(self):
        self.assertEqual(tokenize("Mise / agent-memory, Agent memory!"), ["mise", "agent", "memory"])

    def test_build_search_query_is_parameterized(self):
        query, params = build_search_query("agent memory", limit=7)
        self.assertIn('FROM "collection://00000000-0000-4000-8000-000000000001"', query)
        self.assertNotIn("SELECT *", query)
        self.assertNotIn("agent", query)
        self.assertIn("LIMIT 7", query)
        self.assertEqual(params[-1], "Archived")
        self.assertTrue(all(p == "%agent%" or p == "%memory%" for p in params[:-1]))

    def test_search_treats_like_wildcards_as_literal_text(self):
        query, params = build_search_query("%_")
        self.assertIn("LIKE ? ESCAPE '\\'", query)
        self.assertTrue(all(param == "%\\%\\_%" for param in params[:-1]))

    def test_parse_nested_mcp_json(self):
        raw = json.dumps({"result": json.dumps({"results": [{"Name": "Mise"}], "has_more": False})})
        parsed = parse_mcp_result(raw)
        self.assertEqual(parsed["results"][0]["Name"], "Mise")

    def test_decode_relation(self):
        raw = json.dumps(["https://app.notion.com/a", "https://app.notion.com/b"])
        self.assertEqual(decode_relation(raw), ["https://app.notion.com/a", "https://app.notion.com/b"])

    def test_rank_prefers_exact_memory_key(self):
        rows = [
            {"Name": "Agent memory notes", "Memory Key": "concept:notes", "Abstract": "agent memory"},
            {"Name": "Ares Memory Space", "Memory Key": "system:ares-memory-space", "Abstract": "canonical"},
        ]
        ranked = rank_rows(rows, "system:ares-memory-space")
        self.assertEqual(ranked[0]["Memory Key"], "system:ares-memory-space")

    def test_rank_does_not_treat_mise_ready_as_authority(self):
        rows = [
            {
                "Name": "Derived memory",
                "Memory Key": "timeline:derived",
                "Abstract": "matching episode",
                "Mise Ready": "__YES__",
                "Updated": "2026-07-16T12:00:00-05:00",
            },
            {
                "Name": "MemPalace episode",
                "Memory Key": "mempalace:episode:abc",
                "Abstract": "matching episode",
                "Authority": "Primary",
                "Origin": "Import",
                "Mise Ready": "__NO__",
                "Updated": "2026-07-16T11:00:00-05:00",
            },
        ]
        ranked = rank_rows(rows, "matching")
        # Authority and readiness are returned as review signals, not trusted
        # ranking boosts. Recency breaks otherwise-equal relevance.
        self.assertEqual(ranked[0]["Memory Key"], "timeline:derived")

    def test_declared_authority_does_not_override_better_relevance(self):
        rows = [
            {"Name": "Exact target", "Memory Key": "concept:target", "Authority": "Uncertain"},
            {"Name": "Other", "Memory Key": "concept:other", "Authority": "Primary"},
        ]
        ranked = rank_rows(rows, "concept:target")
        self.assertEqual(ranked[0]["Memory Key"], "concept:target")

    def test_declared_confidence_does_not_override_recency(self):
        rows = [
            {"Memory Key": "older", "Abstract": "matching", "Confidence": 1.0, "Updated": "2020-01-01T00:00:00+00:00"},
            {"Memory Key": "newer", "Abstract": "matching", "Confidence": 0.0, "Updated": "2026-01-01T00:00:00+00:00"},
        ]
        self.assertEqual(rank_rows(rows, "matching")[0]["Memory Key"], "newer")

    def test_data_source_identifier_requires_exact_uuid_grammar(self):
        with self.assertRaises(ValueError):
            build_search_query("memory", data_source_url='collection://x" UNION SELECT *')


if __name__ == "__main__":
    unittest.main()
