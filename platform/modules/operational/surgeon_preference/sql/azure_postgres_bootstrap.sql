-- Surgeon Preference Pipeline Azure Postgres bootstrap.
-- Run this against the Azure database named: surgeon_preference

create schema if not exists bronze_raw;
create schema if not exists pipeline_audit;
create schema if not exists metadata_catalog;
create schema if not exists iceberg_catalog;

create table if not exists bronze_raw.ingested_files (
    file_id uuid primary key,
    run_id text not null,
    bucket text not null,
    object_key text not null,
    object_uri text not null,
    original_filename text not null,
    file_extension text not null,
    content_type text,
    size_bytes bigint,
    checksum_sha256 text,
    status text not null default 'landed',
    record_count integer not null default 0,
    error_message text,
    created_at timestamptz not null default current_timestamp,
    updated_at timestamptz not null default current_timestamp
);

create table if not exists bronze_raw.ingested_records (
    record_id uuid primary key,
    file_id uuid references bronze_raw.ingested_files(file_id),
    run_id text not null,
    record_ordinal integer not null,
    raw_payload jsonb not null,
    created_at timestamptz not null default current_timestamp
);

create table if not exists pipeline_audit.pipeline_runs (
    run_id text primary key,
    status text not null,
    source_path text,
    files_landed integer not null default 0,
    records_processed integer not null default 0,
    gold_operational_key text,
    gold_analytics_key text,
    error_message text,
    started_at timestamptz not null default current_timestamp,
    completed_at timestamptz,
    pipeline_version text,
    data_product_version text
);

create table if not exists metadata_catalog.object_store_objects (
    object_key text primary key,
    run_id text,
    bucket text not null,
    object_uri text not null,
    layer text not null,
    artifact_type text not null,
    content_type text,
    size_bytes bigint,
    checksum_sha256 text,
    source_filename text,
    created_at timestamptz not null default current_timestamp
);

create table if not exists metadata_catalog.gold_artifacts (
    run_id text not null,
    artifact_name text not null,
    object_key text not null,
    record_count integer not null default 0,
    schema_version text,
    data_product_version text,
    created_at timestamptz not null default current_timestamp,
    primary key (run_id, artifact_name)
);

create table if not exists iceberg_catalog.catalog_bootstrap (
    catalog_name text primary key,
    warehouse_uri text not null,
    namespace text not null,
    status text not null,
    error_message text,
    updated_at timestamptz not null default current_timestamp
);

select table_schema, table_name
from information_schema.tables
where table_schema in (
    'bronze_raw',
    'pipeline_audit',
    'metadata_catalog',
    'iceberg_catalog'
)
order by table_schema, table_name;
