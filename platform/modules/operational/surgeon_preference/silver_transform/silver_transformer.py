from pathlib import Path
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from file_format_reader import FileReader
from config.paths import SILVER_A_DIR


class SilverTransformer:
    """
    Silver-A transformer for surgical preference data.

    Converts raw bronze-extracted files into a clean, flattened analytical format.
    Handles both flat CSV-style rows and nested JSON structures safely.
    """

    def __init__(self, silver_a_dir=SILVER_A_DIR):
        self.silver_a_dir = Path(silver_a_dir)
        self.silver_a_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Helpers
    # -----------------------------
    def clean_str(self, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    def safe_get(self, d: Any, key: str, default=None):
        """Safely get key from dict-like object."""
        if isinstance(d, dict):
            return d.get(key, default)
        return default

    def normalise_content(self, content: Any) -> Dict[str, Any]:
        """
        Normalises content into a consistent dict structure.

        Handles:
        - Flat CSV rows
        - Nested surgical JSON
        """
        if content is None:
            return {}

        # Case 1: already structured nested dict
        if isinstance(content, dict):
            return content

        # Case 2: list (CSV chunk or multi-row input)
        if isinstance(content, list):
            # Take first row only for Silver-A row-level processing
            first = content[0] if content else {}
            return first if isinstance(first, dict) else {}

        return {}

    # -----------------------------
    # Core transformation
    # -----------------------------
    def flatten_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten bronze file into Silver-A row.
        """
        metadata = card.get("metadata", {})
        content_raw = card.get("content", {})

        content = self.normalise_content(content_raw)

        # Detect flat CSV-style row (no nested surgeon/procedure structure)
        is_flat = any(
            k in content for k in [
                "surgeon_name",
                "surgeon_id",
                "procedure_name",
                "procedure_code"
            ]
        )

        if is_flat:
            surgeon_id = self.clean_str(content.get("surgeon_id"))
            surgeon_name = self.clean_str(content.get("surgeon_name"))
            surgeon_specialty = self.clean_str(content.get("specialty"))

            procedure_name = self.clean_str(content.get("procedure_name"))
            procedure_code = self.clean_str(content.get("procedure_code"))
            procedure_subspecialty = self.clean_str(content.get("subspecialty"))
            procedure_type = self.clean_str(content.get("surgery_type"))

        else:
            surgeon = content.get("surgeon", {})
            procedure = content.get("procedure", {})

            surgeon_id = self.clean_str(surgeon.get("id"))
            surgeon_name = self.clean_str(surgeon.get("full_name"))
            surgeon_specialty = self.clean_str(surgeon.get("specialty"))

            procedure_name = self.clean_str(procedure.get("name"))
            procedure_code = self.clean_str(procedure.get("code"))
            procedure_subspecialty = self.clean_str(procedure.get("subspecialty"))
            procedure_type = self.clean_str(procedure.get("surgery_type"))

        return {
            "file_name": metadata.get("file_name", ""),
            "file_type": metadata.get("file_type", ""),

            "surgeon_id": surgeon_id,
            "surgeon_name": surgeon_name,
            "surgeon_specialty": surgeon_specialty,

            "procedure_code": procedure_code,
            "procedure_name": procedure_name,
            "procedure_subspecialty": procedure_subspecialty,
            "procedure_surgery_type": procedure_type,

            "glove_size": self.clean_str(content.get("glove_size")),

            "anaesthetic_notes": self.clean_str(self.safe_get(content, "anaesthetic_notes")),
            "positioning_description": self.clean_str(self.safe_get(content, "positioning_description")),
            "operating_theatre_description": self.clean_str(self.safe_get(content, "operating_theatre_description")),
            "skin_prep_description": self.clean_str(self.safe_get(content, "skin_prep_description")),

            "instruments": json.dumps(content.get("instruments", [])),
            "equipment": json.dumps(content.get("equipment", [])),
            "draping": json.dumps(content.get("draping", [])),
            "consumables": json.dumps(content.get("consumables", [])),
            "disposables": json.dumps(content.get("disposables", [])),
            "implants": json.dumps(content.get("implants", [])) if content.get("implants") else None,
            "sutures": json.dumps(content.get("sutures", [])),
            "dressings": json.dumps(content.get("dressings", [])),

            "version_number": self.safe_get(content.get("version", {}), "version"),
            "version_updated_by": self.clean_str(self.safe_get(content.get("version", {}), "updated_by")),
            "source_system": self.clean_str(content.get("source_system")),

            "processed_at": datetime.utcnow().isoformat(),
            "pipeline_version": "silver_a_v2",
        }

    # -----------------------------
    # IO
    # -----------------------------
    def write_silver_a(self, cleaned_rows: List[Dict[str, Any]]):
        if not cleaned_rows:
            raise ValueError("Silver-A produced no rows. Check input data pipeline.")

        output_file = self.silver_a_dir / "silver_a_cleaned.jsonl"

        with output_file.open("w", encoding="utf-8") as f:
            for row in cleaned_rows:
                f.write(json.dumps(row) + "\n")

    # -----------------------------
    # Pipeline entrypoint
    # -----------------------------
    def transform_files(self, file_paths: List[Path]):
        cleaned_rows = []

        for file_path in file_paths:
            try:
                file_data = FileReader.read_file(file_path)

                file_data["metadata"] = file_data.get("metadata", {})
                file_data["metadata"]["file_name"] = file_path.name

                row = self.flatten_card(file_data)
                cleaned_rows.append(row)

            except Exception as e:
                raise RuntimeError(f"Failed processing {file_path}") from e

        self.write_silver_a(cleaned_rows)
        return cleaned_rows