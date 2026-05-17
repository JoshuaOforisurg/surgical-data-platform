import random
from datetime import datetime
from faker import Faker

from generate.clinical_mapping_logic import generate_clinical_mapping

fake = Faker()

def generate_clean_preference_card() -> dict:
    # -------------------------
    # Clinical mapping
    # -------------------------
    specialty, subspecialty, procedure, instruments = generate_clinical_mapping()

    # -------------------------
    # Surgeon
    # -------------------------
    surgeon = {
        "id": str(fake.random_int(min=1000, max=9999)),
        "full_name": f"Mr {fake.last_name()}",
        "specialty": specialty,
        "glove_size": random.choice(["6.5", "7", "7.5", "8", None])
    }

    # -------------------------
    # Procedure
    # -------------------------
    procedure_obj = {
        "code": procedure["code"],
        "name": procedure["name"],
        "subspecialty": subspecialty,
        "surgery_type": procedure["surgery_type"]
    }

    # -------------------------
    # Preference Card Sections
    # -------------------------
    positioning = {
        "description": "Supine with arm board",
        "equipment": ["Arm board", "Bolster"]
    }

    equipment = [
        {"name": "Tourniquet", "required": True},
        {"name": "C-arm", "required": True}
    ]

    skin_prep = {
        "description": "Chlorhexidine",
        "prep": "2-minute scrub"
    }

    draping = [
        {"name": "Large drape"},
        {"name": "Fenestrated drape"}
    ]

    consumables = [
        {"name": "Gauze", "quantity": 10},
        {"name": "Suction tubing", "quantity": 1}
    ]

    disposables = [
        {"name": "Scalpel blade 10", "quantity": 1},
        {"name": "Light handle covers", "quantity": 2}
    ]

    implants = [
        {"name": "Locking plate"},
        {"name": "Screws"}
    ]

    sutures = [
        {"name": "Vicryl", "size": "2-0", "quantity": 2},
        {"name": "Monocryl", "size": "3-0", "quantity": 1}
    ]

    dressings = [
        {"name": "Mepore"},
        {"name": "Opsite"}
    ]

    # -------------------------
    # Versioning
    # -------------------------
    version = {
        "version": 1,
        "updated_by": "system",
        "updated_at": datetime.utcnow(),
        "change_summary": "Initial auto-generated version"
    }

    # -------------------------
    # Final structured record
    # -------------------------
    return {
        "surgeon": surgeon,
        "procedure": procedure_obj,
        "specialty": specialty,
        "anaesthetic": {"notes": None},
        "positioning": positioning,
        "equipment": equipment,
        "operating_theatre": {"description": "Standard orthopaedic theatre"},
        "instruments": instruments,
        "skin_prep": skin_prep,
        "draping": draping,
        "consumables": consumables,
        "disposables": disposables,
        "implants": implants,
        "special_instructions": {"notes": None},
        "sutures": sutures,
        "dressings": dressings,
        "free_text_updates": {"notes": None},
        "version": version,
        "source_system": "excel"
    }
