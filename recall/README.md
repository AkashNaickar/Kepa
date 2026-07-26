# Recall — MCP Server Config

This directory contains configuration for wiring the CockroachDB Managed MCP Server
into your coding agent (Claude Code, Cursor, etc.).

## Claude Code

Add to your MCP config (`.claude/mcp.json` or `~/.config/claude/mcp.json`):

```json
{
  "mcpServers": {
    "kepa": {
      "url": "https://your-cluster.cockroachlabs.cloud/mcp"
    }
  }
}
```

## Cursor

Add to your MCP config (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "kepa": {
      "url": "https://your-cluster.cockroachlabs.cloud/mcp"
    }
  }
}
```

## Available MCP Tools

Once connected, you can query the `memory` table via the MCP server's built-in tools:

- `query_memory` — semantic search over stored memories using vector similarity
- `get_memory` — fetch a specific memory by ID

<!-- TODO: Document the exact tool names once the Managed MCP Server exposes them -->
