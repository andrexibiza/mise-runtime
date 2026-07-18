from __future__ import annotations

import json
import re
from typing import Any

DATA_SOURCE_URL = "collection://00000000-0000-4000-8000-000000000001"
DATA_SOURCE_PATTERN = re.compile(
    r"collection://[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
SEARCH_FIELDS = ("Memory Key", "Name", "Aliases", "Recall When", "Abstract", "Agent Brief")
RETRIEVAL_FIELDS = (
    "id", "url", "Name", "Memory Key", "Type", "Memory Types", "Status", "Abstract",
    "Agent Brief", "Recall When", "Authority", "Confidence", "Salience", "Sensitivity",
    "Origin", "Mise Ready", "date:Last Verified:start", "date:Review By:start",
    "date:Expires:start", "Connections", "Connected From", "Updated",
)


def _select_list() -> str:
    return ", ".join(field if field in {"id", "url"} else f'"{field}"' for field in RETRIEVAL_FIELDS)


def normalize_data_source_url(value: str) -> str:
    candidate = str(value or "").strip()
    if not DATA_SOURCE_PATTERN.fullmatch(candidate):
        raise ValueError("data_source_url must be collection:// followed by a UUID")
    return candidate.lower()


def tokenize(text: str, maximum: int = 6) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9_-]*", (text or "").lower())
    out: list[str] = []
    for word in words:
        for part in word.replace("_", "-").split("-"):
            if len(part) < 2 or part in out:
                continue
            out.append(part)
            if len(out) >= maximum:
                return out
    return out


def build_search_query(text: str, limit: int = 10, data_source_url: str = DATA_SOURCE_URL) -> tuple[str, list[Any]]:
    data_source_url = normalize_data_source_url(data_source_url)
    terms = tokenize(text) or [text.strip().lower()]
    clauses: list[str] = []
    params: list[Any] = []
    for term in terms:
        term_clauses = []
        for field in SEARCH_FIELDS:
            term_clauses.append(f'instr(lower("{field}"), ?) > 0')
            params.append(term)
        clauses.append("(" + " OR ".join(term_clauses) + ")")
    bounded = max(1, min(int(limit), 25))
    query = (
        f'SELECT {_select_list()} FROM "{data_source_url}" WHERE '
        + " AND ".join(clauses)
        + f' AND "Status" != ? AND "Memory Key" IS NOT NULL AND "Memory Key" != \'\' '
        + f'AND url IS NOT NULL AND url != \'\' ORDER BY "Updated" DESC LIMIT {bounded}'
    )
    params.append("Archived")
    return query, params


def parse_mcp_result(raw: Any) -> Any:
    value = raw
    for _ in range(4):
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ""
            if stripped[0] in "[{\"":
                try:
                    value = json.loads(stripped)
                    continue
                except json.JSONDecodeError:
                    return value
            return value
        if isinstance(value, dict) and set(value) == {"result"}:
            value = value["result"]
            continue
        return value
    return value


def decode_relation(value: Any) -> list[str]:
    if not value:
        return []
    parsed = parse_mcp_result(value)
    if isinstance(parsed, list):
        return [str(x) for x in parsed]
    return []


def _score(row: dict[str, Any], query: str) -> float:
    q = (query or "").strip().lower()
    terms = tokenize(q)
    score = 0.0
    key = str(row.get("Memory Key") or "").lower()
    name = str(row.get("Name") or "").lower()
    if q and key == q:
        score += 100
    if q and name == q:
        score += 60
    weighted = (("Memory Key", 12), ("Name", 10), ("Aliases", 6), ("Recall When", 4), ("Abstract", 3), ("Agent Brief", 2))
    for field, weight in weighted:
        text = str(row.get(field) or "").lower()
        score += sum(weight for term in terms if term in text)
    # Declared Authority, Confidence, and readiness are returned for review,
    # never trusted as truth or relevance boosts. Any may be stale.
    return score


def rank_rows(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (_score(row, query), str(row.get("Updated") or "")), reverse=True)


def compact_record(row: dict[str, Any], include_brief: bool = True) -> dict[str, Any]:
    fields = [
        "id", "url", "Name", "Memory Key", "Type", "Memory Types", "Status",
        "Abstract", "Recall When", "Authority", "Confidence", "Salience",
        "Sensitivity", "Origin", "Mise Ready", "date:Last Verified:start",
        "date:Review By:start", "date:Expires:start", "Connections", "Connected From",
    ]
    if include_brief:
        fields.insert(8, "Agent Brief")
    out = {field: row.get(field) for field in fields if row.get(field) not in (None, "")}
    for relation in ("Connections", "Connected From"):
        if relation in out:
            out[relation] = decode_relation(out[relation])
    return out
