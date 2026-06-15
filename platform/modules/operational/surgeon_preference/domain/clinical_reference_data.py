from __future__ import annotations

import difflib
import re
from typing import Dict, Optional


CLINICAL_SPECIAL_INSTRUCTIONS = [
    "Confirm implant sizes before incision.",
    "Ensure the C-arm is draped before the patient enters theatre.",
    "Verify timing of antibiotic prophylaxis.",
    "Check diathermy plate placement.",
    "Confirm patient positioning before skin preparation.",
    "Confirm all implant trays are complete.",
    "Confirm prosthesis sizes with the surgeon.",
    "Verify tourniquet pressure and duration.",
]


def _profile(
    name: str,
    subspecialty: str,
    surgery_type: str,
    opcs_code: Optional[str],
    aliases: list[str],
    expected_instruments: list[str],
    expected_implants: list[str],
    expected_equipment: list[str],
    instrument_system: str,
    implant_system: Optional[str],
    manufacturer: Optional[str],
) -> dict:
    return {
        "name": name,
        "specialty": "Orthopaedics",
        "subspecialty": subspecialty,
        "surgery_type": surgery_type,
        "opcs_code": opcs_code,
        "aliases": aliases,
        "expected_instruments": expected_instruments,
        "expected_implants": expected_implants,
        "expected_equipment": expected_equipment,
        "instrument_systems": [instrument_system],
        "implant_system": implant_system,
        "manufacturer": manufacturer,
    }


CLINICAL_PROCEDURE_PROFILES: Dict[str, dict] = {
    "ORTH_JOINT_KNEE_001": _profile(
        name="Total Knee Replacement",
        subspecialty="Joint Replacement",
        surgery_type="Arthroplasty",
        opcs_code="W40.1",
        aliases=["total knee arthroplasty", "tkr", "tka", "journey knee"],
        expected_instruments=["JOURNEY II BCS Knee System", "Large Orthopaedic Set"],
        expected_implants=["Femoral Component", "Tibial Baseplate", "Polyethylene Insert"],
        expected_equipment=["Stryker SmartPump Tourniquet System", "Stryker System 8 Power Tool Kit"],
        instrument_system="SYS_KNEE_JOURNEY_001",
        implant_system="Zimmer Biomet NexGen TKA System",
        manufacturer="Zimmer Biomet / Smith & Nephew",
    ),
    "ORTH_JOINT_HIP_001": _profile(
        name="Total Hip Replacement (Cemented)",
        subspecialty="Joint Replacement",
        surgery_type="Arthroplasty",
        opcs_code="W37.1",
        aliases=["total hip replacement", "cemented total hip replacement", "thr", "tha"],
        expected_instruments=["Smith & Nephew R3 Acetabular System", "Large Orthopaedic Set"],
        expected_implants=["Acetabular Cup Component", "Femoral Stem Component", "Ceramic Head Component"],
        expected_equipment=["C-Arm Image Intensifier", "Stryker System 8 Power Tool Kit"],
        instrument_system="SYS_HIP_R3_001",
        implant_system="DePuy Pinnacle Hip System Matrix",
        manufacturer="Smith & Nephew / DePuy Synthes",
    ),
    "ORTH_JOINT_SHOULDER_001": _profile(
        name="Total Shoulder Replacement",
        subspecialty="Joint Replacement",
        surgery_type="Arthroplasty",
        opcs_code=None,
        aliases=["shoulder replacement", "anatomic shoulder replacement"],
        expected_instruments=["Zimmer Biomet Comprehensive Shoulder System"],
        expected_implants=["Humeral Stem Component", "Glenoid Base Component"],
        expected_equipment=["Standard Diathermy Machine"],
        instrument_system="SYS_SHOULDER_ZIMMER_001",
        implant_system="Zimmer Biomet Comprehensive Anatomic Line",
        manufacturer="Zimmer Biomet",
    ),
    "ORTH_JOINT_SHOULDER_REV_001": _profile(
        name="Reverse Shoulder Replacement",
        subspecialty="Joint Replacement",
        surgery_type="Arthroplasty",
        opcs_code=None,
        aliases=["reverse shoulder arthroplasty", "reverse total shoulder replacement"],
        expected_instruments=["Medacta Shoulder System (MSS)"],
        expected_implants=["Humeral Tray", "Glenosphere Component"],
        expected_equipment=["Standard Diathermy Machine"],
        instrument_system="SYS_SHOULDER_MEDACTA_001",
        implant_system="Medacta Reverse Shoulder Hardware Assembly",
        manufacturer="Medacta",
    ),
    "ORTH_TRAUMA_TIBFIB_001": _profile(
        name="ORIF Tibia and Fibula",
        subspecialty="Trauma",
        surgery_type="Fracture Fixation",
        opcs_code=None,
        aliases=["orif tibia fibula", "open reduction internal fixation tibia fibula"],
        expected_instruments=["Synthes Large Fragment Set"],
        expected_implants=["Anatomic Tibia Locking Plate Set", "Cortical Screws"],
        expected_equipment=["C-Arm Image Intensifier", "Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_TRAUMA_SYNTHES_LARGE_001",
        implant_system="DePuy Synthes 4.5mm LCP Titanium System",
        manufacturer="DePuy Synthes",
    ),
    "ORTH_TRAUMA_ANKLE_001": _profile(
        name="ORIF Ankle",
        subspecialty="Trauma",
        surgery_type="Fracture Fixation",
        opcs_code=None,
        aliases=["ankle orif", "open reduction internal fixation ankle"],
        expected_instruments=["Synthes Small Fragment Set"],
        expected_implants=["Distal Fibula Plate Set", "Malleolar Screws"],
        expected_equipment=["C-Arm Image Intensifier", "Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_TRAUMA_SYNTHES_SMALL_001",
        implant_system="DePuy Synthes 3.5mm LCP Ankle Cluster",
        manufacturer="DePuy Synthes",
    ),
    "ORTH_TRAUMA_NOF_001": _profile(
        name="Fixation of fracture of neck of femur using intramedullary nail",
        subspecialty="Trauma",
        surgery_type="Fracture Fixation",
        opcs_code=None,
        aliases=["neck of femur nail", "intramedullary nail neck of femur", "tfna"],
        expected_instruments=["DePuy Synthes TFNA Instrument Tray"],
        expected_implants=["Intramedullary Femoral Nail", "Lag Screw Kit"],
        expected_equipment=["C-Arm Image Intensifier", "Stryker System 8 Power Tool Kit"],
        instrument_system="SYS_TRAUMA_TFNA_001",
        implant_system="DePuy Synthes TFNA Intramedullary Line",
        manufacturer="DePuy Synthes",
    ),
    "ORTH_SPINE_LAMINECTOMY_001": _profile(
        name="Lumbar Laminectomy",
        subspecialty="Spine",
        surgery_type="Decompression",
        opcs_code=None,
        aliases=["lumbar decompression", "laminectomy"],
        expected_instruments=["Caspar Retractor System"],
        expected_implants=[],
        expected_equipment=["Midas Rex Spine Shaver / Drill", "Jackson Spinal Surgery Table"],
        instrument_system="SYS_SPINE_CASPAR_001",
        implant_system=None,
        manufacturer="Mixed",
    ),
    "ORTH_SPINE_MICRODISC_001": _profile(
        name="Spinal Microdiscectomy",
        subspecialty="Spine",
        surgery_type="Decompression",
        opcs_code=None,
        aliases=["microdiscectomy", "micro-discectomy", "spinal discectomy"],
        expected_instruments=["Micro-discectomy Curettes Set"],
        expected_implants=[],
        expected_equipment=["Midas Rex Spine Shaver / Drill", "Jackson Spinal Surgery Table"],
        instrument_system="SYS_SPINE_METRX_001",
        implant_system=None,
        manufacturer="Medtronic",
    ),
    "ORTH_SPORTS_RCR_001": _profile(
        name="Arthroscopic Rotator Cuff Repair",
        subspecialty="Sports Medicine",
        surgery_type="Arthroscopy",
        opcs_code=None,
        aliases=["rotator cuff repair", "arthroscopic cuff repair"],
        expected_instruments=["Arthrex Cuff Repair Kit"],
        expected_implants=["SutureTape Anchors", "SwiveLock Anchors"],
        expected_equipment=["Arthroscopy stack system with HD camera", "Arthrex Synergy UHD4 Imaging Console"],
        instrument_system="SYS_ARTHREX_SHOULDER_001",
        implant_system="Arthrex SpeedBridge Anchor System",
        manufacturer="Arthrex",
    ),
    "ORTH_SPORTS_BICEPS_001": _profile(
        name="Arthroscopic Biceps Tenodesis",
        subspecialty="Sports Medicine",
        surgery_type="Arthroscopy",
        opcs_code=None,
        aliases=["biceps tenodesis", "arthroscopic tenodesis"],
        expected_instruments=["Biceps Tenodesis Kit"],
        expected_implants=["Tenodesis Screw"],
        expected_equipment=["Arthroscopy stack system with HD camera"],
        instrument_system="SYS_ARTHREX_BICEPS_001",
        implant_system="Arthrex BioComposite Tenodesis Screw Kit",
        manufacturer="Arthrex",
    ),
    "ORTH_HAND_CTR_001": _profile(
        name="Carpal Tunnel Release",
        subspecialty="Hand Surgery",
        surgery_type="Soft Tissue Release",
        opcs_code=None,
        aliases=["carpal tunnel decompression", "ctr"],
        expected_instruments=["Minor Hand Instrument Set"],
        expected_implants=[],
        expected_equipment=["Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_HAND_MINOR_001",
        implant_system=None,
        manufacturer="Mixed",
    ),
    "ORTH_HAND_TRIGGER_001": _profile(
        name="Percutaneous Trigger Finger Release",
        subspecialty="Hand Surgery",
        surgery_type="Soft Tissue Release",
        opcs_code=None,
        aliases=["trigger finger release", "percutaneous trigger release"],
        expected_instruments=["Minor Hand Instrument Set"],
        expected_implants=[],
        expected_equipment=["Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_HAND_MINOR_001",
        implant_system=None,
        manufacturer="Mixed",
    ),
    "ORTH_HAND_CMC_001": _profile(
        name="Thumb Carpometacarpal Joint Arthroplasty",
        subspecialty="Hand Surgery",
        surgery_type="Arthroplasty",
        opcs_code=None,
        aliases=["thumb cmc arthroplasty", "thumb carpometacarpal arthroplasty"],
        expected_instruments=["Hand Arthroplasty Set"],
        expected_implants=["Trapeziatome Spacer"],
        expected_equipment=["Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_HAND_ACUMED_001",
        implant_system="Acumed Total Thumb CMC System",
        manufacturer="Acumed",
    ),
    "ORTH_FOOT_MTPJ_001": _profile(
        name="MTPJ Fusion",
        subspecialty="Foot and Ankle",
        surgery_type="Fusion",
        opcs_code=None,
        aliases=["mtp fusion", "1st mtp fusion", "first mtp fusion"],
        expected_instruments=["Small Bone Set"],
        expected_implants=["1st MTP Fusion Plate", "Compression Screws"],
        expected_equipment=["Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_FOOT_SMALL_BONE_001",
        implant_system="Wright Medical Foot Fusion Construct Set",
        manufacturer="Wright Medical",
    ),
    "ORTH_FOOT_ANKLE_SCOPE_001": _profile(
        name="Ankle Arthroscopy",
        subspecialty="Foot and Ankle",
        surgery_type="Arthroscopy",
        opcs_code=None,
        aliases=["ankle scope", "arthroscopic ankle procedure"],
        expected_instruments=["Small Joint Arthroscopy Set"],
        expected_implants=[],
        expected_equipment=["Arthroscopy stack system with HD camera"],
        instrument_system="SYS_FOOT_ANKLE_SCOPE_001",
        implant_system=None,
        manufacturer="Smith & Nephew",
    ),
    "ORTH_FOOT_ACHILLES_001": _profile(
        name="Open Achilles Tendon Repair",
        subspecialty="Foot and Ankle",
        surgery_type="Tendon Repair",
        opcs_code=None,
        aliases=["achilles tendon repair", "open tendo achilles repair"],
        expected_instruments=["Large Orthopaedic Set"],
        expected_implants=[],
        expected_equipment=["Stryker SmartPump Tourniquet System"],
        instrument_system="SYS_FOOT_ACHILLES_001",
        implant_system="Arthrex PARS Percutaneous Achilles Assembly",
        manufacturer="Arthrex",
    ),
}


CLINICAL_SYSTEM_DISPLAY_NAMES = {
    "SYS_KNEE_JOURNEY_001": "JOURNEY II BCS Total Knee Instrumentation",
    "SYS_HIP_R3_001": "R3 Acetabular and Cemented Hip Instrumentation",
    "SYS_SHOULDER_ZIMMER_001": "Comprehensive Anatomic Shoulder Instrumentation",
    "SYS_SHOULDER_MEDACTA_001": "Medacta Reverse Shoulder Instrumentation",
    "SYS_TRAUMA_SYNTHES_LARGE_001": "Synthes Large Fragment LCP Instrumentation",
    "SYS_TRAUMA_SYNTHES_SMALL_001": "Synthes Small Fragment Ankle Instrumentation",
    "SYS_TRAUMA_TFNA_001": "DePuy Synthes TFNA Instrumentation",
    "SYS_SPINE_CASPAR_001": "Caspar Lumbar Decompression Instrumentation",
    "SYS_SPINE_METRX_001": "Medtronic METRx Microdiscectomy Instrumentation",
    "SYS_ARTHREX_SHOULDER_001": "Arthrex Shoulder Arthroscopy Instrumentation",
    "SYS_ARTHREX_BICEPS_001": "Arthrex Biceps Tenodesis Instrumentation",
    "SYS_HAND_MINOR_001": "Minor Hand Soft-Tissue Instrumentation",
    "SYS_HAND_ACUMED_001": "Acumed Thumb CMC Arthroplasty Instrumentation",
    "SYS_FOOT_SMALL_BONE_001": "Forefoot Fusion Small Bone Instrumentation",
    "SYS_FOOT_ANKLE_SCOPE_001": "Small Joint Ankle Arthroscopy Instrumentation",
    "SYS_FOOT_ACHILLES_001": "Achilles Tendon Repair Instrumentation",
}


CLINICAL_SUPPLY_PROFILES = {
    "ORTH_JOINT_KNEE_001": {
        "expected_draping": ["Total Knee Arthroplasty Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 3L", "Pulse Lavage Tip", "Sterile Gloves"],
        "expected_disposables": ["Disposable Saw Blade - Oscillating", "Disposable Drill Bit 3.2mm", "Cement Mixing Cartridge"],
        "expected_sutures": ["Vicryl 1", "Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Aquacel Surgical", "Wool and Crepe"],
    },
    "ORTH_JOINT_HIP_001": {
        "expected_draping": ["Total Hip Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 3L", "Pulse Lavage Tip", "Bone Cement Mixing Bowl Kit"],
        "expected_disposables": ["Disposable Reamer - Large", "Cement Mixing Cartridge", "Cement Delivery Gun Nozzle"],
        "expected_sutures": ["Vicryl 1", "Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Aquacel Surgical"],
    },
    "ORTH_JOINT_SHOULDER_001": {
        "expected_draping": ["Shoulder Split Sheet Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Diathermy Pencil"],
        "expected_disposables": ["Disposable Saw Blade - Reciprocating", "Disposable Drill Bit 3.2mm"],
        "expected_sutures": ["Ethibond Excel #2", "Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Mepore"],
    },
    "ORTH_JOINT_SHOULDER_REV_001": {
        "expected_draping": ["Shoulder Split Sheet Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Diathermy Pencil"],
        "expected_disposables": ["Disposable Saw Blade - Reciprocating", "Disposable Drill Bit 3.2mm"],
        "expected_sutures": ["Ethibond Excel #2", "Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Mepore"],
    },
    "ORTH_TRAUMA_TIBFIB_001": {
        "expected_draping": ["Universal Extremity Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["Disposable Drill Bit 3.2mm", "K-wire 2.0mm"],
        "expected_sutures": ["Vicryl 1", "Vicryl 2-0", "Nylon 3-0"],
        "expected_dressings": ["Mepore", "Wool and Crepe"],
    },
    "ORTH_TRAUMA_ANKLE_001": {
        "expected_draping": ["Universal Extremity Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["Disposable Drill Bit 2.5mm", "K-wire 1.6mm"],
        "expected_sutures": ["Vicryl 2-0", "Nylon 3-0"],
        "expected_dressings": ["Mepore", "Wool and Crepe"],
    },
    "ORTH_TRAUMA_NOF_001": {
        "expected_draping": ["Hip Fracture Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["Guide Wire", "Disposable Drill Bit 3.2mm"],
        "expected_sutures": ["Vicryl 1", "Vicryl 2-0", "Clips"],
        "expected_dressings": ["Aquacel Surgical"],
    },
    "ORTH_SPINE_LAMINECTOMY_001": {
        "expected_draping": ["Spine Surgical Drape Pack"],
        "expected_consumables": ["Bone Wax", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["Surgical Patties", "Disposable Burr 3.5mm"],
        "expected_sutures": ["Vicryl 1", "Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Opsite Post-Op"],
    },
    "ORTH_SPINE_MICRODISC_001": {
        "expected_draping": ["Spine Surgical Drape Pack"],
        "expected_consumables": ["Surgical Patties", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["Disposable Burr 3.5mm"],
        "expected_sutures": ["Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Opsite Post-Op"],
    },
    "ORTH_SPORTS_RCR_001": {
        "expected_draping": ["Shoulder Arthroscopy Drape Pack"],
        "expected_consumables": ["Arthroscopy Fluid 3L", "Pump Tubing", "Suction Tubing"],
        "expected_disposables": ["Arthroscopy Shaver Blade 4.0mm", "Disposable Cannula Set"],
        "expected_sutures": ["FiberWire #2", "SutureTape 1.3mm"],
        "expected_dressings": ["Opsite Post-Op"],
    },
    "ORTH_SPORTS_BICEPS_001": {
        "expected_draping": ["Shoulder Arthroscopy Drape Pack"],
        "expected_consumables": ["Arthroscopy Fluid 3L", "Pump Tubing", "Suction Tubing"],
        "expected_disposables": ["Arthroscopy Shaver Blade 4.0mm", "Disposable Cannula Set"],
        "expected_sutures": ["FiberWire #2", "SutureTape 1.3mm"],
        "expected_dressings": ["Opsite Post-Op"],
    },
    "ORTH_HAND_CTR_001": {
        "expected_draping": ["Hand and Foot Aperture Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Local Anaesthetic Syringe", "Sterile Gloves"],
        "expected_disposables": ["Scalpel Blade #15"],
        "expected_sutures": ["Nylon 4-0"],
        "expected_dressings": ["Mepore", "Crepe Bandage"],
    },
    "ORTH_HAND_TRIGGER_001": {
        "expected_draping": ["Hand and Foot Aperture Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Local Anaesthetic Syringe", "Sterile Gloves"],
        "expected_disposables": ["Scalpel Blade #15"],
        "expected_sutures": ["Nylon 4-0"],
        "expected_dressings": ["Mepore", "Crepe Bandage"],
    },
    "ORTH_HAND_CMC_001": {
        "expected_draping": ["Hand and Foot Aperture Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["K-wire 1.6mm", "Disposable Drill Bit 2.0mm"],
        "expected_sutures": ["Vicryl 2-0", "Nylon 4-0"],
        "expected_dressings": ["Mepore", "Crepe Bandage"],
    },
    "ORTH_FOOT_MTPJ_001": {
        "expected_draping": ["Hand and Foot Aperture Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["K-wire 1.6mm", "Disposable Drill Bit 2.0mm"],
        "expected_sutures": ["Vicryl 2-0", "Nylon 3-0"],
        "expected_dressings": ["Mepore", "Wool and Crepe"],
    },
    "ORTH_FOOT_ANKLE_SCOPE_001": {
        "expected_draping": ["Ankle Arthroscopy Drape Pack"],
        "expected_consumables": ["Arthroscopy Fluid 3L", "Pump Tubing", "Suction Tubing"],
        "expected_disposables": ["Arthroscopy Shaver Blade 4.0mm", "Disposable Trocar Set"],
        "expected_sutures": ["Nylon 3-0"],
        "expected_dressings": ["Mepore", "Wool and Crepe"],
    },
    "ORTH_FOOT_ACHILLES_001": {
        "expected_draping": ["Hand and Foot Aperture Drape Pack"],
        "expected_consumables": ["Skin Marker Pen", "Irrigation Fluid 0.9% Saline 1L", "Suction Tubing"],
        "expected_disposables": ["Scalpel Blade #15"],
        "expected_sutures": ["FiberWire #5", "Vicryl 2-0", "Nylon 3-0"],
        "expected_dressings": ["Mepore", "Wool and Crepe"],
    },
}


for _procedure_id, _supply_profile in CLINICAL_SUPPLY_PROFILES.items():
    if _procedure_id in CLINICAL_PROCEDURE_PROFILES:
        CLINICAL_PROCEDURE_PROFILES[_procedure_id].update(_supply_profile)


def _build_instrument_systems() -> Dict[str, dict]:
    systems: Dict[str, dict] = {}
    for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items():
        for system_id in profile["instrument_systems"]:
            system = systems.setdefault(
                system_id,
                {
                    "name": CLINICAL_SYSTEM_DISPLAY_NAMES.get(system_id, system_id),
                    "manufacturer": profile["manufacturer"],
                    "aliases": [],
                    "instruments": [],
                    "compatible_implants": [],
                    "compatible_procedures": [],
                },
            )
            aliases = [
                system_id,
                CLINICAL_SYSTEM_DISPLAY_NAMES.get(system_id, ""),
                profile["expected_instruments"][0] if profile["expected_instruments"] else "",
                profile["implant_system"] or "",
                *profile["expected_instruments"],
            ]
            system["aliases"] = sorted({*system["aliases"], *[alias for alias in aliases if alias]})
            system["instruments"] = sorted({*system["instruments"], *profile["expected_instruments"]})
            system["compatible_implants"] = sorted(
                {*system["compatible_implants"], *profile["expected_implants"]}
            )
            system["compatible_procedures"] = sorted(
                {*system["compatible_procedures"], procedure_id}
            )
    return systems


CLINICAL_INSTRUMENT_SYSTEMS: Dict[str, dict] = _build_instrument_systems()


def _normalise(text: str) -> str:
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _is_fuzzy_match(str1: str, str2: str, threshold: float = 0.84) -> bool:
    s1 = _normalise(str1)
    s2 = _normalise(str2)
    if not s1 or not s2:
        return False
    if s1 == s2:
        return True
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())
    if len(s1) <= 4 or len(s2) <= 4:
        return tokens1.issubset(tokens2) or tokens2.issubset(tokens1)
    if s1 in s2 or s2 in s1:
        return True
    return difflib.SequenceMatcher(None, s1, s2).ratio() >= threshold


def _match_score(str1: str, str2: str, threshold: float = 0.84) -> float:
    s1 = _normalise(str1)
    s2 = _normalise(str2)
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    tokens1 = set(s1.split())
    tokens2 = set(s2.split())
    if len(s1) <= 4 or len(s2) <= 4:
        return 0.91 if tokens1.issubset(tokens2) or tokens2.issubset(tokens1) else 0.0

    ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    if s1 in s2 or s2 in s1:
        ratio = max(ratio, 0.92)
    return ratio if ratio >= threshold else 0.0


def find_procedure_match(text: str) -> Optional[str]:
    if not text:
        return None
    best_key = None
    best_score = 0.0
    for key, data in CLINICAL_PROCEDURE_PROFILES.items():
        candidates = [data["name"], *data.get("aliases", [])]
        score = max(_match_score(text, candidate) for candidate in candidates)
        if score > best_score:
            best_key = key
            best_score = score
    return best_key


def find_instrument_system_match(text: str) -> Optional[str]:
    if not text:
        return None
    for key, data in CLINICAL_INSTRUMENT_SYSTEMS.items():
        if _is_fuzzy_match(text, data["name"]):
            return key
        for alias in data.get("aliases", []):
            if alias and _is_fuzzy_match(text, alias):
                return key
    return None


def normalise_special_instruction(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    best_instruction = None
    best_score = 0.0
    for instruction in CLINICAL_SPECIAL_INSTRUCTIONS:
        score = _match_score(text, instruction, threshold=0.72)
        if score > best_score:
            best_instruction = instruction
            best_score = score
    return best_instruction if best_instruction and best_score >= 0.72 else " ".join(text.split())
