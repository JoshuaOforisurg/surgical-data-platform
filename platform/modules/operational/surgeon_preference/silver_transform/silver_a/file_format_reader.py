from pathlib import Path
from typing import Dict, Any, Optional
import json
import pandas as pd
import logging
import PyPDF2

import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class FileReader:
    """
    Unified file reader for bronze ingestion layer.

    Normalises different file formats into a consistent:
    {
        "content": dict | list,
        "metadata": {...}
    }
    """

    # -------------------------
    # Dispatcher
    # -------------------------
    @staticmethod
    def read_file(file_path: Path) -> Dict[str, Any]:
        extension = file_path.suffix.lower()

        try:
            if extension == ".pdf":
                return FileReader._read_pdf(file_path)
            elif extension == ".txt":
                return FileReader._read_txt(file_path)
            elif extension == ".csv":
                return FileReader._read_csv(file_path)
            elif extension == ".json":
                return FileReader._read_json(file_path)
            elif extension == ".xlsx":
                return FileReader._read_excel(file_path)
            elif extension == ".xml":
                return FileReader._read_xml(file_path)
            else:
                raise ValueError(f"Unsupported file format: {extension}")

        except Exception as e:
            logger.error(f"Failed reading file {file_path}: {e}")
            raise

    # -------------------------
    # PDF
    # -------------------------
    @staticmethod
    def _read_pdf(file_path: Path) -> Dict[str, Any]:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)

            pages_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

        return {
            "content": {
                "raw_text": "\n".join(pages_text)
            },
            "metadata": {
                "file_type": "pdf"
            }
        }

    # -------------------------
    # TXT
    # -------------------------
    @staticmethod
    def _read_txt(file_path: Path) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        return {
            "content": {
                "raw_text": text
            },
            "metadata": {
                "file_type": "txt"
            }
        }

    # -------------------------
    # CSV
    # -------------------------
    @staticmethod
    def _read_csv(file_path: Path, chunk_size: Optional[int] = None) -> Dict[str, Any]:
        if chunk_size:
            chunks = pd.read_csv(file_path, chunksize=chunk_size, keep_default_na=False)
            data = []
            for chunk in chunks:
                data.extend(chunk.to_dict(orient="records"))
        else:
            data = pd.read_csv(file_path, keep_default_na=False).to_dict(orient="records")

        return {
            "content": data,   # list[dict]
            "metadata": {
                "file_type": "csv"
            }
        }

    # -------------------------
    # JSON
    # -------------------------
    @staticmethod
    def _read_json(file_path: Path) -> Dict[str, Any]:
        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            data = []
        else:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = [json.loads(line) for line in text.splitlines() if line.strip()]

        return {
            "content": data,
            "metadata": {
                "file_type": "json"
            }
        }

    # -------------------------
    # Excel
    # -------------------------
    @staticmethod
    def _read_excel(file_path: Path) -> Dict[str, Any]:
        data = pd.read_excel(file_path).to_dict(orient="records")

        return {
            "content": data,
            "metadata": {
                "file_type": "xlsx"
            }
        }

    # -------------------------
    # XML (basic but structured)
    # -------------------------
    @staticmethod
    def _read_xml(file_path: Path) -> Dict[str, Any]:
        tree = ET.parse(file_path)
        root = tree.getroot()

        data = []
        for elem in root:
            data.append({
                "tag": elem.tag,
                "text": elem.text
            })

        return {
            "content": data,
            "metadata": {
                "file_type": "xml"
            }
        }
