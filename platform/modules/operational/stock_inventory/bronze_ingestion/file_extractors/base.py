from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator


class BaseExtractor(ABC):
    format_name: str

    def __init__(self, source_path: Path | str):
        self.source_path = Path(source_path)

    @abstractmethod
    def extract(self) -> Iterator[dict[str, Any]]:
        """Yield raw records from the source file."""

