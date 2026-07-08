from __future__ import annotations

import json
from typing import Any, Iterator

from bronze_ingestion.file_extractors.base import BaseExtractor


class JSONLExtractor(BaseExtractor):
    format_name = "jsonl"

    def extract(self) -> Iterator[dict[str, Any]]:
        with self.source_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"Unsupported JSONL payload in {self.source_path} line {line_number}: expected object"
                    )
                yield payload

