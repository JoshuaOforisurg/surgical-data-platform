from __future__ import annotations

from generate_synthetic_data.catalogue.procedures import PROCEDURES, SPECIALTIES, SUBSPECIALTIES
from generate_synthetic_data.catalogue.clinical_profiles import CLINICAL_PREFERENCE_PROFILES
from generate_synthetic_data.catalogue.supplies import CONSUMABLES_ITEMS, DISPOSABLES_ITEMS, DRESSING_OPTIONS, SUTURE_NAMES
from generate_synthetic_data.catalogue.special_instructions import SPECIAL_INSTRUCTIONS_POOL
from generate_synthetic_data.catalogue.surgeons import SURGEON_NAMES, SURGEON_UPDATE_ROLES

__all__ = [
    "SPECIALTIES",
    "SUBSPECIALTIES",
    "PROCEDURES",
    "CLINICAL_PREFERENCE_PROFILES",
    "SPECIAL_INSTRUCTIONS_POOL",
    "CONSUMABLES_ITEMS",
    "DISPOSABLES_ITEMS",
    "SUTURE_NAMES",
    "DRESSING_OPTIONS",
    "SURGEON_NAMES",
    "SURGEON_UPDATE_ROLES",
]
