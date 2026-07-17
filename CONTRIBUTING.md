# Contributing

1. Keep the plugin small and use Hermes's existing Notion MCP tools.
2. Do not add a Worker, webhook, queue, event journal, or parallel persistence layer.
3. Keep data-source identifiers strictly validated and query values parameterized.
4. Add or update tests for every behavior change.
5. Run:

```bash
PYTHONPATH=/path/to/hermes-agent python -m unittest discover -s tests -v
python -m compileall -q hermes-plugin scripts tests
```
