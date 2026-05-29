from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import csv
import PyPDF2  # For PDFs
import pandas as pd  # For CSVs and TXTs
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileReader:
    """
    Reads files of different formats (PDF, TXT, CSV, JSON, XLSX, XML) and extracts data.
    Returns a consistent dictionary structure for each file.
    """

    @staticmethod
    def read_file(file_path: Path) -> Dict[str, Any]:
        """
        Read a file based on its extension and return its data as a dictionary.
        """
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
            logger.error(f"Error reading file {file_path}: {e}")
            raise

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
    def _read_csv(file_path: Path, chunk_size: Optional[int] = None) -> Dict[str, Any]:
        """Read a CSV file and return as a dictionary."""
        if chunk_size:
            # Process CSV in chunks for large files
            chunks = pd.read_csv(file_path, chunksize=chunk_size)
            data = [chunk.to_dict(orient="records") for chunk in chunks]
        else:
            data = pd.read_csv(file_path).to_dict(orient="records")
        return {"content": data, "metadata": {"file_type": "csv"}}

    @staticmethod
    def _read_json(file_path: Path) -> Dict[str, Any]:
        """Read a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"content": data, "metadata": {"file_type": "json"}}

    @staticmethod
    def _read_excel(file_path: Path) -> Dict[str, Any]:
        """Read an Excel file."""
        data = pd.read_excel(file_path).to_dict(orient="records")
        return {"content": data, "metadata": {"file_type": "xlsx"}}

    @staticmethod
    def _read_xml(file_path: Path) -> Dict[str, Any]:
        """Read an XML file."""
        import xml.etree.ElementTree as ET
        tree = ET.parse(file_path)
        root = tree.getroot()
        data = [{"tag": elem.tag, "text": elem.text} for elem in root.iter()]
        return {"content": data, "metadata": {"file_type": "xml"}}
