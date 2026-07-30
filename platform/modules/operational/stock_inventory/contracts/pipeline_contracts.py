from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PipelineStageResult:
    stage: str
    manifest_path: str
    record_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StockInventoryPipelineResult:
    run_id: str
    source_dir: str
    generated_manifest_path: str
    stages: list[dict[str, Any]]
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineQualityCheck:
    name: str
    passed: bool
    severity: str
    message: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineQualityResult:
    run_id: str
    status: str
    checked_at: str
    pipeline_manifest_path: str
    checks: list[dict[str, Any]]
    check_count: int
    failure_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
