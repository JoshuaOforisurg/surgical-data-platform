"""Exercise real Streamlit forms against local synthetic data, retaining audit evidence.

Run from the module root with PYTHONPATH=. and --allow-local-writes. This creates
a test user, draft, review, publication and rollback; it does not delete history.
Do not run while another user is editing or publishing these local cards.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from streamlit.testing.v1 import AppTest

from config.settings import load_settings
from scripts.verify_phase1 import require_local_services, verify
from storage.object_store import ObjectStoreClient
from streamlit_services.draft_review_service import draft_display_name
from streamlit_services.preference_card_repository import PreferenceCardRepository


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def run_app(app):
    app.run()
    assert not app.exception, [error.message for error in app.exception]
    assert not app.error, [error.value for error in app.error]
    assert widget(app.metric, "Data source").value == "Postgres"


def smoke() -> dict:
    settings = load_settings()
    require_local_services(settings)
    baseline = verify()
    assert baseline["passed"], baseline
    os.environ.update({
        "APP_CURRENT_USER_EMAIL": "phase1-verification@example.invalid",
        "APP_CURRENT_USER_NAME": "Phase 1 Verification",
        "APP_ADMIN_ALLOWLIST": "phase1-verification@example.invalid",
        "APP_ORGANISATION_ID": "default",
        "APP_ORGANISATION_NAME": "Surgeon Preference Demo",
        "ENABLE_DRAFT_SUBMISSIONS": "true",
        "ENABLE_DRAFT_REVIEWS": "true",
        "ENABLE_DRAFT_PUBLISHING": "true",
    })
    store = ObjectStoreClient(settings.minio)
    repository = PreferenceCardRepository(settings.postgres)
    draft_prefix = "gold/operational/drafts/"
    previous_drafts = set(store.list_objects(draft_prefix))
    app = AppTest.from_file("app.py", default_timeout=180)
    run_app(app)
    surgeon = app.selectbox(key="edit_surgeon").value
    procedure = app.selectbox(key="edit_procedure").value

    def current_card():
        return next(row for row in repository.list_current_cards(limit=1_000_000)
                    if row["surgeon_name"] == surgeon and row["procedure_name"] == procedure)

    original = current_card()
    original_history = repository.list_card_history(surgeon, procedure, limit=1_000_000)
    original_version_id = str(next(row for row in original_history if row["is_current"])["version_id"])
    version = original["current_version_number"]
    original_instructions = original["card_payload"]["special_instructions"]
    test_instructions = original_instructions + "\nSynthetic workflow verification only."
    # The edit and create forms share labels; the edit form is rendered first.
    widget(app.text_area, "Special Instructions").set_value(test_instructions)
    widget(app.button, "Save Draft Edit").click()
    run_app(app)
    created = set(store.list_objects(draft_prefix)) - previous_drafts
    assert len(created) == 1, created
    draft_key = created.pop()

    def draft():
        return json.loads(store.get_text(draft_key))

    assert draft()["status"] == "pending_review"
    assert current_card()["current_version_number"] == version
    widget(app.selectbox, "Select draft to review").select(draft_display_name(draft()))
    widget(app.text_area, "Review comments").set_value("Synthetic local workflow verification.")
    widget(app.button, "Record Review Decision").click()
    run_app(app)
    assert draft()["status"] == "approved_pending_publish"
    assert current_card()["current_version_number"] == version
    app.selectbox(key="publish_draft").select(draft_display_name(draft()))
    widget(app.checkbox, "I confirm this approved draft should become the published Gold preference card.").check()
    widget(app.button, "Publish Approved Draft").click()
    run_app(app)
    assert draft()["status"] == "published"
    published = current_card()
    assert published["current_version_number"] == version + 1
    assert published["card_payload"]["special_instructions"] == test_instructions

    run_app(app)
    app.selectbox(key="view_surgeon").select(surgeon)
    run_app(app)
    widget(app.selectbox, "Select procedure").select(procedure)
    run_app(app)
    history = repository.list_card_history(surgeon, procedure, limit=1_000_000)
    source = next(row for row in history if str(row["version_id"]) == original_version_id)
    label = (f"{source['version_label']} - published {source['published_at']} "
             f"by {source['published_by']}")
    widget(app.selectbox, "Historical version to copy").select(label)
    widget(app.text_area, "Rollback reason").set_value("Restore original content after synthetic workflow verification.")
    widget(app.checkbox, "I understand this will create a new current version copied from the selected historical version.").check()
    run_app(app)
    widget(app.button, "Create Rollback Version").click()
    run_app(app)
    restored = current_card()
    assert restored["current_version_number"] == version + 2
    assert restored["card_payload"]["special_instructions"] == original_instructions
    history = repository.list_card_history(surgeon, procedure, limit=1_000_000)
    assert sum(bool(row["is_current"]) for row in history) == 1
    assert len(history) == len(original_history) + 2

    with psycopg2.connect(settings.postgres.psycopg2_dsn) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT status FROM app_workflow.preference_card_drafts WHERE draft_id = %s", (draft()["draft_id"],))
            assert cur.fetchone()["status"] == "published"
            cur.execute("SELECT decision FROM app_workflow.draft_reviews WHERE draft_id = %s", (draft()["draft_id"],))
            assert cur.fetchone()["decision"] == "approved"
            cur.execute("SELECT published_gold_key, card_id, version_id FROM app_workflow.preference_card_publish_events WHERE draft_id = %s", (draft()["draft_id"],))
            event = cur.fetchone()
            published_key = event["published_gold_key"]
            assert str(event["card_id"]) == str(original["card_id"])
            assert str(event["version_id"]) == str(published["version_id"])
            cur.execute("SELECT published_gold_key FROM app_workflow.preference_card_publish_events WHERE version_id = %s AND organisation_id = 'default'", (str(restored["version_id"]),))
            rollback_key = cur.fetchone()["published_gold_key"]
    assert store.get_text(published_key).strip()
    assert store.get_text(rollback_key).strip()
    final = verify()
    assert final["passed"], final
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "mode": "Streamlit AppTest with real local Postgres and MinIO; synthetic admin identity",
        "run_id": baseline["run_id"],
        "draft_id": draft()["draft_id"],
        "draft_key": draft_key,
        "published_gold_key": published_key,
        "rollback_gold_key": rollback_key,
        "card_id": str(original["card_id"]),
        "versions": {"original": version, "published": version + 1, "rollback": version + 2},
        "checks": {
            "postgres_read_path": True,
            "draft_and_review_leave_current_card_unchanged": True,
            "published_edit_visible_in_postgres": True,
            "rollback_restores_original_content": True,
            "history_retained_with_one_current_version": True,
            "draft_review_publish_audit_rows_present": True,
            "rollback_publication_linked_to_exact_version": True,
            "postgres_and_gold_snapshots_match_after_rollback": True,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-local-writes", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.allow_local_writes:
        parser.error("Use --allow-local-writes only against synthetic local data.")
    report = smoke()
    content = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
