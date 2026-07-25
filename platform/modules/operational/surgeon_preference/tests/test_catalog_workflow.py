from bronze_Ingestion.catalog import BronzeCatalogRepository


def test_record_draft_review_decision_is_noop_when_postgres_disabled():
    repository = BronzeCatalogRepository(settings=None)

    repository.record_draft_review_decision(
        {
            "review_id": "00000000-0000-0000-0000-000000000001",
            "decision": "approved",
            "reviewer": "Theatre Reviewer",
            "reviewed_at": "2026-07-22T10:00:00+00:00",
        },
        "gold/operational/draft_reviews/review.json",
    )


def test_user_registry_methods_are_noops_when_postgres_disabled():
    repository = BronzeCatalogRepository(settings=None)

    assert repository.upsert_app_user_seen(
        user_email="editor@example.com",
        display_name="Editor",
        roles=["authenticated", "editor"],
        status="active",
        auth_provider="local_env",
    ) is None
    assert repository.list_app_users() == []

    repository.record_draft_submission(
        {
            "draft_id": "draft-1",
            "submitted_by": "Editor",
            "submitter_email": "editor@example.com",
            "submitter_roles": ["editor"],
        },
        "gold/operational/drafts/draft-1.json",
    )
