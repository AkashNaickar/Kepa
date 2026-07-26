-- Kepa memory table
-- Targets CockroachDB Cloud Serverless with vector indexing enabled
-- Requires: CockroachDB Managed MCP Server enabled on the cluster

CREATE TABLE IF NOT EXISTS memory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    repo        STRING NOT NULL,
    file_paths  STRING[] NOT NULL DEFAULT '{}',
    event_type  STRING NOT NULL CHECK (event_type IN ('bug_fix', 'decision', 'review_comment')),
    context     STRING NOT NULL,
    resolution  STRING NOT NULL DEFAULT '',
    source_url  STRING NOT NULL DEFAULT '',
    embedding   VECTOR(1536),
    metadata    JSONB NOT NULL DEFAULT '{}'
);

-- Index for filtering by repo and event type
CREATE INDEX IF NOT EXISTS idx_memory_repo_event ON memory (repo, event_type);

-- Index for time-range queries
CREATE INDEX IF NOT EXISTS idx_memory_created_at ON memory (created_at DESC);

-- Vector index for semantic similarity search
-- Requires the vector extension; CockroachDB Cloud Serverless supports this natively
-- when the vector preview feature is enabled
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON memory USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Comment: After enabling the Managed MCP Server on your CockroachDB Cloud cluster,
-- this table will be automatically exposed via MCP for agent queries.
-- You can customize which columns are queryable through the MCP dashboard.
