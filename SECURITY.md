# Security

Mise uses Hermes's authenticated Notion MCP connection and stores no Notion token.

The configured data-source identifier is validated as an exact `collection://<uuid>` value before the UUID is passed to the current Notion `query-data-source` API. Caller text is placed only in native Notion `contains` filter values and is never executable query language.

The provider is read-only and exposes no model-facing tools. Notion permissions are enforced by the connected Hermes integration.

Report vulnerabilities privately through GitHub Security Advisories.
