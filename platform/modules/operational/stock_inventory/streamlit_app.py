from __future__ import annotations

import json
import os

from streamlit_renderers import render_gold_dashboard
from streamlit_services import (
    dashboard_snapshot,
    dashboard_snapshot_from_object_store,
    list_gold_manifests,
    list_object_gold_manifests,
)


def object_store_mode_enabled() -> bool:
    return os.getenv("STOCK_DASHBOARD_STORAGE_MODE", "local").strip().lower() == "object_store"


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Stock Inventory Operations", layout="wide")

    st.sidebar.header("Gold run")
    object_store = None
    root_prefix = None
    if object_store_mode_enabled():
        from config.settings import load_settings
        from storage.object_store import S3ObjectStoreClient

        settings = load_settings()
        root_prefix = settings.object_store.root_prefix
        object_store = S3ObjectStoreClient(settings.object_store)
        object_store.wait_until_ready()
        manifest_options = list_object_gold_manifests(object_store, root_prefix)
    else:
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
        if object_store is not None and root_prefix is not None:
            snapshot = dashboard_snapshot_from_object_store(object_store, selected_manifest.manifest_path, root_prefix)
        else:
            snapshot = dashboard_snapshot(selected_manifest.manifest_path)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
        st.title("Stock Inventory Operations")
        st.error(f"Unable to load Gold dashboard snapshot: {exc}")
        return

    render_gold_dashboard(st, snapshot)


if __name__ == "__main__":
    main()
