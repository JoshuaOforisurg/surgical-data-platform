from __future__ import annotations

import json
from typing import Any, Iterator

from bronze_ingestion.file_extractors.base import BaseExtractor


class JSONExtractor(BaseExtractor):
    format_name = "json"

    def extract(self) -> Iterator[dict[str, Any]]:
        payload = json.loads(self.source_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            for record in payload:
                if isinstance(record, dict):
                    yield record
            return
        if isinstance(payload, dict):
            yield payload
            return
        raise ValueError(f"Unsupported JSON payload in {self.source_path}: expected object or list")

