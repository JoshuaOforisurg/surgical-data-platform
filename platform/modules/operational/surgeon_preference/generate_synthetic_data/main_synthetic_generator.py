import random
from pathlib import Path
from datetime import datetime

# Domain models
from domain.surgeon_preference_model import (
    SurgeonPreferenceCard, Surgeon, Procedure, Positioning,
    InstrumentItem, SkinPrep, PreferenceVersion, EquipmentItem,
    AnaestheticNotes, OperatingTheatre, DrapingItem, Consumables,
    Disposables, Implants, SpecialInstructions, SutureItem, DressingItem
)

# Exporters
from generate_synthetic_data.file_exporters import (
    export_to_csv,
    export_to_txt,
    export_to_json,
    export_to_pdf
)

# Clinical mapping logic
from generate_synthetic_data.clinical_mapping_logic import generate_clinical_mapping

# Metadata
from generate_synthetic_data import mock_data

# Messiness
from generate_synthetic_data.messiness_generator import apply_messiness


# ============================================================
# GENERATE A SINGLE CARD
# ============================================================

def generate_single_card(output_dir: str = "output", messy: bool = True):
    """
    Generates a single surgeon preference card aligned to mock_data.py.
    """

    # ---------------------------------------------------------
    # 1. Clinical mapping & profile lookup
    # ---------------------------------------------------------
    specialty, subspecialty, procedure_data = generate_clinical_mapping()
    procedure_name = procedure_data["name"]
    profile = mock_data.CLINICAL_PREFERENCE_PROFILES[procedure_name]

    # ---------------------------------------------------------
    # 2. Surgeon
    # ---------------------------------------------------------
    surgeon_obj = Surgeon(
        id=f"SURG_{random.randint(10000, 99999)}",
        full_name=f"Dr {random.choice(['Smith', 'Jones', 'Patel', 'Brown', 'Taylor'])}",
        specialty=specialty,
        glove_size=random.choice(["6.5", "7.0", "7.5", "8.0"])
    )

    # ---------------------------------------------------------
    # 3. Procedure
    # ---------------------------------------------------------
    procedure_obj = Procedure(
        name=procedure_name,
        subspecialty=subspecialty,
        diagnosis_codes=procedure_data["codes"]["diagnosis"],
        procedure_codes=procedure_data["codes"]["procedure"]
    )

    # ---------------------------------------------------------
    # 4. Anaesthetic, Positioning, Theatre, Skin Prep
    # ---------------------------------------------------------
    anaesthetic_text = profile.get("anaesthetic", "Standard GA")
    anaesthetic_obj = AnaestheticNotes(notes=anaesthetic_text)

    positioning_obj = Positioning(
        description=profile.get("positioning", "Standard supine"),
        equipment=None
    )

    operating_theatre_obj = OperatingTheatre(
        description="Standard NHS Operating Theatre",
        supports=["Laminar Flow", "Integrated Displays"]
    )

    skin_prep_obj = SkinPrep(
        description=profile.get("skin_prep", "Standard chlorhexidine prep")
    )

    special_instructions_obj = SpecialInstructions(
        notes=random.choice(mock_data.SPECIAL_INSTRUCTIONS_POOL)
    )

    version_obj = PreferenceVersion(
        version=random.randint(1, 5),
        updated_by=random.choice(["Admin", "Theatre Coordinator", "Clinical Lead"]),
        updated_at=datetime.now(),
        change_summary="Routine update of preference metadata."
    )

    # ---------------------------------------------------------
    # 5. Instruments, Equipment, Drapes, Consumables, Disposables
    # ---------------------------------------------------------
    instrument_objects = [
        InstrumentItem(name=i["name"], quantity=i.get("quantity", 1))
        for i in profile.get("instruments", [])
    ]

    equipment_objects = [
        EquipmentItem(name=e, required=True)
        for e in profile.get("equipment", [])
    ]

    draping_objects = [
        DrapingItem(name=profile.get("drape_pack", "Standard drape pack"))
    ]

    consumables_objects = [
        Consumables(name=c, quantity=random.randint(1, 5))
        for c in random.sample(mock_data.CONSUMABLES_ITEMS, k=min(3, len(mock_data.CONSUMABLES_ITEMS)))
    ]

    disposables_objects = [
        Disposables(name=d, quantity=random.randint(1, 2))
        for d in random.sample(mock_data.DISPOSABLES_ITEMS, k=min(2, len(mock_data.DISPOSABLES_ITEMS)))
    ]

    # ---------------------------------------------------------
    # 6. Implants (optional)
    # ---------------------------------------------------------
    implants_list = profile.get("implants", [])
    implants_objects = None
    if implants_list:
        implants_objects = [Implants(name=imp) for imp in implants_list]

    # ---------------------------------------------------------
    # 7. Sutures & Dressings
    # ---------------------------------------------------------
    sutures_objects = [
        SutureItem(
            name=random.choice(mock_data.SUTURE_NAMES),
            quantity=random.randint(1, 3)
        )
    ]

    dressing_objects = [
        DressingItem(
            name=random.choice(mock_data.DRESSING_OPTIONS)
        )
    ]

    # ---------------------------------------------------------
    # 8. Assemble final Pydantic card
    # ---------------------------------------------------------
    card_record = SurgeonPreferenceCard(
        surgeon=surgeon_obj,
        procedure=procedure_obj,
        specialty=specialty,
        anaesthetic=anaesthetic_obj,
        positioning=positioning_obj,
        operating_theatre=operating_theatre_obj,
        skin_prep=skin_prep_obj,
        special_instructions=special_instructions_obj,
        instruments=instrument_objects,
        equipment=equipment_objects,
        draping=draping_objects,
        consumables=consumables_objects,
        disposables=disposables_objects,
        implants=implants_objects,
        sutures=sutures_objects,
        dressings=dressing_objects,
        version=version_obj,
        source_system="Synthetic Preference Generator v3"
    )

    # ---------------------------------------------------------
    # 9. Messiness
    # ---------------------------------------------------------
    record_to_export = apply_messiness(card_record) if messy else card_record

    # ---------------------------------------------------------
    # 10. Export
    # ---------------------------------------------------------
    export_to_csv(record_to_export, f"{output_dir}/master_preferences.csv")
    export_to_txt(record_to_export, f"{output_dir}/master_preferences.txt")
    export_to_json(record_to_export, f"{output_dir}/master_preferences.json")
    export_to_pdf(record_to_export, f"{output_dir}/preference_card_{record_to_export.surgeon.id}.pdf")

    return record_to_export


# ============================================================
# GENERATE A BATCH
# ============================================================

def generate_batch(n: int = 10, output_dir: str = "output", messy: bool = True):
    """
    Generates a batch of surgeon preference cards.
    """
    out_path = Path(output_dir)

    if out_path.exists():
        for old_file in out_path.glob("master_preferences.*"):
            old_file.unlink()
        for old_pdf in out_path.glob("preference_card_*.pdf"):
            old_pdf.unlink()
    else:
        out_path.mkdir(parents=True, exist_ok=True)

    return [generate_single_card(output_dir=output_dir, messy=messy) for _ in range(n)]


if __name__ == "__main__":
    batch_size = 20
    print(f"Generating {batch_size} synthetic preference cards...")
    cards = generate_batch(n=batch_size, output_dir="output", messy=True)
    print("Done.")
