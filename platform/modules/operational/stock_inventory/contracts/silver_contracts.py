from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SilverARecord:
    silver_record_id: str
    run_id: str
    dataset: str
    source_record_id: str
    source_file_id: str
    source_checksum_sha256: str
    source_row_number: int
    transformed_at: str
    validation_errors: list[str]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SilverATableResult:
    dataset: str
    output_path: str
    records: int
    invalid_records: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SilverATransformResult:
    run_id: str
    bronze_manifest_path: str
    table_outputs: list[dict[str, Any]]
    table_count: int
    record_count: int
    invalid_record_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SilverBTableResult:
    dataset: str
    output_path: str
    records: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SilverBTransformResult:
    run_id: str
    silver_a_manifest_path: str
    table_outputs: list[dict[str, Any]]
    table_count: int
    record_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
