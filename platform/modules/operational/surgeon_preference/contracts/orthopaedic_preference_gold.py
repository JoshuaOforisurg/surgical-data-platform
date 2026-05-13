from pydantic import BaseModel, Field, field_validator
from datetime import datetime

# -----------------------------------------
# CANONICAL MAPPINGS
# -----------------------------------------

SPECIALITY_CANONICAL = "Orthopaedics"

SUBSPECIALITY_MAP = {
    "joints": "Joints",
    "joint": "Joints",
    "arthroplasty": "Joints",
    "trauma": "Trauma",
    "fracture": "Trauma",
    "spine": "Spine",
    "paediatric": "Paediatric",
    "paeds": "Paediatric",
    "foot and ankle": "Foot And Ankle",
    "foot & ankle": "Foot And Ankle",
    "faa": "Foot And Ankle",
}

RETRACTOR_MAP = {
    "small": "Small",
    "sm": "Small",
    "medium": "Medium",
    "med": "Medium",
    "large": "Large",
    "lg": "Large",
    "extra large": "Extra Large",
    "xl": "Extra Large",
}

DRILL_BRAND_MAP = {
    "stryker": "Stryker",
    "depuy": "Depuy Synthes",
    "depuy synthes": "Depuy Synthes",
    "arthrex": "Arthrex V300",
    "arthrex v300": "Arthrex V300",
    "zimmer": "Zimmer Biomet",
    "zimmer biomet": "Zimmer Biomet",
    "smith & nephew": "Smith & Nephew",
    "medtronic": "Medtronic",
}

# -----------------------------------------
# PROCEDURE ↔ SUBSPECIALITY MAPPING
# -----------------------------------------

PROCEDURE_SUBSPECIALITY_RULES = {
    "joints": ["knee", "hip", "arthroplasty", "replacement", "revision"],
    "trauma": ["fracture", "fixation", "nailing", "open reduction"],
    "spine": ["lumbar", "cervical", "decompression", "fusion"],
    "paediatric": ["clubfoot", "slipped", "paediatric"],
    "foot and ankle": ["achilles", "ankle", "foot", "tendon"],
}

# -----------------------------------------
# GOLD MODEL
# -----------------------------------------

class OrthopaedicPreferenceGold(BaseModel):
    surgeon_id: int = Field(..., ge=1000, le=9999)
    surgeon_name: str
    speciality: str
    subspeciality: str
    procedure: str
    instrument: str
    preferred_retractor_size: str
    preferred_drill_brand: str
    needs_backup_suction: bool
    years_of_experience: int = Field(..., ge=1, le=40)
    hospital_affiliation: str
    generation_timestamp: datetime

    # -----------------------------------------
    # VALIDATORS
    # -----------------------------------------

    @field_validator("speciality")
    def normalise_speciality(cls, v):
        return SPECIALITY_CANONICAL

    @field_validator("subspeciality")
    def normalise_subspeciality(cls, v):
        key = v.strip().lower()
        if key not in SUBSPECIALITY_MAP:
            raise ValueError(f"Unknown subspeciality: {v}")
        return SUBSPECIALITY_MAP[key]

    @field_validator("preferred_retractor_size")
    def normalise_retractor_size(cls, v):
        key = v.strip().lower()
        if key not in RETRACTOR_MAP:
            raise ValueError(f"Unknown retractor size: {v}")
        return RETRACTOR_MAP[key]

    @field_validator("preferred_drill_brand")
    def normalise_drill_brand(cls, v):
        key = v.strip().lower()
        if key not in DRILL_BRAND_MAP:
            raise ValueError(f"Unknown drill brand: {v}")
        return DRILL_BRAND_MAP[key]

    @field_validator("surgeon_name")
    def clean_surgeon_name(cls, v):
        v = v.replace("Dr.", "").replace("Mr.", "").strip()
        if not any(c.isalpha() for c in v):
            raise ValueError("surgeon_name must contain alphabetic characters")
        return v

    @field_validator("procedure")
    def validate_procedure(cls, v, info):
        proc = v.lower()

        # Pydantic v2: use info.data instead of values
        subspec = info.data.get("subspeciality", "").lower()

        allowed_keywords = PROCEDURE_SUBSPECIALITY_RULES.get(subspec, [])
        if not any(k in proc for k in allowed_keywords):
            raise ValueError(
                f"Procedure '{v}' does not match subspeciality '{subspec}'"
            )

        if any(x in proc for x in ["test", "dummy", "sample"]):
            raise ValueError("procedure contains non-clinical placeholder text")

        return v.title()

    @field_validator("generation_timestamp")
    def validate_timestamp(cls, v):
        if v.year < 2020:
            raise ValueError("timestamp is unrealistically old")
        return v
