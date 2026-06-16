from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import re
from datetime import datetime, UTC

from config.paths import SILVER_A_DIR
from silver_transform.silver_a.file_format_reader import FileReader


def clean_text(v: Any, case_style: Optional[str] = None) -> Optional[str]:
    """Strips whitespace and standardises casing."""
    if v is None:
        return None

    s = str(v).strip()
    if not s:
        return None

    if case_style == "title":
        return s.title()
    elif case_style == "upper":
        return s.upper()
    elif case_style == "lower":
        return s.lower()
    return s


class SilverTransformer:
    """
    Silver-A transformer for surgical preference data.

    Responsibility: Purely structural and basic data sanitization.
    - Trims all hidden/dirty whitespace.
    - Standardizes text casing (Title Case for names/specialties, UPPERCASE for codes).
    - Ensures valid schema extraction and production-safe fallback types.
    """

    def __init__(self, silver_a_dir=SILVER_A_DIR):
        self.silver_a_dir = Path(silver_a_dir)
        self.silver_a_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Basic Cleaning Helpers (Silver-A Scope)
    # -----------------------------

    def safe_get(self, d: Any, key: str, default=None):
        if isinstance(d, dict):
            return d.get(key, default)
        return default

    def nested_get(self, d: Any, key: str, nested_key: str = "description", default=None):
        value = self.safe_get(d, key)
        if isinstance(value, dict):
            return value.get(nested_key, default)
        return value if value is not None else default

    def normalise_content(self, content: Any) -> Dict[str, Any]:
        if content is None:
            return {}
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            first = content[0] if content else {}
            return first if isinstance(first, dict) else {}
        return {}

    def clean_code_list(self, codes: Any) -> List[str]:
        """Ensures codes are structured as lists, stripped, and uppercase."""
        if not codes:
            return []
        if isinstance(codes, str) and "," in codes:
            codes = [code.strip() for code in codes.split(",")]
        if isinstance(codes, str):
            codes = [codes]
        return [
            clean_text(c, case_style="upper")
            for c in codes
            if clean_text(c) is not None
        ]

    def structural_items_json(self, value: Any) -> str:
        if not value:
            return json.dumps([])
        if isinstance(value, list):
            return json.dumps(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return json.dumps(parsed)
            except json.JSONDecodeError:
                pass
            items = []
            for part in value.split(","):
                item_text = part.strip()
                if not item_text:
                    continue
                quantity_match = re.search(r"\(x(-?\d+)\)", item_text)
                quantity = int(quantity_match.group(1)) if quantity_match else 1
                name = re.sub(r"\s*\(x-?\d+\)\s*", "", item_text).strip()
                name = re.sub(r"\s*\[Size:[^\]]+\]\s*", "", name).strip()
                if name and name.upper() != "N/A":
                    items.append({"name": name, "quantity": quantity})
            return json.dumps(items)
        return json.dumps([])

    # -----------------------------
    # Core transformation
    # -----------------------------
    def flatten_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        metadata = card.get("metadata", {}) or {}
        content_raw = card.get("content", {})
        content = self.normalise_content(content_raw)
        surgeon: Dict[str, Any] = {}

        # Detect flat schema variations
        is_flat = any(
            k in content for k in [
                "surgeon_name", "surgeon_id", "procedure_name", "procedure_code"
            ]
        )

        if is_flat:
            surgeon_id = clean_text(content.get("surgeon_id"))
            surgeon_name = clean_text(content.get("surgeon_name"), case_style="title")
            surgeon_specialty = clean_text(content.get("specialty"), case_style="title")

            procedure_name = clean_text(content.get("procedure_name"), case_style="title")
            procedure_codes = self.clean_code_list(
                content.get("procedure_code") or content.get("procedure_codes")
            )
            diagnosis_codes = self.clean_code_list(
                content.get("diagnosis_code") or content.get("diagnosis_codes")
            )

            procedure_subspecialty = clean_text(content.get("subspecialty"), case_style="title")
            procedure_type = clean_text(content.get("surgery_type"), case_style="title")
        else:
            surgeon_raw = content.get("surgeon", {})
            procedure_raw = content.get("procedure", {})

            surgeon = surgeon_raw if isinstance(surgeon_raw, dict) else {"full_name": surgeon_raw}
            procedure = procedure_raw if isinstance(procedure_raw, dict) else {"name": procedure_raw}

            surgeon_id = clean_text(surgeon.get("id"))
            surgeon_name = clean_text(surgeon.get("full_name"), case_style="title")

            # Robust extraction matching messiness generator and standard nested layouts
            raw_specialty = content.get("specialty") or surgeon.get("specialty")
            surgeon_specialty = clean_text(raw_specialty, case_style="title")

            procedure_name = clean_text(procedure.get("name"), case_style="title")
            procedure_codes = self.clean_code_list(procedure.get("procedure_codes") or procedure.get("code"))
            diagnosis_codes = self.clean_code_list(procedure.get("diagnosis_codes"))

            procedure_subspecialty = clean_text(procedure.get("subspecialty") or procedure.get("sub_specialty"),
                                                     case_style="title")
            procedure_type = clean_text(procedure.get("surgery_type") or procedure.get("type"), case_style="title")

        # Basic text cleaning for notes (preserving typos for Silver-B processing)
        special_instructions = content.get("special_instructions", {})
        notes_raw = special_instructions.get("notes") if isinstance(special_instructions, dict) else None

        anaesthetic_notes = clean_text(
            self.safe_get(content, "anaesthetic_notes")
            or self.nested_get(content, "anaesthetic", "notes")
        )
        positioning_description = clean_text(
            self.safe_get(content, "positioning_description")
            or self.nested_get(content, "positioning")
        )
        operating_theatre_description = clean_text(
            self.safe_get(content, "operating_theatre_description")
            or self.nested_get(content, "operating_theatre")
        )
        skin_prep_description = clean_text(
            self.safe_get(content, "skin_prep_description")
            or self.safe_get(content, "skin_prep_desc")
            or self.nested_get(content, "skin_prep")
        )
        instrument_system = clean_text(
            self.safe_get(content, "instrument_system")
            or self.safe_get(content, "instrument_set")
            or self.safe_get(content, "system")
        )
        implant_system = clean_text(
            self.safe_get(content, "implant_system")
            or self.safe_get(content, "implant_set")
        )

        return {
            "file_name": metadata.get("file_name", ""),
            "file_type": metadata.get("file_type", ""),

            "surgeon_id": surgeon_id,
            "surgeon_name": surgeon_name,
            "surgeon_specialty": surgeon_specialty,

            "procedure_name": procedure_name,
            "procedure_codes": json.dumps(procedure_codes),
            "diagnosis_codes": json.dumps(diagnosis_codes),
            "procedure_subspecialty": procedure_subspecialty,
            "procedure_surgery_type": procedure_type,

            "glove_size": clean_text(surgeon.get("glove_size") if not is_flat else content.get("glove_size")),

            "special_instructions_notes": clean_text(notes_raw),
            "anaesthetic_notes": anaesthetic_notes,
            "positioning_description": positioning_description,
            "operating_theatre_description": operating_theatre_description,
            "skin_prep_description": skin_prep_description,
            "instrument_system": instrument_system,
            "implant_system": implant_system,

            # Structural arrays kept intact as raw strings for Silver-B parsing
            "instruments": self.structural_items_json(content.get("instruments")),
            "equipment": self.structural_items_json(content.get("equipment")),
            "draping": self.structural_items_json(content.get("draping")),
            "consumables": self.structural_items_json(content.get("consumables")),
            "disposables": self.structural_items_json(content.get("disposables")),
            "implants": self.structural_items_json(content.get("implants")) if content.get("implants") else None,
            "sutures": self.structural_items_json(content.get("sutures")),
            "dressings": self.structural_items_json(content.get("dressings")),

            "version_number": self.safe_get(content.get("version", {}), "version"),
            "version_updated_by": clean_text(self.safe_get(content.get("version", {}), "updated_by")),
            "source_system": clean_text(content.get("source_system")),

            "processed_at": datetime.now(UTC).isoformat(),
            "pipeline_version": "silver_a_v4",
        }

    # -----------------------------
    # EXECUTION PIPELINES
    # -----------------------------
    def transform_records(self, bronze_data: List[Dict[str, Any]]):
        cleaned_rows = []
        for record in bronze_data:
            row = self.flatten_card({"metadata": {}, "content": record})
            cleaned_rows.append(row)
        self.write_silver_a(cleaned_rows)
        return cleaned_rows

    def write_silver_a(self, cleaned_rows: List[Dict[str, Any]]):
        if not cleaned_rows:
            raise ValueError("Silver-A produced no rows")
        output_file = self.silver_a_dir / "silver_a_cleaned.jsonl"
        with output_file.open("w", encoding="utf-8") as f:
            for row in cleaned_rows:
                f.write(json.dumps(row) + "\n")
