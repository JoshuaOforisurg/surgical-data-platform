from __future__ import annotations

import difflib
import re
from typing import Dict, Optional


CLINICAL_SPECIAL_INSTRUCTIONS = [
    "Confirm implant sizes before incision.",
    "Verify timing of antibiotic prophylaxis.",
    "Check diathermy plate placement and skin assessment later.",
    "Confirm patient positioning before skin preparation.",
    "Ensure patient position is checked and secure.",
    "Confirm all implant trays are complete.",
    "Pre-wash the surgical site with scrub solution and chlorhexidine spray.",
    "Confirm prosthesis sizes with the surgeon.",
    "Verify tourniquet pressure and duration.",
]


CLINICAL_PROCEDURE_SPECIAL_INSTRUCTIONS = {
    "ORTH_JOINT_KNEE_001": [
        "Confirm all trays are complete.",
        "Confirm prosthesis sizes with the surgeon during the morning brief.",
        "Confirm valgus bushing angle is 5 degrees for male patients or 6 degrees for female patients.",
        "Confirm if procedure will be robotic assisted.",
        "Ensure patient position is checked and secure.",
        "Confirm cement and pulse lavage are available before incision.",
        "Put up x-rays on computer screen before procedure starts.",
        "Verify tourniquet pressure and duration.",
    ],
    "ORTH_JOINT_HIP_001": [
        "Confirm all trays are complete.",
        "Confirm prosthesis sizes with the surgeon during the morning brief.",
        "Confirm prosthesis sizes with the surgeon.",
        "Confirm if procedure will be robotic assisted.",
        "Confirm cement system and femoral preparation equipment before incision.",
        "Put up x-rays on computer screen before procedure starts.",
    ],
    "ORTH_JOINT_SHOULDER_001": [
        "Confirm shoulder implant trays and glenoid preparation instruments are complete.",
        "Confirm patient positioning before skin preparation.",
        "Patient head should be away from the anaesthetic machine.",
    ],
    "ORTH_JOINT_SHOULDER_REV_001": [
        "Confirm reverse shoulder implant trays are complete.",
        "Confirm patient positioning before skin preparation.",
        "Patient head should be away from the anaesthetic machine.",
        "Confirm if joint will be cemented.",
        "Confirm if surgeon will be using NextAR augmented reality system.",
    ],
    "ORTH_TRAUMA_TIBFIB_001": [
        "Confirm fracture fixation implant trays, k-wires and disposables are complete.",
        "Put up x-rays on computer screen before procedure starts.",
        "Ensure the C-arm is draped before the procedure starts.",
        "Verify tourniquet pressure and duration.",

    ],
    "ORTH_TRAUMA_ANKLE_001": [
        "Ensure the C-arm is draped before the procedure starts.",
        "Confirm ankle fixation plates, screws, and K-wires are available.",
        "Verify tourniquet pressure and duration.",
        "Confirm sizes of screws and plates with the surgeon before procedure starts.",
    ],
    "ORTH_TRAUMA_NOF_001": [
        "Ensure the C-arm is draped before the procedure starts.",
        "Confirm intramedullary nail, guide wire, and lag screw options before incision.",
        "Confirm sizes of screws and plates with the surgeon before procedure starts.",
    ],
    "ORTH_SPINE_LAMINECTOMY_001": [
        "Confirm prone positioning and pressure area protection before skin preparation.",
        "Confirm microscope or headlight availability if requested by the surgeon.",
        "Ensure the microscope and C-arm are draped before the procedure starts.",

    ],
    "ORTH_SPINE_MICRODISC_001": [
        "Confirm prone positioning and pressure area protection before skin preparation.",
        "Confirm microscope or headlight availability if requested by the surgeon.",
        "Ensure the microscope and C-arm are draped before the procedure starts.",
    ],
    "ORTH_SPORTS_RCR_001": [
        "Confirm arthroscopy stack, pump tubing, and shaver system before skin preparation.",
        "Ensure the patient name and details are entered on the stack machine before the procedure starts.",
        "Patient head should be away from the anaesthetic machine.",
        "Confirm suture anchor and implant options before incision.",
    ],
    "ORTH_SPORTS_BICEPS_001": [
        "Confirm arthroscopy stack, pump tubing, and shaver system before skin preparation.",
        "Ensure the patient name and details are entered on the stack machine before the procedure starts.",
        "Patient head should be away from the anaesthetic machine.",
        "Confirm tenodesis screw options before incision.",
    ],
    "ORTH_HAND_CTR_001": [
        "Confirm local anaesthetic and tourniquet setup before skin preparation.",
        "Confirm hand table and minor hand set are available.",
    ],
    "ORTH_HAND_TRIGGER_001": [
        "Confirm local anaesthetic and minor hand set before skin preparation.",
        "Confirm correct digit and side during team brief.",
    ],
    "ORTH_HAND_CMC_001": [
        "Confirm thumb CMC implant or spacer options before incision.",
        "Confirm hand table, image intensifier access, and K-wires are available.",
    ],
    "ORTH_FOOT_MTPJ_001": [
        "Ensure the C-arm is available before the patient enters theatre.",
        "Confirm forefoot fusion plates, screws, and K-wires are available.",
    ],
    "ORTH_FOOT_ANKLE_SCOPE_001": [
        "Confirm arthroscopy stack, pump tubing, and small-joint shaver system before skin preparation.",
        "Patient head should be away from the anaesthetic machine.",
        "Confirm ankle distraction setup if requested by the surgeon.",
    ],
    "ORTH_FOOT_ACHILLES_001": [
        "Confirm prone positioning and pressure area protection before skin preparation.",
        "Confirm FiberWire and Achilles repair system before incision.",
    ],
}


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
    expected_positioning: Optional[list[str]] = None,
    expected_anaesthetic: Optional[list[str]] = None,
    expected_skin_prep: Optional[list[str]] = None,
    theatre_environment: str = "Standard elective theatre",
    laterality_required: bool = True,
    imaging_required: bool = False,
    implant_representative_required: bool = False,
    loan_kit_lead_time_days: int = 0,
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
        "expected_positioning": expected_positioning or ["Supine", "Pressure areas checked"],
        "expected_anaesthetic": expected_anaesthetic or ["General anaesthetic", "Regional anaesthetic if clinically appropriate"],
        "expected_skin_prep": expected_skin_prep or ["Chlorhexidine 2% in 70% alcohol", "Iodine alternative if chlorhexidine allergy"],
        "theatre_environment": theatre_environment,
        "laterality_required": laterality_required,
        "imaging_required": imaging_required,
        "implant_representative_required": implant_representative_required,
        "loan_kit_lead_time_days": loan_kit_lead_time_days,
    }


CLINICAL_PROCEDURE_PROFILES: Dict[str, dict] = {
    "ORTH_JOINT_KNEE_001": _profile(
        name="Total Knee Replacement",
        subspecialty="Joint Replacement",
        surgery_type="Arthroplasty",
        opcs_code="W40.1",
        aliases=["total knee arthroplasty", "tkr", "tka", "journey knee"],
        expected_instruments=["JOURNEY II BCS Knee System", "Large Orthopaedic Set", "Heraeus Cement Gun", "J&J PFC Knee Retractors", "Splash Bowl", "Jug"],
        expected_implants=["Femoral Component", "Tibial Baseplate", "Polyethylene Insert", "Patella"],
        expected_equipment=["Stryker SmartPump Tourniquet System", "Diathermy Machine", "Neptune Suction Machine"],
        instrument_system="SYS_KNEE_JOURNEY_001",
        implant_system="BCS Journey II Knee",
        manufacturer="Smith & Nephew",
        expected_positioning=["Supine", "Lateral post", "Foot support", "Gel heel pad"],
        expected_anaesthetic=["Spinal anaesthetic", "General anaesthetic", "Adductor canal block"],
        expected_skin_prep=["Chlorhexidine 2% in 70% alcohol", "Iodine alternative if chlorhexidine allergy"],
        theatre_environment="Ultra-clean air orthopaedic theatre",
        laterality_required=True,
        imaging_required=True,
        implant_representative_required=True,
        loan_kit_lead_time_days=2,
    ),
    "ORTH_JOINT_HIP_001": _profile(
        name="Total Hip Replacement (Cemented)",
        subspecialty="Joint Replacement",
        surgery_type="Arthroplasty",
        opcs_code="W37.1",
        aliases=["total hip replacement", "cemented total hip replacement", "thr", "tha"],
        expected_instruments=["Smith & Nephew R3 Acetabular System", "Large Orthopaedic Set", "Heraeus Cement Gun", "J&J PFC Knee Retractors", "Splash Bowl", "Jug"],
        expected_implants=["Acetabular Cup Component", "Liner Component", "Femoral Stem Component", "Ceramic Head Component"],
        expected_equipment=["C-Arm Image Intensifier", "Diathermy Machine", "Neptune Suction Machine"],
        instrument_system="SYS_HIP_R3_001",
        implant_system="R3/CPCS System",
        manufacturer="Smith & Nephew",
        expected_positioning=["Lateral decubitus", "Beanbag", "Padded supports", "Axillary roll"],
        expected_anaesthetic=["Spinal anaesthetic", "General anaesthetic", "Fascia iliaca block"],
        expected_skin_prep=["Chlorhexidine 2% in 70% alcohol", "Iodine alternative if chlorhexidine allergy"],
        theatre_environment="Ultra-clean air orthopaedic theatre",
        laterality_required=True,
        imaging_required=True,
        implant_representative_required=True,
        loan_kit_lead_time_days=2,
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


CLINICAL_OPERATIONAL_METADATA = {
    "ORTH_JOINT_KNEE_001": {
        "case_complexity": "High",
        "expected_duration_minutes": 105,
        "turnaround_minutes": 35,
        "requires_ultra_clean_air": True,
        "blood_product_group_and_save": True,
        "antibiotic_window_minutes": 60,
        "critical_checks": [
            "Laterality marked and consent checked",
            "Implant sizes confirmed against templating",
            "Tourniquet start time visible",
        ],
    },
    "ORTH_JOINT_HIP_001": {
        "case_complexity": "High",
        "expected_duration_minutes": 120,
        "turnaround_minutes": 40,
        "requires_ultra_clean_air": True,
        "blood_product_group_and_save": True,
        "antibiotic_window_minutes": 60,
        "critical_checks": [
            "Laterality marked and consent checked",
            "Templated cup, stem, head and liner sizes available",
            "Cement mixing and pressurisation kit opened only after confirmation",
        ],
    },
    "ORTH_JOINT_SHOULDER_001": {
        "case_complexity": "High",
        "expected_duration_minutes": 130,
        "turnaround_minutes": 40,
        "expected_positioning": ["Beach chair", "Head secured", "Arm positioner available"],
        "expected_anaesthetic": ["General anaesthetic", "Interscalene block"],
        "theatre_environment": "Laminar-flow orthopaedic theatre",
        "requires_ultra_clean_air": True,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Head and airway access confirmed", "Glenoid sizing trays complete"],
    },
    "ORTH_JOINT_SHOULDER_REV_001": {
        "case_complexity": "High",
        "expected_duration_minutes": 150,
        "turnaround_minutes": 45,
        "expected_positioning": ["Beach chair", "Head secured", "Arm positioner available"],
        "expected_anaesthetic": ["General anaesthetic", "Interscalene block"],
        "theatre_environment": "Laminar-flow orthopaedic theatre",
        "requires_ultra_clean_air": True,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "implant_representative_required": True,
        "loan_kit_lead_time_days": 3,
        "critical_checks": ["NextAR plan loaded if requested", "Baseplate and glenosphere options complete"],
    },
    "ORTH_TRAUMA_TIBFIB_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 110,
        "turnaround_minutes": 30,
        "expected_positioning": ["Supine", "Radiolucent table", "Limb support"],
        "theatre_environment": "Trauma theatre with image intensifier access",
        "imaging_required": True,
        "blood_product_group_and_save": True,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["C-arm positioned and screened", "Open fracture antibiotics confirmed if applicable"],
    },
    "ORTH_TRAUMA_ANKLE_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 90,
        "turnaround_minutes": 25,
        "expected_positioning": ["Supine", "Radiolucent extension", "Sandbag under ipsilateral hip"],
        "theatre_environment": "Trauma theatre with image intensifier access",
        "imaging_required": True,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["C-arm lateral and mortise views checked", "Tourniquet pressure and duration recorded"],
    },
    "ORTH_TRAUMA_NOF_001": {
        "case_complexity": "High",
        "expected_duration_minutes": 85,
        "turnaround_minutes": 30,
        "expected_positioning": ["Fracture table", "Traction boot", "Perineal post padded"],
        "theatre_environment": "Trauma theatre with image intensifier access",
        "imaging_required": True,
        "blood_product_group_and_save": True,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Fracture table available", "Guide wire and lag screw lengths available"],
    },
    "ORTH_SPINE_LAMINECTOMY_001": {
        "case_complexity": "High",
        "expected_duration_minutes": 120,
        "turnaround_minutes": 35,
        "expected_positioning": ["Prone", "Wilson frame or spinal frame", "Eyes and pressure areas checked"],
        "expected_anaesthetic": ["General anaesthetic with endotracheal tube"],
        "theatre_environment": "Spine theatre with radiolucent table",
        "imaging_required": True,
        "laterality_required": False,
        "blood_product_group_and_save": True,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Spinal level confirmed", "Microscope or headlight available if requested"],
    },
    "ORTH_SPINE_MICRODISC_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 90,
        "turnaround_minutes": 30,
        "expected_positioning": ["Prone", "Wilson frame or spinal frame", "Eyes and pressure areas checked"],
        "expected_anaesthetic": ["General anaesthetic with endotracheal tube"],
        "theatre_environment": "Spine theatre with radiolucent table",
        "imaging_required": True,
        "laterality_required": True,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Spinal level confirmed", "Microscope draped before incision"],
    },
    "ORTH_SPORTS_RCR_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 100,
        "turnaround_minutes": 25,
        "expected_positioning": ["Beach chair or lateral decubitus", "Head secured", "Arm traction available"],
        "expected_anaesthetic": ["General anaesthetic", "Interscalene block"],
        "theatre_environment": "Arthroscopy theatre",
        "imaging_required": False,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Pump pressure agreed", "Anchor sizes and backup anchors available"],
    },
    "ORTH_SPORTS_BICEPS_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 75,
        "turnaround_minutes": 25,
        "expected_positioning": ["Beach chair or lateral decubitus", "Head secured", "Arm traction available"],
        "expected_anaesthetic": ["General anaesthetic", "Interscalene block"],
        "theatre_environment": "Arthroscopy theatre",
        "imaging_required": False,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Tenodesis screw sizes available", "Arthroscopy stack patient details entered"],
    },
    "ORTH_HAND_CTR_001": {
        "case_complexity": "Low",
        "expected_duration_minutes": 25,
        "turnaround_minutes": 15,
        "expected_positioning": ["Supine", "Hand table", "Arm board"],
        "expected_anaesthetic": ["Local anaesthetic", "Regional block"],
        "theatre_environment": "Minor hand theatre",
        "imaging_required": False,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 0,
        "critical_checks": ["Correct hand and side confirmed", "Tourniquet setup available if requested"],
    },
    "ORTH_HAND_TRIGGER_001": {
        "case_complexity": "Low",
        "expected_duration_minutes": 20,
        "turnaround_minutes": 15,
        "expected_positioning": ["Supine", "Hand table", "Arm board"],
        "expected_anaesthetic": ["Local anaesthetic"],
        "theatre_environment": "Minor hand theatre",
        "imaging_required": False,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 0,
        "critical_checks": ["Correct digit and side confirmed", "Local anaesthetic dose checked"],
    },
    "ORTH_HAND_CMC_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 95,
        "turnaround_minutes": 25,
        "expected_positioning": ["Supine", "Hand table", "Arm board"],
        "expected_anaesthetic": ["Regional block", "General anaesthetic"],
        "theatre_environment": "Hand theatre with image intensifier access",
        "imaging_required": True,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Thumb CMC implant or spacer options available", "Image intensifier access confirmed"],
    },
    "ORTH_FOOT_MTPJ_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 75,
        "turnaround_minutes": 25,
        "expected_positioning": ["Supine", "Foot bolster", "Radiolucent foot extension"],
        "expected_anaesthetic": ["Regional block", "General anaesthetic"],
        "theatre_environment": "Foot and ankle theatre with image intensifier access",
        "imaging_required": True,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Plate side and screw options confirmed", "C-arm access checked"],
    },
    "ORTH_FOOT_ANKLE_SCOPE_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 65,
        "turnaround_minutes": 25,
        "expected_positioning": ["Supine", "Ankle distraction if requested", "Foot support"],
        "expected_anaesthetic": ["General anaesthetic", "Regional block"],
        "theatre_environment": "Arthroscopy theatre",
        "imaging_required": False,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Small-joint shaver available", "Fluid management setup checked"],
    },
    "ORTH_FOOT_ACHILLES_001": {
        "case_complexity": "Moderate",
        "expected_duration_minutes": 70,
        "turnaround_minutes": 25,
        "expected_positioning": ["Prone", "Chest rolls", "Feet free over table edge"],
        "expected_anaesthetic": ["General anaesthetic", "Regional block"],
        "theatre_environment": "Foot and ankle theatre",
        "imaging_required": False,
        "blood_product_group_and_save": False,
        "antibiotic_window_minutes": 60,
        "critical_checks": ["Prone pressure areas checked", "FiberWire or Achilles repair system available"],
    },
}


for _procedure_id, _metadata in CLINICAL_OPERATIONAL_METADATA.items():
    if _procedure_id in CLINICAL_PROCEDURE_PROFILES:
        CLINICAL_PROCEDURE_PROFILES[_procedure_id].update(_metadata)


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
        "expected_consumables": [
            "Skin Marker Pen",
            "Chlorhexidine 2% Applicator",
            "Irrigation Fluid 0.9% Saline 3L",
            "Pulse Lavage Tip",
            "Suction Tubing",
            "Diathermy Pencil",
            "Light Handle Covers",
            "Sterile Gloves",
            "Sterile Gown",
            "Sharps Pad",
            "Bladder Syringe",
            "Eschmark Bandage",
        ],
        "expected_disposables": [
            "Disposable Saw Blade - Oscillating",
            "Disposable Drill Bit 3.2mm",
            "Cement Mixing Cartridge",
            "Cement Delivery Gun Nozzle",
        ],
        "expected_sutures": ["Vicryl 1", "Vicryl 2-0", "Monocryl 3-0"],
        "expected_dressings": ["Aquacel Surgical", "Wool and Crepe"],
    },
    "ORTH_JOINT_HIP_001": {
        "expected_draping": ["Total Hip Drape Pack"],
        "expected_consumables": [
            "Skin Marker Pen",
            "Chlorhexidine 2% Applicator",
            "Irrigation Fluid 0.9% Saline 3L",
            "Pulse Lavage Tip",
            "Suction Tubing",
            "Diathermy Pencil",
            "Light Handle Covers",
            "Bone Cement Mixing Bowl Kit",
            "Sterile Gloves",
            "Sterile Gown",
        ],
        "expected_disposables": [
            "Disposable Reamer - Large",
            "Cement Mixing Cartridge",
            "Cement Delivery Gun Nozzle",
            "Disposable Femoral Canal Brush",
        ],
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
        "expected_disposables": ["Disposable Drill Bit 2.5mm", "K-wire 1.6mm", "K-wire 2.0mm"],
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


for _procedure_id, _instructions in CLINICAL_PROCEDURE_SPECIAL_INSTRUCTIONS.items():
    if _procedure_id in CLINICAL_PROCEDURE_PROFILES:
        CLINICAL_PROCEDURE_PROFILES[_procedure_id]["expected_special_instructions"] = _instructions


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
