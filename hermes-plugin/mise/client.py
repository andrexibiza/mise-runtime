from __future__ import annotations

from typing import Any

from .retrieval import data_source_id_from_url, flatten_query_response, parse_mcp_result

QUERY_TOOL = "mcp__notion__API_query_data_source"


class NotionMCPClient:
    """Read a configured Notion data source through Hermes's MCP connection."""

    def __init__(self, data_source_url: str):
        self.data_source_url = data_source_url

    def query(self, request: dict[str, Any]) -> dict[str, Any]:
        from tools.registry import registry

        entry = registry.get_entry(QUERY_TOOL)
        if entry is None:
            from tools.mcp_tool import discover_mcp_tools
            discover_mcp_tools()
            entry = registry.get_entry(QUERY_TOOL)
        if entry is None or not entry.check_fn():
            raise RuntimeError(f"Notion MCP tool unavailable: {QUERY_TOOL}")

        arguments = {
            "data_source_id": data_source_id_from_url(self.data_source_url),
            **request,
        }
        result = parse_mcp_result(entry.handler(arguments))
        if not isinstance(result, dict) or "results" not in result:
            raise RuntimeError("Unexpected Notion query response")
        return flatten_query_response(result)
