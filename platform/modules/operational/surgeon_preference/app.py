import json
import pandas as pd
import streamlit as st

from streamlit_renderers.preference_card import build_preference_card
# 1. Update this to import our dynamic factory function instead of MinIOClient
from streamlit_services.streamlit_service import get_storage_client

# ----------------------------
# APP CONFIG
# ----------------------------
st.set_page_config(page_title="Surgical Data Platform", layout="wide")
st.title("Surgical Preference Platform")

# ----------------------------
# INIT STORAGE CLIENT (AUTOMATIC SWITCHER)
# ----------------------------
# 2. This now automatically spins up MinIO locally OR Azure in the cloud
storage = get_storage_client()

# ----------------------------
# LOAD GOLD DATA (SAFE)
# ----------------------------
@st.cache_data(ttl=60)
def load_gold_data():
    try:
        # 3. This now safely returns a clean list of file path strings
        objects = storage.list_objects("gold/")

        if not objects:
            return None

        # 4. Sort alphabetically/chronologically by filename to get the latest pipeline run
        objects = sorted(objects, reverse=True)

        # 5. 'key' is now just a plain string path, no dictionary indexing needed!
        key = objects[0]

        local_path = "/tmp/gold.csv"
        storage.download_file(key, local_path)

        # CSV ONLY (simplify + stabilise)
        return pd.read_csv(local_path)

    except Exception as e:
        st.error(f"Failed to load gold data: {e}")
        return None


# ----------------------------
# LOAD DATA
# ----------------------------
df = load_gold_data()

if df is None or df.empty:
    st.warning("No Gold data found. Run pipeline first.")
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

if st.button("Generate Preference Card"):
    card = build_preference_card(df, selected_surgeon)

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
- **Implant system:** {p.get('implant_system', 'N/A')}
- **Approach:** {p.get('approach', 'N/A')}
- **Instrument set:** {p.get('instrument_set', 'N/A')}
- **Laterality:** {p.get('laterality', 'N/A')}
- **Priority:** {p.get('priority_level', 'N/A')}
"""
            )
