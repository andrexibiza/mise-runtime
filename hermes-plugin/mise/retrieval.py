from __future__ import annotations

import json
import re
from typing import Any

DATA_SOURCE_URL = "collection://00000000-0000-4000-8000-000000000001"
DATA_SOURCE_PATTERN = re.compile(
    r"collection://[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
SEARCH_FIELDS = ("Memory Key", "Name", "Aliases", "Recall When", "Abstract", "Agent Brief")
SEARCH_FIELD_TYPES = {
    "Memory Key": "rich_text",
    "Name": "title",
    "Aliases": "rich_text",
    "Recall When": "rich_text",
    "Abstract": "rich_text",
    "Agent Brief": "rich_text",
}
QUESTION_FILLER = {
    "a", "an", "answer", "can", "could", "did", "do", "does", "exact", "for", "from",
    "how", "is", "key", "me", "memory", "mise", "name", "named", "of", "only", "please",
    "record", "tell", "the", "to", "what", "when", "where", "which", "who", "whose", "with",
    "would", "you",
}
BASIC_QUESTION_WORDS = {
    "a", "an", "answer", "can", "could", "did", "do", "does", "for", "from", "how", "is",
    "me", "of", "only", "please", "tell", "the", "to", "what", "when", "where", "which",
    "who", "whose", "with", "would", "you",
}
QUESTION_OPENERS = {"can", "could", "do", "does", "how", "is", "what", "when", "where", "which", "who", "would"}
RETRIEVAL_FIELDS = (
    "id", "url", "Name", "Memory Key", "Type", "Memory Types", "Status", "Abstract",
    "Agent Brief", "Recall When", "Authority", "Confidence", "Salience", "Sensitivity",
    "Origin", "Mise Ready", "date:Last Verified:start", "date:Review By:start",
    "date:Expires:start", "Connections", "Connected From", "Updated",
)


def normalize_data_source_url(value: str) -> str:
    candidate = str(value or "").strip()
    if not DATA_SOURCE_PATTERN.fullmatch(candidate):
        raise ValueError("data_source_url must be collection:// followed by a UUID")
    return candidate.lower()


def data_source_id_from_url(value: str) -> str:
    return normalize_data_source_url(value).removeprefix("collection://")


def tokenize(text: str, maximum: int = 6) -> list[str]:
    source = (text or "").lower()
    words = re.findall(r"[a-z0-9][a-z0-9_-]*", source)
    is_question = bool(words and words[0] in QUESTION_OPENERS)
    explicit_name = re.search(r"\b(?:exact\s+)?name\s+is\s+([^?!.]+)", source) if is_question else None
    if explicit_name:
        words = re.findall(r"[a-z0-9][a-z0-9_-]*", explicit_name.group(1))

    unique: list[str] = []
    for word in words:
        for part in word.replace("_", "-").split("-"):
            if len(part) < 2 or part in unique:
                continue
            unique.append(part)

    if is_question and not explicit_name:
        subject = [part for part in unique if part not in QUESTION_FILLER]
        unique = subject or [part for part in unique if part not in BASIC_QUESTION_WORDS]

    return unique[:maximum]


def build_search_request(text: str, limit: int = 10, data_source_url: str = DATA_SOURCE_URL) -> dict[str, Any]:
    normalize_data_source_url(data_source_url)
    terms = tokenize(text) or [text.strip().lower()]
    clauses: list[dict[str, Any]] = []
    for term in terms:
        term_clauses: list[dict[str, Any]] = []
        for field in SEARCH_FIELDS:
            term_clauses.append({
                "property": field,
                SEARCH_FIELD_TYPES[field]: {"contains": term},
            })
        clauses.append({"or": term_clauses})
    clauses.extend([
        {"property": "Status", "select": {"does_not_equal": "Archived"}},
        {"property": "Memory Key", "rich_text": {"is_not_empty": True}},
    ])
    bounded = max(1, min(int(limit), 25))
    return {
        "filter": {"and": clauses},
        "sorts": [{"property": "Updated", "direction": "descending"}],
        "page_size": bounded,
    }


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
        if isinstance(value, dict) and set(value) == {"content"} and isinstance(value["content"], list):
            texts = [item.get("text", "") for item in value["content"] if isinstance(item, dict) and item.get("type") == "text"]
            if len(texts) == 1:
                value = texts[0]
                continue
        return value
    return value


def _plain_text(items: list[dict[str, Any]] | None) -> str:
    return "".join(
        item.get("plain_text") or item.get("text", {}).get("content") or ""
        for item in (items or [])
    )


def _property_value(name: str, prop: dict[str, Any]) -> tuple[str, Any]:
    kind = prop.get("type")
    if kind in {"title", "rich_text"}:
        return name, _plain_text(prop.get(kind))
    if kind in {"select", "status"}:
        return name, (prop.get(kind) or {}).get("name")
    if kind == "multi_select":
        return name, [item.get("name") for item in prop.get(kind) or []]
    if kind == "relation":
        return name, [item.get("id") for item in prop.get(kind) or []]
    if kind == "date":
        return f"date:{name}:start", (prop.get("date") or {}).get("start")
    if kind in {"number", "checkbox", "url", "last_edited_time", "created_time"}:
        return name, prop.get(kind)
    return name, None


def flatten_page(page: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"id": page.get("id"), "url": page.get("url")}
    for name, prop in (page.get("properties") or {}).items():
        key, value = _property_value(name, prop or {})
        row[key] = value
    return row


def flatten_query_response(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("results")
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected Notion query response")
    out = dict(result)
    out["results"] = [flatten_page(page) if isinstance(page, dict) and "properties" in page else page for page in rows]
    return out


def decode_relation(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
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
