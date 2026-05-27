# file_reader.py
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import csv
import PyPDF2  # For PDFs
import pandas as pd  # For CSVs and TXTs
from datetime import datetime

class FileReader:
    """
    Reads files of different formats (PDF, TXT, CSV, JSON) and extracts data.
    Returns a consistent dictionary structure for each file.
    """

    @staticmethod
    def read_file(file_path: Path) -> Dict[str, Any]:
        """
        Read a file based on its extension and return its data as a dictionary.
        """
        extension = file_path.suffix.lower()

        if extension == ".pdf":
            return FileReader._read_pdf(file_path)
        elif extension == ".txt":
            return FileReader._read_txt(file_path)
        elif extension == ".csv":
            return FileReader._read_csv(file_path)
        elif extension == ".json":
            return FileReader._read_json(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    @staticmethod
    def _read_pdf(file_path: Path) -> Dict[str, Any]:
        """Read a PDF file and extract text."""
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([page.extract_text() for page in reader.pages])
        return {"content": text, "metadata": {"file_type": "pdf"}}

    @staticmethod
    def _read_txt(file_path: Path) -> Dict[str, Any]:
        """Read a TXT file."""
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {"content": text, "metadata": {"file_type": "txt"}}

    @staticmethod
    def _read_csv(file_path: Path) -> Dict[str, Any]:
        """Read a CSV file and return as a dictionary."""
        data = pd.read_csv(file_path).to_dict(orient="records")
        return {"content": data, "metadata": {"file_type": "csv"}}

    @staticmethod
    def _read_json(file_path: Path) -> Dict[str, Any]:
        """Read a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"content": data, "metadata": {"file_type": "json"}}
