import json
import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from extractors.extractor_interface import BaseExtractor


class JsonExtractor(BaseExtractor):
    """
    JSON extractor for surgeon preference data.
    Supports a top-level list of records.
    """

    def __init__(self, source: Any):
        super().__init__(source)

        self._file_handle: Optional[Any] = None
        self._row_count: int = 0
        self._loaded_at: Optional[str] = None

    def load(self) -> None:
        """
        Open JSON file safely.
        """

        path = Path(self.source)

        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        self._file_handle = path.open(
            "r",
            encoding="utf-8"
        )

        self._row_count = 0

        self._loaded_at = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        """
        Stream JSON records.
        Assumes top-level list structure.
        """

        if self._file_handle is None:
            raise RuntimeError("Extractor not loaded. Call load() first.")

        try:
            data = json.load(self._file_handle)

            if not isinstance(data, list):
                raise ValueError(
                    "Expected top-level JSON list of records"
                )

            for record in data:
                self._row_count += 1
                yield record

        finally:
            self.close()

    def metadata(self) -> Dict[str, Any]:
        """
        Ingestion metadata for auditing.
        """

        path = Path(self.source)

        return {
            "source": str(path),
            "format": "json",
            "size_bytes": (
                path.stat().st_size
                if path.exists()
                else None
            ),
            "rows_read": self._row_count,
            "extracted_at": self._loaded_at,
        }

    def close(self) -> None:
        """
        Safely close file handle.
        """

        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()