import json
import os
import uuid
from datetime import UTC, datetime
from html import escape
from urllib.parse import quote

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import load_settings
from domain.clinical_reference_service import ClinicalReferenceService
from streamlit_services.access_control import (
    ACTIVE_STATUS,
    ADMIN_ROLE,
    AUTHENTICATED_ROLE,
    EDITOR_ROLE,
    PENDING_ACCESS_STATUS,
    REVIEWER_ROLE,
    SUSPENDED_STATUS,
    load_current_user,
    publish_block_reason,
    review_block_reason,
    submission_block_reason,
    user_management_block_reason,
)
from streamlit_renderers.preference_card import build_preference_card, current_preference_rows
from streamlit_services.draft_review_service import (
    REVIEW_DECISION_PREFIX,
    build_review_decision,
    draft_change_rows,
    draft_display_name,
    load_drafts,
    load_pending_drafts,
    save_reviewed_draft,
    save_review_payload,
)
from streamlit_services.publishing_service import (
    PUBLISH_EVENT_PREFIX,
    apply_approved_draft_to_gold,
    build_publish_event,
    load_publishable_drafts,
    mark_draft_published,
    save_publish_event,
    save_published_gold,
)
from streamlit_services.streamlit_service import get_storage_client
from streamlit_services.user_registry_service import sync_user_with_registry, update_user_access


GOLD_OPERATIONAL_KEY = "gold/operational/latest/gold_operational_preference_cards.csv"
DRAFT_PREFIX = "gold/operational/drafts"
GITHUB_PROFILE_URL = os.getenv("APP_GITHUB_PROFILE_URL", "https://github.com/JoshuaOforisurg")
CONTACT_EMAIL = os.getenv("APP_CONTACT_EMAIL", "info@surgeonpreference.com").strip()
ENABLE_DRAFT_SUBMISSIONS = os.getenv("ENABLE_DRAFT_SUBMISSIONS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_DRAFT_REVIEWS = os.getenv("ENABLE_DRAFT_REVIEWS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_DRAFT_PUBLISHING = os.getenv("ENABLE_DRAFT_PUBLISHING", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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
    menu_items={
        "About": (
            "Surgeon Preference is a surgical operations data product for "
            "viewing preference cards, capturing draft changes, and auditing "
            "review decisions."
        )
    },
)


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

    .sp-footer {
        border-top: 1px solid var(--sp-border);
        color: var(--sp-muted);
        display: flex;
        flex-wrap: wrap;
        gap: 0.7rem 1rem;
        justify-content: space-between;
        font-size: 0.9rem;
        line-height: 1.55;
        margin-top: 2.5rem;
        padding: 1.15rem 0 0.25rem;
    }

    .sp-footer strong {
        color: var(--sp-dark-blue);
    }

    .sp-footer a {
        color: var(--sp-blue);
        font-weight: 700;
        text-decoration: none;
    }

    .sp-footer a:hover {
        color: var(--sp-dark-blue);
        text-decoration: underline;
    }

    .sp-footer-links {
        align-items: center;
        display: inline-flex;
        flex-wrap: wrap;
        gap: 0.85rem;
        white-space: nowrap;
    }

    .sp-footer-link {
        align-items: center;
        display: inline-flex;
        gap: 0.35rem;
    }

    .sp-footer-link svg {
        height: 1rem;
        width: 1rem;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


inject_theme()


def render_project_footer() -> None:
    contact_subject = quote("Surgeon Preference enquiry")
    contact_href = f"mailto:{CONTACT_EMAIL}?subject={contact_subject}"
    st.markdown(
        f"""
<footer class="sp-footer">
    <div>
        <strong>Surgeon Preference</strong> is a surgical data engineering
        product for preference-card operations, draft review, and controlled
        publishing. Built by Joshua Ofori Donkor, combining theatre workflow
        experience with biomedical science and data engineering.
    </div>
    <div class="sp-footer-links">
        <a class="sp-footer-link" href="{escape(GITHUB_PROFILE_URL)}" target="_blank" rel="noopener noreferrer">
            GitHub portfolio
        </a>
        <a class="sp-footer-link" href="{escape(contact_href)}" aria-label="Contact Joshua Ofori Donkor by email">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect width="20" height="16" x="2" y="4" rx="2"></rect>
                <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
            </svg>
            Contact
        </a>
    </div>
</footer>
        """,
        unsafe_allow_html=True,
    )

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


def save_draft(payload: dict, submitter) -> str:
    block_reason = submission_block_reason(submitter, ENABLE_DRAFT_SUBMISSIONS)
    if block_reason:
        raise PermissionError(block_reason)

    storage = get_storage_client()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    draft_id = payload["draft_id"]
    key = f"{DRAFT_PREFIX}/{timestamp}_{draft_id}.json"
    payload.update(
        {
            "submitted_by": submitter.display_name,
            "submitter_email": submitter.email,
            "submitter_roles": list(submitter.roles),
            "submitter_status": submitter.status,
        }
    )
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


def record_review_in_postgres(review: dict, blob_review_key: str) -> tuple[bool, str]:
    settings = load_settings().postgres
    if not settings:
        return False, "Postgres settings are not configured for this deployment."

    try:
        repository = BronzeCatalogRepository(settings)
        repository.initialise()
        repository.record_draft_review_decision(review, blob_review_key)
    except psycopg2.Error as exc:
        return False, str(exc).strip()

    return True, "Review decision written to the Postgres workflow audit."


def record_publish_in_postgres(publish_event: dict, publish_event_key: str) -> tuple[bool, str]:
    settings = load_settings().postgres
    if not settings:
        return False, "Postgres settings are not configured for this deployment."

    try:
        repository = BronzeCatalogRepository(settings)
        repository.initialise()
        repository.record_publish_event(publish_event, publish_event_key)
    except psycopg2.Error as exc:
        return False, str(exc).strip()

    return True, "Publish event written to the Postgres workflow audit."


def record_draft_submission_in_postgres(draft: dict, draft_key: str) -> tuple[bool, str]:
    settings = load_settings().postgres
    if not settings:
        return False, "Postgres settings are not configured for this deployment."

    try:
        repository = BronzeCatalogRepository(settings)
        repository.initialise()
        repository.record_draft_submission(draft, draft_key)
    except psycopg2.Error as exc:
        return False, str(exc).strip()

    return True, "Draft submission written to the Postgres workflow audit."


@st.cache_data(ttl=30)
def load_postgres_metadata() -> dict:
    settings = load_settings().postgres
    repository = BronzeCatalogRepository(settings)
    health = repository.healthcheck(initialise=False)
    if not settings or not health.get("reachable"):
        return {"health": health}

    metadata = {
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

    if health.get("valid"):
        metadata["workflow_reviews"] = _postgres_frame(
            settings,
            """
            SELECT
                review_id,
                draft_id,
                decision,
                reviewer_name,
                reviewer_email,
                reviewer_roles,
                surgeon_name,
                procedure,
                reviewed_at,
                blob_review_key
            FROM app_workflow.draft_reviews
            ORDER BY reviewed_at DESC
            LIMIT 50
            """,
        )
        metadata["workflow_audit"] = _postgres_frame(
            settings,
            """
            SELECT
                event_type,
                actor_email,
                actor_name,
                actor_roles,
                entity_type,
                entity_id,
                created_at
            FROM app_workflow.audit_events
            ORDER BY created_at DESC
            LIMIT 50
            """,
        )
        metadata["app_users"] = _postgres_frame(
            settings,
            """
            SELECT
                user_email,
                display_name,
                roles,
                status,
                auth_provider,
                last_seen_at,
                updated_at
            FROM app_workflow.app_users
            ORDER BY updated_at DESC
            LIMIT 100
            """,
        )

    return metadata


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

overview_tab, view_tab, edit_tab, create_tab, review_tab, publish_tab, access_tab, metadata_tab = st.tabs(
    [
        "Overview",
        "Preference cards",
        "Draft edit",
        "Create draft",
        "Review queue",
        "Publish queue",
        "Access",
        "Metadata",
    ]
)


def detect_auth_provider(headers) -> str:
    for key in headers or {}:
        if str(key).lower().startswith("x-ms-client-principal"):
            return "azure_container_apps"
    return "local_env"


current_user = load_current_user(os.environ, st.context.headers)
current_user, user_registry_warning = sync_user_with_registry(
    current_user,
    load_settings().postgres,
    detect_auth_provider(st.context.headers),
)
draft_submission_disabled_reason = submission_block_reason(current_user, ENABLE_DRAFT_SUBMISSIONS)

if user_registry_warning:
    st.warning(user_registry_warning)


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


def normalise_role_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return sorted({str(item).strip().lower() for item in value if str(item).strip()})
    text = str(value).strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    return sorted({item.strip().lower() for item in text.split(",") if item.strip()})


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
    if current_user:
        st.caption(
            f"Signed in as {current_user.display_name} ({current_user.email}); "
            f"roles: {', '.join(current_user.roles) if current_user.roles else 'viewer'}; "
            f"status: {current_user.status}"
        )
    if draft_submission_disabled_reason:
        st.info(
            f"{draft_submission_disabled_reason} The form shows the workflow, "
            "but only authorised users can save changes."
        )

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
            submitted = st.form_submit_button(
                "Save Draft Edit",
                disabled=draft_submission_disabled_reason is not None,
            )

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
            try:
                key = save_draft(draft, current_user)
                postgres_ok, postgres_message = record_draft_submission_in_postgres(draft, key)
                if postgres_ok:
                    load_postgres_metadata.clear()
                st.success(f"Draft saved: {key}")
                if postgres_ok:
                    st.success(postgres_message)
                else:
                    st.warning(
                        "The draft was saved to object storage, but the Postgres workflow "
                        f"audit was not written: {postgres_message}"
                    )
            except PermissionError as exc:
                st.error(str(exc))


with create_tab:
    if current_user:
        st.caption(
            f"Signed in as {current_user.display_name} ({current_user.email}); "
            f"roles: {', '.join(current_user.roles) if current_user.roles else 'viewer'}; "
            f"status: {current_user.status}"
        )
    if draft_submission_disabled_reason:
        st.info(
            f"{draft_submission_disabled_reason} Enable draft submissions only "
            "for authenticated and authorised users."
        )

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
        create_submitted = st.form_submit_button(
            "Save New Draft",
            disabled=draft_submission_disabled_reason is not None,
        )

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
        try:
            key = save_draft(draft, current_user)
            postgres_ok, postgres_message = record_draft_submission_in_postgres(draft, key)
            if postgres_ok:
                load_postgres_metadata.clear()
            st.success(f"Draft saved: {key}")
            if postgres_ok:
                st.success(postgres_message)
            else:
                st.warning(
                    "The draft was saved to object storage, but the Postgres workflow "
                    f"audit was not written: {postgres_message}"
                )
        except PermissionError as exc:
            st.error(str(exc))


with review_tab:
    st.subheader("Human review queue")
    st.write(
        "Draft preference changes stay separate from the published Gold preference card "
        "until a theatre reviewer records a decision. This Version 2 workflow records "
        "the decision only; publishing approved changes remains a separate controlled step."
    )

    review_disabled_reason = review_block_reason(current_user, ENABLE_DRAFT_REVIEWS)

    if current_user:
        st.caption(
            f"Signed in as {current_user.display_name} ({current_user.email}); "
            f"roles: {', '.join(current_user.roles) if current_user.roles else 'viewer'}"
        )

    if review_disabled_reason:
        st.info(
            f"{review_disabled_reason} The queue can still be inspected, but approve/reject "
            "actions require a named authorised reviewer."
        )

    storage = get_storage_client()
    pending_drafts = load_pending_drafts(storage, DRAFT_PREFIX)
    review_keys = storage.list_objects(REVIEW_DECISION_PREFIX)

    review_col_1, review_col_2 = st.columns(2)
    review_col_1.metric("Pending drafts", len(pending_drafts))
    review_col_2.metric("Review decisions", len(review_keys))

    if not pending_drafts:
        st.warning("No pending drafts found in object storage.")
    else:
        draft_options = {draft_display_name(draft): draft for draft in pending_drafts}
        selected_draft_label = st.selectbox("Select draft to review", list(draft_options))
        selected_draft = draft_options[selected_draft_label]

        context_columns = [
            ("Draft type", selected_draft.get("draft_type")),
            ("Status", selected_draft.get("status")),
            ("Surgeon", selected_draft.get("surgeon_name")),
            ("Procedure", selected_draft.get("procedure")),
            ("Created", selected_draft.get("created_at")),
        ]
        render_summary_tiles(context_columns)

        changes = draft_change_rows(selected_draft)
        st.subheader("Proposed changes")
        if changes:
            st.dataframe(pd.DataFrame(changes), width="stretch", hide_index=True)
        else:
            st.info("This draft does not contain field-level changes.")

        with st.expander("Draft object details"):
            st.write(selected_draft.get("_object_key"))

        with st.form("draft_review_decision_form"):
            reviewer = st.text_input(
                "Reviewer",
                value=current_user.display_name if current_user else "",
                disabled=True,
            )
            decision = st.selectbox("Decision", ["approved", "needs_changes", "rejected"])
            comments = st.text_area("Review comments")
            review_submitted = st.form_submit_button(
                "Record Review Decision",
                disabled=review_disabled_reason is not None,
            )

        if review_submitted:
            try:
                review = build_review_decision(
                    draft=selected_draft,
                    reviewer=current_user.display_name if current_user else reviewer,
                    decision=decision,
                    comments=comments,
                    reviewer_email=current_user.email if current_user else "",
                    reviewer_roles=current_user.roles if current_user else (),
                )
                review_key = save_review_payload(storage, review)
                updated_draft = save_reviewed_draft(storage, selected_draft, review, review_key)
                postgres_ok, postgres_message = record_review_in_postgres(review, review_key)
                if postgres_ok:
                    load_postgres_metadata.clear()

                st.success(f"Review decision archived: {review_key}")
                st.success(f"Draft moved to status: {updated_draft['status']}")
                if postgres_ok:
                    st.success(postgres_message)
                else:
                    st.warning(
                        "The review was saved to object storage, but the Postgres workflow "
                        f"audit was not written: {postgres_message}"
                    )
            except ValueError as exc:
                st.error(str(exc))


with publish_tab:
    st.subheader("Controlled publish queue")
    st.write(
        "Approved drafts wait here until an authorised publisher creates a new "
        "published Gold preference-card version. This keeps review separate from "
        "release and gives the platform a rollback/audit foundation."
    )

    publish_disabled_reason = publish_block_reason(current_user, ENABLE_DRAFT_PUBLISHING)

    if current_user:
        st.caption(
            f"Signed in as {current_user.display_name} ({current_user.email}); "
            f"roles: {', '.join(current_user.roles) if current_user.roles else 'viewer'}"
        )

    if publish_disabled_reason:
        st.info(
            f"{publish_disabled_reason} Approved drafts can still be inspected, "
            "but publishing requires an authorised admin."
        )

    storage = get_storage_client()
    publishable_drafts = load_publishable_drafts(storage, DRAFT_PREFIX)
    publish_event_keys = storage.list_objects(PUBLISH_EVENT_PREFIX)

    publish_col_1, publish_col_2 = st.columns(2)
    publish_col_1.metric("Approved drafts awaiting publish", len(publishable_drafts))
    publish_col_2.metric("Publish events", len(publish_event_keys))

    if not publishable_drafts:
        st.warning("No approved drafts are waiting to be published.")
    else:
        draft_options = {draft_display_name(draft): draft for draft in publishable_drafts}
        selected_publish_label = st.selectbox(
            "Select approved draft to publish",
            list(draft_options),
            key="publish_draft",
        )
        selected_publish_draft = draft_options[selected_publish_label]

        render_summary_tiles(
            [
                ("Draft type", selected_publish_draft.get("draft_type")),
                ("Status", selected_publish_draft.get("status")),
                ("Review decision", selected_publish_draft.get("review_decision")),
                ("Surgeon", selected_publish_draft.get("surgeon_name")),
                ("Procedure", selected_publish_draft.get("procedure")),
                ("Reviewed", selected_publish_draft.get("reviewed_at")),
            ]
        )

        changes = draft_change_rows(selected_publish_draft)
        st.subheader("Approved changes")
        if changes:
            st.dataframe(pd.DataFrame(changes), width="stretch", hide_index=True)
        else:
            st.info("This approved draft creates a new card or has no field-level diff.")

        with st.expander("Publish source details"):
            st.write(selected_publish_draft.get("_object_key"))
            st.write(selected_publish_draft.get("review_object_key"))

        with st.form("publish_approved_draft_form"):
            publisher = st.text_input(
                "Publisher",
                value=current_user.display_name if current_user else "",
                disabled=True,
            )
            acknowledge = st.checkbox(
                "I confirm this approved draft should become the published Gold preference card."
            )
            publish_submitted = st.form_submit_button(
                "Publish Approved Draft",
                disabled=publish_disabled_reason is not None,
            )

        if publish_submitted:
            if not acknowledge:
                st.error("Confirm the publish action before publishing this approved draft.")
            else:
                try:
                    published_at = datetime.now(UTC).isoformat()
                    publisher_name = current_user.display_name if current_user else publisher
                    published_gold = apply_approved_draft_to_gold(
                        current_gold=current_df,
                        draft=selected_publish_draft,
                        publisher=publisher_name,
                        editable_fields=EDITABLE_FIELDS,
                        published_at=published_at,
                    )
                    draft_context_event = build_publish_event(
                        draft=selected_publish_draft,
                        publisher=publisher_name,
                        publisher_email=current_user.email if current_user else "",
                        publisher_roles=current_user.roles if current_user else (),
                        published_gold_key="",
                        latest_gold_key=GOLD_OPERATIONAL_KEY,
                        row_count=len(published_gold),
                        published_at=published_at,
                    )
                    published_gold_key = save_published_gold(
                        storage=storage,
                        published_gold=published_gold,
                        publish_id=draft_context_event["publish_id"],
                        latest_gold_key=GOLD_OPERATIONAL_KEY,
                    )
                    publish_event = {
                        **draft_context_event,
                        "published_gold_key": published_gold_key,
                    }
                    publish_event_key = save_publish_event(storage, publish_event)
                    updated_draft = mark_draft_published(
                        storage=storage,
                        draft=selected_publish_draft,
                        publish_event=publish_event,
                        publish_event_key=publish_event_key,
                    )
                    postgres_ok, postgres_message = record_publish_in_postgres(
                        publish_event,
                        publish_event_key,
                    )
                    load_gold_data.clear()
                    load_postgres_metadata.clear()

                    st.success(f"Published Gold version: {published_gold_key}")
                    st.success(f"Publish event archived: {publish_event_key}")
                    st.success(f"Draft moved to status: {updated_draft['status']}")
                    if postgres_ok:
                        st.success(postgres_message)
                    else:
                        st.warning(
                            "The publish was saved to object storage, but the Postgres workflow "
                            f"audit was not written: {postgres_message}"
                        )
                except ValueError as exc:
                    st.error(str(exc))


with access_tab:
    st.subheader("Access management")
    st.write(
        "Manage who can create drafts, review changes, or publish approved preference cards. "
        "This is an admin-only control surface backed by the Postgres workflow audit."
    )

    access_disabled_reason = user_management_block_reason(current_user)
    if current_user:
        st.caption(
            f"Signed in as {current_user.display_name} ({current_user.email}); "
            f"roles: {', '.join(current_user.roles) if current_user.roles else 'viewer'}; "
            f"status: {current_user.status}"
        )

    if access_disabled_reason:
        st.info(f"{access_disabled_reason} Existing users can still be viewed in Metadata.")
    else:
        postgres_settings = load_settings().postgres
        if not postgres_settings:
            st.warning("Postgres user registry is not configured for this deployment.")
        else:
            postgres_metadata = load_postgres_metadata()
            app_users_df = postgres_metadata.get("app_users", pd.DataFrame())
            if app_users_df.empty:
                st.info(
                    "No app users have been recorded yet. You can pre-register the first "
                    "approved user below."
                )
            else:
                st.dataframe(app_users_df, width="stretch", hide_index=True)

            user_options = []
            if not app_users_df.empty and "user_email" in app_users_df.columns:
                user_options = app_users_df["user_email"].dropna().astype(str).tolist()
            user_options = ["Invite or type new user", *user_options]

            selected_access_user = st.selectbox(
                "User to update",
                user_options,
                key="access_user",
            )
            selected_user_row = None
            if selected_access_user != "Invite or type new user" and not app_users_df.empty:
                matches = app_users_df[app_users_df["user_email"].astype(str) == selected_access_user]
                if not matches.empty:
                    selected_user_row = matches.iloc[0].to_dict()

            with st.form("access_management_form"):
                target_email = st.text_input(
                    "User email",
                    value="" if selected_user_row is None else str(selected_user_row.get("user_email") or ""),
                )
                target_display_name = st.text_input(
                    "Display name",
                    value="" if selected_user_row is None else str(selected_user_row.get("display_name") or ""),
                )
                current_status = (
                    str(selected_user_row.get("status") or PENDING_ACCESS_STATUS)
                    if selected_user_row
                    else PENDING_ACCESS_STATUS
                )
                target_status = st.selectbox(
                    "Status",
                    [PENDING_ACCESS_STATUS, ACTIVE_STATUS, SUSPENDED_STATUS],
                    index=[PENDING_ACCESS_STATUS, ACTIVE_STATUS, SUSPENDED_STATUS].index(current_status)
                    if current_status in {PENDING_ACCESS_STATUS, ACTIVE_STATUS, SUSPENDED_STATUS}
                    else 0,
                )
                current_roles = (
                    normalise_role_values(selected_user_row.get("roles"))
                    if selected_user_row
                    else [AUTHENTICATED_ROLE, EDITOR_ROLE]
                )
                target_roles = st.multiselect(
                    "Roles",
                    [AUTHENTICATED_ROLE, EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE],
                    default=[
                        role
                        for role in current_roles
                        if role in {AUTHENTICATED_ROLE, EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE}
                    ],
                )
                save_access = st.form_submit_button("Save Access Change")

            if save_access:
                updated_user, error_message = update_user_access(
                    settings=postgres_settings,
                    target_email=target_email,
                    display_name=target_display_name or target_email,
                    roles=target_roles,
                    status=target_status,
                    actor=current_user,
                )
                if error_message:
                    st.error(error_message)
                else:
                    load_postgres_metadata.clear()
                    st.success(f"Access updated for {updated_user['user_email']}.")
                    st.caption(
                        f"Status: {updated_user['status']}; "
                        f"roles: {', '.join(updated_user['roles'])}"
                    )


with metadata_tab:
    st.metric("Gold rows", len(df))
    st.metric("Current cards", len(current_df))
    st.metric("Surgeons", current_df["surgeon_name"].nunique())
    st.metric("Procedures", current_df["procedure"].nunique() if "procedure" in current_df else 0)
    storage = get_storage_client()
    draft_rows = load_drafts(storage, DRAFT_PREFIX)
    draft_keys = [draft["_object_key"] for draft in draft_rows]
    review_keys = storage.list_objects(REVIEW_DECISION_PREFIX)
    pending_count = sum(1 for draft in draft_rows if draft.get("status") == "pending_review")
    st.metric("Drafts pending", pending_count)
    st.metric("Review decisions", len(review_keys))
    if draft_rows:
        draft_summary = pd.DataFrame(
            [
                {
                    "draft_id": draft.get("draft_id"),
                    "status": draft.get("status"),
                    "review_decision": draft.get("review_decision"),
                    "surgeon_name": draft.get("surgeon_name"),
                    "procedure": draft.get("procedure"),
                    "created_at": draft.get("created_at"),
                    "reviewed_at": draft.get("reviewed_at"),
                    "draft_key": draft.get("_object_key"),
                }
                for draft in draft_rows[:50]
            ]
        )
        st.dataframe(draft_summary, width="stretch", hide_index=True)
    if review_keys:
        st.dataframe(pd.DataFrame({"review_decision_key": review_keys[-25:]}), width="stretch")

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
        ("Workflow reviews", "workflow_reviews"),
        ("Workflow audit events", "workflow_audit"),
        ("App users", "app_users"),
    ]
    for label, key in postgres_sections:
        if key in postgres_metadata:
            with st.expander(label, expanded=key in {"runs", "object_summary"}):
                st.dataframe(postgres_metadata[key], width="stretch", hide_index=True)

    st.subheader("Clinical reference metadata")
    st.dataframe(load_reference_metadata(), width="stretch", hide_index=True)


render_project_footer()
