from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# -------------------------
# Core Entities
# -------------------------

class Surgeon(BaseModel):
    id: str
    full_name: str
    specialty: str
    glove_size: Optional[str] = None


class Procedure(BaseModel):
    code: str
    name: str
    subspecialty: Optional[str] = None
    surgery_type: Optional[str] = None


# -------------------------
# Preference Card Sections (Ordered)
# -------------------------

class AnaestheticNotes(BaseModel):  # 0
    notes: Optional[str] = None


class Positioning(BaseModel):  # 1
    description: str
    equipment: Optional[List[str]] = None


class EquipmentItem(BaseModel):  # 2
    name: str
    required: bool = True
    notes: Optional[str] = None


class OperatingTheatre(BaseModel):  # 3
    description: str
    supports: Optional[List[str]] = None


class InstrumentItem(BaseModel):  # 4
    name: str
    quantity: Optional[int] = 1
    notes: Optional[str] = None


class SkinPrep(BaseModel):  # 5
    description: str
    prep: Optional[str] = None


class DrapingItem(BaseModel):  # 6
    name: str
    notes: Optional[str] = None


class Consumables(BaseModel):  # 7
    name: str
    quantity: Optional[int] = 1
    notes: Optional[str] = None


class Disposables(BaseModel):  # 8
    name: str
    quantity: Optional[int] = 1
    notes: Optional[str] = None


class Implants(BaseModel):  # 9
    name: str
    notes: Optional[str] = None


class SpecialInstructions(BaseModel):  # 10
    notes: Optional[str] = None


class SutureItem(BaseModel):  # 11
    name: str
    size: Optional[str] = None
    quantity: Optional[int] = 1


class DressingItem(BaseModel):  # 12
    name: str
    notes: Optional[str] = None


class FreeTextUpdates(BaseModel):  # 13
    notes: Optional[str] = None


# -------------------------
# Versioning
# -------------------------

class PreferenceVersion(BaseModel):
    version: int
    updated_by: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    change_summary: Optional[str] = None


# -------------------------
# Main Preference Card Model
# -------------------------

class FreeText:
    pass


class SurgeonPreferenceCard(BaseModel):
    surgeon: Surgeon
    procedure: Procedure
    specialty: str

    # Ordered sections (matching your numbering)
    anaesthetic: Optional[AnaestheticNotes] = None             # 0
    positioning: Positioning                                   # 1
    equipment: Optional[List[EquipmentItem]] = None            # 2
    operating_theatre: Optional[OperatingTheatre] = None       # 3
    instruments: List[InstrumentItem]                          # 4
    skin_prep: Optional[SkinPrep] = None                       # 5
    draping: Optional[List[DrapingItem]] = None                # 6
    consumables: Optional[List[Consumables]] = None            # 7
    disposables: Optional[List[Disposables]] = None            # 8
    implants: Optional[List[Implants]] = None                  # 9
    special_instructions: Optional[SpecialInstructions] = None # 10
    sutures: Optional[List[SutureItem]] = None                 # 11
    dressings: Optional[List[DressingItem]] = None             # 12
    free_text_updates: Optional[FreeTextUpdates] = None          # 13

    version: PreferenceVersion

    source_system: str = Field(
        default="streamlit",
        description="streamlit | excel | epr"
    )
