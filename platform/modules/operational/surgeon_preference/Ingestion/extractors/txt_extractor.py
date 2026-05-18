from pathlib import Path
from typing import Any, Dict, Generator, Optional
from extractor_interface import BaseExtractor


class TXTExtractor(BaseExtractor):
    """
    TXT implementation of the BaseExtractor for unstructured surgeon data.
    Streams non-empty lines cleanly to prevent memory spikes.
    """

    def __init__(self, source: Any):
        super().__init__(source)
        self._file_handle: Optional[Any] = None
        self._line_count: int = 0

    def load(self) -> None:
        """
        Open the TXT file and reset tracking counters.
        """
        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"Source text file not found: {path}")

        self._file_handle = path.open("r", encoding="utf-8")
        self._line_count = 0

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        """
        Stream text rows line-by-line as raw payloads.
        """
        if self._file_handle is None:
            raise RuntimeError("Extractor not loaded. Call load() first.")

        for raw_line in self._file_handle:
            self._line_count += 1
            clean_line = raw_line.strip()

            # Skip entirely blank operational spaces or breaks
            if not clean_line:
                continue

            # Yielding a raw dictionary structure fits your pipeline interface
            yield {
                "raw_text_line": clean_line,
                "line_number": self._line_count
            }

    def close(self) -> None:
        """
        Safely shut down the file stream stream.
        """
        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()

    def metadata(self) -> Dict[str, Any]:
        """
        Basic metadata tracking for unstructured data file tracking.
        """
        path = Path(self.source)
        return {
            "source": str(path),
            "format": "txt",
            "size_bytes": path.stat().st_size if path.exists() else None,
            "total_lines_processed": self._line_count,
        }
