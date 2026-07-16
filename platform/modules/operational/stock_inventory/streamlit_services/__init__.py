"""Streamlit services for stock inventory operational views."""

from streamlit_services.gold_dashboard_service import (
    DashboardSnapshot,
    GoldManifestOption,
    dashboard_snapshot,
    list_gold_manifests,
)

__all__ = ["DashboardSnapshot", "GoldManifestOption", "dashboard_snapshot", "list_gold_manifests"]
