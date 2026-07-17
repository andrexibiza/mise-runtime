# Implementation

Mise is one read-only Hermes `MemoryProvider`.

- `__init__.py` handles profile configuration, provider activation, system context, and automatic prefetch.
- `client.py` makes one query through Hermes's authenticated Notion MCP registry.
- `retrieval.py` validates the data-source identifier, builds bounded parameterized search, ranks matches, and returns compact records with provenance.

The provider exposes no model-facing tools and implements no write path. Explicit Notion reads and writes remain the responsibility of Hermes's existing Notion MCP tools.
