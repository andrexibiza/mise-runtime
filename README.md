# Mise for Hermes

**Automatic Notion recall for Hermes Agent—without a vector database, embedding pipeline, or memory service.**

Hermes can already call Notion through MCP. Those calls happen only after the model decides to make them. Mise runs earlier: Hermes invokes it through the native `MemoryProvider` lifecycle before generating a response.

The result is simple: relevant memory arrives automatically instead of depending on the model to remember that it should search for memory.

## What happens on every recall

1. Hermes sends the current user message to Mise's `prefetch()` hook.
2. Mise runs one bounded query against the configured Notion data source.
3. It searches the graph's identity, alias, recall, abstract, and agent-brief fields.
4. It returns at most four compact records with their memory keys and provenance.
5. Hermes injects that context before the model responds.

Mise adds no model-facing tools. Explicit Notion work still uses Hermes's normal Notion MCP integration.

## Why use Mise

### Recall is runtime-controlled

A prompt can ask a model to search Notion. Mise makes recall part of the runtime path. The model receives relevant context before it chooses tools or writes an answer.

### Your memory stays inspectable

The source of truth remains a normal Notion knowledge graph. People can read it, edit it, permission it, export it, and inspect exactly what the agent may recall.

### Context stays bounded

Mise returns compact abstracts and agent briefs rather than loading whole pages or databases. Full source pages remain available through the existing Notion MCP tools when deeper evidence is required.

### Provenance travels with recall

Each prefetched record carries its stable memory key, Notion locator, origin, and last-verification date when available. Retrieved prose does not arrive detached from its source.

### No second memory stack

```text
Hermes MemoryManager
        |
        | automatic prefetch
        v
Mise MemoryProvider
        |
        | one authenticated MCP query
        v
Your Notion knowledge graph
```

No vector store. No embeddings. No Worker. No webhook. No queue. No duplicate database. No separate credentials.

## Designed for durable agent memory

Mise is useful when memory must:

- survive model and vendor changes;
- remain owned and human-editable;
- preserve stable identity, summaries, provenance, and time;
- enter context automatically across Hermes surfaces and sessions; and
- use the Notion permissions and connection already configured in Hermes.

The provider is intentionally read-only. It recalls memory automatically; authorized creation and editing continue through Hermes's existing Notion MCP tools.

## Install

```bash
python scripts/install.py
hermes memory setup
```

Select `mise`, then provide the exact `collection://<UUID>` URL for your Mise data source. Start a new Hermes session after setup.

Environment-based setup is also supported:

```bash
export MISE_DATA_SOURCE_URL='collection://YOUR-DATA-SOURCE-UUID'
hermes config set memory.provider mise
```

Hermes must already have its Notion MCP integration authenticated with access to that data source.

## Mise graph fields

The provider is built for a Mise-compatible Notion graph. Recall uses these properties:

- `Name`
- `Memory Key`
- `Aliases`
- `Recall When`
- `Abstract`
- `Agent Brief`
- `Status`
- `Origin`
- `Authority`
- `Confidence`
- `Sensitivity`
- `Last Verified`
- `Review By`
- `Expires`
- `Connections`
- `Connected From`

Records marked `Archived` are excluded from automatic recall.

## Security

- the data source must match the exact `collection://<UUID>` grammar;
- caller text is passed as bound parameters and SQL wildcard characters are escaped;
- automatic recall is capped at four traceable records and 10,000 characters;
- `is_available()` performs no network I/O;
- initialization verifies the live MCP query path;
- the provider stores no Notion token; and
- the provider exposes no additional write tools.

## Verify

```bash
PYTHONPATH=/path/to/hermes-agent python -m unittest discover -s tests -v
python -m compileall -q hermes-plugin scripts tests
```

The test suite exercises the official Hermes loader, profile configuration, bounded retrieval, literal search, provenance-carrying prefetch, and zero-tool provider contract.
