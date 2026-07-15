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
st.set_page_config(page_title="Surgeon Preference Pipeline", layout="wide")


def inject_theme() -> None:
    st.markdown(
        """
<style>
    :root {
        --sp-blue: #005eb8;
        --sp-dark-blue: #003087;
        --sp-pale-blue: #e8f4ff;
        --sp-border: #d8dde0;
        --sp-text: #212b32;
        --sp-muted: #4c6272;
        --sp-white: #ffffff;
    }

    .stApp {
        background: #f5f9fc;
        color: var(--sp-text);
    }

    [data-testid="stHeader"] {
        background: rgba(247, 251, 255, 0.94);
        border-bottom: 1px solid rgba(0, 94, 184, 0.14);
    }

    .block-container {
        max-width: 1280px;
        padding-top: 1.25rem;
        padding-bottom: 3rem;
    }

    h1 {
        color: var(--sp-dark-blue);
        background: transparent;
        border: 0;
        padding: 0.25rem 0 0.6rem;
        box-shadow: none;
    }

    h2, h3 {
        color: var(--sp-dark-blue);
        margin-top: 1.15rem;
    }

    div[data-testid="stAlert"] {
        border: 1px solid #b7dcff;
        background: var(--sp-pale-blue);
        color: var(--sp-dark-blue);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 2px solid var(--sp-border);
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: 0;
        color: var(--sp-dark-blue);
        font-weight: 700;
        padding: 0.65rem 0.85rem;
    }

    .stTabs [aria-selected="true"] {
        background: var(--sp-pale-blue);
        color: var(--sp-dark-blue);
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background-color: var(--sp-blue);
    }

    .sp-hero {
        background: linear-gradient(180deg, #ffffff 0%, #eef7ff 100%);
        border: 1px solid #c8dff3;
        padding: 1.35rem 1.45rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 10px 24px rgba(0, 48, 135, 0.06);
    }

    .sp-kicker {
        color: var(--sp-blue);
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
    }

    .sp-hero h1 {
        margin: 0;
        padding: 0;
    }

    .sp-lead {
        color: var(--sp-muted);
        font-size: 1.02rem;
        line-height: 1.55;
        max-width: 920px;
        margin: 0.55rem 0 0;
    }

    .sp-summary-grid {
        display: grid;
        gap: 0.9rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: 0.4rem 0 1.2rem;
    }

    .sp-summary-tile {
        background: var(--sp-white);
        border: 1px solid var(--sp-border);
        padding: 0.85rem 1rem;
        min-height: 5.8rem;
        box-shadow: 0 8px 20px rgba(0, 48, 135, 0.05);
    }

    .sp-summary-label {
        color: var(--sp-muted);
        font-size: 0.86rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    .sp-summary-value {
        color: var(--sp-dark-blue);
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1.15;
        overflow-wrap: anywhere;
    }

    .sp-field-list {
        background: var(--sp-white);
        border: 1px solid var(--sp-border);
        margin: 0.45rem 0 1.2rem;
    }

    .sp-field-row {
        display: grid;
        grid-template-columns: minmax(9rem, 14rem) minmax(0, 1fr);
        border-bottom: 1px solid #e5edf3;
    }

    .sp-field-row:last-child {
        border-bottom: 0;
    }

    .sp-field-label {
        background: #f3f8fc;
        color: var(--sp-muted);
        font-weight: 800;
        padding: 0.72rem 0.85rem;
    }

    .sp-field-value {
        color: var(--sp-text);
        line-height: 1.45;
        padding: 0.72rem 0.9rem;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
    }

    @media (max-width: 900px) {
        .sp-summary-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .sp-field-row {
            grid-template-columns: 1fr;
        }

        .sp-field-label {
            padding-bottom: 0.35rem;
        }

        .sp-field-value {
            padding-top: 0.35rem;
        }
    }

    @media (max-width: 560px) {
        .sp-summary-grid {
            grid-template-columns: 1fr;
        }
    }

    [data-testid="stMetric"] {
        background: var(--sp-white);
        border: 1px solid var(--sp-border);
        padding: 0.85rem 1rem;
        box-shadow: 0 8px 20px rgba(0, 48, 135, 0.06);
    }

    [data-testid="stMetricLabel"] {
        color: var(--sp-muted);
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        color: var(--sp-dark-blue);
        font-weight: 800;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        background: var(--sp-blue);
        border: 1px solid var(--sp-blue);
        color: var(--sp-white);
        font-weight: 800;
        min-height: 2.45rem;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        background: var(--sp-dark-blue);
        border-color: var(--sp-dark-blue);
        color: var(--sp-white);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--sp-border);
    }
</style>
        """,
        unsafe_allow_html=True,
    )


inject_theme()

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

st.markdown(
    """
<section class="sp-hero">
    <div class="sp-kicker">Version 1 surgical data product</div>
    <h1>Surgeon Preference</h1>
    <p class="sp-lead">
        A working theatre operations app for viewing surgeon preference cards,
        checking procedure requirements, and capturing draft preference updates.
        It is powered by a medallion data pipeline that publishes the latest
        validated Gold dataset into cloud object storage.
    </p>
</section>
    """,
    unsafe_allow_html=True,
)

status_col_1, status_col_2, status_col_3, status_col_4 = st.columns(4)
status_col_1.metric("Current cards", len(current_df))
status_col_2.metric("Surgeons", current_df["surgeon_name"].nunique())
status_col_3.metric("Procedures", current_df["procedure"].nunique() if "procedure" in current_df else 0)
status_col_4.metric("Pipeline layer", "Gold")

overview_tab, view_tab, edit_tab, create_tab, metadata_tab = st.tabs(
    ["Overview", "Preference cards", "Draft edit", "Create draft", "Metadata"]
)


def render_overview() -> None:
    st.subheader("What this app is for")
    st.write(
        "Surgeon preference cards help theatre teams prepare the right equipment, "
        "instrument sets, consumables, implants, positioning, skin preparation, "
        "and special instructions before a procedure starts."
    )
    st.write(
        "This version uses synthetic clinical data only. It demonstrates how a "
        "hospital-facing preference-card workflow could be structured before any "
        "real hospital integration or patient-related data is introduced."
    )

    workflow_col_1, workflow_col_2, workflow_col_3 = st.columns(3)
    with workflow_col_1:
        st.markdown("#### View")
        st.write("Select a surgeon and procedure to view the latest operational card.")
    with workflow_col_2:
        st.markdown("#### Draft")
        st.write("Propose updates without overwriting the validated Gold dataset.")
    with workflow_col_3:
        st.markdown("#### Audit")
        st.write("Check run metadata, object storage outputs, and clinical references.")

    st.subheader("Current dataset")
    preview_columns = [
        column
        for column in [
            "surgeon_name",
            "hospital",
            "specialty",
            "procedure",
            "readiness_status",
            "confidence",
        ]
        if column in current_df.columns
    ]
    st.dataframe(
        current_df[preview_columns].sort_values(preview_columns[:1]),
        width="stretch",
        hide_index=True,
    )


def _display_value(value) -> str:
    if pd.isna(value) or value == "":
        return "N/A"
    return str(value)


def render_summary_tiles(items: list[tuple[str, object]]) -> None:
    tiles = []
    for label, value in items:
        tiles.append(
            '<div class="sp-summary-tile">'
            f'<div class="sp-summary-label">{escape(label)}</div>'
            f'<div class="sp-summary-value">{escape(_display_value(value))}</div>'
            "</div>"
        )
    st.markdown(f'<div class="sp-summary-grid">{"".join(tiles)}</div>', unsafe_allow_html=True)


def render_field_list(items: list[tuple[str, object]]) -> None:
    rows = []
    for label, value in items:
        rows.append(
            '<div class="sp-field-row">'
            f'<div class="sp-field-label">{escape(label)}</div>'
            f'<div class="sp-field-value">{escape(_display_value(value))}</div>'
            "</div>"
        )
    st.markdown(f'<div class="sp-field-list">{"".join(rows)}</div>', unsafe_allow_html=True)


def render_card(card: dict) -> None:
    st.header(card.get("surgeon_name", "Unknown Surgeon"))
    details_col_1, details_col_2 = st.columns(2)
    details_col_1.write(f"Hospital: {_display_value(card.get('hospital'))}")
    details_col_2.write(f"Specialty: {_display_value(card.get('specialty'))}")

    st.subheader("Clinical preference card")
    for index, p in enumerate(card.get("procedures", []), start=1):
        with st.expander(f"{index}. {p.get('procedure', 'Unknown Procedure')}", expanded=index == 1):
            render_summary_tiles(
                [
                    ("Readiness", p.get("readiness_status")),
                    ("Version", p.get("preference_card_version_label")),
                    ("Confidence", p.get("confidence")),
                    ("OPCS", p.get("opcs_code")),
                ]
            )

            st.markdown("##### Theatre setup")
            render_field_list(
                [
                    ("Procedure ID", p.get("procedure_id")),
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
                ]
            )

            st.markdown("##### Clinical notes")
            render_field_list(
                [
                    ("Positioning", p.get("positioning")),
                    ("Anaesthetic", p.get("anaesthetic_notes")),
                    ("Skin prep", p.get("skin_prep")),
                    ("Special instructions", p.get("special_instructions")),
                    ("Version updated", p.get("version_updated_at")),
                ]
            )


with overview_tab:
    render_overview()


with view_tab:
    search_term = st.text_input("Search surgeon or procedure", key="card_search")
    filtered_df = current_df.copy()
    if search_term:
        search_mask = pd.Series(False, index=filtered_df.index)
        for search_column in ["surgeon_name", "procedure", "specialty", "hospital"]:
            if search_column in filtered_df.columns:
                search_mask = search_mask | filtered_df[search_column].astype(str).str.contains(
                    search_term,
                    case=False,
                    na=False,
                )
        filtered_df = filtered_df[search_mask]

    filtered_surgeons = filtered_df["surgeon_name"].dropna().unique().tolist()
    if not filtered_surgeons:
        st.warning("No matching preference cards found.")
    else:
        selected_surgeon = st.selectbox("Select surgeon", filtered_surgeons, key="view_surgeon")
        selected_procedure = None

        surgeon_df = filtered_df[filtered_df["surgeon_name"] == selected_surgeon]
        if "procedure" in surgeon_df.columns:
            procedures = surgeon_df["procedure"].dropna().unique().tolist()
            if procedures:
                selected_procedure = st.selectbox(
                    "Select procedure",
                    ["All procedures"] + procedures,
                )

        procedure_filter = None if selected_procedure == "All procedures" else selected_procedure
        card = build_preference_card(current_df, selected_surgeon, procedure_filter)

        if not card:
            st.warning("No data found for surgeon")
        else:
            render_card(card)

        st.subheader("Matching rows")
        summary_columns = [
            column
            for column in [
                "surgeon_name",
                "hospital",
                "specialty",
                "procedure",
                "procedure_id",
                "readiness_status",
                "confidence",
            ]
            if column in surgeon_df.columns
        ]
        st.dataframe(
            surgeon_df[summary_columns],
            width="stretch",
            hide_index=True,
        )


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
        st.dataframe(pd.DataFrame({"draft_key": draft_keys[-25:]}), width="stretch")

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
                width="stretch",
                hide_index=True,
            )
        if postgres_health.get("missing_columns"):
            missing_columns = [
                {"table": table, "missing_column": column}
                for table, columns in postgres_health["missing_columns"].items()
                for column in columns
            ]
            st.dataframe(pd.DataFrame(missing_columns), width="stretch", hide_index=True)
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
                st.dataframe(postgres_metadata[key], width="stretch", hide_index=True)

    st.subheader("Clinical reference metadata")
    st.dataframe(load_reference_metadata(), width="stretch", hide_index=True)
