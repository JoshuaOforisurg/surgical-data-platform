from __future__ import annotations

import difflib
import re
from typing import Dict, Optional


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


CLINICAL_INSTRUMENT_SYSTEMS: Dict[str, dict] = {
    system_id: {
        "name": profile["expected_instruments"][0] if profile["expected_instruments"] else system_id,
        "manufacturer": profile["manufacturer"],
        "aliases": [
            system_id,
            profile["expected_instruments"][0] if profile["expected_instruments"] else "",
            profile["implant_system"] or "",
            *profile["expected_instruments"],
        ],
        "instruments": profile["expected_instruments"],
        "compatible_implants": profile["expected_implants"],
        "compatible_procedures": [procedure_id],
    }
    for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items()
    for system_id in profile["instrument_systems"]
}


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


def find_procedure_match(text: str) -> Optional[str]:
    if not text:
        return None
    for key, data in CLINICAL_PROCEDURE_PROFILES.items():
        if _is_fuzzy_match(text, data["name"]):
            return key
        for alias in data.get("aliases", []):
            if _is_fuzzy_match(text, alias):
                return key
    return None


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
