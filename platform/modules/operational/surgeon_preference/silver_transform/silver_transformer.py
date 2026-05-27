# silver_transformer.py
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
from file_format_reader import FileReader  # Import the FileReader class

class SilverTransformer:
    """
    Transforms data from files (PDF, TXT, CSV, JSON) into flattened, cleaned Silver-A rows.
    """

    def __init__(self, silver_a_dir: str = "data/silver_a_cleaned"):
        self.silver_a_dir = Path(silver_a_dir)
        self.silver_a_dir.mkdir(parents=True, exist_ok=True)

    def clean_str(self, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    def flatten_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten a card (dictionary) into a Silver-A row.
        Assumes the card has a 'content' key with the extracted data.
        """
        # Handle nested JSON data (e.g., from CSV or JSON files)
        if isinstance(card["content"], list):
            # If content is a list (e.g., CSV rows), process the first row
            content = card["content"] if card["content"] else {}
        else:
            content = card["content"]

        return {
            "file_name": card["metadata"].get("file_name", ""),
            "file_type": card["metadata"].get("file_type", ""),
            "surgeon_id": self.clean_str(content.get("surgeon", {}).get("id")),
            "surgeon_name": self.clean_str(content.get("surgeon", {}).get("full_name")),
            "surgeon_specialty": self.clean_str(content.get("surgeon", {}).get("specialty")),
            "glove_size": self.clean_str(content.get("surgeon", {}).get("glove_size")),
            "procedure_code": self.clean_str(content.get("procedure", {}).get("code")),
            "procedure_name": self.clean_str(content.get("procedure", {}).get("name")),
            "procedure_subspecialty": self.clean_str(content.get("procedure", {}).get("subspecialty")),
            "procedure_surgery_type": self.clean_str(content.get("procedure", {}).get("surgery_type")),
            "anaesthetic_notes": self.clean_str(content.get("anaesthetic", {}).get("notes")),
            "positioning_description": self.clean_str(content.get("positioning", {}).get("description")),
            "operating_theatre_description": self.clean_str(content.get("operating_theatre", {}).get("description")),
            "skin_prep_description": self.clean_str(content.get("skin_prep", {}).get("description")),
            "instruments": json.dumps(content.get("instruments", [])),
            "equipment": json.dumps(content.get("equipment", [])),
            "draping": json.dumps(content.get("draping", [])),
            "consumables": json.dumps(content.get("consumables", [])),
            "disposables": json.dumps(content.get("disposables", [])),
            "implants": json.dumps(content.get("implants", [])) if content.get("implants") else None,
            "sutures": json.dumps(content.get("sutures", [])),
            "dressings": json.dumps(content.get("dressings", [])),
            "version_number": content.get("version", {}).get("version"),
            "version_updated_by": self.clean_str(content.get("version", {}).get("updated_by")),
            "source_system": self.clean_str(content.get("source_system")),
            "processed_at": datetime.utcnow().isoformat(),
            "pipeline_version": "silver_a_v1",
        }

    def write_silver_a(self, cleaned_rows: List[Dict[str, Any]]):
        """Write Silver-A cleaned rows to disk as JSONL."""
        output_file = self.silver_a_dir / "silver_a_cleaned.jsonl"
        with output_file.open("w", encoding="utf-8") as f:
            for row in cleaned_rows:
                f.write(json.dumps(row) + "\n")

    def transform_files(self, file_paths: List[Path]):
        """
        Process a list of files (PDF, TXT, CSV, JSON) and write cleaned data to Silver-A.
        """
        cleaned_rows = []
        for file_path in file_paths:
            try:
                file_data = FileReader.read_file(file_path)
                file_data["metadata"]["file_name"] = file_path.name
                cleaned_row = self.flatten_card(file_data)
                cleaned_rows.append(cleaned_row)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        self.write_silver_a(cleaned_rows)
        return cleaned_rows
