from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from bronze_ingestion.file_extractors import CSVExtractor, JSONExtractor, JSONLExtractor
from config.paths import BRONZE_MANIFEST_DIR, BRONZE_RAW_DIR, BRONZE_RECORDS_DIR, SYNTHETIC_GENERATED_DIR
from contracts.bronze_contracts import BronzeIngestionResult, BronzeRecord, BronzeSourceFile


SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl"}
EXTRACTORS = {
    ".csv": CSVExtractor,
    ".json": JSONExtractor,
    ".jsonl": JSONLExtractor,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_name(path: Path) -> str:
    return path.name.removesuffix(path.suffix)


class BronzeInventoryPipeline:
    def __init__(
        self,
        raw_dir: Path = BRONZE_RAW_DIR,
        records_dir: Path = BRONZE_RECORDS_DIR,
        manifest_dir: Path = BRONZE_MANIFEST_DIR,
    ):
        self.raw_dir = raw_dir
        self.records_dir = records_dir
        self.manifest_dir = manifest_dir

    def ingest(self, source_path: Path, run_id: str | None = None) -> BronzeIngestionResult:
        run_id = run_id or datetime.now(UTC).strftime("run_%Y%m%d_%H%M%S")
        source_files = self._source_files(source_path)
        ingested_at = datetime.now(UTC).replace(microsecond=0).isoformat()

        run_raw_dir = self.raw_dir / run_id
        run_records_dir = self.records_dir / run_id
        run_raw_dir.mkdir(parents=True, exist_ok=True)
        run_records_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        source_metadata: list[dict[str, Any]] = []
        record_outputs: list[dict[str, Any]] = []
        total_records = 0

        for source_file in source_files:
            copied_path = run_raw_dir / source_file.name
            shutil.copy2(source_file, copied_path)

            source = BronzeSourceFile(
                run_id=run_id,
                dataset=dataset_name(source_file),
                source_path=str(source_file),
                raw_path=str(copied_path),
                file_name=source_file.name,
                file_extension=source_file.suffix.lower().lstrip("."),
                size_bytes=source_file.stat().st_size,
                checksum_sha256=sha256_file(source_file),
                ingested_at=ingested_at,
            )
            source_metadata.append(source.to_dict())

            record_path = run_records_dir / f"{source.dataset}__{source.file_extension}.jsonl"
            record_count = self._write_bronze_records(
                source_file=source_file,
                source=source,
                record_path=record_path,
                ingested_at=ingested_at,
            )
            total_records += record_count
            record_outputs.append(
                {
                    "dataset": source.dataset,
                    "source_file": source.file_name,
                    "record_path": str(record_path),
                    "records": record_count,
                }
            )

        manifest_path = self.manifest_dir / f"{run_id}.json"
        result = BronzeIngestionResult(
            run_id=run_id,
            source_files=source_metadata,
            record_outputs=record_outputs,
            file_count=len(source_metadata),
            record_count=total_records,
            manifest_path=str(manifest_path),
        )
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result

    def _source_files(self, source_path: Path) -> list[Path]:
        source_path = Path(source_path)
        if source_path.is_file():
            files = [source_path]
        elif source_path.is_dir():
            files = sorted(path for path in source_path.iterdir() if path.is_file())
        else:
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        supported_files = [path for path in files if path.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not supported_files:
            raise ValueError(f"No supported source files found in {source_path}")
        return supported_files

    def _write_bronze_records(
        self,
        source_file: Path,
        source: BronzeSourceFile,
        record_path: Path,
        ingested_at: str,
    ) -> int:
        extractor = EXTRACTORS[source_file.suffix.lower()](source_file)
        count = 0
        with record_path.open("w", encoding="utf-8") as output:
            for row_number, payload in enumerate(extractor.extract(), start=1):
                count += 1
                record = BronzeRecord(
                    record_id=f"{source.run_id}:{source.file_name}:{row_number}",
                    run_id=source.run_id,
                    dataset=source.dataset,
                    source_file=source.file_name,
                    source_format=source.file_extension,
                    source_row_number=row_number,
                    ingested_at=ingested_at,
                    raw_payload=payload,
                )
                output.write(json.dumps(record.to_dict()) + "\n")
        return count


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest stock inventory sources into the local bronze layer.")
    parser.add_argument(
        "--source",
        default=str(SYNTHETIC_GENERATED_DIR),
        help="Source file or directory containing CSV, JSON, or JSONL inputs.",
    )
    parser.add_argument("--run-id", default=None, help="Optional deterministic run id for repeatable local runs.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = BronzeInventoryPipeline().ingest(Path(args.source), run_id=args.run_id)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
