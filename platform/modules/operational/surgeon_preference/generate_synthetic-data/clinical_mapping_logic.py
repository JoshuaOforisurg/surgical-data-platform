import random

# Unified lists to ensure alignment
# Start with Orthopaedics and scale to other specialties later on
SPECIALTIES = [
    "Orthopaedics"
]

SUBSPECIALTIES = {
    "Orthopaedics": [
        "Trauma",
        "Joints",
        "Spine",
        "Upper Limb",  # Matched to PROCEDURES
        "Lower Limb"   # Matched to PROCEDURES
    ]
}

PROCEDURES = {
    "Trauma": [
        {"code": "W20.1 Z58.2 Z58.3", "name": "ORIF Tibia and Fibula", "surgery_type": "Open"},
        {"code": "W25.1 Z58.2 Z58.3", "name": "ORIF Ankle", "surgery_type": "Open"},
        {"code": "W24.2 Z58.1", "name": "Fixation of fracture of neck of femur using intramedullary nail", "surgery_type": "Open"}
    ],
    "Joints": [
        {"code": "W40.1", "name": "Total Knee Replacement", "surgery_type": "Open"},
        {"code": "W37.1", "name": "Total Hip Replacement (Cemented)", "surgery_type": "Open"} # Fixed space
    ],
    "Spine": [
        {"code": "V29.1", "name": "Lumbar Laminectomy", "surgery_type": "Open"},
        {"code": "V29.6", "name": "Spinal Microdiscectomy", "surgery_type": "Open"}
    ],
    "Upper Limb": [
        {"code": "T79.1 T64.5 Y76.7", "name": "Arthroscopic Rotator Cuff Repair + Biceps Tenodesis", "surgery_type": "Arthroscopic"}, # Fixed name
        {"code": "O38.1 Y53.4", "name": "Reverse Shoulder Replacement", "surgery_type": "Open"} # Fixed name
    ],
    "Lower Limb": [
        {"code": "W59.3 Z77.4","name": "MTPJ Fusion", "surgery_type": "Open"},
        {"code": "W86.3 Z85.6","name": "Ankle arthroscopy + Ankle arthroscopic cheilectomy", "surgery_type": "Open"}
    ],
    "Hand Surgery": [
        {"code": "T52.1", "name": "Carpal Tunnel Release", "surgery_type": "Open"}
    ]
}

INSTRUMENT_SYSTEMS = {
    "Total Knee Replacement": [
        {"name": "JOURNEY II BCS Knee System", "quantity": 7},
        {"name": "Large Orthopaedic Set", "quantity": 1}
    ],
    "Total Hip Replacement (Cemented)": [
        {"name": "Smith & Nephew R3 Acetabular System", "quantity": 4},
        {"name": "Large Orthopaedic Set", "quantity": 1}
    ],
    "Lumbar Laminectomy": [
        {"name": "Spine Decompression Set", "quantity": 1}
    ],
    "Arthroscopic Rotator Cuff Repair + Biceps Tenodesis": [
        {"name": "Arthrex Cuff repair instruments", "quantity": 1}
    ],
    "Reverse Shoulder Replacement": [
        {"name": "Medacta Shoulder System (MSS)", "quantity": 5}
    ]
}

def generate_clinical_mapping():
    # 1. Choose a specialty
    specialty = random.choice(SPECIALTIES)

    # 2. Choose a subspecialty within that specialty
    subspecialty = random.choice(SUBSPECIALTIES[specialty])

    # 3. Choose a procedure within that subspecialty
    procedure = random.choice(PROCEDURES[subspecialty])

    # 4. Get instrument systems for that procedure
    instruments = INSTRUMENT_SYSTEMS.get(procedure["name"], [])

    return specialty, subspecialty, procedure, instruments

# Test the script
print(generate_clinical_mapping())
