from __future__ import annotations

import csv
from typing import Any, Iterator

from bronze_ingestion.file_extractors.base import BaseExtractor


class CSVExtractor(BaseExtractor):
    format_name = "csv"

    def extract(self) -> Iterator[dict[str, Any]]:
        with self.source_path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                yield dict(row)

