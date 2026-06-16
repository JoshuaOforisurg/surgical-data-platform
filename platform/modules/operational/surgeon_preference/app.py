import json
import uuid
from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from streamlit_renderers.preference_card import build_preference_card
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

surgeons = df["surgeon_name"].dropna().unique().tolist()
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

    surgeon_df = df[df["surgeon_name"] == selected_surgeon]
    if "procedure" in surgeon_df.columns:
        procedures = surgeon_df["procedure"].dropna().unique().tolist()
        if procedures:
            selected_procedure = st.selectbox("Select Procedure", ["All procedures"] + procedures)

    if st.button("Generate Preference Card"):
        procedure_filter = None if selected_procedure == "All procedures" else selected_procedure
        card = build_preference_card(df, selected_surgeon, procedure_filter)

        if not card:
            st.warning("No data found for surgeon")
        else:
            render_card(card)


with edit_tab:
    edit_surgeon = st.selectbox("Surgeon", surgeons, key="edit_surgeon")
    edit_df = df[df["surgeon_name"] == edit_surgeon]
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
    st.metric("Surgeons", df["surgeon_name"].nunique())
    st.metric("Procedures", df["procedure"].nunique() if "procedure" in df else 0)
    draft_keys = get_storage_client().list_objects(DRAFT_PREFIX)
    st.metric("Drafts pending", len(draft_keys))
    if draft_keys:
        st.dataframe(pd.DataFrame({"draft_key": draft_keys[-25:]}), use_container_width=True)
