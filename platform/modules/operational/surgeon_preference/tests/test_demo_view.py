from streamlit.testing.v1 import AppTest


def test_selected_demo_card_updates_when_search_changes_between_aliases():
    app = AppTest.from_file("app.py", default_timeout=30).run()

    app.text_input[0].set_value("THR").run()
    assert app.selectbox[0].options[0] == (
        "Mr Mensah  ·  Total Hip Replacement (Cemented)"
    )
    assert all("Total Hip Replacement" in option for option in app.selectbox[0].options)
    assert app.selectbox[0].value == 0
    assert {metric.label: metric.value for metric in app.metric}["Consumables"] == "10"

    app.text_input[0].set_value("TKA").run()
    assert app.selectbox[0].options[0] == "Mr Patel  ·  Total Knee Replacement"
    assert app.selectbox[0].value == 0
    assert {metric.label: metric.value for metric in app.metric}["Consumables"] == "12"
    assert not app.exception
