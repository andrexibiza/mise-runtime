import json
import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).parents[1] / "hermes-plugin"
sys.path.insert(0, str(PLUGIN))

from mise.retrieval import (
    build_search_request,
    data_source_id_from_url,
    decode_relation,
    flatten_page,
    parse_mcp_result,
    rank_rows,
    tokenize,
)


class RetrievalTests(unittest.TestCase):
    def test_tokenize_is_bounded_and_literal(self):
        self.assertEqual(tokenize("Mise / agent-memory, Agent memory!"), ["mise", "agent", "memory"])

    def test_tokenize_reaches_subject_terms_in_natural_memory_questions(self):
        query = (
            "What is the exact Memory Key of the Mise record whose exact Name is "
            "Agents Dashboard? Answer with only the Memory Key."
        )
        self.assertEqual(tokenize(query), ["agents", "dashboard"])

    def test_tokenize_keeps_keyword_terms_when_query_only_ends_in_question_mark(self):
        self.assertEqual(
            tokenize("Mise / agent-memory, Agent memory?"),
            ["mise", "agent", "memory"],
        )

    def test_tokenize_keeps_explicit_name_when_name_is_a_schema_word(self):
        query = (
            "What is the exact Memory Key of the Mise record whose exact Name is "
            "Memory? Answer with only the Memory Key."
        )
        self.assertEqual(tokenize(query), ["memory"])

    def test_build_search_request_uses_native_notion_filters(self):
        request = build_search_request("agent memory", limit=7)
        self.assertEqual(request["page_size"], 7)
        self.assertEqual(request["sorts"], [{"property": "Updated", "direction": "descending"}])
        clauses = request["filter"]["and"]
        self.assertEqual(len(clauses), 4)
        self.assertEqual(clauses[0]["or"][0], {
            "property": "Memory Key",
            "rich_text": {"contains": "agent"},
        })
        self.assertIn({"property": "Name", "title": {"contains": "memory"}}, clauses[1]["or"])
        self.assertEqual(clauses[-2], {
            "property": "Status",
            "select": {"does_not_equal": "Archived"},
        })
        self.assertEqual(clauses[-1], {
            "property": "Memory Key",
            "rich_text": {"is_not_empty": True},
        })

    def test_literal_search_terms_are_values_not_query_language(self):
        request = build_search_request("%_")
        first = request["filter"]["and"][0]["or"][0]
        self.assertEqual(first["rich_text"]["contains"], "%_")

    def test_data_source_identifier_is_extracted_from_collection_url(self):
        self.assertEqual(
            data_source_id_from_url("collection://00000000-0000-4000-8000-000000000001"),
            "00000000-0000-4000-8000-000000000001",
        )

    def test_flatten_page_decodes_current_notion_property_shapes(self):
        page = {
            "id": "page-1",
            "url": "https://notion.so/page-1",
            "properties": {
                "Name": {"type": "title", "title": [{"plain_text": "Mise"}]},
                "Memory Key": {"type": "rich_text", "rich_text": [{"plain_text": "system:mise"}]},
                "Memory Types": {"type": "multi_select", "multi_select": [{"name": "Semantic"}]},
                "Status": {"type": "select", "select": {"name": "Active"}},
                "Mise Ready": {"type": "checkbox", "checkbox": True},
                "Confidence": {"type": "number", "number": 0.95},
                "Last Verified": {"type": "date", "date": {"start": "2026-07-19"}},
                "Connections": {"type": "relation", "relation": [{"id": "related-1"}]},
                "Updated": {"type": "last_edited_time", "last_edited_time": "2026-07-19T01:02:03Z"},
            },
        }
        row = flatten_page(page)
        self.assertEqual(row["Name"], "Mise")
        self.assertEqual(row["Memory Key"], "system:mise")
        self.assertEqual(row["Memory Types"], ["Semantic"])
        self.assertEqual(row["Mise Ready"], True)
        self.assertEqual(row["date:Last Verified:start"], "2026-07-19")
        self.assertEqual(row["Connections"], ["related-1"])
        self.assertEqual(row["Updated"], "2026-07-19T01:02:03Z")

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
            build_search_request("memory", data_source_url='collection://x" UNION SELECT *')


if __name__ == "__main__":
    unittest.main()
