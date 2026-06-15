from domain.clinical_reference_data import (
    CLINICAL_PROCEDURE_PROFILES,
    CLINICAL_SPECIAL_INSTRUCTIONS,
)


# Improved `mock_data.py` (production-ready, modular, scalable)

# ============================================================
# mock_data.py - Production-ready metadata for synthetic generator
# ============================================================

# ============================================================
# SPECIALTIES & SUBSPECIALTIES
# ============================================================

SPECIALTIES = [
    "Orthopaedics"
]

SUBSPECIALTIES = {
    "Orthopaedics": [
        "Joint Replacement",
        "Sports Medicine",
        "Trauma",
        "Hand Surgery",
        "Foot and Ankle",
        "Spine",
    ]
}

# ============================================================
# PROCEDURE DEFINITIONS (used by mapping logic)
# ============================================================

PROCEDURES = {
    "Trauma": [
        {
            "codes": {"diagnosis": ["S82.40XA"], "procedure": ["0QS604Z"]},
            "name": "ORIF Tibia and Fibula",
            "subspecialty": "Trauma",
        },
        {
            "codes": {"diagnosis": ["S82.80XA"], "procedure": ["0QS704Z"]},
            "name": "ORIF Ankle",
            "subspecialty": "Trauma",
        },
        {
            "codes": {"diagnosis": ["S72.00XA"], "procedure": ["0QS004Z"]},
            "name": "Fixation of fracture of neck of femur using intramedullary nail",
            "subspecialty": "Trauma",
        },
    ],

    "Joint Replacement": [
        {
            "codes": {"diagnosis": ["M17.10"], "procedure": ["0SRC0JZ"]},
            "name": "Total Knee Replacement",
            "subspecialty": "Joint Replacement",
        },
        {
            "codes": {"diagnosis": ["M16.10"], "procedure": ["0SRD0JZ"]},
            "name": "Total Hip Replacement (Cemented)",
            "subspecialty": "Joint Replacement",
        },
        {
            "codes": {"diagnosis": ["M19.011"], "procedure": ["0RRG0JZ"]},
            "name": "Total Shoulder Replacement",
            "subspecialty": "Joint Replacement",
        },
        {
            "codes": {"diagnosis": ["M19.011"], "procedure": ["0RRG0JZ"]},
            "name": "Reverse Shoulder Replacement",
            "subspecialty": "Joint Replacement",
        },
    ],

    "Spine": [
        {
            "codes": {"diagnosis": ["M48.06"], "procedure": ["00SN0ZZ"]},
            "name": "Lumbar Laminectomy",
            "subspecialty": "Spine",
        },
        {
            "codes": {"diagnosis": ["M51.26"], "procedure": ["00SN4ZZ"]},
            "name": "Spinal Microdiscectomy",
            "subspecialty": "Spine",
        },
    ],

    "Sports Medicine": [
        {
            "codes": {"diagnosis": ["M75.100"], "procedure": ["0LQ44ZZ"]},
            "name": "Arthroscopic Rotator Cuff Repair",
            "subspecialty": "Sports Medicine",
        },
        {
            "codes": {"diagnosis": ["M75.200"], "procedure": ["0LQ44ZZ"]},
            "name": "Arthroscopic Biceps Tenodesis",
            "subspecialty": "Sports Medicine",
        },
    ],

    "Hand Surgery": [
        {
            "codes": {"diagnosis": ["G56.00"], "procedure": ["01N60ZZ"]},
            "name": "Carpal Tunnel Release",
            "subspecialty": "Hand Surgery",
        },
        {
            "codes": {"diagnosis": ["M65.331"], "procedure": ["01N70ZZ"]},
            "name": "Percutaneous Trigger Finger Release",
            "subspecialty": "Hand Surgery",
        },
        {
            "codes": {"diagnosis": ["M18.0"], "procedure": ["0LPU0ZZ"]},
            "name": "Thumb Carpometacarpal Joint Arthroplasty",
            "subspecialty": "Hand Surgery",
        },
    ],

    "Foot and Ankle": [
        {
            "codes": {"diagnosis": ["M20.10"], "procedure": ["0LQ54ZZ"]},
            "name": "MTPJ Fusion",
            "subspecialty": "Foot and Ankle",
        },
        {
            "codes": {"diagnosis": ["M25.571"], "procedure": ["0LQC4ZZ"]},
            "name": "Ankle Arthroscopy",
            "subspecialty": "Foot and Ankle",
        },
        {
            "codes": {"diagnosis": ["M77.41"], "procedure": ["0LQJ0ZZ"]},
            "name": "Open Achilles Tendon Repair",
            "subspecialty": "Foot and Ankle",
        },
    ],
}

# ============================================================
# CLINICAL PREFERENCE PROFILES (core metadata)
# ============================================================

CLINICAL_PREFERENCE_PROFILES = {
    # --- Joint Replacement ---
    "Total Knee Replacement": {
        "positioning": "Supine on standard table with foot support",
        "anaesthetic": "Spinal Anaesthesia with 0.5% Heavy Bupivacaine",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Total Knee Arthroplasty Drape Pack",
        "equipment": [
            "Stryker SmartPump Tourniquet System",
            "Stryker System 8 Power Tool Kit",
        ],
        "instrument_system": "Zimmer Biomet NexGen Complete Instrumentation",
        "instruments": [
            {"name": "JOURNEY II BCS Knee System", "quantity": 7},
            {"name": "Large Orthopaedic Set", "quantity": 1},
        ],
        "implant_system": "Zimmer Biomet NexGen TKA System",
        "implants": ["Femoral Component", "Tibial Baseplate", "Polyethylene Insert"],
    },

    "Total Hip Replacement (Cemented)": {
        "positioning": "Lateral Decubitus on standard table",
        "anaesthetic": "Spinal Anaesthesia with 0.5% Heavy Bupivacaine",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Total Hip Drape Pack",
        "equipment": [
            "C-Arm Image Intensifier",
            "Stryker System 8 Power Tool Kit",
        ],
        "instrument_system": "DePuy Pinnacle Acetabular Preparation Kit",
        "instruments": [
            {"name": "Smith & Nephew R3 Acetabular System", "quantity": 4},
            {"name": "Large Orthopaedic Set", "quantity": 1},
        ],
        "implant_system": "DePuy Pinnacle Hip System Matrix",
        "implants": [
            "Acetabular Cup Component",
            "Femoral Stem Component",
            "Ceramic Head Component",
        ],
    },

    # --- Shoulder ---
    "Total Shoulder Replacement": {
        "positioning": "Beach chair position",
        "anaesthetic": "General Anaesthesia + LMA",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Shoulder Split Sheet Pack",
        "equipment": ["Standard Diathermy Machine"],
        "instrument_system": "Zimmer Biomet Comprehensive Shoulder Prep Trays",
        "instruments": [
            {"name": "Zimmer Biomet Comprehensive Shoulder System", "quantity": 3}
        ],
        "implant_system": "Zimmer Biomet Comprehensive Anatomic Line",
        "implants": ["Humeral Stem Component", "Glenoid Base Component"],
    },

    "Reverse Shoulder Replacement": {
        "positioning": "Beach chair position",
        "anaesthetic": "General Anaesthesia + LMA",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Shoulder Split Sheet Pack",
        "equipment": ["Standard Diathermy Machine"],
        "instrument_system": "Medacta Shoulder System Guided Instrumentation",
        "instruments": [
            {"name": "Medacta Shoulder System (MSS)", "quantity": 5}
        ],
        "implant_system": "Medacta Reverse Shoulder Hardware Assembly",
        "implants": ["Humeral Tray", "Glenosphere Component"],
    },

    # --- Trauma ---
    "ORIF Tibia and Fibula": {
        "positioning": "Supine on standard table",
        "anaesthetic": "General Anaesthesia with endotracheal intubation",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Universal Extremity Drape Pack",
        "equipment": [
            "C-Arm Image Intensifier",
            "Stryker SmartPump Tourniquet System",
        ],
        "instrument_system": "Synthes LCP Large Fragment System Trays",
        "instruments": [{"name": "Synthes Large Fragment Set", "quantity": 1}],
        "implant_system": "DePuy Synthes 4.5mm LCP Titanium System",
        "implants": ["Anatomic Tibia Locking Plate Set", "Cortical Screws"],
    },

    "ORIF Ankle": {
        "positioning": "Supine on standard table",
        "anaesthetic": "General Anaesthesia with endotracheal intubation",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Universal Extremity Drape Pack",
        "equipment": [
            "C-Arm Image Intensifier",
            "Stryker SmartPump Tourniquet System",
        ],
        "instrument_system": "Synthes LCP Small Fragment Reduction Kit",
        "instruments": [{"name": "Synthes Small Fragment Set", "quantity": 1}],
        "implant_system": "DePuy Synthes 3.5mm LCP Ankle Cluster",
        "implants": ["Distal Fibula Plate Set", "Malleolar Screws"],
    },

    "Fixation of fracture of neck of femur using intramedullary nail": {
        "positioning": "Fracture Table Positioning",
        "anaesthetic": "General Anaesthesia with endotracheal intubation",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Universal Extremity Drape Pack",
        "equipment": [
            "C-Arm Image Intensifier",
            "Stryker System 8 Power Tool Kit",
        ],
        "instrument_system": "DePuy Synthes TFNA Insertion System",
        "instruments": [
            {"name": "DePuy Synthes TFNA Instrument Tray", "quantity": 2}
        ],
        "implant_system": "DePuy Synthes TFNA Intramedullary Line",
        "implants": ["Intramedullary Femoral Nail", "Lag Screw Kit"],
    },

    # --- Spine ---
    "Lumbar Laminectomy": {
        "positioning": "Prone with Wilson frame",
        "anaesthetic": "General Anaesthesia with endotracheal intubation + Muscle Relaxant",
        "skin_prep": "Betadine aqueous solution",
        "drape_pack": "Spine Surgical Drape Pack",
        "equipment": [
            "Midas Rex Spine Shaver / Drill",
            "Jackson Spinal Surgery Table",
        ],
        "instrument_system": "Caspar Lumbar Retraction Instrument Core",
        "instruments": [{"name": "Caspar Retractor System", "quantity": 1}],
        "implant_system": None,
        "implants": None,
    },

    "Spinal Microdiscectomy": {
        "positioning": "Prone with Wilson frame",
        "anaesthetic": "General Anaesthesia with endotracheal intubation + Muscle Relaxant",
        "skin_prep": "Betadine aqueous solution",
        "drape_pack": "Spine Surgical Drape Pack",
        "equipment": [
            "Midas Rex Spine Shaver / Drill",
            "Jackson Spinal Surgery Table",
        ],
        "instrument_system": "Medtronic METRx Microdiscectomy Instrument Tray",
        "instruments": [{"name": "Micro-discectomy Curettes Set", "quantity": 1}],
        "implant_system": None,
        "implants": None,
    },

    # --- Sports Medicine ---
    "Arthroscopic Rotator Cuff Repair": {
        "positioning": "Beach chair position",
        "anaesthetic": "Interscalene Brachial Plexus Block + Light Sedation",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Shoulder Split Sheet Pack",
        "equipment": [
            "Arthroscopy stack system with HD camera",
            "Arthrex Synergy UHD4 Imaging Console",
        ],
        "instrument_system": "Arthrex Synergy Shoulder Arthroscopy System",
        "instruments": [{"name": "Arthrex Cuff Repair Kit", "quantity": 1}],
        "implant_system": "Arthrex SpeedBridge Anchor System",
        "implants": ["SutureTape Anchors", "SwiveLock Anchors"],
    },

    "Arthroscopic Biceps Tenodesis": {
        "positioning": "Beach chair position",
        "anaesthetic": "Interscalene Brachial Plexus Block + Light Sedation",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Shoulder Split Sheet Pack",
        "equipment": ["Arthroscopy stack system with HD camera"],
        "instrument_system": "Arthrex Biceps Tenodesis Master Instrument Tray",
        "instruments": [{"name": "Biceps Tenodesis Kit", "quantity": 1}],
        "implant_system": "Arthrex BioComposite Tenodesis Screw Kit",
        "implants": ["Tenodesis Screw"],
    },

    # --- Hand Surgery ---
    "Carpal Tunnel Release": {
        "positioning": "Supine on standard table with arm board",
        "anaesthetic": "Interscalene Brachial Plexus Block + Light Sedation",
        "skin_prep": "Betadine aqueous solution",
        "drape_pack": "Hand and Foot Aperture Drape Pack",
        "equipment": ["Stryker SmartPump Tourniquet System"],
        "instrument_system": "Stryker EndoBlade Carpal Tunnel Instrumentation",
        "instruments": [{"name": "Minor Hand Instrument Set", "quantity": 1}],
        "implant_system": None,
        "implants": None,
    },

    "Percutaneous Trigger Finger Release": {
        "positioning": "Supine on standard table with arm board",
        "anaesthetic": "Local Infiltration with 1% Lignocaine",
        "skin_prep": "Betadine aqueous solution",
        "drape_pack": "Hand and Foot Aperture Drape Pack",
        "equipment": ["Stryker SmartPump Tourniquet System"],
        "instrument_system": "Standard Open/Percutaneous Tenotomy Kit",
        "instruments": [{"name": "Minor Hand Instrument Set", "quantity": 1}],
        "implant_system": None,
        "implants": None,
    },

    "Thumb Carpometacarpal Joint Arthroplasty": {
        "positioning": "Supine on standard table with arm board",
        "anaesthetic": "General Anaesthesia + LMA",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Hand and Foot Aperture Drape Pack",
        "equipment": ["Stryker SmartPump Tourniquet System"],
        "instrument_system": "Acumed Hand Arthroplasty Specialized Tools",
        "instruments": [{"name": "Hand Arthroplasty Set", "quantity": 1}],
        "implant_system": "Acumed Total Thumb CMC System",
        "implants": ["Trapeziatome Spacer"],
    },

    # --- Foot & Ankle ---
    "MTPJ Fusion": {
        "positioning": "Supine on standard table",
        "anaesthetic": "Spinal Anaesthesia with 0.5% Heavy Bupivacaine",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Hand and Foot Aperture Drape Pack",
        "equipment": ["Stryker SmartPump Tourniquet System"],
        "instrument_system": "Wright Medical Pro-Toe Forefoot System",
        "instruments": [{"name": "Small Bone Set", "quantity": 1}],
        "implant_system": "Wright Medical Foot Fusion Construct Set",
        "implants": ["1st MTP Fusion Plate", "Compression Screws"],
    },

    "Ankle Arthroscopy": {
        "positioning": "Supine on standard table with leg holder",
        "anaesthetic": "General Anaesthesia + LMA",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Hand and Foot Aperture Drape Pack",
        "equipment": ["Arthroscopy stack system with HD camera"],
        "instrument_system": "Smith & Nephew Dyonics Small Joint Scope Core",
        "instruments": [{"name": "Small Joint Arthroscopy Set", "quantity": 1}],
        "implant_system": None,
        "implants": None,
    },

    "Open Achilles Tendon Repair": {
        "positioning": "Prone Position",
        "anaesthetic": "General Anaesthesia with endotracheal intubation",
        "skin_prep": "ChloraPrep 2% chlorhexidine gluconate",
        "drape_pack": "Hand and Foot Aperture Drape Pack",
        "equipment": ["Stryker SmartPump Tourniquet System"],
        "instrument_system": "Arthrex PARS Achilles Tendon System Trays",
        "instruments": [{"name": "Large Orthopaedic Set", "quantity": 1}],
        "implant_system": "Arthrex PARS Percutaneous Achilles Assembly",
    }
}


for _clinical_profile in CLINICAL_PROCEDURE_PROFILES.values():
    _profile_name = _clinical_profile["name"]
    if _profile_name in CLINICAL_PREFERENCE_PROFILES:
        _mock_profile = CLINICAL_PREFERENCE_PROFILES[_profile_name]
        expected_draping = _clinical_profile.get("expected_draping") or []
        if expected_draping:
            _mock_profile["drape_pack"] = expected_draping[0]
        _mock_profile["consumables"] = _clinical_profile.get("expected_consumables", [])
        _mock_profile["disposables"] = _clinical_profile.get("expected_disposables", [])
        _mock_profile["sutures"] = _clinical_profile.get("expected_sutures", [])
        _mock_profile["dressings"] = _clinical_profile.get("expected_dressings", [])
# ============================================================
# SPECIAL INSTRUCTIONS POOL
# ============================================================

SPECIAL_INSTRUCTIONS_POOL = CLINICAL_SPECIAL_INSTRUCTIONS
# ============================================================
# CONSUMABLES & DISPOSABLES
# ============================================================

CONSUMABLES_ITEMS = [
    "Gauze Swabs 10x10",
    "Gauze Swabs 5x5",
    "Irrigation Fluid 0.9% Saline 1L",
    "Irrigation Fluid 0.9% Saline 3L",
    "Suction Tubing",
    "Light Handle Covers",
    "Ultrasound Gel",
    "Skin Marker Pen",
    "Chlorhexidine 2% Applicator",
    "Betadine Prep Solution",
    "Scalpel Blade #10",
    "Scalpel Blade #15",
    "Suture Removal Kit",
    "Sterile Gloves (Pair)",
    "Sterile Gown",
    "Suction Yankauer Tip",
    "Diathermy Pencil",
    "Diathermy Tip",
    "Syringe 10ml",
    "Syringe 20ml",
]

DISPOSABLES_ITEMS = [
    "K-wire 1.6mm",
    "K-wire 2.0mm",
    "Steinmann Pin 3.0mm",
    "Steinmann Pin 4.0mm",
    "Disposable Drill Bit 3.2mm",
    "Disposable Drill Bit 4.5mm",
    "Disposable Saw Blade – Oscillating",
    "Disposable Saw Blade – Reciprocating",
    "Arthroscopy Shaver Blade 4.0mm",
    "Arthroscopy Shaver Blade 5.5mm",
    "Pulse Lavage Tip",
    "Cement Mixing Cartridge",
    "Cement Delivery Gun Nozzle",
    "Disposable Trocar Set",
    "Disposable Burr 3.5mm",
    "Disposable Burr 4.0mm",
    "Disposable Reamer – Small",
    "Disposable Reamer – Large",
]
# ============================================================
# SUTURE NAMES (clinically realistic)
# ============================================================

SUTURE_NAMES = [
    # Absorbable – deep tissue
    "Vicryl 1",
    "Vicryl 0",
    "Vicryl 2-0",
    "Vicryl 3-0",
    "PDS II 0",
    "PDS II 1",
    "PDS II 2-0",

    # Absorbable – skin closure
    "Monocryl 3-0",
    "Monocryl 4-0",
    "Monocryl 5-0",

    # Non‑absorbable – skin
    "Prolene 3-0",
    "Prolene 4-0",
    "Ethilon 3-0",
    "Ethilon 4-0",

    # Tendon / ligament repair
    "FiberWire #2",
    "FiberWire #5",
    "FiberTape 2mm",

    # Arthroscopy sutures
    "SutureTape 1.3mm",
    "TigerWire #2",

    # Heavy non‑absorbable
    "Ethibond Excel #2",
    "Ethibond Excel #5",
    "Ti-Cron #2",
]
# ============================================================
# DRESSING OPTIONS (clinically realistic)
# ============================================================

DRESSING_OPTIONS = [
    # Primary contact dressings
    "Mepitel",
    "Adaptic",
    "Jelonet",

    # Absorbent post‑op dressings
    "Mepore",
    "Melolin",
    "Primapore",

    # Advanced surgical dressings
    "Opsite Post-Op",
    "Opsite Flexifix",
    "Aquacel Surgical",
    "Aquacel Ag",
    "Tegaderm Foam",

    # Closure support
    "Steri-Strips 6mm",
    "Steri-Strips 12mm",

    # Compression / support
    "Crepe Bandage",
    "Wool and Crepe",
    "Tubigrip Size B",
    "Tubigrip Size C",
]
