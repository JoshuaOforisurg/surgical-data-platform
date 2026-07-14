from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GoldArtifactResult:
    artifact: str
    output_path: str
    records: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GoldPublishResult:
    run_id: str
    silver_b_manifest_path: str
    artifacts: list[dict[str, Any]]
    artifact_count: int
    record_count: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
