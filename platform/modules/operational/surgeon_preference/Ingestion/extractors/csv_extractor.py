import csv
from pathlib import Path
from typing import Any, Dict, Generator, Optional
import datetime

from extractor_interface import BaseExtractor


class CSVExtractor(BaseExtractor):
    """
    CSV implementation of BaseExtractor for surgeon preference data.
    Streams raw data exactly as received for auditing and tracking.
    """

    def __init__(self, source: Any):
        super().__init__(source)
        self._file_handle: Optional[Any] = None
        self._reader: Optional[csv.DictReader] = None
        self._row_count: int = 0
        self._loaded_at: Optional[str] = None

    def load(self) -> None:
        """
        Open the CSV file and prepare the DictReader without pre-reading data.
        """
        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"Surgeon data file not found: {path}")

        self._file_handle = path.open("r", newline="", encoding="utf-8")
        self._reader = csv.DictReader(self._file_handle)
        self._row_count = 0
        self._loaded_at = datetime.datetime.utcnow().isoformat() + "Z"

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        """
        Stream raw surgeon rows safely. Guarantees file closure on error.
        """
        if self._reader is None:
            raise RuntimeError("Extractor not loaded. Call load() first.")

        try:
            for row in self._reader:
                self._row_count += 1
                # Yield raw text exactly as it appears in the CSV
                yield dict(row)
        finally:
            # Safely closes the file even if a row corrupts mid-stream
            if self._file_handle and not self._file_handle.closed:
                self._file_handle.close()

    def metadata(self) -> Dict[str, Any]:
        """
        Audit trails for surgeon data tracking.
        """
        path = Path(self.source)
        return {
            "source": str(path),
            "format": "csv",
            "size_bytes": path.stat().st_size if path.exists() else None,
            "rows_read": self._row_count,
            "columns": self._reader.fieldnames if self._reader else None,
            "extracted_at": self._loaded_at,
        }
