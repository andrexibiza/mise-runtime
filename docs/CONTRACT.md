# Contract

The provider requires one profile-scoped value: `data_source_url`, formatted as `collection://<uuid>`.

It implements the Hermes `MemoryProvider` boundary:

- local, network-free `is_available()`;
- live MCP verification during `initialize()`;
- static memory-use guidance through `system_prompt_block()`;
- bounded automatic recall through `prefetch()`; and
- an empty `get_tool_schemas()` result.

All network access uses `mcp__notion__notion_query_data_sources` through Hermes's authenticated MCP registry. The provider stores no credential and exposes no write operation.
