from pathlib import Path
from typing import Any, Dict, Generator, Optional
import datetime

from extractors.extractor_interface import BaseExtractor


class TXTExtractor(BaseExtractor):
    """
    Streams unstructured TXT data line-by-line for ingestion.
    """

    def __init__(self, source: Any):
        super().__init__(source)

        self._file_handle: Optional[Any] = None
        self._line_count: int = 0
        self._loaded_at: Optional[str] = None

    def load(self) -> None:
        """
        Opens TXT file safely and resets counters.
        """

        path = Path(self.source)

        if not path.exists():
            raise FileNotFoundError(
                f"Source text file not found: {path}"
            )

        self._file_handle = path.open(
            "r",
            encoding="utf-8-sig"
        )

        self._line_count = 0

        self._loaded_at = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        """
        Streams non-empty lines safely.
        """

        if self._file_handle is None:
            raise RuntimeError(
                "Extractor not loaded. Call load() first."
            )

        data_line_number = 0

        for raw_line in self._file_handle:
            clean_line = raw_line.strip()

            # skip blank lines
            if not clean_line:
                continue

            data_line_number += 1
            self._line_count += 1

            yield {
                "raw_text_line": clean_line,
                "line_number": data_line_number
            }

    def metadata(self) -> Dict[str, Any]:
        """
        Ingestion metadata for auditing.
        """

        path = Path(self.source)

        return {
            "source": str(path),
            "format": "txt",
            "size_bytes": (
                path.stat().st_size
                if path.exists()
                else None
            ),
            "lines_read": self._line_count,
            "extracted_at": self._loaded_at,
        }

    def close(self) -> None:
        """
        Safely closes file handle.
        """

        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()