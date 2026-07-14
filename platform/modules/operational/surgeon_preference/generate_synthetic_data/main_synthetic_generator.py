import random
import argparse
from pathlib import Path
from datetime import datetime
from typing import Iterable

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
from generate_synthetic_data import shared_catalogue
from domain.clinical_reference_service import ClinicalReferenceService

# Messiness
from generate_synthetic_data.messiness_generator import apply_messiness


# ============================================================
# GENERATE A SINGLE CARD
# ============================================================

STRUCTURED_FORMATS = ("json", "csv")
MASTER_FORMATS = ("csv", "txt", "json")


def _normalise_formats(formats: str | Iterable[str] | None) -> tuple[str, ...]:
    if formats is None:
        return STRUCTURED_FORMATS
    if isinstance(formats, str):
        parts = formats.split(",")
    else:
        parts = list(formats)
    normalised = tuple(part.strip().lower() for part in parts if part.strip())
    unsupported = sorted(set(normalised) - {"csv", "json", "txt", "pdf"})
    if unsupported:
        raise ValueError(f"Unsupported synthetic export format(s): {', '.join(unsupported)}")
    return normalised


def _export_record(record, output_dir: str, stem: str, formats: Iterable[str]) -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    for file_format in formats:
        target = out_path / f"{stem}.{file_format}"
        if file_format == "csv":
            export_to_csv(record, str(target))
        elif file_format == "txt":
            export_to_txt(record, str(target))
        elif file_format == "json":
            export_to_json(record, str(target))
        elif file_format == "pdf":
            export_to_pdf(record, str(target))


def generate_single_card(
    output_dir: str = "output",
    messy: bool = True,
    export: bool = True,
    stem: str = "master_preferences",
    formats: str | Iterable[str] | None = MASTER_FORMATS,
):
    """
    Generates a single surgeon preference card aligned to the shared clinical catalogue.
    """

    # ---------------------------------------------------------
    # 1. Clinical mapping & profile lookup
    # ---------------------------------------------------------
    specialty, subspecialty, procedure_data = generate_clinical_mapping()
    procedure_name = procedure_data["name"]
    profile = shared_catalogue.CLINICAL_PREFERENCE_PROFILES[procedure_name]
    reference_service = ClinicalReferenceService()
    procedure_id = reference_service.resolve_procedure(procedure_name)
    instruction_pool = (
        reference_service.instructions_for_procedure(procedure_id)
        or shared_catalogue.SPECIAL_INSTRUCTIONS_POOL
    )

    # ---------------------------------------------------------
    # 2. Surgeon
    # ---------------------------------------------------------
    surgeon_obj = Surgeon(
        id=f"SURG_{random.randint(10000, 99999)}",
        full_name=random.choice(shared_catalogue.SURGEON_NAMES),
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
        notes=random.choice(instruction_pool)
    )

    version_obj = PreferenceVersion(
        version=random.randint(1, 5),
        updated_by=random.choice(shared_catalogue.SURGEON_UPDATE_ROLES),
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

    draping_names = [
        profile.get("drape_pack", "Standard drape pack"),
        *profile.get("draping_order", []),
    ]
    draping_objects = [
        DrapingItem(name=name)
        for name in dict.fromkeys(name for name in draping_names if name)
    ]

    consumables_objects = [
        Consumables(name=c, quantity=random.randint(1, 5))
        for c in profile.get("consumables", [])
    ]

    disposables_objects = [
        Disposables(name=d, quantity=random.randint(1, 2))
        for d in profile.get("disposables", [])
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
        SutureItem(name=suture, quantity=random.randint(1, 3))
        for suture in (profile.get("sutures") or [random.choice(shared_catalogue.SUTURE_NAMES)])
    ]

    dressing_objects = [
        DressingItem(name=dressing)
        for dressing in (profile.get("dressings") or [random.choice(shared_catalogue.DRESSING_OPTIONS)])
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

    if export:
        _export_record(
            record_to_export,
            output_dir=output_dir,
            stem=stem,
            formats=_normalise_formats(formats),
        )

    return record_to_export


# ============================================================
# GENERATE A BATCH
# ============================================================

def generate_batch(
    n: int = 100,
    output_dir: str = "output",
    messy: bool = True,
    output_mode: str = "master",
    file_formats: str | Iterable[str] | None = STRUCTURED_FORMATS,
):
    """
    Generates a batch of surgeon preference cards.
    """
    out_path = Path(output_dir)

    out_path.mkdir(parents=True, exist_ok=True)
    for old_file in out_path.glob("master_preferences.*"):
        old_file.unlink()
    for old_pdf in out_path.glob("preference_card_*.pdf"):
        old_pdf.unlink()
    partitioned_dir = out_path / "partitioned"
    if partitioned_dir.exists():
        for old_file in partitioned_dir.iterdir():
            if old_file.is_file():
                old_file.unlink()
    else:
        partitioned_dir.mkdir(parents=True, exist_ok=True)

    mode = output_mode.lower()
    if mode not in {"master", "partitioned", "both"}:
        raise ValueError("output_mode must be one of: master, partitioned, both")

    individual_formats = _normalise_formats(file_formats)
    structured_individual_formats = tuple(
        file_format for file_format in individual_formats if file_format in STRUCTURED_FORMATS
    )
    if mode in {"partitioned", "both"} and not structured_individual_formats:
        raise ValueError("Partitioned ingestion requires at least one structured format: json or csv")

    cards = []
    for idx in range(1, n + 1):
        card = generate_single_card(output_dir=output_dir, messy=messy, export=False)
        cards.append(card)
        if mode in {"master", "both"}:
            _export_record(card, output_dir=output_dir, stem="master_preferences", formats=MASTER_FORMATS)
        if mode in {"partitioned", "both"}:
            file_format = structured_individual_formats[(idx - 1) % len(structured_individual_formats)]
            _export_record(
                card,
                output_dir=str(partitioned_dir),
                stem=f"preference_card_{idx:05d}",
                formats=(file_format,),
            )

    return cards


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic surgeon preference cards.")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output-dir", default="generate_synthetic_data/output")
    parser.add_argument("--clean", action="store_true", help="Disable messy source-data perturbations.")
    parser.add_argument(
        "--output-mode",
        choices=["master", "partitioned", "both"],
        default="master",
        help="master writes aggregate files; partitioned writes one structured file per card.",
    )
    parser.add_argument(
        "--file-formats",
        default="json,csv",
        help="Comma-separated partitioned formats. Structured ingestion supports json,csv.",
    )
    args = parser.parse_args()

    batch_size = args.count
    print(f"Generating {batch_size} synthetic preference cards...")
    cards = generate_batch(
        n=batch_size,
        output_dir=args.output_dir,
        messy=not args.clean,
        output_mode=args.output_mode,
        file_formats=args.file_formats,
    )
    print("Done.")
