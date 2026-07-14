from __future__ import annotations

import os
import importlib.util
from pathlib import Path
from typing import Any


def _platform_root() -> Path:
    configured_root = os.getenv("SURGICAL_PLATFORM_ROOT")
    candidates = []
    if configured_root:
        candidates.append(Path(configured_root))
    candidates.extend(Path(__file__).resolve().parents)

    for candidate in candidates:
        if (candidate / "shared" / "catalogue" / "__init__.py").exists():
            return candidate

    raise ImportError(
        "Unable to locate platform shared catalogue. Set SURGICAL_PLATFORM_ROOT "
        "or ensure shared/catalogue is available beside the application package."
    )


PLATFORM_ROOT = _platform_root()
SHARED_CATALOGUE_DIR = PLATFORM_ROOT / "shared" / "catalogue"


def _load_shared_module(module_name: str, file_name: str) -> Any:
    module_path = SHARED_CATALOGUE_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load shared catalogue module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_clinical_profiles = _load_shared_module("shared_catalogue_clinical_profiles", "clinical_profiles.py")
_procedures = _load_shared_module("shared_catalogue_procedures", "procedures.py")
_special_instructions = _load_shared_module("shared_catalogue_special_instructions", "special_instructions.py")
_supplies = _load_shared_module("shared_catalogue_supplies", "supplies.py")
_surgeons = _load_shared_module("shared_catalogue_surgeons", "surgeons.py")

CLINICAL_PREFERENCE_PROFILES = _clinical_profiles.CLINICAL_PREFERENCE_PROFILES
CONSUMABLES_ITEMS = _supplies.CONSUMABLES_ITEMS
DISPOSABLES_ITEMS = _supplies.DISPOSABLES_ITEMS
DRESSING_OPTIONS = _supplies.DRESSING_OPTIONS
PROCEDURES = _procedures.PROCEDURES
SPECIAL_INSTRUCTIONS_POOL = _special_instructions.SPECIAL_INSTRUCTIONS_POOL
SPECIALTIES = _procedures.SPECIALTIES
SUBSPECIALTIES = _procedures.SUBSPECIALTIES
SURGEON_NAMES = _surgeons.SURGEON_NAMES
SURGEON_UPDATE_ROLES = _surgeons.SURGEON_UPDATE_ROLES
SUTURE_NAMES = _supplies.SUTURE_NAMES

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
