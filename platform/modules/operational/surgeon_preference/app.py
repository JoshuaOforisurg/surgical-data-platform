import json
import uuid
from datetime import UTC, datetime
from html import escape

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
st.set_page_config(
    page_title="Surgeon Preference",
    layout="wide",
)


def inject_theme() -> None:
    st.markdown(
        """
<style>
    :root {
        --nhs-blue: #005eb8;
        --nhs-dark-blue: #003087;
        --nhs-bright-blue: #0072ce;
        --nhs-pale-blue: #e8f4ff;
        --nhs-white: #ffffff;
        --nhs-grey: #f0f4f5;
        --nhs-border: #d8dde0;
        --nhs-text: #212b32;
        --nhs-muted: #4c6272;
        --nhs-green: #007f3b;
        --nhs-red: #da291c;
    }

    .stApp {
        background:
            linear-gradient(180deg, #f7fbff 0%, #eef5fb 42%, #ffffff 100%);
        color: var(--nhs-text);
    }

    [data-testid="stHeader"] {
        background: rgba(247, 251, 255, 0.92);
        border-bottom: 1px solid rgba(0, 94, 184, 0.12);
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 1280px;
    }

    .sp-hero {
        background: var(--nhs-white);
        border-left: 7px solid var(--nhs-blue);
        border-bottom: 1px solid var(--nhs-border);
        padding: 1.25rem 1.35rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 26px rgba(0, 48, 135, 0.08);
    }

    .sp-kicker {
        color: var(--nhs-blue);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }

    .sp-title {
        color: var(--nhs-dark-blue);
        font-size: 2.1rem;
        line-height: 1.12;
        font-weight: 800;
        margin: 0;
    }

    .sp-subtitle {
        color: var(--nhs-muted);
        font-size: 0.98rem;
        margin-top: 0.45rem;
        margin-bottom: 0;
        max-width: 860px;
    }

    .sp-banner {
        background: var(--nhs-pale-blue);
        border: 1px solid #b7dcff;
        border-left: 5px solid var(--nhs-bright-blue);
        color: var(--nhs-dark-blue);
        padding: 0.8rem 1rem;
        margin: 0.6rem 0 1.1rem;
        font-weight: 650;
    }

    [data-testid="stMetric"] {
        background: var(--nhs-white);
        border: 1px solid var(--nhs-border);
        border-top: 4px solid var(--nhs-blue);
        padding: 0.85rem 1rem;
        box-shadow: 0 8px 20px rgba(0, 48, 135, 0.06);
    }

    [data-testid="stMetricLabel"] {
        color: var(--nhs-muted);
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        color: var(--nhs-dark-blue);
        font-weight: 800;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 2px solid var(--nhs-border);
    }

    .stTabs [data-baseweb="tab"] {
        background: var(--nhs-white);
        border: 1px solid var(--nhs-border);
        border-bottom: 0;
        color: var(--nhs-dark-blue);
        font-weight: 750;
        padding: 0.65rem 0.9rem;
    }

    .stTabs [aria-selected="true"] {
        background: var(--nhs-blue);
        color: var(--nhs-white);
    }

    .sp-card-head,
    .sp-procedure {
        background: var(--nhs-white);
        border: 1px solid var(--nhs-border);
        box-shadow: 0 8px 20px rgba(0, 48, 135, 0.055);
    }

    .sp-card-head {
        border-left: 6px solid var(--nhs-blue);
        padding: 1rem 1.1rem;
        margin: 1rem 0;
    }

    .sp-card-head h2 {
        color: var(--nhs-dark-blue);
        font-size: 1.45rem;
        margin: 0 0 0.5rem;
    }

    .sp-card-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
    }

    .sp-chip {
        background: #eef7ff;
        border: 1px solid #c8e1f8;
        color: var(--nhs-dark-blue);
        font-size: 0.84rem;
        font-weight: 650;
        padding: 0.28rem 0.52rem;
    }

    .sp-procedure {
        padding: 1rem 1.1rem;
        margin: 0.85rem 0;
        border-top: 4px solid var(--nhs-bright-blue);
    }

    .sp-procedure h3 {
        color: var(--nhs-dark-blue);
        font-size: 1.15rem;
        margin: 0 0 0.65rem;
    }

    .sp-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 0.55rem;
    }

    .sp-field {
        background: #f8fbfd;
        border: 1px solid #e1e8ed;
        padding: 0.55rem 0.65rem;
        min-height: 4.1rem;
    }

    .sp-label {
        color: var(--nhs-muted);
        font-size: 0.72rem;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }

    .sp-value {
        color: var(--nhs-text);
        font-size: 0.9rem;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        background: var(--nhs-blue);
        border: 1px solid var(--nhs-blue);
        color: var(--nhs-white);
        font-weight: 800;
        min-height: 2.45rem;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        background: var(--nhs-dark-blue);
        border-color: var(--nhs-dark-blue);
        color: var(--nhs-white);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--nhs-border);
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def safe_html(value, default: str = "N/A") -> str:
    if value is None or value == "":
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return escape(str(value))


def render_hero() -> None:
    st.markdown(
        """
<section class="sp-hero">
  <div class="sp-kicker">Operational data product</div>
  <h1 class="sp-title">Surgeon Preference Pipeline</h1>
  <p class="sp-subtitle">Clinically aligned preference cards, medallion pipeline outputs, and audit metadata for theatre readiness workflows.</p>
</section>
        """,
        unsafe_allow_html=True,
    )


inject_theme()
render_hero()

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
    st.warning("No Gold data found in object storage. Run the pipeline first.")
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
current_df = current_preference_rows(df)
surgeons = current_df["surgeon_name"].dropna().unique().tolist()
procedures_count = current_df["procedure"].nunique() if "procedure" in current_df else 0
draft_keys = get_storage_client().list_objects(DRAFT_PREFIX)

st.markdown(
    """
<div class="sp-banner">Gold data loaded from the active object store. Latest operational cards are ready for review.</div>
    """,
    unsafe_allow_html=True,
)

metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
metric_col_1.metric("Gold rows", f"{len(df):,}")
metric_col_2.metric("Current cards", f"{len(current_df):,}")
metric_col_3.metric("Surgeons", f"{current_df['surgeon_name'].nunique():,}")
metric_col_4.metric("Procedures", f"{procedures_count:,}")

view_tab, edit_tab, create_tab, metadata_tab = st.tabs(
    ["Operational cards", "Draft edit", "Create draft", "Metadata"]
)


def render_card(card: dict) -> None:
    st.markdown(
        f"""
<section class="sp-card-head">
  <h2>{safe_html(card.get("surgeon_name"), "Unknown Surgeon")}</h2>
  <div class="sp-card-meta">
    <span class="sp-chip">Hospital: {safe_html(card.get("hospital"))}</span>
    <span class="sp-chip">Specialty: {safe_html(card.get("specialty"))}</span>
    <span class="sp-chip">Procedures: {len(card.get("procedures", []))}</span>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )

    for p in card.get("procedures", []):
        field_rows = [
            ("Procedure ID", p.get("procedure_id")),
            ("OPCS code", p.get("opcs_code")),
            ("Version", p.get("preference_card_version_label")),
            ("Version updated", p.get("version_updated_at")),
            ("Readiness", p.get("readiness_status")),
            ("Confidence", p.get("confidence")),
            ("Instrument system", p.get("instrument_system")),
            ("Implant system", p.get("implant_system")),
            ("Instrument set", p.get("instrument_set")),
            ("Equipment", p.get("equipment")),
            ("Draping", p.get("draping")),
            ("Consumables", p.get("consumables")),
            ("Disposables", p.get("disposables")),
            ("Implants", p.get("implants")),
            ("Sutures", p.get("sutures")),
            ("Dressings", p.get("dressings")),
            ("Positioning", p.get("positioning")),
            ("Anaesthetic", p.get("anaesthetic_notes")),
            ("Skin prep", p.get("skin_prep")),
            ("Special instructions", p.get("special_instructions")),
        ]
        fields_html = "\n".join(
            f"""
    <div class="sp-field">
      <div class="sp-label">{safe_html(label)}</div>
      <div class="sp-value">{safe_html(value)}</div>
    </div>
            """
            for label, value in field_rows
        )
        st.markdown(
            f"""
<section class="sp-procedure">
  <h3>{safe_html(p.get("procedure"), "Unknown Procedure")}</h3>
  <div class="sp-grid">
{fields_html}
  </div>
</section>
            """,
            unsafe_allow_html=True,
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
    st.metric("Drafts pending", len(draft_keys))
    if draft_keys:
        st.dataframe(pd.DataFrame({"draft_key": draft_keys[-25:]}), use_container_width=True)

    postgres_metadata = load_postgres_metadata()
    postgres_health = postgres_metadata["health"]

    st.subheader("Surgeon preference metadata catalogue")
    pg_col_1, pg_col_2, pg_col_3 = st.columns(3)
    pg_col_1.metric("Reachable", "Yes" if postgres_health.get("reachable") else "No")
    pg_col_2.metric("Schema valid", "Yes" if postgres_health.get("valid") else "No")
    pg_col_3.metric("Missing tables", len(postgres_health.get("missing_tables", [])))

    if not postgres_health.get("valid"):
        st.warning(postgres_health.get("message", "Surgeon preference metadata catalogue is not aligned."))
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
