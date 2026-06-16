import json
import uuid
from datetime import UTC, datetime

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import load_settings
from domain.clinical_reference_service import ClinicalReferenceService
from streamlit_renderers.preference_card import build_preference_card, current_preference_rows
from streamlit_services.streamlit_service import get_storage_client


GOLD_OPERATIONAL_KEY = "gold/operational/latest/gold_operational_preference_cards.csv"
DRAFT_PREFIX = "gold/operational/drafts"
EDITABLE_FIELDS = [
    "instrument_set",
    "equipment",
    "draping",
    "consumables",
    "disposables",
    "implants",
    "sutures",
    "dressings",
    "positioning",
    "anaesthetic_notes",
    "skin_prep",
    "special_instructions",
]

# ----------------------------
# APP CONFIG
# ----------------------------
st.set_page_config(page_title="Surgical Data Platform", layout="wide")
st.title("Surgical Preference Platform")

# ----------------------------
# LOAD OPERATIONAL GOLD DATA (SAFE)
# ----------------------------
@st.cache_data(ttl=60)
def load_gold_data():
    try:
        storage = get_storage_client()
        local_path = "/tmp/gold.csv"
        storage.download_file(GOLD_OPERATIONAL_KEY, local_path)

        return pd.read_csv(local_path)

    except Exception as e:
        st.error(f"Failed to load gold data: {e}")
        return None


def save_draft(payload: dict) -> str:
    storage = get_storage_client()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    draft_id = payload["draft_id"]
    key = f"{DRAFT_PREFIX}/{timestamp}_{draft_id}.json"
    storage.put_text(key, json.dumps(payload, indent=2), "application/json")
    return key


@st.cache_data(ttl=300)
def load_reference_metadata() -> pd.DataFrame:
    rows = []
    for item in ClinicalReferenceService().operational_metadata_table():
        row = item.model_dump()
        for field in [
            "expected_positioning",
            "expected_anaesthetic",
            "expected_skin_prep",
            "critical_checks",
        ]:
            row[field] = ", ".join(row.get(field) or [])
        rows.append(row)
    return pd.DataFrame(rows)


def _postgres_frame(settings, query: str) -> pd.DataFrame:
    with psycopg2.connect(settings.psycopg2_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET statement_timeout = '5s'")
            cur.execute(query)
            return pd.DataFrame(cur.fetchall())


@st.cache_data(ttl=30)
def load_postgres_metadata() -> dict:
    settings = load_settings().postgres
    repository = BronzeCatalogRepository(settings)
    health = repository.healthcheck(initialise=False)
    if not settings or not health.get("reachable"):
        return {"health": health}

    return {
        "health": health,
        "runs": _postgres_frame(
            settings,
            """
            SELECT
                run_id,
                status,
                pipeline_version,
                data_product_version,
                files_landed,
                records_processed,
                gold_operational_key,
                gold_analytics_key,
                started_at,
                completed_at,
                error_message
            FROM pipeline_audit.pipeline_runs
            ORDER BY started_at DESC
            LIMIT 25
            """,
        ),
        "object_summary": _postgres_frame(
            settings,
            """
            SELECT
                layer,
                artifact_type,
                COUNT(*) AS object_count,
                SUM(size_bytes) AS total_size_bytes,
                MAX(created_at) AS latest_created_at
            FROM metadata_catalog.object_store_objects
            GROUP BY layer, artifact_type
            ORDER BY layer, artifact_type
            """,
        ),
        "gold_artifacts": _postgres_frame(
            settings,
            """
            SELECT
                run_id,
                artifact_name,
                object_key,
                record_count,
                schema_version,
                data_product_version,
                created_at
            FROM metadata_catalog.gold_artifacts
            ORDER BY created_at DESC, artifact_name
            LIMIT 50
            """,
        ),
        "ingested_files": _postgres_frame(
            settings,
            """
            SELECT
                run_id,
                original_filename,
                file_extension,
                status,
                record_count,
                size_bytes,
                checksum_sha256,
                created_at,
                updated_at
            FROM bronze_raw.ingested_files
            ORDER BY created_at DESC
            LIMIT 50
            """,
        ),
        "iceberg": _postgres_frame(
            settings,
            """
            SELECT
                catalog_name,
                namespace,
                warehouse_uri,
                status,
                error_message,
                updated_at
            FROM iceberg_catalog.catalog_bootstrap
            ORDER BY updated_at DESC
            """,
        ),
    }


# ----------------------------
# LOAD DATA
# ----------------------------
df = load_gold_data()

if df is None or df.empty:
    st.warning("No Gold data found in MinIO. Run pipeline first.")
    st.stop()

# ----------------------------
# VALIDATION
# ----------------------------
if "surgeon_name" not in df.columns:
    st.error("Invalid dataset: missing surgeon_name column")
    st.stop()

# ----------------------------
# UI LOGIC
# ----------------------------
st.success("Gold data loaded")

current_df = current_preference_rows(df)
surgeons = current_df["surgeon_name"].dropna().unique().tolist()
view_tab, edit_tab, create_tab, metadata_tab = st.tabs(
    ["Operational cards", "Draft edit", "Create draft", "Metadata"]
)


def render_card(card: dict) -> None:
    st.header(card.get("surgeon_name", "Unknown Surgeon"))
    st.write(f"Hospital: {card.get('hospital', 'N/A')}")
    st.write(f"Specialty: {card.get('specialty', 'N/A')}")
    st.markdown("---")
    st.subheader("Clinical Preference Card")
    for p in card.get("procedures", []):
        st.markdown(
            f"""
### {p.get('procedure', 'Unknown')}
- **Procedure ID:** {p.get('procedure_id', 'N/A')}
- **OPCS code:** {p.get('opcs_code', 'N/A')}
- **Version:** {p.get('preference_card_version_label', 'N/A')}
- **Version updated:** {p.get('version_updated_at', 'N/A')}
- **Readiness:** {p.get('readiness_status', 'N/A')}
- **Instrument system:** {p.get('instrument_system', 'N/A')}
- **Implant system:** {p.get('implant_system', 'N/A')}
- **Instrument set:** {p.get('instrument_set', 'N/A')}
- **Equipment:** {p.get('equipment', 'N/A')}
- **Draping:** {p.get('draping', 'N/A')}
- **Consumables:** {p.get('consumables', 'N/A')}
- **Disposables:** {p.get('disposables', 'N/A')}
- **Implants:** {p.get('implants', 'N/A')}
- **Sutures:** {p.get('sutures', 'N/A')}
- **Dressings:** {p.get('dressings', 'N/A')}
- **Confidence:** {p.get('confidence', 'N/A')}
- **Positioning:** {p.get('positioning', 'N/A')}
- **Anaesthetic:** {p.get('anaesthetic_notes', 'N/A')}
- **Skin prep:** {p.get('skin_prep', 'N/A')}
- **Special instructions:** {p.get('special_instructions', 'N/A')}
"""
        )


with view_tab:
    selected_surgeon = st.selectbox("Select Surgeon", surgeons, key="view_surgeon")
    selected_procedure = None

    surgeon_df = current_df[current_df["surgeon_name"] == selected_surgeon]
    if "procedure" in surgeon_df.columns:
        procedures = surgeon_df["procedure"].dropna().unique().tolist()
        if procedures:
            selected_procedure = st.selectbox("Select Procedure", ["All procedures"] + procedures)

    if st.button("Generate Preference Card"):
        procedure_filter = None if selected_procedure == "All procedures" else selected_procedure
        card = build_preference_card(current_df, selected_surgeon, procedure_filter)

        if not card:
            st.warning("No data found for surgeon")
        else:
            render_card(card)


with edit_tab:
    edit_surgeon = st.selectbox("Surgeon", surgeons, key="edit_surgeon")
    edit_df = current_df[current_df["surgeon_name"] == edit_surgeon]
    edit_procedures = edit_df["procedure"].dropna().unique().tolist()
    edit_procedure = st.selectbox("Procedure", edit_procedures, key="edit_procedure")
    selected_rows = edit_df[edit_df["procedure"] == edit_procedure]

    if not selected_rows.empty:
        current = selected_rows.iloc[0].to_dict()
        with st.form("edit_preference_form"):
            edited = {
                field: st.text_area(
                    field.replace("_", " ").title(),
                    value=str(current.get(field) or ""),
                    height=90 if field in {"consumables", "disposables", "special_instructions"} else 70,
                )
                for field in EDITABLE_FIELDS
            }
            submitted = st.form_submit_button("Save Draft Edit")

        if submitted:
            draft = {
                "draft_id": str(uuid.uuid4()),
                "draft_type": "edit",
                "status": "pending_review",
                "created_at": datetime.now(UTC).isoformat(),
                "surgeon_id": current.get("surgeon_id"),
                "surgeon_name": current.get("surgeon_name"),
                "procedure": current.get("procedure"),
                "procedure_id": current.get("procedure_id"),
                "original": {field: current.get(field) for field in EDITABLE_FIELDS},
                "proposed": edited,
                "source_gold_key": GOLD_OPERATIONAL_KEY,
            }
            key = save_draft(draft)
            st.success(f"Draft saved: {key}")


with create_tab:
    with st.form("create_preference_form"):
        new_surgeon = st.text_input("Surgeon Name")
        new_specialty = st.text_input("Specialty", value="Orthopaedics")
        new_procedure = st.text_input("Procedure")
        new_subspecialty = st.text_input("Subspecialty")
        new_fields = {
            field: st.text_area(
                field.replace("_", " ").title(),
                height=80 if field in {"consumables", "disposables", "special_instructions"} else 60,
            )
            for field in EDITABLE_FIELDS
        }
        create_submitted = st.form_submit_button("Save New Draft")

    if create_submitted:
        draft = {
            "draft_id": str(uuid.uuid4()),
            "draft_type": "create",
            "status": "pending_review",
            "created_at": datetime.now(UTC).isoformat(),
            "surgeon_name": new_surgeon,
            "specialty": new_specialty,
            "procedure": new_procedure,
            "subspecialty": new_subspecialty,
            "proposed": new_fields,
            "source_gold_key": GOLD_OPERATIONAL_KEY,
        }
        key = save_draft(draft)
        st.success(f"Draft saved: {key}")


with metadata_tab:
    st.metric("Gold rows", len(df))
    st.metric("Current cards", len(current_df))
    st.metric("Surgeons", current_df["surgeon_name"].nunique())
    st.metric("Procedures", current_df["procedure"].nunique() if "procedure" in current_df else 0)
    draft_keys = get_storage_client().list_objects(DRAFT_PREFIX)
    st.metric("Drafts pending", len(draft_keys))
    if draft_keys:
        st.dataframe(pd.DataFrame({"draft_key": draft_keys[-25:]}), use_container_width=True)

    postgres_metadata = load_postgres_metadata()
    postgres_health = postgres_metadata["health"]

    st.subheader("Postgres metadata catalogue")
    pg_col_1, pg_col_2, pg_col_3 = st.columns(3)
    pg_col_1.metric("Reachable", "Yes" if postgres_health.get("reachable") else "No")
    pg_col_2.metric("Schema valid", "Yes" if postgres_health.get("valid") else "No")
    pg_col_3.metric("Missing tables", len(postgres_health.get("missing_tables", [])))

    if not postgres_health.get("valid"):
        st.warning(postgres_health.get("message", "Postgres metadata catalogue is not aligned."))
        if postgres_health.get("missing_tables"):
            st.dataframe(
                pd.DataFrame({"missing_table": postgres_health["missing_tables"]}),
                use_container_width=True,
                hide_index=True,
            )
        if postgres_health.get("missing_columns"):
            missing_columns = [
                {"table": table, "missing_column": column}
                for table, columns in postgres_health["missing_columns"].items()
                for column in columns
            ]
            st.dataframe(pd.DataFrame(missing_columns), use_container_width=True, hide_index=True)
    else:
        st.success(postgres_health["message"])

    postgres_sections = [
        ("Pipeline runs", "runs"),
        ("Object store objects", "object_summary"),
        ("Gold artifacts", "gold_artifacts"),
        ("Bronze ingested files", "ingested_files"),
        ("Iceberg catalog", "iceberg"),
    ]
    for label, key in postgres_sections:
        if key in postgres_metadata:
            with st.expander(label, expanded=key in {"runs", "object_summary"}):
                st.dataframe(postgres_metadata[key], use_container_width=True, hide_index=True)

    st.subheader("Clinical reference metadata")
    st.dataframe(load_reference_metadata(), use_container_width=True, hide_index=True)
