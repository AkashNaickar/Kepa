# Kepa

> A memory layer for coding agents that persists decisions and bug fixes in CockroachDB and retrieves them via MCP.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## Overview

Kepa gives coding agents (Claude Code, Cursor, etc.) persistent memory. When a human discusses a bug fix or architectural decision in a PR, Kepa captures it via GitHub webhooks, summarizes and embeds it with Bedrock, and stores it in CockroachDB. Agents then query those memories through an MCP server to recall past context.

## Architecture

<!-- TODO: Insert architecture diagram here (GitHub webhook → Lambda → Bedrock → CockroachDB → MCP → Agent) -->

```
GitHub Event
    ↓
AWS Lambda (capture)
    ↓
Amazon Bedrock (summarize + embed)
    ↓
CockroachDB Cloud (store)
    ↓
CockroachDB Managed MCP Server (query)
    ↓
Claude Code / Cursor
```

## Prerequisites

- [ ] CockroachDB Cloud Serverless cluster 
- [ ] CockroachDB Managed MCP Server enabled on your cluster
- [ ] AWS account with Bedrock model access enabled (Claude or Titan embeddings)
- [ ] Python 3.11+
- [ ] GitHub repo with webhook configured
- [ ] Claude Code or Cursor (for the MCP client side)

## Setup

<!-- TODO: Flesh out each step -->

1. **CockroachDB**: Create a serverless cluster, enable the Managed MCP Server, and run the schema migration:
   ```bash
   cockroach sql --url "$DATABASE_URL" -f infra/schema.sql
   ```

2. **AWS Lambda**:
   - Create the Lambda function with the Python 3.11 runtime
   - Attach the IAM policy from `capture/iam-policy.json`
   - Set environment variables (see `.env.example`)
   - Configure the GitHub webhook to point at the Lambda's API Gateway URL

3. **S3 Bucket**: Create the bucket for raw diffs/PR bodies:
   ```bash
   # TODO: Run the setup script once you have AWS CLI configured
   bash capture/s3-bucket.sh
   ```

4. **MCP Client**: Configure your agent to point at the CockroachDB Managed MCP Server endpoint (see `recall/`).

## Running the Demo

<!-- TODO: Fill in demo steps -->

1. Clone this repo and the `demo-repo/` subfolder
2. Configure your `.env` from `.env.example`
3. Open a PR in `demo-repo/` with a mock bug fix
4. Watch the webhook fire → Lambda → Bedrock → CockroachDB
5. Ask your agent: *"What do we know about fixing the null pointer in user service?"*

## CockroachDB Tools Used

- [ ] CockroachDB Cloud Serverless (storage + vector search)
- [ ] CockroachDB Managed MCP Server (agent query interface)
- [ ] `vector` column type with indexing for semantic search
- [ ] `jsonb` for flexible metadata storage

## AWS Services Used

- [ ] AWS Lambda (webhook handler / capture function)
- [ ] Amazon Bedrock (summarization + embedding generation)
- [ ] Amazon S3 (raw diff and PR body storage)
- [ ] AWS IAM (least-privilege roles)

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
