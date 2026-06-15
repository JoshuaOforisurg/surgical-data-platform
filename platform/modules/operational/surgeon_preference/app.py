import pandas as pd
import streamlit as st

from streamlit_renderers.preference_card import build_preference_card
from streamlit_services.streamlit_service import get_storage_client


GOLD_OPERATIONAL_KEY = "gold/operational/latest/gold_operational_preference_cards.csv"

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
selected_surgeon = st.selectbox("Select Surgeon", surgeons)
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
