CREATE SCHEMA IF NOT EXISTS stock_metadata;

CREATE TABLE IF NOT EXISTS stock_metadata.pipeline_runs (
    run_id TEXT PRIMARY KEY,
    source_dir TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    pipeline_manifest_path TEXT,
    error_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stock_metadata.pipeline_stages (
    run_id TEXT NOT NULL REFERENCES stock_metadata.pipeline_runs(run_id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    record_count BIGINT NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    manifest_path TEXT,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, stage_name)
);

CREATE TABLE IF NOT EXISTS stock_metadata.ingested_files (
    source_file_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stock_metadata.pipeline_runs(run_id) ON DELETE CASCADE,
    dataset_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_extension TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256 TEXT NOT NULL,
    canonical_for_silver BOOLEAN NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ingested_files_run_id_idx
    ON stock_metadata.ingested_files(run_id);
CREATE INDEX IF NOT EXISTS ingested_files_checksum_idx
    ON stock_metadata.ingested_files(checksum_sha256);

CREATE TABLE IF NOT EXISTS stock_metadata.quality_gate_results (
    run_id TEXT NOT NULL REFERENCES stock_metadata.pipeline_runs(run_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, check_name)
);

CREATE TABLE IF NOT EXISTS stock_metadata.published_artifacts (
    run_id TEXT NOT NULL REFERENCES stock_metadata.pipeline_runs(run_id) ON DELETE CASCADE,
    object_key TEXT NOT NULL,
    object_uri TEXT NOT NULL,
    local_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, object_key)
);

CREATE INDEX IF NOT EXISTS published_artifacts_uri_idx
    ON stock_metadata.published_artifacts(object_uri);
