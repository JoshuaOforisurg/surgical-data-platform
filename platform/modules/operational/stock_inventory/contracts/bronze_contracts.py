from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BronzeSourceFile:
    run_id: str
    source_file_id: str
    dataset: str
    source_path: str
    raw_path: str
    file_name: str
    file_extension: str
    size_bytes: int
    checksum_sha256: str
    canonical_for_silver: bool
    ingested_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BronzeRecord:
    record_id: str
    run_id: str
    source_file_id: str
    source_checksum_sha256: str
    dataset: str
    source_file: str
    source_format: str
    canonical_for_silver: bool
    source_row_number: int
    ingested_at: str
    raw_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BronzeIngestionResult:
    run_id: str
    source_files: list[dict[str, Any]]
    record_outputs: list[dict[str, Any]]
    file_count: int
    record_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
