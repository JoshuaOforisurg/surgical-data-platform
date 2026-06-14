from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(log_dir: str | Path = "logs", level: int = logging.INFO) -> logging.Logger:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_path / "surgeon_preference_pipeline.log")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    return logging.getLogger("surgeon_preference_pipeline")
