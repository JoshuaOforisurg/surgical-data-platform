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
