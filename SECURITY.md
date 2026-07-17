# Security

Mise uses Hermes's authenticated Notion MCP connection and stores no Notion token.

The configured data-source identifier is validated as an exact `collection://<uuid>` value before interpolation as a SQL table identifier. Query values remain bound parameters, and `LIKE` wildcard characters in caller text are escaped.

The provider is read-only and exposes no model-facing tools. Notion permissions are enforced by the connected Hermes integration.

Report vulnerabilities privately through GitHub Security Advisories.
