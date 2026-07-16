from __future__ import annotations

from streamlit_renderers.gold_dashboard import currency, render_gold_dashboard
from streamlit_services.gold_dashboard_service import DashboardSnapshot


class Recorder:
    def __init__(self, calls: list[tuple[str, object]] | None = None):
        self.calls = calls if calls is not None else []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def title(self, value):
        self.calls.append(("title", value))

    def caption(self, value):
        self.calls.append(("caption", value))

    def metric(self, label, value):
        self.calls.append(("metric", (label, value)))

    def subheader(self, value):
        self.calls.append(("subheader", value))

    def bar_chart(self, value):
        self.calls.append(("bar_chart", value))

    def dataframe(self, value, **kwargs):
        self.calls.append(("dataframe", (value, kwargs)))

    def columns(self, count):
        return [Recorder(self.calls) for _ in range(count)]

    def tabs(self, labels):
        self.calls.append(("tabs", labels))
        return [Recorder(self.calls) for _ in labels]


def test_currency_formats_dashboard_values():
    assert currency(1234.5) == "GBP 1,234.50"


def test_render_gold_dashboard_uses_snapshot_sections():
    snapshot = DashboardSnapshot(
        run_id="run_ui",
        case_count=5,
        ready_case_count=3,
        shortage_case_count=1,
        critical_shortage_case_count=1,
        shortage_line_count=2,
        reorder_position_count=4,
        total_available_stock_value_gbp=1234.5,
        estimated_issue_value_gbp=250.0,
        readiness_status_counts={"ready": 10, "shortage": 2},
        availability_status_counts={"available": 7, "unavailable": 1},
        top_shortages=[{"case_id": "CASE-001"}],
        top_reorders=[{"item_id": "INV-001"}],
        top_usage_costs=[{"item_id": "INV-002"}],
    )
    ui = Recorder()

    render_gold_dashboard(ui, snapshot)

    assert ("title", "Stock Inventory Operations") in ui.calls
    assert ("caption", "Run: run_ui") in ui.calls
    assert ("metric", ("Cases", 5)) in ui.calls
    assert ("metric", ("Available stock value", "GBP 1,234.50")) in ui.calls
    assert ("tabs", ["Shortages", "Reorders", "Usage and cost"]) in ui.calls
    assert any(call[0] == "dataframe" and call[1][0] == [{"case_id": "CASE-001"}] for call in ui.calls)
