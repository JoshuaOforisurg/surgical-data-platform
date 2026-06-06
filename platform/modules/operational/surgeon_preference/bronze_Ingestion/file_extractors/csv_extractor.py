import csv
import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from extractor_interface import BaseExtractor


class CSVExtractor(BaseExtractor):
    """
    CSV implementation of BaseExtractor for surgeon preference data.
    Streams raw data exactly as received for auditing and traceability.
    """

    def __init__(self, source: Any):
        super().__init__(source)

        self._file_handle: Optional[Any] = None
        self._reader: Optional[csv.DictReader] = None

        self._row_count: int = 0
        self._loaded_at: Optional[str] = None

    def load(self) -> None:
        """
        Opens the CSV file and prepares the DictReader.
        """

        path = Path(self.source)

        if not path.exists():
            raise FileNotFoundError(
                f"Surgeon data file not found: {path}"
            )

        # utf-8-sig handles Excel BOM issues safely
        self._file_handle = path.open(
            mode="r",
            newline="",
            encoding="utf-8-sig"
        )

        self._reader = csv.DictReader(self._file_handle)

        self._row_count = 0

        self._loaded_at = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        """
        Streams raw CSV rows one at a time.
        """

        if self._reader is None:
            raise RuntimeError(
                "Extractor not loaded. Call load() first."
            )

        for row in self._reader:
            self._row_count += 1

            # Preserve raw values exactly as ingested
            yield dict(row)

    def metadata(self) -> Dict[str, Any]:
        """
        Returns ingestion metadata for logging/auditing.
        """

        path = Path(self.source)

        return {
            "source": str(path),
            "format": "csv",
            "size_bytes": (
                path.stat().st_size
                if path.exists()
                else None
            ),
            "rows_read": self._row_count,
            "columns": (
                self._reader.fieldnames
                if self._reader
                else []
            ),
            "extracted_at": self._loaded_at,
        }

    def close(self) -> None:
        """
        Safely closes the file handle.
        """

        if (
            self._file_handle
            and not self._file_handle.closed
        ):
            self._file_handle.close()