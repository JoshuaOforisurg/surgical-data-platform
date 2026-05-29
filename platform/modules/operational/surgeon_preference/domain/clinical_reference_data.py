# clinical_reference_data.py

from typing import Dict, Optional
import re


# =========================================================
# ORTHOPAEDIC CLINICAL REFERENCE LAYER
# ---------------------------------------------------------
# Canonical internal IDs are used instead of external coding
# systems to keep Silver-B stable and extensible.
#
# Real OPCS / ICD / SNOMED mappings can be added later as
# supplementary metadata.
# =========================================================


# =========================================================
# PROCEDURE PROFILES
# =========================================================

CLINICAL_PROCEDURE_PROFILES: Dict[str, dict] = {
    "ORTH_HIP_001": {
        "name": "Total Hip Replacement",
        "variant": "Cemented",
        "opcs_code": "W37.1",

        "aliases": [
            "total hip replacement",
            "total hip arthroplasty",
            "cemented total hip replacement",
            "thr",
            "tha",
        ],

        "subspecialty": "Hip",
        "surgery_type": "Joint Replacement",
        "specialty": "Orthopaedics",

        "expected_instruments": [
            "S&N R3 Acetabular Trials 45–64 mm",
            "S&N R3 Acetabular Reamers 42–64 mm",
            "S&N R3 Main Instrument Set",
            "S&N CPCS Stem Instrument Set",
        ],

        "expected_implants": [
            "CPCS Femoral Stem",
            "R3 Acetabular Shell",
            "R3 Acetabular Liner",
            "Oxinium Taper Femoral Head",
        ],

        "expected_equipment": [
            "Orthopaedic Table",
            "Pelvic Support",
            "Back Support",
        ],

        "instrument_systems": [
            "SYS_HIP_SN_001"
        ],
    },

    "ORTH_KNEE_001": {
        "name": "Total Knee Replacement",
        "variant": "Standard",
        "opcs_code": "W40.1",

        "aliases": [
            "total knee replacement",
            "total knee arthroplasty",
            "tkr",
            "tka",
        ],

        "subspecialty": "Knee",
        "surgery_type": "Joint Replacement",
        "specialty": "Orthopaedics",

        "expected_instruments": [
            "Journey II Spacer Set",
            "Journey II Femoral Preparation Set",
            "Journey II Tibial Preparation Set",
            "Journey II Trial Set",
            "Journey II Finishing Instrument Set",
            "Journey II Patella Tray",
        ],

        "expected_implants": [
            "Journey II BCS Femoral Component",
            "Journey II Tibial Baseplate",
            "Journey II Articular Insert",
            "Journey II Constrained Insert",
            "Journey II Patella Component",
        ],

        "expected_equipment": [
            "Tourniquet",
            "Foot Bolster",
            "Lateral Support",
            "Diathermy Machine",
        ],

        "instrument_systems": [
            "SYS_KNEE_SN_001"
        ],
    },

    "ORTH_SPORTS_001": {
        "name": "ACL Reconstruction",
        "variant": "Standard",
        "opcs_code": None,

        "aliases": [
            "acl reconstruction",
            "anterior cruciate ligament reconstruction",
            "acl repair",
        ],

        "subspecialty": "Knee",
        "surgery_type": "Sports Medicine",
        "specialty": "Orthopaedics",

        "expected_instruments": [
            "FlipCutter",
            "Tendon Stripper",
            "Cannulated Reamer",
            "Tunnel Dilator",
            "Hook Probe",
            "Suture Passer",
        ],

        "expected_implants": [
            "TightRope II",
            "Biocomposite Interference Screw",
            "PEEK Interference Screw",
            "SwiveLock Anchor",
            "FiberLoop Suture",
        ],

        "expected_equipment": [
            "Arthroscopy Stack System",
            "Tourniquet",
            "Foot Bolster",
            "Diathermy Machine",
        ],

        "instrument_systems": [
            "SYS_ACL_ARTHREX_001"
        ],
    },
}


# =========================================================
# INSTRUMENT SYSTEM PROFILES
# =========================================================

CLINICAL_INSTRUMENT_SYSTEMS: Dict[str, dict] = {
    "SYS_HIP_SN_001": {
        "name": "Smith & Nephew THA System",
        "manufacturer": "Smith & Nephew",

        "aliases": [
            "smith and nephew hip",
            "s&n hip system",
            "r3 hip system",
            "cpcs hip system",
        ],

        "instruments": [
            "S&N R3 Acetabular Trials 45–64 mm",
            "S&N R3 Acetabular Reamers 42–64 mm",
            "S&N R3 Main Instrument Set",
            "S&N CPCS Stem Instrument Set",
        ],

        "compatible_implants": [
            "CPCS Femoral Stem",
            "R3 Acetabular Shell",
            "R3 Acetabular Liner",
            "Oxinium Taper Femoral Head",
        ],

        "compatible_procedures": [
            "ORTH_HIP_001"
        ],
    },

    "SYS_KNEE_SN_001": {
        "name": "Journey II Total Knee System",
        "manufacturer": "Smith & Nephew",

        "aliases": [
            "journey ii",
            "journey knee",
            "bcs knee system",
        ],

        "instruments": [
            "Journey II Spacer Set",
            "Journey II Femoral Preparation Set",
            "Journey II Tibial Preparation Set",
            "Journey II Trial Set",
            "Journey II Finishing Instrument Set",
            "Journey II Patella Tray",
        ],

        "compatible_implants": [
            "Journey II BCS Femoral Component",
            "Journey II Tibial Baseplate",
            "Journey II Articular Insert",
            "Journey II Constrained Insert",
            "Journey II Patella Component",
        ],

        "compatible_procedures": [
            "ORTH_KNEE_001"
        ],
    },

    "SYS_ACL_ARTHREX_001": {
        "name": "Arthrex ACL Reconstruction System",
        "manufacturer": "Arthrex",

        "aliases": [
            "arthrex acl",
            "arthrex toolbox",
            "acl reconstruction system",
        ],

        "instruments": [
            "FlipCutter",
            "Tendon Stripper",
            "Cannulated Reamer",
            "Tunnel Dilator",
            "Hook Probe",
            "Suture Passer",
        ],

        "compatible_implants": [
            "TightRope II",
            "Biocomposite Interference Screw",
            "PEEK Interference Screw",
            "SwiveLock Anchor",
            "FiberLoop Suture",
        ],

        "compatible_procedures": [
            "ORTH_SPORTS_001"
        ],
    },
}


# =========================================================
# NORMALISATION
# =========================================================

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


# =========================================================
# LOOKUP HELPERS
# =========================================================

def find_procedure_match(text: str) -> Optional[str]:
    if not text:
        return None

    cleaned = _normalise(text)

    for key, data in CLINICAL_PROCEDURE_PROFILES.items():
        if cleaned == _normalise(data["name"]):
            return key

        for alias in data.get("aliases", []):
            if cleaned == _normalise(alias):
                return key

    return None


def find_instrument_system_match(text: str) -> Optional[str]:
    if not text:
        return None

    cleaned = _normalise(text)

    for key, data in CLINICAL_INSTRUMENT_SYSTEMS.items():
        if cleaned == _normalise(data["name"]):
            return key

        for alias in data.get("aliases", []):
            if cleaned == _normalise(alias):
                return key

    return None


def get_procedure_profile(procedure_id: str) -> Optional[dict]:
    return CLINICAL_PROCEDURE_PROFILES.get(procedure_id)


def get_instrument_system_profile(system_id: str) -> Optional[dict]:
    return CLINICAL_INSTRUMENT_SYSTEMS.get(system_id)