from __future__ import annotations

import json

from generate_synthetic_data.main_synthetic_stock_generator import (
    GenerationConfig,
    generate_stock_sources,
)


def test_generator_uses_surgeon_preference_gold_for_case_demand(tmp_path):
    preference_path = tmp_path / "preference_gold.json"
    preference_path.write_text(
        json.dumps(
            [
                {
                    "surgeon_id": "SURG-001",
                    "surgeon_name": "Mr Test",
                    "hospital": "Test NHS Trust",
                    "procedure": "Total Knee Replacement",
                    "procedure_id": "PROC-TKR",
                    "procedure_code": "0SRC0JZ",
                    "subspecialty": "Joint Replacement",
                    "preference_card_uid": "pref-test-tkr",
                    "preference_card_version": 3,
                    "is_current": True,
                    "validation_status": "SUCCESS",
                    "instruments_json": json.dumps(
                        [{"name": "Large Orthopaedic Set", "quantity": 2}]
                    ),
                    "consumables_json": json.dumps(
                        [
                            {"name": "Skin Marker Pen", "quantity": 4},
                            {"name": "Uncatalogued Trial Item", "quantity": 1},
                        ]
                    ),
                }
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "sources"

    manifest = generate_stock_sources(
        GenerationConfig(
            output_dir=output_dir,
            event_count=2,
            movement_count=2,
            case_count=2,
            seed=42,
            surgeon_preference_gold_path=preference_path,
        )
    )
    demand = json.loads((output_dir / "upcoming_case_demand.json").read_text(encoding="utf-8"))

    assert manifest["demand_source"]["mode"] == "surgeon_preference_gold"
    assert manifest["demand_source"]["card_count"] == 1
    assert {row["case_id"] for row in demand} == {"CASE-250001", "CASE-250002"}
    assert {row["surgeon_name"] for row in demand} == {"Mr Test"}
    assert {row["preference_card_uid"] for row in demand} == {"pref-test-tkr"}
    assert {row["preference_card_version"] for row in demand} == {3}
    assert {row["preference_source"] for row in demand} == {"surgeon_preference_gold"}
    for case_id in {row["case_id"] for row in demand}:
        assert len({row["theatre"] for row in demand if row["case_id"] == case_id}) == 1
    assert any(row["catalogue_match_status"] == "unmatched" for row in demand)
