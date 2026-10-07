# Local Postgres Inspection Guide

Use this guide when checking the local Docker Postgres database from DBeaver.

## Connection

The local Docker Compose stack publishes Postgres on the host machine so GUI
tools can inspect it.

Typical DBeaver settings:

```text
Host: localhost
Port: 5433
Database: surgeon_preference
Username: surgeon_preference_user
Password: value of DB_PASSWORD in your local .env
```

If the connection fails, confirm the Docker stack is running:

```bash
docker compose ps
```

The database contents live in the Docker volume, not in the image itself. If an
image was deleted but the volume still exists, the data can still be present
after the service is recreated. If the volume was deleted, the database will be
empty until the pipeline runs again.

## Schemas To Check

The most important schemas are:

```text
pipeline_audit
bronze_raw
metadata_catalog
iceberg_catalog
app_workflow
```

## Operational Preference Cards

These rows prove that Streamlit can read the operational source of truth from
Postgres.

```sql
select
    organisation_id,
    surgeon_name,
    procedure_name,
    current_version_number,
    status,
    updated_at
from app_workflow.preference_cards
order by updated_at desc, surgeon_name, procedure_name;
```

## Version History

These rows prove that imports, draft publishes, and rollbacks create an audit
trail instead of overwriting history.

```sql
select
    c.organisation_id,
    c.surgeon_name,
    c.procedure_name,
    v.version_number,
    v.version_label,
    v.is_current,
    v.change_type,
    v.source_version_id,
    v.change_reason,
    v.published_by,
    v.published_at,
    v.created_at
from app_workflow.preference_card_versions v
join app_workflow.preference_cards c
    on c.card_id = v.card_id
order by v.created_at desc, v.version_number desc;
```

## Pipeline Runs

These rows prove that the ETL pipeline has executed and published Gold output.

```sql
select
    run_id,
    status,
    files_landed,
    records_processed,
    gold_operational_key,
    gold_analytics_key,
    started_at,
    completed_at,
    error_message
from pipeline_audit.pipeline_runs
order by started_at desc;
```

## Gold Artifacts

These rows prove that Gold files were catalogued.

```sql
select
    run_id,
    artifact_name,
    object_key,
    record_count,
    schema_version,
    data_product_version,
    created_at
from metadata_catalog.gold_artifacts
order by created_at desc, artifact_name;
```

## Workflow Audit

These rows prove that draft submission, review, publish, access, and rollback
events are captured.

```sql
select
    event_type,
    organisation_id,
    actor_email,
    actor_name,
    entity_type,
    entity_id,
    created_at
from app_workflow.audit_events
order by created_at desc;
```
