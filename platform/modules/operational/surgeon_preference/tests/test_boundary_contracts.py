import json

import pytest

from config.pipeline_version import SILVER_SCHEMA_VERSION
from contracts.boundary_contracts import (
    ContractViolationError,
    validate_silver_to_gold_records,
)


def _valid_record():
    return {
        "pipeline_version": SILVER_SCHEMA_VERSION,
        "surgeon_name": "Mr Test Surgeon",
        "procedure_name": "Total Knee Replacement",
        "instruments": json.dumps([{"name": "Knee tray", "quantity": 1}]),
        "clinical_resolution": {
            "procedure_id": "ORTH_JOINT_KNEE_001",
            "procedure_name": "Total Knee Replacement",
        },
        "clinical_validation": {
            "valid": True,
            "readiness_status": "Ready",
            "flags": [],
            "missing_expected_items": [],
            "confidence": 0.98,
        },
        "quarantine_status": {"is_corrupted": False},
        "_enrichment_meta": {"status": "SUCCESS", "confidence": 0.98},
    }


def test_silver_to_gold_contract_accepts_current_schema():
    summary = validate_silver_to_gold_records([_valid_record()])

    assert summary == {
        "contract_version": "silver_to_gold_v1",
        "silver_schema_version": SILVER_SCHEMA_VERSION,
        "records_validated": 1,
        "passed": True,
    }


def test_silver_to_gold_contract_allows_clinically_quarantined_record():
    record = _valid_record()
    record["clinical_validation"]["valid"] = False
    record["clinical_validation"]["readiness_status"] = "Review required"
    record["quarantine_status"] = {
        "is_corrupted": True,
        "quarantine_reason": "CRITICAL_QUANTITY_ANOMALY",
    }
    record["_enrichment_meta"]["status"] = "QUARANTINED"

    assert validate_silver_to_gold_records([record])["passed"] is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda record: record.update(pipeline_version="silver_a_v999"), "unsupported Silver schema"),
        (lambda record: record.pop("clinical_validation"), "clinical_validation"),
        (lambda record: record.update(instruments="not-json"), "valid JSON"),
        (lambda record: record.update(surgeon_name=""), "surgeon_name"),
    ],
)
def test_silver_to_gold_contract_rejects_breaking_records(mutation, message):
    record = _valid_record()
    mutation(record)

    with pytest.raises(ContractViolationError, match=message):
        validate_silver_to_gold_records([record])
