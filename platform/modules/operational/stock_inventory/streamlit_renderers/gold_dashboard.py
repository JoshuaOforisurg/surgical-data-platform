from __future__ import annotations

from typing import Any

from streamlit_services import DashboardSnapshot, dashboard_snapshot


def currency(value: float) -> str:
    return f"GBP {value:,.2f}"


def render_metric_row(ui: Any, metrics: list[tuple[str, str | int | float]]) -> None:
    columns = ui.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics, strict=True):
        column.metric(label, value)


def render_gold_dashboard(ui: Any, snapshot: DashboardSnapshot | None = None) -> None:
    snapshot = snapshot or dashboard_snapshot()

    ui.title("Stock Inventory Operations")
    ui.caption(f"Run: {snapshot.run_id}")

    render_metric_row(
        ui,
        [
            ("Cases", snapshot.case_count),
            ("Ready", snapshot.ready_case_count),
            ("Shortage", snapshot.shortage_case_count),
            ("Critical", snapshot.critical_shortage_case_count),
        ],
    )
    render_metric_row(
        ui,
        [
            ("Shortage lines", snapshot.shortage_line_count),
            ("Reorder positions", snapshot.reorder_position_count),
            ("Available stock value", currency(snapshot.total_available_stock_value_gbp)),
            ("Issued value", currency(snapshot.estimated_issue_value_gbp)),
        ],
    )

    left, right = ui.columns(2)
    with left:
        ui.subheader("Readiness")
        ui.bar_chart(snapshot.readiness_status_counts)
    with right:
        ui.subheader("Availability")
        ui.bar_chart(snapshot.availability_status_counts)

    tabs = ui.tabs(["Shortages", "Reorders", "Usage and cost"])
    with tabs[0]:
        ui.dataframe(snapshot.top_shortages, use_container_width=True, hide_index=True)
    with tabs[1]:
        ui.dataframe(snapshot.top_reorders, use_container_width=True, hide_index=True)
    with tabs[2]:
        ui.dataframe(snapshot.top_usage_costs, use_container_width=True, hide_index=True)
