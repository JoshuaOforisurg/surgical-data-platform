import re
from typing import Optional
import os

from surgeon_preference_enum import (
    SurgeonTitle,
    Anaesthetic,
    Speciality,
    PreferenceCategory,
    CaseUrgency,
)


# -----------------------------
# NORMALISATION MAPS
# -----------------------------

TITLE_NORMALISATION = {
    "cons": "Consultant",
    "consultant": "Consultant",
    "conslt": "Consultant",
    "registrar": "Registrar",
    "reg": "Registrar",
    "sho": "SHO",
    "fellow": "Fellow",
}

SPECIALITY_NORMALISATION = {
    "ortho": "Orthopaedics",
    "orthopaedic": "Orthopaedics",
    "orthopaedics": "Orthopaedics",
    "orthopedics": "Orthopaedics",
    "orthopod": "Orthopaedics",
    "ortho surg": "Orthopaedics",
    "orto": "Orthopaedics",
    "ent": "ENT",
    "ear nose throat": "ENT",
    "general": "General Surgery",
    "gs": "General Surgery",
    "urology": "Urology",
    "uro": "Urology",
    "bariatric": "Upper GI",
    "neuro": "Neurosurgery",
    "neurosurg": "Neurosurgery",
    "cardio": "Cardiothoracic",
    "plastics": "Plastics",
    "vascular": "Vascular",
    "venous": "Vascular",
    "vasc": "Vascular",
    "gynae": "Gynaecology",
    "gynaecology": "Gynaecology",
    "ophthal": "Ophthalmology",
    "optal": "Ophthalmology",
    "ophthalmology": "Ophthalmology",
    "colo": "Colorectal",
    "cr": "Colorectal"
}

URGENCY_NORMALISATION = {
    "ele": "Elective",
    "elective": "Elective",
    "urg": "Urgent",
    "urgent": "Urgent",
    "emerg": "Emergency",
    "emergency": "Emergency",
}


# -----------------------------
# NORMALISATION HELPERS
# -----------------------------

def normalise_value(raw: Optional[str], mapping: dict) -> Optional[str]:
    if not raw:
        return None

    cleaned = raw.strip().lower()

    # direct match
    if cleaned in mapping:
        return mapping[cleaned]

    # fuzzy match: remove punctuation
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", cleaned)
    if cleaned in mapping:
        return mapping[cleaned]

    return None


# -----------------------------
# PUBLIC VALIDATION FUNCTIONS
# -----------------------------

def validate_title(raw_title: str) -> Optional[SurgeonTitle]:
    normalised = normalise_value(raw_title, TITLE_NORMALISATION)
    if normalised:
        return SurgeonTitle(normalised)
    return None


def validate_speciality(raw_speciality: str) -> Optional[Speciality]:
    normalised = normalise_value(raw_speciality, SPECIALITY_NORMALISATION)
    if normalised:
        return Speciality(normalised)
    return None


def validate_urgency(raw_urgency: str) -> Optional[CaseUrgency]:
    normalised = normalise_value(raw_urgency, URGENCY_NORMALISATION)
    if normalised:
        return CaseUrgency(normalised)
    return None


def validate_preference_category(raw_category: str) -> Optional[PreferenceCategory]:
    if not raw_category:
        return None

    cleaned = raw_category.strip().lower()

    for category in PreferenceCategory:
        if cleaned == category.value.lower():
            return category

    return None
