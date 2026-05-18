import json
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from extractor_interface import BaseExtractor

class JsonExtractor(BaseExtractor):
    def __init__(self, source: Any):
        super().__init__(source)
        self._file_handle = None
        self._row_count = 0

    def load(self) -> None:
        path = Path(self.source)
        self._file_handle = path.open("r", encoding="utf-8")
        self._row_count = 0

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        if not self._file_handle:
            raise RuntimeError("Not loaded")
        try:
            # Assumes the JSON file is a top-level list of preference objects
            data = json.load(self._file_handle)
            for record in data:
                self._row_count += 1
                yield record
        finally:
            if self._file_handle:
                self._file_handle.close()

    def metadata(self) -> Dict[str, Any]:
        return {"source": str(self.source), "format": "json", "rows_read": self._row_count}
