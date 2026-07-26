<![CDATA[<div align="center">

# 🧠 Kepa

**Persistent memory for coding agents — powered by CockroachDB and AWS Bedrock**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CockroachDB](https://img.shields.io/badge/CockroachDB-Cloud_Serverless-6933FF?logo=cockroachlabs&logoColor=white)](https://cockroachlabs.cloud)
[![AWS](https://img.shields.io/badge/AWS-Bedrock_|_Lambda_|_S3-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-000000)](https://modelcontextprotocol.io)

*Built for the CockroachDB × AWS Hackathon*

</div>

---

## Overview

Every day, development teams solve hard bugs and make critical architectural decisions — then forget about them. That context lives in merged PRs and review threads, invisible to the coding agents that could benefit from it most.

**Kepa** fixes this. It acts as a memory layer between your GitHub activity and your coding agent (Claude Code, Cursor, etc.):

1. **Capture** — A GitHub webhook fires when a PR is merged or reviewed. An AWS Lambda function receives the payload, calls Amazon Bedrock to summarize the change and generate a vector embedding, then writes the structured "memory" to CockroachDB.
2. **Store** — CockroachDB Cloud Serverless holds every memory in a single `memory` table with vector-indexed embeddings for semantic search and JSONB metadata for flexible querying.
3. **Recall** — Coding agents query memories through CockroachDB's Managed MCP Server. When an agent encounters a bug or needs architectural context, it can ask: *"What do we know about the null pointer in the user service?"* and get back the exact decision or fix from weeks ago.

The result: agents that learn from your team's history instead of starting from scratch every session.

---

## Architecture

<!-- TODO: Replace this ASCII diagram with a proper SVG/PNG once the flow is finalized -->

```
┌───────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
│               │  POST   │                      │ Invoke  │                      │
│    GitHub     │────────▶│   AWS Lambda          │────────▶│  Amazon Bedrock      │
│  (webhook)    │         │   (capture/handler)   │         │  (summarize + embed) │
│               │         │                      │         │                      │
└───────────────┘         └──────────┬───────────┘         └──────────────────────┘
                                     │
                        ┌────────────┼────────────┐
                        ▼                         ▼
              ┌──────────────────┐     ┌─────────────────────────┐
              │                  │     │                         │
              │   Amazon S3     │     │   CockroachDB Cloud     │
              │   (raw diffs)   │     │   Serverless            │
              │                  │     │   (memory table +       │
              └──────────────────┘     │    vector index)        │
                                       │                         │
                                       └────────────┬────────────┘
                                                    │
                                                    │ MCP
                                                    ▼
                                       ┌─────────────────────────┐
                                       │  CockroachDB Managed    │
                                       │  MCP Server             │
                                       └────────────┬────────────┘
                                                    │
                                      ┌─────────────┼─────────────┐
                                      ▼                           ▼
                             ┌──────────────┐            ┌──────────────┐
                             │  Claude Code │            │   Cursor     │
                             └──────────────┘            └──────────────┘
```

**Data flow:**
1. A developer merges a PR or leaves a review comment in GitHub
2. The webhook fires a POST to the Lambda function URL
3. Lambda classifies the event (`bug_fix`, `decision`, `review_comment`), calls Bedrock to summarize and embed it, archives the raw payload to S3, and writes the structured memory to CockroachDB
4. Coding agents query the MCP server to semantically search past memories

---

## Repository Structure

```
kepa/
├── infra/                  # Database schema and infrastructure config
│   └── schema.sql          # CockroachDB memory table + vector index
├── capture/                # AWS Lambda webhook handler
│   ├── handler.py          # Main Lambda function (Python 3.11)
│   ├── iam-policy.json     # Least-privilege IAM policy
│   └── s3-bucket.sh        # S3 bucket creation script
├── recall/                 # MCP server wiring for coding agents
│   └── README.md           # Claude Code + Cursor config examples
├── demo-repo/              # Throwaway repo for the live demo
│   └── README.md
├── .env.example            # All required environment variables
├── .gitignore
├── LICENSE                 # Apache 2.0
└── README.md               # ← You are here
```

---

## Prerequisites

| Requirement | Purpose | Link |
|---|---|---|
| CockroachDB Cloud Serverless cluster | Memory storage + vector search | [Create cluster](https://cockroachlabs.cloud) |
| CockroachDB Managed MCP Server | Agent query interface | Enable via Cloud dashboard |
| AWS account with Bedrock access | Summarization + embedding generation | [Request model access](https://console.aws.amazon.com/bedrock/) |
| Python 3.11+ | Lambda runtime + local testing | [python.org](https://www.python.org/) |
| AWS CLI (configured) | S3 bucket creation + Lambda deploy | [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| GitHub repo with webhook | Event source for captures | Any repo you own |
| Claude Code or Cursor | MCP client (agent side) | — |

---

## Setup

### 1. Clone and configure environment

```bash
git clone https://github.com/your-username/kepa.git
cd kepa
cp .env.example .env
# Fill in your actual credentials in .env
```

### 2. Provision CockroachDB

Create a CockroachDB Cloud Serverless cluster and run the schema migration:

```bash
cockroach sql --url "$DATABASE_URL" -f infra/schema.sql
```

> [!NOTE]
> Make sure vector indexing is enabled on your cluster. CockroachDB Cloud Serverless supports the `VECTOR` type and IVFFlat indexes natively.

Then enable the **Managed MCP Server** in your CockroachDB Cloud dashboard and note the endpoint URL.

### 3. Create the S3 bucket

```bash
bash capture/s3-bucket.sh [OPTIONAL_BUCKET_NAME] [OPTIONAL_REGION]
```

The script creates a private, encrypted, versioned bucket. See [s3-bucket.sh](capture/s3-bucket.sh) for details.

### 4. Deploy the Lambda function

<!-- TODO: Add SAM/CDK template or step-by-step deploy instructions -->

1. Create a Lambda function with the **Python 3.11** runtime
2. Upload `capture/handler.py` as the function code
3. Attach the IAM policy from [`capture/iam-policy.json`](capture/iam-policy.json)
4. Set the environment variables from your `.env` file
5. Create an API Gateway trigger (or Lambda Function URL) and note the endpoint

### 5. Configure the GitHub webhook

In your target repo's settings → **Webhooks** → **Add webhook**:

| Field | Value |
|---|---|
| Payload URL | Your Lambda endpoint from step 4 |
| Content type | `application/json` |
| Secret | Same value as `GITHUB_WEBHOOK_SECRET` in `.env` |
| Events | Pull requests, Pull request reviews |

### 6. Wire up your coding agent

Follow the instructions in [`recall/README.md`](recall/README.md) to configure Claude Code or Cursor to point at your CockroachDB Managed MCP Server endpoint.

---

## Running the Demo

### Local test (no AWS required)

Run the Lambda handler locally with a mock GitHub webhook payload:

```bash
python capture/handler.py
```

This fires the full pipeline with stub implementations — you'll see log output for each step without making real API calls.

### End-to-end demo

1. Configure your `.env` with real credentials
2. Deploy the Lambda and configure the webhook (steps 4–5 above)
3. Open a PR in `demo-repo/` with a commit like: *"fix: null pointer in user service when email is missing"*
4. Merge the PR — the webhook fires → Lambda → Bedrock → CockroachDB
5. Open Claude Code or Cursor (with MCP configured) and ask:

   > *"What do we know about fixing the null pointer in the user service?"*

6. The agent queries CockroachDB via MCP and returns the captured memory

---

## CockroachDB Tools Used

| Feature | How Kepa uses it |
|---|---|
| **CockroachDB Cloud Serverless** | Zero-ops storage for memories — auto-scales, no cluster management |
| **Managed MCP Server** | Exposes the `memory` table as MCP tools for coding agents to query directly |
| **`VECTOR(1536)` column + IVFFlat index** | Semantic similarity search — agents find relevant memories by meaning, not keywords |
| **`JSONB` columns** | Flexible metadata storage for author, PR title, S3 keys, and future extensions |
| **`STRING[]` arrays** | Stores affected file paths as a native array for efficient filtering |
| **`CHECK` constraints** | Enforces valid event types (`bug_fix`, `decision`, `review_comment`) at the database level |

---

## AWS Services Used

| Service | How Kepa uses it |
|---|---|
| **AWS Lambda** | Stateless webhook handler — receives GitHub events, orchestrates the capture pipeline |
| **Amazon Bedrock** | Summarizes PR context (Titan Text / Claude) and generates 1536-dim embeddings (Titan Embed) |
| **Amazon S3** | Archives raw diffs and PR bodies for auditability and future reprocessing |
| **AWS IAM** | Least-privilege execution role scoped to Bedrock InvokeModel + S3 read/write on one bucket |

---

## Roadmap

<!-- TODO: Prioritize and flesh these out -->

- [ ] Add SAM/CDK template for one-command Lambda deploy
- [ ] Support `pull_request_review` and `issue_comment` webhook events
- [ ] Implement Bedrock calls (replace stubs with real `boto3` InvokeModel)
- [ ] Add retention policies / TTL on old memories
- [ ] Build a simple web dashboard to browse stored memories
- [ ] Add tests for the capture pipeline
- [ ] Multi-repo support with per-repo access controls

---

## Contributing

Contributions are welcome! Please open an issue or PR. See the [LICENSE](LICENSE) for terms.

---

<div align="center">

**Apache 2.0** — see [LICENSE](LICENSE) for details.

Built by Akash Naickar for the CockroachDB × AWS Hackathon

</div>
]]>
