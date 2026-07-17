import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "hermes-plugin"))
from mise import MiseMemoryProvider


class FakeClient:
    def __init__(self, rows=None):
        self.rows = rows or [{
            "Name": "Mise",
            "Memory Key": "system:mise",
            "Abstract": "A Notion knowledge graph used as durable memory.",
            "Agent Brief": "Use this record when deciding how memory retrieval works.",
            "Origin": "Human",
            "url": "https://notion.so/mise",
            "date:Last Verified:start": "2026-07-17",
        }]
        self.last_query = ""

    def query(self, query, params):
        self.last_query = query
        return {"results": self.rows if '"Status" != ?' in query else []}


class AutoRecallTests(unittest.TestCase):
    def test_provider_adds_automatic_provenance_carrying_recall_without_duplicate_tools(self):
        client = FakeClient()
        provider = MiseMemoryProvider(
            client,
            "collection://00000000-0000-4000-8000-000000000001",
        )
        provider.active = True

        self.assertEqual(provider.get_tool_schemas(), [])
        recall = provider.prefetch("How should memory retrieval work?")
        self.assertIn("Mise", recall)
        self.assertIn("system:mise", recall)
        self.assertIn("https://notion.so/mise", recall)
        self.assertIn("Origin: Human", recall)
        self.assertIn("Last verified: 2026-07-17", recall)
        self.assertIn('"Memory Key" IS NOT NULL', client.last_query)
        self.assertIn("url IS NOT NULL", client.last_query)

    def test_prefetch_is_hard_bounded_and_drops_untraceable_records(self):
        huge = "x" * 1_000_000
        rows = [{"Name": "Untraceable", "Abstract": "must not appear"}]
        rows += [{
            "Name": f"Record {index}",
            "Memory Key": f"claim:record-{index}",
            "url": f"https://notion.so/record-{index}",
            "Abstract": huge,
            "Agent Brief": huge,
        } for index in range(4)]
        provider = MiseMemoryProvider(
            FakeClient(rows),
            "collection://00000000-0000-4000-8000-000000000001",
        )
        provider.active = True

        recall = provider.prefetch("record")
        self.assertLessEqual(len(recall), 10_000)
        self.assertNotIn("Untraceable", recall)
        self.assertEqual(recall.count("Source: https://notion.so/record-"), 4)


if __name__ == "__main__":
    unittest.main()
