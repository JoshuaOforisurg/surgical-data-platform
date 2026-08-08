from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from config.settings import ObjectStoreSettings, load_settings
from metadata.repository import metadata_repository_from_settings
from orchestration.quality_gates import latest_pipeline_manifest
from storage.object_store import ObjectStoreClient, content_type_for, sha256_file


@dataclass(frozen=True)
class PublishedArtifact:
    local_path: str
    object_key: str
    object_uri: str
    content_type: str
    checksum_sha256: str


@dataclass(frozen=True)
class PublishRunResult:
    run_id: str
    status: str
    published_at: str
    pipeline_manifest_path: str
    artifact_count: int
    artifacts: list[dict[str, Any]]
    object_manifest_uri: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class RunArtifactPublisher:
    def __init__(
        self,
        object_store: Any,
        settings: ObjectStoreSettings,
        metadata_repository: Any | None = None,
    ):
        self.object_store = object_store
        self.settings = settings
        self.metadata_repository = metadata_repository

    def publish(self, pipeline_manifest_path: Path) -> PublishRunResult:
        pipeline_manifest_path = Path(pipeline_manifest_path)
        pipeline_manifest = read_json(pipeline_manifest_path)
        run_id = str(pipeline_manifest["run_id"])
        published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        local_paths = self.collect_local_paths(pipeline_manifest_path, pipeline_manifest)
        published = [self.publish_path(run_id, path) for path in local_paths]
        result_without_uri = {
            "run_id": run_id,
            "status": "published",
            "published_at": published_at,
            "pipeline_manifest_path": str(pipeline_manifest_path),
            "artifact_count": len(published),
            "artifacts": [asdict(artifact) for artifact in published],
        }
        object_manifest_key = f"{self.settings.root_prefix}/runs/{run_id}/publish_manifest.json"
        object_manifest_uri = self.object_store.uri(object_manifest_key)
        self.object_store.put_text(
            object_manifest_key,
            json.dumps({**result_without_uri, "object_manifest_uri": object_manifest_uri}, indent=2),
            content_type="application/json",
        )
        result = PublishRunResult(
            **result_without_uri,
            object_manifest_uri=object_manifest_uri,
        )
        if self.metadata_repository is not None:
            self.metadata_repository.record_published_artifacts(result)
        return result

    def collect_local_paths(self, pipeline_manifest_path: Path, pipeline_manifest: dict[str, Any]) -> list[Path]:
        paths = [pipeline_manifest_path]
        for stage in pipeline_manifest.get("stages", []):
            manifest_path = Path(stage["manifest_path"])
            paths.append(manifest_path)
            if manifest_path.exists():
                paths.extend(self.stage_output_paths(read_json(manifest_path)))

        existing_paths = []
        seen: set[Path] = set()
        for path in paths:
            resolved = path.resolve()
            if resolved.exists() and resolved not in seen:
                existing_paths.append(resolved)
                seen.add(resolved)
        return existing_paths

    def stage_output_paths(self, manifest: dict[str, Any]) -> list[Path]:
        paths = []
        for output in manifest.get("record_outputs", []):
            paths.append(Path(output["record_path"]))
        for output in manifest.get("table_outputs", []):
            paths.append(Path(output["output_path"]))
        for artifact in manifest.get("artifacts", []):
            paths.append(Path(artifact["output_path"]))
        return paths

    def publish_path(self, run_id: str, local_path: Path) -> PublishedArtifact:
        checksum = sha256_file(local_path)
        object_key = self.object_key(run_id, local_path)
        content_type = content_type_for(local_path)
        object_uri = self.object_store.upload_file(
            local_path,
            object_key,
            content_type=content_type,
            metadata={"run_id": run_id, "checksum_sha256": checksum},
        )
        return PublishedArtifact(
            local_path=str(local_path),
            object_key=object_key,
            object_uri=object_uri,
            content_type=content_type,
            checksum_sha256=checksum,
        )

    def object_key(self, run_id: str, local_path: Path) -> str:
        parts = local_path.parts
        if "data_lake" in parts:
            relative_path = Path(*parts[parts.index("data_lake"):]).as_posix()
        else:
            try:
                relative_path = local_path.relative_to(MODULE_ROOT).as_posix()
            except ValueError:
                relative_path = local_path.name
        return f"{self.settings.root_prefix}/runs/{run_id}/{relative_path}"


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Publish stock inventory run artifacts to object storage.")
    parser.add_argument(
        "--pipeline-manifest",
        default=None,
        help="Pipeline manifest path. Defaults to the latest local pipeline manifest.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    settings = load_settings()
    repository = metadata_repository_from_settings(settings)
    manifest_path = Path(args.pipeline_manifest) if args.pipeline_manifest else latest_pipeline_manifest()
    object_store = ObjectStoreClient(settings.object_store)
    object_store.wait_until_ready()
    result = RunArtifactPublisher(object_store, settings.object_store, repository).publish(manifest_path)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
