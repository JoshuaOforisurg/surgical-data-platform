-- Surgeon Preference Pipeline Azure Postgres bootstrap.
-- Run this against the Azure database named: surgeon_preference

create schema if not exists bronze_raw;
create schema if not exists pipeline_audit;
create schema if not exists metadata_catalog;
create schema if not exists iceberg_catalog;
create schema if not exists app_workflow;

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

create table if not exists app_workflow.app_users (
    user_email text primary key,
    display_name text not null,
    roles text[] not null default '{}',
    status text not null default 'pending_access',
    auth_provider text,
    last_seen_at timestamptz,
    created_at timestamptz not null default current_timestamp,
    updated_at timestamptz not null default current_timestamp
);

create table if not exists app_workflow.draft_reviews (
    review_id uuid primary key,
    draft_id text,
    draft_object_key text,
    blob_review_key text,
    draft_type text,
    decision text not null,
    reviewer_name text not null,
    reviewer_email text,
    reviewer_roles text[] not null default '{}',
    comments text,
    reviewed_at timestamptz not null,
    source_gold_key text,
    surgeon_id text,
    surgeon_name text,
    procedure text,
    procedure_id text,
    review_payload jsonb not null,
    created_at timestamptz not null default current_timestamp
);

create table if not exists app_workflow.audit_events (
    event_id uuid primary key,
    event_type text not null,
    actor_email text,
    actor_name text,
    actor_roles text[] not null default '{}',
    entity_type text not null,
    entity_id text,
    event_payload jsonb not null,
    created_at timestamptz not null default current_timestamp
);

alter table app_workflow.draft_reviews
    add column if not exists blob_review_key text;

alter table app_workflow.app_users
    add column if not exists status text not null default 'pending_access';

alter table app_workflow.app_users
    add column if not exists auth_provider text;

alter table app_workflow.app_users
    add column if not exists last_seen_at timestamptz;

create index if not exists idx_app_users_status
    on app_workflow.app_users(status);

create index if not exists idx_draft_reviews_draft_id
    on app_workflow.draft_reviews(draft_id);

create index if not exists idx_draft_reviews_decision
    on app_workflow.draft_reviews(decision);

create index if not exists idx_audit_events_entity
    on app_workflow.audit_events(entity_type, entity_id);

create index if not exists idx_audit_events_actor
    on app_workflow.audit_events(actor_email);

select table_schema, table_name
from information_schema.tables
where table_schema in (
    'bronze_raw',
    'pipeline_audit',
    'metadata_catalog',
    'iceberg_catalog',
    'app_workflow'
)
order by table_schema, table_name;
