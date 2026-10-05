import pandas as pd

from streamlit_services.product_readiness_service import (
    BLOCKED,
    NEEDS_ATTENTION,
    READY,
    UNKNOWN,
    build_product_readiness_summary,
    contract_signal,
    draft_workflow_signal,
    gold_dataset_signal,
    pipeline_metadata_signal,
)


def _gold_df(**overrides):
    row = {
        "instrument_set": "Primary knee set",
        "equipment": "Tourniquet",
        "consumables": "Skin marker, suction tubing",
        "disposables": "Saw blade",
        "special_instructions": "Confirm prosthesis sizes.",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_gold_dataset_signal_blocks_empty_gold():
    signal = gold_dataset_signal(pd.DataFrame())

    assert signal.status == BLOCKED
    assert "No current preference cards" in signal.summary


def test_gold_dataset_signal_flags_incomplete_frontline_sections():
    signal = gold_dataset_signal(_gold_df(consumables=""))

    assert signal.status == NEEDS_ATTENTION
    assert "consumables" in signal.detail


def test_gold_dataset_signal_accepts_complete_current_cards():
    signal = gold_dataset_signal(_gold_df())

    assert signal.status == READY
    assert "current cards" in signal.summary


def test_draft_workflow_signal_highlights_review_and_publish_backlog():
    signal = draft_workflow_signal(
        [
            {"status": "pending_review"},
            {"status": "approved_pending_publish"},
            {"status": "changes_requested"},
        ]
    )

    assert signal.status == NEEDS_ATTENTION
    assert "waiting for review" in signal.summary
    assert "waiting for publish" in signal.summary


def test_pipeline_metadata_signal_uses_latest_run_status():
    signal = pipeline_metadata_signal(
        {
            "health": {"reachable": True},
            "runs": pd.DataFrame(
                [
                    {
                        "run_id": "run_1",
                        "status": "completed",
                        "records_processed": 100,
                    }
                ]
            ),
        }
    )

    assert signal.status == READY
    assert "run_1" in signal.summary


def test_pipeline_metadata_signal_blocks_failed_latest_run():
    signal = pipeline_metadata_signal(
        {
            "health": {"reachable": True},
            "runs": pd.DataFrame(
                [
                    {
                        "run_id": "run_2",
                        "status": "failed",
                        "error_message": "quality gate failed",
                    }
                ]
            ),
        }
    )

    assert signal.status == BLOCKED
    assert "failed" in signal.summary
    assert "quality gate failed" in signal.detail


def test_contract_signal_reads_quality_and_contract_manifest_evidence():
    signal = contract_signal(
        {
            "contract_summary": {
                "passed": True,
                "contract_version": "silver_to_gold_v1",
                "records_validated": 25,
            },
            "quality_summary": {"passed": True},
        }
    )

    assert signal.status == READY
    assert "25" in signal.summary


def test_contract_signal_is_unknown_for_older_runs_without_manifest():
    signal = contract_signal(None)

    assert signal.status == UNKNOWN


def test_product_readiness_summary_uses_highest_risk_status():
    summary = build_product_readiness_summary(
        current_gold=_gold_df(),
        drafts=[{"status": "pending_review"}],
        metadata={
            "health": {"reachable": True},
            "runs": pd.DataFrame(
                [
                    {
                        "run_id": "run_1",
                        "status": "completed",
                        "records_processed": 10,
                    }
                ]
            ),
        },
        latest_manifest={
            "contract_summary": {"passed": True, "records_validated": 10},
            "quality_summary": {"passed": True},
        },
    )

    assert summary["overall_status"] == NEEDS_ATTENTION
    assert len(summary["signals"]) == 4
