import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


class QuarantineHandler:
    """
    Handles invalid rows by streaming them straight to disk with error messages
    for audit, debugging, and clinical safety. Uses zero persistent memory.
    """

    def __init__(self, output_dir: str = "quarantine"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate a truly unique file name per pipeline invocation
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:6]  # Prevents name collisions across processes
        self.file_path = self.output_dir / f"quarantine_{ts}_{unique_id}.jsonl"

        self._file_handle = None
        self._row_count = 0

    def add(self, raw_row: Dict[str, Any], error: str, source: str) -> None:
        """
        Immediately append a quarantined row to disk. Uses zero RAM.
        """
        # Open the file only when the first error occurs (Lazy Initialisation)
        if self._file_handle is None:
            self._file_handle = self.file_path.open("w", encoding="utf-8")

        quarantine_entry = {
            "raw": raw_row,
            "error": error,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Write as JSON Lines (one JSON object per line) for optimal streaming performance
        self._file_handle.write(json.dumps(quarantine_entry) + "\n")
        self._row_count += 1

    def flush(self) -> Path | None:
        """
        Safely closes the file stream. Returns the file path if entries were logged.
        """
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None

        if self._row_count == 0:
            # Clean up the empty tracking link if no errors occurred
            return None

        return self.file_path
