from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from bronze_ingestion.loader.bronze_pipeline import (
    DEFAULT_CANONICAL_FORMAT_PRIORITY,
    BronzeInventoryPipeline,
)
from config.paths import (
    BRONZE_MANIFEST_DIR,
    BRONZE_RAW_DIR,
    BRONZE_RECORDS_DIR,
    GOLD_MANIFEST_DIR,
    GOLD_RECORDS_DIR,
    PIPELINE_MANIFEST_DIR,
    SILVER_A_MANIFEST_DIR,
    SILVER_A_RECORDS_DIR,
    SILVER_B_MANIFEST_DIR,
    SILVER_B_RECORDS_DIR,
    SYNTHETIC_GENERATED_DIR,
)
from contracts.pipeline_contracts import PipelineStageResult, StockInventoryPipelineResult
from generate_synthetic_data.main_synthetic_stock_generator import (
    GenerationConfig,
    generate_stock_sources,
    non_negative_int,
)
from gold_cleaned.publisher import GoldInventoryPublisher
from silver_transform.silver_a.transformer import SilverATransformer
from silver_transform.silver_b.transformer import SilverBTransformer


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


class StockInventoryOrchestrator:
    def __init__(
        self,
        bronze_raw_dir: Path = BRONZE_RAW_DIR,
        bronze_records_dir: Path = BRONZE_RECORDS_DIR,
        bronze_manifest_dir: Path = BRONZE_MANIFEST_DIR,
        silver_a_records_dir: Path = SILVER_A_RECORDS_DIR,
        silver_a_manifest_dir: Path = SILVER_A_MANIFEST_DIR,
        silver_b_records_dir: Path = SILVER_B_RECORDS_DIR,
        silver_b_manifest_dir: Path = SILVER_B_MANIFEST_DIR,
        gold_records_dir: Path = GOLD_RECORDS_DIR,
        gold_manifest_dir: Path = GOLD_MANIFEST_DIR,
        pipeline_manifest_dir: Path = PIPELINE_MANIFEST_DIR,
    ):
        self.bronze = BronzeInventoryPipeline(
            raw_dir=bronze_raw_dir,
            records_dir=bronze_records_dir,
            manifest_dir=bronze_manifest_dir,
        )
        self.silver_a = SilverATransformer(records_dir=silver_a_records_dir, manifest_dir=silver_a_manifest_dir)
        self.silver_b = SilverBTransformer(records_dir=silver_b_records_dir, manifest_dir=silver_b_manifest_dir)
        self.gold = GoldInventoryPublisher(records_dir=gold_records_dir, manifest_dir=gold_manifest_dir)
        self.pipeline_manifest_dir = pipeline_manifest_dir

    def run(
        self,
        source_dir: Path = SYNTHETIC_GENERATED_DIR,
        run_id: str | None = None,
        event_count: int = 250,
        movement_count: int = 250,
        case_count: int = 25,
        seed: int = 42,
        run_date: datetime | None = None,
        messy_sources: bool = True,
        regenerate_sources: bool = True,
        surgeon_preference_gold_path: Path | None = None,
        canonical_format_priority: Iterable[str] = DEFAULT_CANONICAL_FORMAT_PRIORITY,
    ) -> StockInventoryPipelineResult:
        run_id = run_id or default_run_id()
        source_dir = Path(source_dir)

        if regenerate_sources:
            generate_stock_sources(
                GenerationConfig(
                    output_dir=source_dir,
                    event_count=event_count,
                    movement_count=movement_count,
                    case_count=case_count,
                    seed=seed,
                    run_date=run_date or GenerationConfig().run_date,
                    messy_sources=messy_sources,
                    surgeon_preference_gold_path=surgeon_preference_gold_path,
                )
            )

        generated_manifest_path = source_dir / "generation_manifest.json"
        bronze_result = self.bronze.ingest(
            source_dir,
            run_id=run_id,
            canonical_format_priority=canonical_format_priority,
        )
        silver_a_result = self.silver_a.transform(Path(bronze_result.manifest_path))
        silver_b_result = self.silver_b.transform(Path(silver_a_result.manifest_path))
        gold_result = self.gold.publish(Path(silver_b_result.manifest_path))

        stages = [
            PipelineStageResult("bronze", bronze_result.manifest_path, bronze_result.record_count).to_dict(),
            PipelineStageResult("silver_a", silver_a_result.manifest_path, silver_a_result.record_count).to_dict(),
            PipelineStageResult("silver_b", silver_b_result.manifest_path, silver_b_result.record_count).to_dict(),
            PipelineStageResult("gold", gold_result.manifest_path, gold_result.record_count).to_dict(),
        ]

        self.pipeline_manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.pipeline_manifest_dir / f"{run_id}.json"
        result = StockInventoryPipelineResult(
            run_id=run_id,
            source_dir=str(source_dir),
            generated_manifest_path=str(generated_manifest_path),
            stages=stages,
            manifest_path=str(manifest_path),
        )
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result


def parse_run_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def env_path(name: str, default: Path | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return str(default) if default is not None else None
    return value.strip()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the full stock inventory pipeline from sources to Gold outputs.")
    parser.add_argument(
        "--source-dir",
        default=env_path("STOCK_PIPELINE_SOURCE_DIR", SYNTHETIC_GENERATED_DIR),
        help="Source output/input directory. Defaults to STOCK_PIPELINE_SOURCE_DIR when set.",
    )
    parser.add_argument("--run-id", default=None, help="Optional deterministic run id.")
    parser.add_argument("--event-count", type=non_negative_int, default=250, help="Synthetic scanner event count.")
    parser.add_argument("--movement-count", type=non_negative_int, default=250, help="Synthetic stock movement count.")
    parser.add_argument("--case-count", type=non_negative_int, default=25, help="Synthetic upcoming case count.")
    parser.add_argument("--seed", type=int, default=42, help="Synthetic generator seed.")
    parser.add_argument("--run-date", type=parse_run_date, default=None, help="Optional ISO-8601 synthetic run date.")
    parser.add_argument(
        "--clean-sources",
        action="store_true",
        help="Write clean CSV files instead of messy spreadsheet-style CSV files.",
    )
    parser.add_argument(
        "--no-regenerate-sources",
        action="store_true",
        help="Use existing source files in --source-dir instead of regenerating synthetic data.",
    )
    parser.add_argument(
        "--surgeon-preference-gold",
        default=env_path("SURGEON_PREFERENCE_GOLD_PATH"),
        help=(
            "Optional surgeon preference operational Gold JSON used to generate case demand. "
            "Defaults to SURGEON_PREFERENCE_GOLD_PATH when set."
        ),
    )
    parser.add_argument(
        "--canonical-format-priority",
        default="jsonl,json,csv",
        help="Comma-separated source format priority for Bronze canonical selection.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = StockInventoryOrchestrator().run(
        source_dir=Path(args.source_dir),
        run_id=args.run_id,
        event_count=args.event_count,
        movement_count=args.movement_count,
        case_count=args.case_count,
        seed=args.seed,
        run_date=args.run_date,
        messy_sources=not args.clean_sources,
        regenerate_sources=not args.no_regenerate_sources,
        surgeon_preference_gold_path=(
            Path(args.surgeon_preference_gold) if args.surgeon_preference_gold else None
        ),
        canonical_format_priority=[item.strip() for item in args.canonical_format_priority.split(",") if item.strip()],
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
