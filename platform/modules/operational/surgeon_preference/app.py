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
from application_services.preference_drafts import submit_preference_draft
from application_services.preference_publishing import publish_preference_draft
from application_services.preference_queries import (
    load_preference_cards,
    search_preference_cards,
)
from application_services.preference_rollbacks import rollback_preference_card
from application_services.preference_reviews import submit_preference_review
from config.settings import load_settings
from domain.clinical_reference_service import ClinicalReferenceService
from streamlit_services.access_control import (
    ACTIVE_STATUS,
    ADMIN_ROLE,
    AUTHENTICATED_ROLE,
    DEFAULT_ORGANISATION_ID,
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
from streamlit_services.auth_links import (
    auth_endpoints_available,
    build_login_links,
    build_logout_link,
)
from streamlit_services.draft_review_service import (
    REVIEW_DECISION_PREFIX,
    draft_change_rows,
    draft_display_name,
    load_drafts,
    load_pending_drafts,
)
from streamlit_services.demo_data import build_synthetic_demo_cards, filter_demo_cards
from streamlit_services.publishing_service import (
    PUBLISH_EVENT_PREFIX,
    load_publishable_drafts,
)
from streamlit_services.preference_card_repository import (
    PreferenceCardRepository,
    current_card_rows_to_dataframe,
)
from streamlit_services.product_readiness_service import build_product_readiness_summary
from streamlit_services.streamlit_service import get_storage_client
from streamlit_services.tenant_access import membership_is_verified
from streamlit_services.user_registry_service import (
    choose_active_membership,
    create_organisation_for_user,
    list_access_requests,
    list_user_memberships,
    resolve_access_request,
    submit_access_request,
    sync_user_with_registry,
    update_user_access,
)
from streamlit_services.tenant_storage import tenant_latest_gold_key, tenant_object_prefix


GOLD_OPERATIONAL_KEY = "gold/operational/latest/gold_operational_preference_cards.csv"
RUN_MANIFEST_PREFIX = "bronze/manifests"
DRAFT_PREFIX = "gold/operational/drafts"
GITHUB_PROFILE_URL = os.getenv("APP_GITHUB_PROFILE_URL", "https://github.com/JoshuaOforisurg")
CONTACT_EMAIL = os.getenv("APP_CONTACT_EMAIL", "info@surgeonpreference.com").strip()
AUTH_PROVIDER_CONFIG = os.getenv("APP_AUTH_PROVIDERS", "aad")
SHOW_AUTH_LINKS = os.getenv("APP_SHOW_AUTH_LINKS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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

    .sp-account-bar {
        align-items: center;
        background: var(--sp-white);
        border: 1px solid #c8dff3;
        color: var(--sp-muted);
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        justify-content: space-between;
        line-height: 1.45;
        margin: 0.65rem 0 1rem;
        padding: 0.75rem 0.9rem;
    }

    .sp-account-bar strong {
        color: var(--sp-dark-blue);
    }

    .sp-auth-actions {
        align-items: center;
        display: inline-flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }

    .sp-auth-link {
        background: var(--sp-blue);
        color: var(--sp-white) !important;
        font-weight: 800;
        padding: 0.42rem 0.7rem;
        text-decoration: none !important;
    }

    .sp-auth-link:hover {
        background: var(--sp-dark-blue);
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


def render_account_bar(user, message: str | None = None, auth_available: bool = True) -> None:
    if not SHOW_AUTH_LINKS:
        return

    if user:
        roles = ", ".join(user.roles) if user.roles else "viewer"
        logout_href = build_logout_link("/")
        content = (
            f"<span><strong>Signed in:</strong> {escape(user.display_name)} "
            f"({escape(user.email)}) - roles: {escape(roles)} - status: {escape(user.status)}</span>"
            f'<span class="sp-auth-actions"><a class="sp-auth-link" href="{escape(logout_href)}" '
            'target="_self">Sign out</a></span>'
        )
    else:
        login_links = build_login_links(AUTH_PROVIDER_CONFIG, "/?view=platform") if auth_available else []
        actions = "".join(
            f'<a class="sp-auth-link" href="{escape(link["href"])}" target="_self">'
            f'Sign in with {escape(link["label"])}</a>'
            for link in login_links
        )
        content = (
            f"<span>{escape(message or 'Viewing public demo data. Sign in to request access.')}</span>"
            f'<span class="sp-auth-actions">{actions}</span>'
        )

    st.markdown(f'<div class="sp-account-bar">{content}</div>', unsafe_allow_html=True)

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


@st.cache_data(ttl=60)
def load_operational_postgres_data(organisation_id: str) -> pd.DataFrame | None:
    settings = load_settings().postgres
    if not settings:
        return None

    try:
        repository = PreferenceCardRepository(settings)
        rows = repository.list_current_cards(organisation_id=organisation_id)
    except psycopg2.Error:
        return None

    if not rows:
        return None
    return current_card_rows_to_dataframe(rows)


def load_current_preference_data(organisation_id: str) -> dict:
    return load_preference_cards(
        user=current_user,
        organisation_id=organisation_id,
        settings=load_settings().postgres,
        gold_loader=load_gold_data,
        postgres_loader=load_operational_postgres_data,
        allow_gold_fallback=False,
    )


@st.cache_data(ttl=60)
def load_preference_card_history(
    organisation_id: str,
    surgeon_name: str,
    procedure_name: str,
) -> pd.DataFrame:
    settings = load_settings().postgres
    if not settings:
        return pd.DataFrame()

    try:
        rows = PreferenceCardRepository(settings).list_card_history(
            organisation_id=organisation_id,
            surgeon_name=surgeon_name,
            procedure_name=procedure_name,
        )
    except psycopg2.Error:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def save_draft(payload: dict, submitter):
    block_reason = submission_block_reason(submitter, ENABLE_DRAFT_SUBMISSIONS)
    if block_reason:
        raise PermissionError(block_reason)
    return submit_preference_draft(
        payload,
        submitter,
        settings=load_settings().postgres,
        storage_factory=get_storage_client,
    )


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


@st.cache_data(ttl=60)
def load_latest_run_manifest() -> dict | None:
    try:
        storage = get_storage_client()
        manifest_keys = sorted(storage.list_objects(RUN_MANIFEST_PREFIX), reverse=True)
        if not manifest_keys:
            return None
        return json.loads(storage.get_text(manifest_keys[0]))
    except Exception:
        return None


def _postgres_frame(settings, query: str, params: tuple = ()) -> pd.DataFrame:
    with psycopg2.connect(settings.psycopg2_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET statement_timeout = '5s'")
            cur.execute(query, params)
            return pd.DataFrame(cur.fetchall())


def sync_published_gold_to_operational_postgres(
    published_gold: pd.DataFrame,
    source_gold_key: str,
    imported_by: str,
) -> tuple[bool, str]:
    settings = load_settings().postgres
    if not settings:
        return False, "Postgres settings are not configured for this deployment."

    try:
        summary = PreferenceCardRepository(settings).import_gold_rows(
            rows=published_gold.to_dict("records"),
            source_gold_key=source_gold_key,
            imported_by=imported_by,
        )
    except (psycopg2.Error, ValueError) as exc:
        return False, str(exc).strip()

    return True, summary.message


@st.cache_data(ttl=30)
def load_postgres_metadata(organisation_id: str) -> dict:
    settings = load_settings().postgres
    repository = BronzeCatalogRepository(settings)
    health = repository.healthcheck(initialise=False)
    if not settings or not health.get("reachable"):
        return {"health": health}

    # Pipeline/catalog tables are currently global (no organisation_id). Keep
    # them out of tenant-facing metadata until their ownership is modelled.
    metadata = {"health": health}

    if health.get("valid"):
        metadata["workflow_reviews"] = _postgres_frame(
            settings,
            """
            SELECT
                review_id,
                organisation_id,
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
            WHERE organisation_id = %s
            ORDER BY reviewed_at DESC
            LIMIT 50
            """,
            (organisation_id,),
        )
        metadata["workflow_audit"] = _postgres_frame(
            settings,
            """
            SELECT
                event_type,
                organisation_id,
                actor_email,
                actor_name,
                actor_roles,
                entity_type,
                entity_id,
                created_at
            FROM app_workflow.audit_events
            WHERE organisation_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (organisation_id,),
        )
        metadata["app_users"] = _postgres_frame(
            settings,
            """
            SELECT
                user_email,
                display_name,
                memberships.roles,
                memberships.status,
                memberships.organisation_id,
                users.auth_provider,
                users.last_seen_at,
                memberships.updated_at
            FROM app_workflow.app_users users
            JOIN app_workflow.organisation_memberships memberships
              ON memberships.user_email = users.user_email
            WHERE memberships.organisation_id = %s
            ORDER BY memberships.updated_at DESC
            LIMIT 100
            """,
            (organisation_id,),
        )
        metadata["organisations"] = _postgres_frame(
            settings,
            """
            SELECT
                organisation_id,
                organisation_name,
                status,
                created_at,
                updated_at
            FROM app_workflow.organisations
            WHERE organisation_id = %s
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            (organisation_id,),
        )
        metadata["organisation_memberships"] = _postgres_frame(
            settings,
            """
            SELECT
                organisation_id,
                user_email,
                roles,
                status,
                created_at,
                updated_at
            FROM app_workflow.organisation_memberships
            WHERE organisation_id = %s
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            (organisation_id,),
        )
        metadata["access_requests"] = _postgres_frame(
            settings,
            """
            SELECT
                access_request_id,
                organisation_id,
                user_email,
                display_name,
                requested_roles,
                requested_organisation_name,
                reason,
                status,
                reviewed_by_email,
                reviewed_at,
                created_at,
                updated_at
            FROM app_workflow.access_requests
            WHERE organisation_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (organisation_id,),
        )
        metadata["operational_current_cards"] = _postgres_frame(
            settings,
            """
            SELECT
                cards.organisation_id,
                cards.surgeon_name,
                cards.procedure_name,
                cards.specialty,
                cards.subspecialty,
                cards.current_version_number,
                cards.status,
                versions.change_type,
                versions.source_gold_key,
                versions.published_by,
                versions.published_at,
                cards.updated_at
            FROM app_workflow.preference_cards cards
            JOIN app_workflow.preference_card_versions versions
                ON cards.current_version_id = versions.version_id
            WHERE cards.organisation_id = %s
            ORDER BY cards.updated_at DESC, cards.surgeon_name, cards.procedure_name
            LIMIT 100
            """,
            (organisation_id,),
        )
        metadata["operational_version_summary"] = _postgres_frame(
            settings,
            """
            SELECT
                cards.organisation_id,
                COALESCE(versions.change_type, 'unknown') AS change_type,
                versions.is_current,
                COUNT(*) AS version_count,
                MAX(versions.created_at) AS latest_version_created_at
            FROM app_workflow.preference_card_versions versions
            JOIN app_workflow.preference_cards cards
                ON cards.card_id = versions.card_id
            WHERE cards.organisation_id = %s
            GROUP BY cards.organisation_id, COALESCE(versions.change_type, 'unknown'), versions.is_current
            ORDER BY latest_version_created_at DESC
            """,
            (organisation_id,),
        )
        metadata["operational_recent_versions"] = _postgres_frame(
            settings,
            """
            SELECT
                cards.organisation_id,
                cards.surgeon_name,
                cards.procedure_name,
                versions.version_number,
                versions.version_label,
                versions.is_current,
                versions.change_type,
                versions.source_version_id,
                versions.change_reason,
                versions.published_by,
                versions.published_at,
                versions.created_at
            FROM app_workflow.preference_card_versions versions
            JOIN app_workflow.preference_cards cards
                ON cards.card_id = versions.card_id
            WHERE cards.organisation_id = %s
            ORDER BY versions.created_at DESC, versions.version_number DESC
            LIMIT 100
            """,
            (organisation_id,),
        )

    return metadata


def detect_auth_provider(headers) -> str:
    for key in headers or {}:
        if str(key).lower().startswith("x-ms-client-principal"):
            return "azure_container_apps"
    return "local_env"


identity_user = load_current_user(os.environ, st.context.headers)
postgres_settings = load_settings().postgres
membership_rows, membership_error = list_user_memberships(
    postgres_settings,
    identity_user.email if identity_user else None,
)
active_membership_rows = [
    row
    for row in membership_rows
    if str(row.get("status") or "").lower() == ACTIVE_STATUS
    and str(row.get("organisation_status") or "").lower() == ACTIVE_STATUS
]
configured_organisation_id = (
    os.getenv("APP_ORGANISATION_ID", DEFAULT_ORGANISATION_ID).strip()
    or DEFAULT_ORGANISATION_ID
)
selected_membership = choose_active_membership(
    active_membership_rows,
    st.session_state.get("workspace_selection"),
    configured_organisation_id,
)

if identity_user and active_membership_rows:
    membership_options = {
        str(row["organisation_id"]): row for row in active_membership_rows
    }
    if len(membership_options) > 1:
        selected_id = str(selected_membership["organisation_id"])
        if st.session_state.get("workspace_selection") not in membership_options:
            st.session_state["workspace_selection"] = selected_id
        selected_id = st.selectbox(
            "Workspace",
            list(membership_options),
            format_func=lambda value: (
                f"{membership_options[value]['organisation_name']} ({value})"
            ),
            key="workspace_selection",
        )
        selected_membership = membership_options[selected_id]

current_user = None
user_registry_warning = membership_error
if identity_user and not membership_error:
    requested_organisation_id = (
        str(selected_membership["organisation_id"])
        if selected_membership
        else configured_organisation_id
    )
    current_user, user_registry_warning = sync_user_with_registry(
        identity_user,
        postgres_settings,
        detect_auth_provider(st.context.headers),
        organisation_id=requested_organisation_id,
    )

membership_verified = membership_is_verified(current_user, selected_membership)
active_organisation_id = (
    str(selected_membership["organisation_id"])
    if membership_verified and selected_membership
    else configured_organisation_id
)
active_organisation_name = (
    str(selected_membership["organisation_name"])
    if membership_verified and selected_membership
    else os.getenv("APP_ORGANISATION_NAME", "Surgeon Preference Demo").strip()
    or "Surgeon Preference Demo"
)
draft_submission_disabled_reason = submission_block_reason(current_user, ENABLE_DRAFT_SUBMISSIONS)

if user_registry_warning:
    st.warning(user_registry_warning)

platform_view = str(st.query_params.get("view", "demo")).strip().lower() == "platform"
azure_auth_available = auth_endpoints_available(
    st.context.headers,
    os.getenv("APP_AUTH_ENDPOINTS_ENABLED"),
)


def render_demo_items(label: str, items, show_quantity: bool = False) -> None:
    st.markdown(f"**{label}**")
    lines = []
    for item in items or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            quantity = item.get("quantity")
            suffix = f" (quantity: {quantity})" if show_quantity and quantity else ""
        else:
            name = str(item or "").strip()
            suffix = ""
        if name:
            lines.append(f"- {escape(name)}{escape(suffix)}")

    st.markdown("\n".join(lines) if lines else "Not specified")


if not platform_view:
    st.title("Surgeon Preference")
    st.write(
        "A workspace for theatre teams to find current surgeon-specific setup, "
        "propose preference updates, and review changes before they are published. "
        "This preview uses synthetic data only; no patient or hospital data is used."
    )
    if st.button("Enter the multi-hospital platform", type="primary"):
        st.query_params["view"] = "platform"
        st.rerun()

    st.divider()
    st.subheader("Explore a sample preference card")

    @st.cache_data(show_spinner=False)
    def load_demo_cards():
        return build_synthetic_demo_cards()

    demo_df = load_demo_cards()
    demo_query = st.text_input(
        "Search by surgeon, specialty, procedure or alias",
        placeholder="For example, Mr Patel, hip, THR or TKA",
        key="demo_card_search",
    )
    demo_search_signature = demo_query.strip().casefold()
    if st.session_state.get("demo_search_signature") != demo_search_signature:
        st.session_state.pop("demo_card_selection", None)
        st.session_state["demo_search_signature"] = demo_search_signature

    matching_demo_cards = filter_demo_cards(demo_df, demo_query).reset_index(drop=True)

    if matching_demo_cards.empty:
        st.info("No sample preference cards match that search.")
    else:
        selected_demo_index = st.selectbox(
            "Preference card",
            options=range(len(matching_demo_cards)),
            format_func=lambda index: (
                f"{matching_demo_cards.iloc[index]['surgeon_name']}  ·  "
                f"{matching_demo_cards.iloc[index]['procedure']}"
            ),
            key="demo_card_selection",
        )
        demo_card = matching_demo_cards.iloc[selected_demo_index]
        st.markdown(f"### {demo_card['surgeon_name']}")
        st.caption(f"{demo_card['specialty']}  ·  {demo_card['procedure']}")
        st.caption("Illustrative synthetic card · confirm requirements against local policy")

        count_col_1, count_col_2, count_col_3 = st.columns(3)
        count_col_1.metric("Instrument items", len(demo_card["instruments"]))
        count_col_2.metric("Consumables", len(demo_card["consumables"]))
        count_col_3.metric("Disposables", len(demo_card["disposables"]))

        if demo_card["instrument_system"] or demo_card["implant_system"]:
            system_col_1, system_col_2 = st.columns(2)
            if demo_card["instrument_system"]:
                system_col_1.write(f"**Instrument system:** {demo_card['instrument_system']}")
            if demo_card["implant_system"]:
                system_col_2.write(f"**Implant system:** {demo_card['implant_system']}")

        setup_col, supply_col = st.columns(2)
        with setup_col:
            st.subheader("Theatre set-up")
            render_demo_items("Instruments", demo_card["instruments"], show_quantity=True)
            render_demo_items("Equipment", demo_card["equipment"])
            render_demo_items("Draping", demo_card["draping"])
        with supply_col:
            st.subheader("Consumables and disposables")
            render_demo_items("Consumables", demo_card["consumables"])
            render_demo_items("Disposables", demo_card["disposables"])

        st.divider()
        closure_col_1, closure_col_2, closure_col_3 = st.columns(3)
        with closure_col_1:
            render_demo_items("Implants", demo_card["implants"])
        with closure_col_2:
            render_demo_items("Sutures", demo_card["sutures"])
        with closure_col_3:
            render_demo_items("Dressings", demo_card["dressings"])

        st.subheader("Preparation and instructions")
        prep_col_1, prep_col_2, prep_col_3 = st.columns(3)
        prep_col_1.write(f"**Positioning**\n\n{demo_card['positioning'] or 'Not specified'}")
        prep_col_2.write(f"**Anaesthetic**\n\n{demo_card['anaesthetic'] or 'Not specified'}")
        prep_col_3.write(f"**Skin preparation**\n\n{demo_card['skin_prep'] or 'Not specified'}")
        render_demo_items("Special instructions", demo_card["special_instructions"])

        st.caption("Synthetic preview only. No quantities are inferred for consumables or disposables.")

    render_project_footer()
    st.stop()

if not membership_verified:

    st.title("Secure platform")
    st.write(
        "Sign in to request access to an organisation workspace. Access is granted "
        "only through an approved organisation membership."
    )
    if st.button("Back to synthetic demo"):
        st.query_params["view"] = "demo"
        st.rerun()
    render_account_bar(
        current_user,
        "Continue with your organisation identity provider to request workspace access.",
        auth_available=azure_auth_available,
    )
    if not identity_user and not azure_auth_available:
        st.info(
            "Microsoft sign-in is handled by Azure Container Apps Authentication and is "
            "available on the hosted platform. This local demo has no identity provider, "
            "so it cannot authenticate an account."
        )

    if identity_user and current_user and postgres_settings and not active_membership_rows:
        st.subheader("Create an organisation workspace")
        st.write(
            "Register your organisation. You will become its first workspace administrator; "
            "this does not grant access to any other organisation."
        )
        with st.form("create_organisation_form"):
            new_organisation_name = st.text_input(
                "Organisation name",
                placeholder="Example: Northside Teaching Hospital",
                max_chars=120,
            )
            create_organisation_submitted = st.form_submit_button(
                "Create workspace", type="primary"
            )
        if create_organisation_submitted:
            organisation, error_message = create_organisation_for_user(
                settings=postgres_settings,
                user=identity_user,
                organisation_name=new_organisation_name,
            )
            if error_message:
                st.error(error_message)
            elif organisation:
                st.session_state["workspace_selection"] = organisation["organisation_id"]
                st.success(
                    f"Workspace created: {organisation['organisation_name']} "
                    f"({organisation['organisation_id']}). You are its first administrator."
                )
                st.rerun()

        st.subheader("Request to join an existing workspace")
        st.caption("Ask the workspace administrator for its workspace ID before requesting access.")
        with st.form("join_organisation_form"):
            join_organisation_id = st.text_input(
                "Workspace ID", placeholder="Example: northside-teaching-hospital"
            )
            join_roles = st.multiselect(
                "Requested access",
                [EDITOR_ROLE, REVIEWER_ROLE],
                default=[EDITOR_ROLE],
            )
            join_reason = st.text_area(
                "Reason",
                placeholder="Describe your role in maintaining theatre preference cards.",
            )
            join_submitted = st.form_submit_button("Request to join")
        if join_submitted:
            access_request, error_message = submit_access_request(
                settings=postgres_settings,
                user=identity_user,
                requested_roles=join_roles,
                requested_organisation_name="",
                reason=join_reason,
                organisation_id=join_organisation_id,
            )
            if error_message:
                st.error(error_message)
            else:
                st.success(
                    "Join request submitted. Access stays pending until an administrator "
                    "of that workspace approves it."
                )
                st.caption(f"Request ID: {access_request['access_request_id']}")
    elif identity_user and membership_error:
        st.info("Organisation access could not be verified. Tenant data is unavailable.")

    render_project_footer()
    st.stop()


# ----------------------------
# LOAD DATA
# ----------------------------
preference_data = load_current_preference_data(active_organisation_id)
df = preference_data["data"]

if df is None or df.empty:
    df = pd.DataFrame(columns=["surgeon_name", "procedure"])
    preference_data["data"] = df
    preference_data["source_layer"] = "Empty workspace"
    preference_data["fallback_used"] = False
    preference_data["message"] = (
        "This workspace has no published preference cards yet. Use Create draft "
        "to start the organisation's catalogue."
    )
    st.info(preference_data["message"])

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
    <div class="sp-kicker">Version 2 review workflow</div>
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
status_col_4.metric("Data source", preference_data["source_layer"])
if preference_data["fallback_used"]:
    st.info(preference_data["message"])
else:
    st.caption(preference_data["message"])

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
st.caption(f"Workspace: {active_organisation_name} ({active_organisation_id})")
render_account_bar(current_user)


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

    if current_df.empty:
        st.info(
            "This new workspace is ready. Add its first preference-card draft, then "
            "assign a reviewer and publisher through workspace access management."
        )
        return

    render_product_readiness()

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
    if preview_columns and not current_df.empty:
        st.dataframe(
            current_df[preview_columns].sort_values(preview_columns[0]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No preference cards have been published in this workspace yet.")


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


def render_product_readiness() -> None:
    st.subheader("Product readiness")
    storage = get_storage_client()
    drafts = load_drafts(storage, DRAFT_PREFIX, organisation_id=active_organisation_id)
    readiness = build_product_readiness_summary(
        current_gold=current_df,
        drafts=drafts,
        metadata=load_postgres_metadata(active_organisation_id),
        latest_manifest=None,
    )
    status_labels = {
        "ready": "Ready",
        "needs_attention": "Needs attention",
        "blocked": "Blocked",
        "unknown": "Unknown",
    }
    render_summary_tiles(
        [
            ("Overall status", status_labels.get(readiness["overall_status"], readiness["overall_status"])),
            ("Draft records", len(drafts)),
            ("Current cards", len(current_df)),
            ("Signals checked", len(readiness["signals"])),
        ]
    )
    st.dataframe(
        pd.DataFrame(readiness["signals"]),
        width="stretch",
        hide_index=True,
    )


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


def render_card_history(surgeon_name: str, procedure_name: str | None) -> None:
    if not procedure_name or procedure_name == "All procedures":
        return
    history = load_preference_card_history(
        active_organisation_id,
        surgeon_name,
        procedure_name,
    )
    if history.empty:
        return

    st.subheader("Version history")
    columns = [
        column
        for column in [
            "version_label",
            "version_number",
            "is_current",
            "change_type",
            "published_by",
            "published_at",
            "change_reason",
            "source_gold_key",
        ]
        if column in history.columns
    ]
    st.dataframe(
        history[columns],
        width="stretch",
        hide_index=True,
    )

    rollback_block_reason = publish_block_reason(current_user, ENABLE_DRAFT_PUBLISHING)
    if rollback_block_reason or preference_data["source_layer"] != "Postgres":
        return

    rollback_options_df = history[history["is_current"] != True].copy()
    if rollback_options_df.empty:
        return

    with st.expander("Revert to a previous version"):
        st.warning(
            "Reverting creates a new current version copied from the selected historical "
            "version. It does not delete or overwrite history."
        )
        option_labels = {}
        for _, row in rollback_options_df.iterrows():
            label = (
                f"{row.get('version_label') or 'version'} "
                f"- published {row.get('published_at') or 'unknown date'} "
                f"by {row.get('published_by') or 'unknown'}"
            )
            option_labels[label] = row.to_dict()

        selected_label = st.selectbox(
            "Historical version to copy",
            list(option_labels),
            key=f"rollback_version_{surgeon_name}_{procedure_name}",
        )
        selected_version = option_labels[selected_label]
        reason = st.text_area(
            "Rollback reason",
            key=f"rollback_reason_{surgeon_name}_{procedure_name}",
            placeholder="Explain why this preference card should be reverted.",
        )
        confirm = st.checkbox(
            "I understand this will create a new current version copied from the selected historical version.",
            key=f"rollback_confirm_{surgeon_name}_{procedure_name}",
        )
        rollback_submitted = st.button(
            "Create Rollback Version",
            disabled=not confirm,
            key=f"rollback_submit_{surgeon_name}_{procedure_name}",
        )

        if rollback_submitted:
            try:
                rollback_result = rollback_preference_card(
                    card_id=str(selected_version.get("card_id")),
                    source_version_id=str(selected_version.get("version_id")),
                    reason=reason,
                    actor=current_user,
                    organisation_id=active_organisation_id,
                    organisation_name=active_organisation_name,
                    settings=load_settings().postgres,
                    storage_factory=get_storage_client,
                    source_gold_key=tenant_latest_gold_key(active_organisation_id),
                )
                if not rollback_result.rolled_back:
                    st.error(rollback_result.error or rollback_result.message)
                    return

                load_gold_data.clear()
                load_operational_postgres_data.clear()
                load_preference_card_history.clear()
                load_postgres_metadata.clear()
                st.success(rollback_result.message)
                if rollback_result.published_gold_key:
                    st.success(f"Gold snapshot refreshed: {rollback_result.published_gold_key}")
                if rollback_result.publish_event_key:
                    st.success(f"Rollback event archived: {rollback_result.publish_event_key}")
                if not rollback_result.audit_saved:
                    st.warning(
                        f"Rollback needs reconciliation at {rollback_result.failure_stage}: "
                        f"{rollback_result.error or 'The Postgres audit was not saved.'}"
                    )
            except (PermissionError, ValueError) as exc:
                st.error(str(exc))


with overview_tab:
    render_overview()


with view_tab:
    search_surgeon_col, search_procedure_col = st.columns(2)
    with search_surgeon_col:
        surgeon_query = st.text_input("Search surgeon", key="card_search_surgeon")
    with search_procedure_col:
        procedure_query = st.text_input(
            "Search procedure",
            key="card_search_procedure",
            placeholder="e.g. hip, THR or total hip replacement",
        )
    filtered_df = search_preference_cards(current_df, surgeon_query, procedure_query)
    st.caption(f"{len(filtered_df)} matching preference cards")

    search_signature = (surgeon_query.strip().casefold(), procedure_query.strip().casefold())
    if st.session_state.get("card_search_signature") != search_signature:
        st.session_state.pop("view_card_pair", None)
        st.session_state["card_search_signature"] = search_signature

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
        if column in filtered_df.columns
    ]
    if not filtered_df.empty:
        st.dataframe(
            filtered_df[summary_columns],
            width="stretch",
            hide_index=True,
        )

    card_pairs = list(
        filtered_df[["surgeon_name", "procedure"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    if not card_pairs:
        st.warning("No matching preference cards found.")
    else:
        selected_surgeon, selected_procedure = st.selectbox(
            "Open preference card",
            card_pairs,
            format_func=lambda pair: f"{pair[0]} - {pair[1]}",
            key="view_card_pair",
        )
        card = build_preference_card(filtered_df, selected_surgeon, selected_procedure)

        if not card:
            st.warning("No preference card found for this surgeon and procedure.")
        else:
            render_card(card)
            render_card_history(selected_surgeon, selected_procedure)


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

    edit_surgeon = st.selectbox(
        "Surgeon",
        surgeons or ["No preference cards yet"],
        disabled=not surgeons,
        key="edit_surgeon",
    )
    edit_df = current_df[current_df["surgeon_name"] == edit_surgeon]
    edit_procedures = edit_df["procedure"].dropna().unique().tolist()
    edit_procedure = st.selectbox(
        "Procedure",
        edit_procedures or ["No procedures yet"],
        disabled=not edit_procedures,
        key="edit_procedure",
    )
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
                "source_gold_key": tenant_latest_gold_key(active_organisation_id),
            }
            try:
                submission = save_draft(draft, current_user)
                if submission.audit_saved:
                    load_postgres_metadata.clear()
                st.success(f"Draft saved: {submission.object_key}")
                if submission.audit_saved:
                    st.success("Draft audit recorded in Postgres.")
                else:
                    st.warning(
                        "The draft was saved to object storage, but the Postgres workflow "
                        f"audit was not written: {submission.audit_error}"
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
            "source_gold_key": tenant_latest_gold_key(active_organisation_id),
        }
        try:
            submission = save_draft(draft, current_user)
            if submission.audit_saved:
                load_postgres_metadata.clear()
            st.success(f"Draft saved: {submission.object_key}")
            if submission.audit_saved:
                st.success("Draft audit recorded in Postgres.")
            else:
                st.warning(
                    "The draft was saved to object storage, but the Postgres workflow "
                    f"audit was not written: {submission.audit_error}"
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
    pending_drafts = load_pending_drafts(
        storage,
        DRAFT_PREFIX,
        organisation_id=active_organisation_id,
    )
    review_keys = storage.list_objects(
        tenant_object_prefix(REVIEW_DECISION_PREFIX, active_organisation_id)
    )

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
                review_result = submit_preference_review(
                    draft=selected_draft,
                    reviewer=current_user,
                    decision=decision,
                    comments=comments,
                    organisation_id=active_organisation_id,
                    organisation_name=active_organisation_name,
                    settings=load_settings().postgres,
                    storage_factory=lambda: storage,
                )
                if review_result.audit_saved:
                    load_postgres_metadata.clear()

                st.success(f"Review decision archived: {review_result.review_object_key}")
                st.success(f"Draft moved to status: {review_result.updated_draft['status']}")
                if review_result.audit_saved:
                    st.success("Review decision recorded in the Postgres workflow audit.")
                else:
                    st.warning(
                        "The review was saved to object storage, but the Postgres workflow "
                        f"audit was not written: {review_result.audit_error}"
                    )
            except (PermissionError, ValueError) as exc:
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
    publishable_drafts = load_publishable_drafts(
        storage,
        DRAFT_PREFIX,
        organisation_id=active_organisation_id,
    )
    publish_event_keys = storage.list_objects(
        tenant_object_prefix(PUBLISH_EVENT_PREFIX, active_organisation_id)
    )

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
                    publish_result = publish_preference_draft(
                        draft=selected_publish_draft,
                        publisher=current_user,
                        organisation_id=active_organisation_id,
                        organisation_name=active_organisation_name,
                        settings=load_settings().postgres,
                        storage_factory=lambda: storage,
                        editable_fields=EDITABLE_FIELDS,
                        source_gold_key=tenant_latest_gold_key(active_organisation_id),
                        published_at=published_at,
                    )
                    if not publish_result.operational_published:
                        raise ValueError(
                            "The preference was not published because the operational Postgres update "
                            f"failed: {publish_result.error or publish_result.operational_message}"
                        )

                    load_operational_postgres_data.clear()
                    load_gold_data.clear()
                    load_operational_postgres_data.clear()
                    load_preference_card_history.clear()
                    load_postgres_metadata.clear()

                    if publish_result.published_gold_key:
                        st.success(f"Published Gold version: {publish_result.published_gold_key}")
                    if publish_result.publish_event_key:
                        st.success(f"Publish event archived: {publish_result.publish_event_key}")
                    if publish_result.updated_draft:
                        st.success(f"Draft moved to status: {publish_result.updated_draft['status']}")
                    st.success(f"Operational publish completed: {publish_result.operational_message}")
                    if publish_result.audit_saved:
                        st.success("Publish event recorded in the Postgres workflow audit.")
                    else:
                        st.warning(f"Publish needs reconciliation at {publish_result.failure_stage}: "
                                   f"{publish_result.error or 'Postgres workflow audit was not saved.'}")
                except (PermissionError, ValueError) as exc:
                    st.error(str(exc))


with access_tab:
    st.subheader("Access management")
    st.write(
        "Manage who can create drafts, review changes, or publish approved preference cards. "
        "This is an admin-only control surface backed by the Postgres workflow audit."
    )

    access_disabled_reason = user_management_block_reason(current_user)
    postgres_settings = load_settings().postgres
    user_access_requests = []
    user_access_request_error = None
    if current_user:
        st.caption(
            f"Signed in as {current_user.display_name} ({current_user.email}); "
            f"roles: {', '.join(current_user.roles) if current_user.roles else 'viewer'}; "
            f"status: {current_user.status}"
        )
        if postgres_settings and not current_user.can_manage_users:
            user_access_requests, user_access_request_error = list_access_requests(
                postgres_settings,
                actor=current_user,
                organisation_id=active_organisation_id,
            )

    st.markdown("#### Request access")
    if current_user is None:
        st.info("Sign in before requesting access to create, review, or publish preference cards.")
        render_account_bar(
            None,
            "Use the secure Azure sign-in flow first. After sign-in, you can request access for your organisation.",
        )
    elif current_user.can_manage_users:
        st.info("You are already an administrator for this workspace.")
    else:
        pending_user_request = next(
            (
                request
                for request in user_access_requests
                if str(request.get("status", "")).strip().lower() == "pending_review"
            ),
            None,
        )
        if user_access_request_error:
            st.warning(user_access_request_error)
        elif user_access_requests:
            st.markdown("##### Your access requests")
            user_request_df = pd.DataFrame(user_access_requests)
            user_request_columns = [
                column
                for column in [
                    "access_request_id",
                    "requested_roles",
                    "requested_organisation_name",
                    "reason",
                    "status",
                    "reviewed_by_email",
                    "reviewed_at",
                    "created_at",
                ]
                if column in user_request_df.columns
            ]
            st.dataframe(
                user_request_df[user_request_columns],
                width="stretch",
                hide_index=True,
            )
        if pending_user_request:
            st.info(
                "You already have a pending request. Submitting this form will update "
                "that pending request instead of creating a duplicate."
            )

        with st.form("access_request_form"):
            requested_organisation = st.text_input(
                "Organisation or hospital",
                value=active_organisation_name,
            )
            requested_roles = st.multiselect(
                "Requested access",
                [EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE],
                default=[EDITOR_ROLE],
                help="Ask only for the minimum access you need.",
            )
            request_reason = st.text_area(
                "Reason",
                placeholder="Example: I help maintain orthopaedic preference cards for theatre preparation.",
            )
            request_submitted = st.form_submit_button(
                "Update Pending Access Request" if pending_user_request else "Submit Access Request",
                disabled=postgres_settings is None,
            )

        if postgres_settings is None:
            st.info("Access requests need Postgres to be configured.")
        elif request_submitted:
            access_request, error_message = submit_access_request(
                settings=postgres_settings,
                user=current_user,
                requested_roles=requested_roles,
                requested_organisation_name=requested_organisation,
                reason=request_reason,
            )
            if error_message:
                st.error(error_message)
            else:
                load_postgres_metadata.clear()
                st.success(
                    "Access request submitted for admin review. You will remain pending "
                    "until an administrator approves the request."
                )
                st.caption(f"Request ID: {access_request['access_request_id']}")

    st.markdown("#### Admin controls")
    if access_disabled_reason:
        st.info(f"{access_disabled_reason} Existing users can still be viewed in Metadata.")
    else:
        if not postgres_settings:
            st.warning("Postgres user registry is not configured for this deployment.")
        else:
            pending_requests, pending_error = list_access_requests(
                postgres_settings,
                actor=current_user,
                organisation_id=active_organisation_id,
                status="pending_review",
            )
            if pending_error:
                st.warning(pending_error)
            elif pending_requests:
                st.markdown("##### Pending access requests")
                pending_df = pd.DataFrame(pending_requests)
                st.dataframe(
                    pending_df[
                        [
                            "access_request_id",
                            "user_email",
                            "display_name",
                            "requested_roles",
                            "requested_organisation_name",
                            "reason",
                            "created_at",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                )

                request_options = {
                    f"{request['user_email']} - {request['access_request_id']}": request
                    for request in pending_requests
                }
                with st.form("resolve_access_request_form"):
                    selected_request_label = st.selectbox(
                        "Access request",
                        list(request_options),
                        key="resolve_access_request",
                    )
                    access_decision = st.selectbox("Decision", ["approved", "rejected"])
                    resolve_submitted = st.form_submit_button("Record Access Decision")

                if resolve_submitted:
                    selected_request = request_options[selected_request_label]
                    resolved_request, error_message = resolve_access_request(
                        settings=postgres_settings,
                        access_request_id=str(selected_request["access_request_id"]),
                        decision=access_decision,
                        actor=current_user,
                    )
                    if error_message:
                        st.error(error_message)
                    else:
                        load_postgres_metadata.clear()
                        st.success(
                            f"Access request {resolved_request['access_request_id']} marked "
                            f"{resolved_request['status']}."
                        )
            else:
                st.info("No pending access requests for this workspace.")

            postgres_metadata = load_postgres_metadata(active_organisation_id)
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
    draft_rows = load_drafts(storage, DRAFT_PREFIX, organisation_id=active_organisation_id)
    draft_keys = [draft["_object_key"] for draft in draft_rows]
    review_keys = storage.list_objects(
        tenant_object_prefix(REVIEW_DECISION_PREFIX, active_organisation_id)
    )
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

    postgres_metadata = load_postgres_metadata(active_organisation_id)
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
        ("Workflow reviews", "workflow_reviews"),
        ("Workflow audit events", "workflow_audit"),
        ("Operational current cards", "operational_current_cards"),
        ("Operational version summary", "operational_version_summary"),
        ("Operational recent versions", "operational_recent_versions"),
        ("Organisations", "organisations"),
        ("Organisation memberships", "organisation_memberships"),
        ("Access requests", "access_requests"),
        ("App users", "app_users"),
    ]
    for label, key in postgres_sections:
        if key in postgres_metadata:
            with st.expander(label):
                st.dataframe(postgres_metadata[key], width="stretch", hide_index=True)

    st.subheader("Clinical reference metadata")
    st.dataframe(load_reference_metadata(), width="stretch", hide_index=True)


render_project_footer()
