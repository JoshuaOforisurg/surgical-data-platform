"""
Synthetic Orthopaedic Preference Dataset Generator
--------------------------------------------------

Generates:
- orthopaedic_preferences.csv
- orthopaedic_preferences.json

Clinical meaning of fields:
- surgeon_id: Unique consultant identifier
- surgeon_name: UK‑style consultant name (Mr/Ms/Miss/Mrs)
- speciality: Always "Orthopaedics"
- subspecialty: Joints, Trauma, Spine, Paediatric, Foot & Ankle
- procedure: Operation performed within the subspecialty
- instrument: Instrument set typically required
- preferred_retractor_size: Surgeon-specific preference
- preferred_drill_brand: Surgeon-specific preference
- needs_backup_suction: Whether surgeon routinely requests backup suction
- years_of_experience: Consultant seniority
- hospital_affiliation: Trust or hospital name
- generation_timestamp: ISO timestamp for ingestion traceability
"""

import os
import random
from datetime import datetime
import pandas as pd
from faker import Faker

fake = Faker()

# -------------------------------------------------
# Configuration
# -------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# -------------------------------------------------
# Domain Data Pools
# -------------------------------------------------

orthopaedic_subspecialties = {
    "Joints": [
        "Uncemented Hip Replacement",
        "Unicompartmental Knee Replacement",
        "Total Knee Replacement",
        "Reverse Total Shoulder Replacement",
        "ACL Reconstruction with LET",
        "Anatomical Shoulder Replacement",
        "Patellofemoral Joint Replacement",
        "Bipolar Hemiarthroplasty"
    ],
    "Trauma": [
        "TMTJ Fusion",
        "Weil Osteotomy",
        "DIPJ/PIPJ Fusion",
        "Distal Radius ORIF",
        "Ankle ORIF",
        "MTPJ Fusion",
        "Removal of Metalwork from Foot",
        "Tibial Plateau Fracture Fixation",
        "Femoral Nail Removal"
    ],
    "Spine": [
        "Spinal Microdiscectomy",
        "Spinal Decompression",
        "Arthroscopic Spinal Decompression",
        "Lumbar Spinal Fusion",
        "Cervical Spinal Fusion",
        "Kyphoplasty",
        "Anterior Cervical Discectomy"
    ],
    "Paediatric": [
        "Paediatric Femoral Osteotomy",
        "Clubfoot Correction",
        "Paediatric Fracture Fixation",
        "Blount’s Disease Correction"
    ],
    "Foot and Ankle": [
        "Triple Arthrodesis",
        "Hallux Valgus Correction",
        "Achilles Tendon Repair",
        "Lateral Ligament Reconstruction"
    ]
}

instruments_by_subspecialty = {
    "Joints": [
        "Large Orthopaedic Set",
        "J&J PFC Knee Retractors",
        "Arthrex Arthroscopy Set",
        "Muller Basic Hip Set",
        "Norfolk and Norwich Retractors",
        "Initial Retractors",
        "Conmed Power Tools",
        "Zimmer Biomet Retractors",
        "Stryker System 6 Retractors",
        "DePuy Synthes Hip Kit"
    ],
    "Trauma": [
        "Conmed Small Joint Set",
        "Mr. Mask Foot Instruments",
        "Hand Set",
        "Hand Set Extras",
        "AO Synthes Chisel Set",
        "Mola Set",
        "Acumed Acutrak Screw Removal Set",
        "Synthes Distal Radius Plate Set",
        "Tornier Humeral Fracture Set",
        "Smith & Nephew Small Fragment Set"
    ],
    "Spine": [
        "Spinal Instrumentation Set",
        "McCulloch Lumbar Retractor Set",
        "Stryker High Speed Burr",
        "SI Bone Fuse Set",
        "Conmed Power Tools",
        "Medtronic CD Horizon Set",
        "Depuy Synthes Spine Set",
        "Globus Medical Spine Set",
        "Nuvasive Spine Set"
    ],
    "Paediatric": [
        "Paediatric Orthopaedic Set",
        "Small Fragment Set",
        "Titanium Elastic Nails",
        "Paediatric Drills",
        "Micro Screws Set",
        "Pfizer Mini Hip Kit",
        "Synthes Paediatric Plates"
    ],
    "Foot and Ankle": [
        "Foot and Ankle Arthrodesis Set",
        "Hallux Valgus Set",
        "Achilles Tendon Repair Kit",
        "Lateral Ligament Reconstruction Set",
        "Small Bone Fixation Set",
        "Stryker Ankle Fusion Set",
        "DePuy Synthes Foot Plates"
    ]
}

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def generate_uk_surgeon_name():
    """UK orthopaedic surgeons use Mr/Ms/Miss/Mrs."""
    title = random.choice(["Mr", "Ms", "Miss", "Mrs"])
    return f"{title} {fake.last_name()}"

def generate_surgeons(n=20):
    surgeons = []
    used_ids = set()

    for _ in range(n):
        subspecialty = random.choice(list(orthopaedic_subspecialties.keys()))

        surgeon_id = random.randint(1000, 9999)
        while surgeon_id in used_ids:
            surgeon_id = random.randint(1000, 9999)
        used_ids.add(surgeon_id)

        surgeons.append({
            "surgeon_id": surgeon_id,
            "surgeon_name": generate_uk_surgeon_name(),
            "speciality": "Orthopaedics",
            "subspecialty": subspecialty,
            "preferred_retractor_size": random.choice(["Small", "Medium", "Large", "Extra Large"]),
            "preferred_drill_brand": random.choice([
                "Stryker", "Depuy Synthes", "Arthrex V300",
                "Zimmer Biomet", "Smith & Nephew", "Medtronic"
            ]),
            "needs_backup_suction": random.choice([True, False]),
            "years_of_experience": random.randint(2, 30),
            "hospital_affiliation": fake.company()
        })

    return surgeons

def generate_preferences(num_records=500):
    surgeons = generate_surgeons()
    batch_timestamp = datetime.now().isoformat()

    rows = []

    for _ in range(num_records):
        surgeon = random.choice(surgeons)
        subspecialty = surgeon["subspecialty"]

        rows.append({
            **surgeon,
            "procedure": random.choice(orthopaedic_subspecialties[subspecialty]),
            "instrument": random.choice(instruments_by_subspecialty[subspecialty]),
            "generation_timestamp": batch_timestamp
        })

    return pd.DataFrame(rows)

# -------------------------------------------------
# Main
# -------------------------------------------------

if __name__ == "__main__":
    df = generate_preferences(500)
    print(df.head())
    print(df.info())

    df.to_csv(os.path.join(DATA_DIR, "orthopaedic_preferences.csv"), index=False)
    df.to_json(os.path.join(DATA_DIR, "orthopaedic_preferences.json"), orient="records", indent=2)
