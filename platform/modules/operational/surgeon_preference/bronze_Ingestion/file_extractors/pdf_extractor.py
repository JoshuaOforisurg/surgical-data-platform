from pathlib import Path
from typing import Any, Dict, Generator, Optional
import datetime
import pypdf

from extractor_interface import BaseExtractor


class PdfExtractor(BaseExtractor):
    """
    Extracts raw text from PDF pages for ingestion into surgeon preference pipeline.
    """

    def __init__(self, source: Any):
        super().__init__(source)

        self._reader: Optional[pypdf.PdfReader] = None
        self._pages_read: int = 0
        self._loaded_at: Optional[str] = None

    def load(self) -> None:
        path = Path(self.source)

        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        self._reader = pypdf.PdfReader(path)
        self._pages_read = 0

        self._loaded_at = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        if self._reader is None:
            raise RuntimeError("Extractor not loaded. Call load() first.")

        for page_num, page in enumerate(self._reader.pages):
            self._pages_read += 1

            text = page.extract_text()

            yield {
                "page_number": page_num + 1,
                "raw_text": text if text else ""
            }

    def metadata(self) -> Dict[str, Any]:
        path = Path(self.source)

        return {
            "source": str(path),
            "format": "pdf",
            "size_bytes": (
                path.stat().st_size
                if path.exists()
                else None
            ),
            "pages_read": self._pages_read,
            "extracted_at": self._loaded_at,
        }

    def close(self) -> None:
        """
        Placeholder for interface consistency.
        PdfReader does not require explicit closure.
        """
        self._reader = None