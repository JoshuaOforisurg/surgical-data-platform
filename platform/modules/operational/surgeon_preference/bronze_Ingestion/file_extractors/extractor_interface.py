from abc import ABC, abstractmethod
from typing import Dict, Generator, Any


class BaseExtractor(ABC):
    """
    A unified interface for all ingestion extractors.
    Each extractor must load a source and yield raw clinical records.
    """

    def __init__(self, source: Any):
        self.source = source

    @abstractmethod
    def load(self) -> None:
        """
        Prepare the extractor (open file, parse JSON, connect to API, etc.)
        """
        pass

    @abstractmethod
    def extract(self) -> Generator[Dict[str, Any], None, None]:
        """
        Yield one raw clinical record at a time.
        Each record must be a dict matching the raw domain model.
        """
        pass

    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """
        Return ingestion metadata (file size, row count, timestamps, etc.)
        Useful for logging and audit trails.
        """
        pass

    # --- Added Python Context Management Helpers ---

    def __enter__(self):
        """Automatically calls load when entering a 'with' block."""
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # This ensures errors bubble up instead of vanishing!

    def close(self) -> None:
        """
        Optional cleanup method.
        Override this in child classes (like CSV) to safely close files.
        """
        pass
