from __future__ import annotations

import json

from streamlit_renderers import render_gold_dashboard
from streamlit_services import dashboard_snapshot, list_gold_manifests


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Stock Inventory Operations", layout="wide")

    st.sidebar.header("Gold run")
    manifest_options = list_gold_manifests()
    if not manifest_options:
        st.title("Stock Inventory Operations")
        st.info("No Gold manifests found yet. Run the stock inventory pipeline first.")
        return

    selected_manifest = st.sidebar.selectbox(
        "Manifest",
        manifest_options,
        format_func=lambda option: option.run_id,
    )

    try:
        snapshot = dashboard_snapshot(selected_manifest.manifest_path)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        st.title("Stock Inventory Operations")
        st.error(f"Unable to load Gold dashboard snapshot: {exc}")
        return

    render_gold_dashboard(st, snapshot)


if __name__ == "__main__":
    main()
