import random
from pathlib import Path
from datetime import datetime

# Import your custom Pydantic models from your domain layer
from domain.surgeon_preference_model import (
    SurgeonPreferenceCard, Surgeon, Procedure, Positioning,
    InstrumentItem, SkinPrep, PreferenceVersion, EquipmentItem,
    AnaestheticNotes, OperatingTheatre, DrapingItem, Consumables,
    Disposables, Implants, SpecialInstructions, SutureItem, DressingItem
)

# Clean, direct local imports of your custom helper modules
from file_exporters import (
    export_to_csv,
    export_to_txt,
    export_to_json,
    export_to_pdf
)
from clinical_mapping_logic import generate_clinical_mapping
import mock_metadata
from messiness_generator import apply_messiness


def generate_single_card(output_dir: str = "output", messy: bool = True):
    """
    Generates a single comprehensive surgeon preference card instantiated as a
    Pydantic object using rich metadata, and writes it to the hybrid pipeline ecosystem.
    """
    # 1. Fetch clinical definitions from your mapping file
    specialty, subspecialty, procedure_data, instruments_data = generate_clinical_mapping()

    # 2. Build core entity Pydantic instances using mock_metadata lists
    surgeon_obj = Surgeon(
        id=f"SURG_{random.randint(10000, 99999)}",
        full_name=random.choice(mock_metadata.SURGEON_NAMES),
        specialty=specialty,
        glove_size=random.choice(mock_metadata.GLOVE_SIZES)
    )

    procedure_obj = Procedure(
        code=procedure_data["code"],
        name=procedure_data["name"],
        subspecialty=subspecialty,
        surgery_type=procedure_data["surgery_type"]
    )

    # 3. Build rich operational layout sections
    anaesthetic_obj = AnaestheticNotes(
        notes=random.choice(mock_metadata.ANAESTHETIC_MODES)
    )

    positioning_obj = Positioning(
        description=random.choice(mock_metadata.POSITIONING_OPTIONS),
        equipment=["Side supports", "Arm board", "Gel pads"] if random.choice([True, False]) else None
    )

    operating_theatre_obj = OperatingTheatre(
        description=random.choice(mock_metadata.THEATRE_DESCRIPTIONS),
        supports=["Laminar Flow", "Integrated Displays"]
    )

    skin_prep_obj = SkinPrep(
        description=random.choice(mock_metadata.SKIN_PREPS),
        prep=random.choice(mock_metadata.PREP_TYPES)
    )

    special_instructions_obj = SpecialInstructions(
        notes=random.choice(mock_metadata.SPECIAL_INSTRUCTIONS_POOL)
    )

    version_obj = PreferenceVersion(
        version=random.randint(1, 5),
        updated_by=random.choice(mock_metadata.UPDATER_NAMES),
        updated_at=datetime.utcnow(),
        change_summary="Routine update of instrument tray configurations." if random.choice([True, False]) else None
    )

    # 4. Map and package list items (using list comprehensions)
    instrument_objects = [
        InstrumentItem(name=i["name"], quantity=i["quantity"], notes=None)
        for i in instruments_data
    ]

    equipment_objects = [
        EquipmentItem(name=eq, required=random.choice([True, False]), notes="Ensure calibrated.")
        for eq in random.sample(mock_metadata.THEATRE_EQUIPMENT, k=random.randint(1, 2))
    ]

    draping_objects = [
        DrapingItem(name=random.choice(mock_metadata.DRAPE_PACKS), notes="Standard approach.")
    ]

    consumables_objects = [
        Consumables(name=c, quantity=random.randint(1, 5))
        for c in random.sample(mock_metadata.CONSUMABLES_ITEMS, k=random.randint(2, 4))
    ]

    disposables_objects = [
        Disposables(name=d, quantity=random.randint(1, 2))
        for d in random.sample(mock_metadata.DISPOSABLES_ITEMS, k=random.randint(2, 3))
    ]

    # Handle conditional logic: only add implants for relevant bone/joint work
    implants_objects = None
    if subspecialty in ["Joints", "Trauma", "Hand Surgery"]:
        implants_objects = [Implants(name=random.choice(mock_metadata.IMPLANT_TYPES))]

    # Generate specialized sutures structured lists
    chosen_suture = random.choice(mock_metadata.SUTURE_NAMES)
    sutures_objects = [
        SutureItem(name=chosen_suture["name"], size=chosen_suture["size"], quantity=random.randint(1, 4))
    ]

    dressing_objects = [
        DressingItem(name=random.choice(mock_metadata.DRESSING_OPTIONS))
    ]

    # 5. Assemble root Pydantic Preference Card Model with all fields satisfied
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
        source_system=random.choice(mock_metadata.SYSTEMS)
    )

    # -------------------------------------------------------------
    # MESSINESS SWITCHBOARD
    # -------------------------------------------------------------
    # OPTION A: Active pipeline corruption stage (Controlled by function call arguments)
    record_to_export = apply_messiness(card_record) if messy else card_record

    # OPTION B: Hard bypass (Uncomment this line below later to force 100% clean data during scaling)
    # record_to_export = card_record
    # -------------------------------------------------------------

    # 6. Export following the Hybrid Strategy
    # Strategy Part 1: All records flow into single shared Master Data Tables
    export_to_csv(record_to_export, f"{output_dir}/master_preferences.csv")
    export_to_txt(record_to_export, f"{output_dir}/master_preferences.txt")
    export_to_json(record_to_export, f"{output_dir}/master_preferences.json")

    # Strategy Part 2: Isolated layout sheets per surgeon to simulate practical printing
    export_to_pdf(record_to_export, f"{output_dir}/preference_card_{record_to_export.surgeon.id}.pdf")

    return record_to_export


def generate_batch(n: int = 10, output_dir: str = "output", messy: bool = True):
    """
    Cleans out old batch datasets to prevent stacking, then loops to
    sequentially generate a brand new data pipeline array.
    """
    out_path = Path(output_dir)

    # AUTOMATIC CLEANUP: Wipe old master files if they exist so data doesn't pool between runs
    if out_path.exists():
        for old_file in out_path.glob("master_preferences.*"):
            old_file.unlink()
        for old_pdf in out_path.glob("preference_card_*.pdf"):
            old_pdf.unlink()
    else:
        out_path.mkdir(parents=True, exist_ok=True)

    records = []
    for _ in range(n):
        record = generate_single_card(output_dir=output_dir, messy=messy)
        records.append(record)
    return records


if __name__ == "__main__":
    # Your target size scale config
    batch_size = 20
    print(f"Generating synthetic structured Pydantic datasets ({batch_size} hybrid scalable cards)...")

    # Set messy=True to run with anomalies, or False for a clean run
    cards = generate_batch(n=batch_size, output_dir="output", messy=True)

    print(f"Done! Check your 'output/' folder.")
    print(f" -> Master sheets generated with {len(cards)} rows consolidated inside.")
    print(f" -> Generated {len(cards)} separate custom clinical PDFs.")
