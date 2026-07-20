from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from agent.memory_provider import MemoryProvider
from .client import NotionMCPClient
from .retrieval import build_search_request, compact_record, normalize_data_source_url, rank_rows

logger = logging.getLogger(__name__)
PREFETCH_MAX_CHARS = 10_000


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class MiseMemoryProvider(MemoryProvider):
    """A small Hermes memory provider backed directly by Notion MCP."""

    def __init__(self, client=None, data_source_url: str = ""):
        self.data_source_url = normalize_data_source_url(data_source_url) if data_source_url else ""
        self.client = client
        self.active = False
        self.hermes_home = ""

    @property
    def name(self) -> str:
        return "mise"

    def _resolve_config(self, hermes_home: str = "") -> str:
        value = os.environ.get("MISE_DATA_SOURCE_URL", "").strip()
        if not value and not self.data_source_url:
            configured_home = hermes_home or self.hermes_home or os.environ.get("HERMES_HOME")
            home = Path(configured_home) if configured_home else Path.home() / ".hermes"
            path = home / "mise.json"
            if path.exists():
                value = json.loads(path.read_text(encoding="utf-8")).get("data_source_url", "")
        if value:
            self.data_source_url = normalize_data_source_url(value)
        return self.data_source_url

    def is_available(self) -> bool:
        try:
            return bool(self._resolve_config())
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            return False

    def get_config_schema(self):
        return [{"key": "data_source_url", "description": "Notion collection:// data source containing Mise", "required": True, "secret": False, "env_var": "MISE_DATA_SOURCE_URL"}]

    def save_config(self, values: dict[str, Any], hermes_home: str) -> None:
        path = Path(hermes_home) / "mise.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        value = normalize_data_source_url((values or {}).get("data_source_url", ""))
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"data_source_url": value}, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(path)

    def initialize(self, session_id: str, **kwargs) -> None:
        try:
            configured_home = kwargs.get("hermes_home") or os.environ.get("HERMES_HOME")
            self.hermes_home = str(configured_home) if configured_home else str(Path.home() / ".hermes")
            self._resolve_config(self.hermes_home)
            if self.client is None and self.data_source_url:
                self.client = NotionMCPClient(self.data_source_url)
            if self.client and self.data_source_url:
                result = self.client.query({
                    "filter": {"property": "Memory Key", "rich_text": {"is_not_empty": True}},
                    "page_size": 1,
                })
                self.active = isinstance(result.get("results"), list)
        except Exception as exc:
            logger.warning("Mise unavailable: %s", exc)
            self.active = False

    def get_context(self) -> str:
        return (
            "Mise is a Notion-backed memory provider. A record's presence or declared authority does not prove "
            "that it is currently true; evaluate current evidence and provenance. Search progressively, open full "
            "pages only when needed, and use direct MCP create/update calls for authorized changes."
        )

    def system_prompt_block(self) -> str:
        return self.get_context() if self.active else ""

    def prefetch(self, query: str, **kwargs) -> str:
        if not self.active or not query.strip():
            return ""
        records = self._search(query, 4)
        blocks = []
        for row in records:
            identity = _clip(row["Memory Key"], 160)
            provenance = [
                f"Source: {_clip(row['url'], 300)}",
                f"Origin: {_clip(row['Origin'], 80)}" if row.get("Origin") else "",
                f"Last verified: {_clip(row['date:Last Verified:start'], 40)}" if row.get("date:Last Verified:start") else "",
            ]
            blocks.append(
                f"- {_clip(row.get('Name', 'Unnamed'), 120)} [{identity}]\n"
                f"  {_clip(row.get('Abstract'), 400)}\n"
                f"  {_clip(row.get('Agent Brief'), 1000)}\n"
                f"  {'; '.join(item for item in provenance if item)}"
            )
        return "\n\n".join(blocks)[:PREFETCH_MAX_CHARS]

    def _search(self, query: str, limit: int = 10):
        request = build_search_request(query, limit=limit, data_source_url=self.data_source_url)
        rows = self.client.query(request).get("results", [])
        traceable = [row for row in rows if str(row.get("Memory Key") or "").strip() and str(row.get("url") or "").strip()]
        return [compact_record(row) for row in rank_rows(traceable, query)[:limit]]

    def get_tool_schemas(self):
        return []


def register(ctx) -> None:
    ctx.register_memory_provider(MiseMemoryProvider())
