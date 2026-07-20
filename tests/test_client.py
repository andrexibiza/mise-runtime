import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "hermes-plugin"))

from mise.client import NotionMCPClient, QUERY_TOOL


class ClientTests(unittest.TestCase):
    def test_uses_current_query_data_source_tool_and_native_arguments(self):
        self.assertEqual(QUERY_TOOL, "mcp__notion__API_query_data_source")
        captured = []
        raw = {
            "results": [{
                "id": "page-1",
                "url": "https://notion.so/page-1",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Mise"}]},
                    "Memory Key": {"type": "rich_text", "rich_text": [{"plain_text": "system:mise"}]},
                },
            }],
            "has_more": False,
        }
        entry = SimpleNamespace(
            check_fn=lambda: True,
            handler=lambda args: captured.append(args) or json.dumps({"result": json.dumps(raw)}),
        )
        request = {
            "page_size": 4,
            "filter": {"property": "Memory Key", "rich_text": {"is_not_empty": True}},
        }
        client = NotionMCPClient("collection://00000000-0000-4000-8000-000000000001")

        with patch("tools.registry.registry.get_entry", return_value=entry):
            result = client.query(request)

        self.assertEqual(captured, [{
            "data_source_id": "00000000-0000-4000-8000-000000000001",
            **request,
        }])
        self.assertEqual(result["results"][0]["Memory Key"], "system:mise")
        self.assertEqual(result["results"][0]["url"], "https://notion.so/page-1")

    def test_configured_data_source_cannot_be_overridden_by_request(self):
        captured = []
        entry = SimpleNamespace(
            check_fn=lambda: True,
            handler=lambda args: captured.append(args) or json.dumps({"results": []}),
        )
        client = NotionMCPClient("collection://00000000-0000-4000-8000-000000000001")

        with patch("tools.registry.registry.get_entry", return_value=entry):
            client.query({"data_source_id": "attacker-controlled", "page_size": 1})

        self.assertEqual(
            captured[0]["data_source_id"],
            "00000000-0000-4000-8000-000000000001",
        )


if __name__ == "__main__":
    unittest.main()