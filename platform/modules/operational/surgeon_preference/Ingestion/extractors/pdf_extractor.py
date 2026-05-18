from pathlib import Path
from typing import Any, Dict, Generator
import pypdf  # Standard open-source library for reading PDFs
from extractor_interface import BaseExtractor


class PdfExtractor(BaseExtractor):
    def __init__(self, source: Any):
        super().__init__(source)
        self._reader = None
        self._pages_read = 0

    def load(self) -> None:
        path = Path(self.source)
        # pypdf reads files directly from the path or binary streams
        self._reader = pypdf.PdfReader(path)
        self._pages_read = 0

    def extract(self) -> Generator[Dict[str, Any], None, None]:
        if not self._reader:
            raise RuntimeError("Not loaded")

        for page_num, page in enumerate(self._reader.pages):
            self._pages_read += 1
            text = page.extract_text()
            # Wrap the raw text in a dictionary to match the interface contract
            yield {
                "page_number": page_num + 1,
                "raw_text": text
            }

    def metadata(self) -> Dict[str, Any]:
        return {"source": str(self.source), "format": "pdf", "pages_read": self._pages_read}
