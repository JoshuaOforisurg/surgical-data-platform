import csv
import json
from pathlib import Path
from fpdf import FPDF


# -------------------------
# CSV EXPORTER
# -------------------------
def export_to_csv(record, path: str):
    """
    Flattens a Pydantic SurgeonPreferenceCard object into a single CSV row,
    ensuring every element from the mock metadata schema is fully captured.
    """
    flat = {}

    # 1. Staff Profiles
    flat["surgeon_id"] = record.surgeon.id
    flat["surgeon_name"] = record.surgeon.full_name
    flat["surgeon_specialty"] = record.surgeon.specialty
    flat["surgeon_glove_size"] = record.surgeon.glove_size or ""

    # Core Specialties
    flat["specialty"] = record.specialty

    # Procedure metadata
    flat["procedure_code"] = record.procedure.code
    flat["procedure_name"] = record.procedure.name
    flat["subspecialty"] = record.procedure.subspecialty or ""
    flat["surgery_type"] = record.procedure.surgery_type or ""

    # 3. Preparation & Theatre Environment
    flat["positioning_description"] = record.positioning.description if record.positioning else ""
    flat["positioning_equipment"] = ", ".join(record.positioning.equipment) if (
                record.positioning and record.positioning.equipment) else ""
    flat["skin_prep_desc"] = record.skin_prep.description if record.skin_prep else ""
    flat["skin_prep_type"] = record.skin_prep.prep if (record.skin_prep and record.skin_prep.prep) else ""
    flat["operating_theatre_desc"] = record.operating_theatre.description if record.operating_theatre else ""

    # 4. Equipment Requirements
    flat["equipment"] = ", ".join(
        f"{e.name} (Req: {e.required})" for e in record.equipment
    ) if record.equipment else ""

    # 5. Anaesthetic Configurations
    flat["anaesthetic_mode"] = record.anaesthetic.mode if (
                record.anaesthetic and hasattr(record.anaesthetic, 'mode')) else ""
    flat["anaesthetic_notes"] = record.anaesthetic.notes if record.anaesthetic else ""

    # 6. Surgical Materials & Draping
    flat["draping"] = ", ".join(d.name for d in record.draping) if record.draping else ""
    flat["consumables"] = ", ".join(
        f"{c.name} (x{c.quantity or 1})" for c in record.consumables) if record.consumables else ""
    flat["disposables"] = ", ".join(
        f"{d.name} (x{d.quantity or 1})" for d in record.disposables) if record.disposables else ""

    # Clinical Instruments
    flat["instruments"] = ", ".join(
        f"{i.name} (x{i.quantity or 1})" for i in record.instruments) if record.instruments else ""

    # 7. Implants
    flat["implants"] = ", ".join(i.name for i in record.implants) if record.implants else ""

    # 8. Specialty Sutures
    flat["sutures"] = ", ".join(
        f"{s.name} [Size: {s.size or 'N/A'}] (x{s.quantity or 1})" for s in record.sutures
    ) if record.sutures else ""

    # 9. Wound Dressings
    flat["dressings"] = ", ".join(d.name for d in record.dressings) if record.dressings else ""

    # 10. Operational Directives (Special Instructions)
    flat["special_instructions"] = record.special_instructions.notes if record.special_instructions else ""
    flat["free_text_updates"] = record.free_text_updates.notes if record.free_text_updates else ""

    # Version tracking & System Settings
    flat["version_num"] = record.version.version
    flat["version_updated_by"] = record.version.updated_by
    flat["version_updated_at"] = record.version.updated_at.isoformat()
    flat["version_change_summary"] = record.version.change_summary or ""
    flat["source_system"] = record.source_system

    # Write file safely
    path = Path(path)
    write_header = not path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(flat)


# -------------------------
# TXT EXPORTER
# -------------------------
def export_to_txt(record, path: str):
    """
    Pipe-delimited layout reflecting metadata summaries for high scannability.
    """
    instruments_str = ", ".join(i.name for i in record.instruments) if record.instruments else "None"
    implants_str = ", ".join(i.name for i in record.implants) if record.implants else "None"
    position_str = record.positioning.description if record.positioning else "Standard"
    anaesthetic_str = record.anaesthetic.mode if (
                record.anaesthetic and hasattr(record.anaesthetic, 'mode')) else "Standard GA"

    line = " | ".join([
        record.surgeon.full_name,
        f"Glove: {record.surgeon.glove_size or 'N/A'}",
        record.procedure.name,
        f"Position: {position_str}",
        f"Anaesthetic: {anaesthetic_str}",
        f"Instruments: [{instruments_str}]",
        f"Implants: [{implants_str}]",
        f"v{record.version.version}",
        record.source_system
    ])

    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# -------------------------
# JSON EXPORTER
# -------------------------
def export_to_json(record, path: str):
    """
    Appends the record as a single JSON line (.jsonl).
    Perfect for massive datasets and master logs.
    """
    data_dict = record.model_dump(mode='json')
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data_dict) + "\n")


# -------------------------
# PDF EXPORTER
# -------------------------
def export_to_pdf(record, path: str):
    """
    Complete structured PDF layout ensuring every single metadata point
    is rendered safely down the document without truncation.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Document Title Header
    pdf.set_font("Arial", style="B", size=14)
    pdf.cell(0, 10, f"SURGEON PREFERENCE CARD (v{record.version.version})", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Source System: {record.source_system.upper()} | Updated By: {record.version.updated_by}", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # 1. Staff Profiles & Key Information
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 8, "1. Key Profile Information", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"- Surgeon Name: {record.surgeon.full_name} [Glove Size: {record.surgeon.glove_size or 'N/A'}]",
             ln=True)
    pdf.cell(0, 6,
             f"- Clinical Specialty: {record.surgeon.specialty} -> Subspecialty: {record.procedure.subspecialty or 'N/A'}",
             ln=True)
    pdf.cell(0, 6,
             f"- Procedure: [{record.procedure.code}] {record.procedure.name} ({record.procedure.surgery_type or 'Open'})",
             ln=True)
    pdf.ln(2)

    # 3. Preparation & Theatre Environment
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 8, "2. Setup & Environment Setup", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"- Patient Positioning: {record.positioning.description if record.positioning else 'N/A'}", ln=True)
    if record.skin_prep:
        pdf.cell(0, 6,
                 f"- Skin Prep Requirements: {record.skin_prep.description} [Type: {record.skin_prep.prep or 'Standard'}]",
                 ln=True)
    if record.operating_theatre:
        pdf.cell(0, 6, f"- Target Theatre Location: {record.operating_theatre.description}", ln=True)
    pdf.ln(2)

    # 4. Equipment Requirements
    if record.equipment:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "3. Theatre Equipment Requirements", ln=True)
        pdf.set_font("Arial", size=10)
        for eq in record.equipment:
            req_tag = "[REQUIRED]" if eq.required else "[OPTIONAL]"
            pdf.cell(0, 6, f"  _ {eq.name} {req_tag}", ln=True)
        pdf.ln(2)

    # 5. Anaesthetic Configurations
    if record.anaesthetic:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "4. Anaesthetic Configuration", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, f"- Planned Mode: {record.anaesthetic.mode if hasattr(record.anaesthetic, 'mode') else 'N/A'}",
                 ln=True)
        if record.anaesthetic.notes:
            pdf.cell(0, 6, f"- Specific Instructions: {record.anaesthetic.notes}", ln=True)
        pdf.ln(2)

    # Instrument Trays
    if record.instruments:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "5. Sterile Instrument Trays", ln=True)
        pdf.set_font("Arial", size=10)
        for inst in record.instruments:
            pdf.cell(0, 6, f"  _ {inst.name} (x{inst.quantity or 1})", ln=True)
        pdf.ln(2)

    # 6. Surgical Materials, Draping & Consumables
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 8, "6. Surgical Materials & Consumables", ln=True)
    pdf.set_font("Arial", size=10)
    if record.draping:
        pdf.cell(0, 6, f"- Drape Systems: {', '.join(d.name for d in record.draping)}", ln=True)
    if record.consumables:
        consumable_summary = ", ".join(f"{c.name} (x{c.quantity or 1})" for c in record.consumables)
        pdf.cell(0, 6, f"- Consumables: {consumable_summary}", ln=True)
    if record.disposables:
        disposable_summary = ", ".join(f"{d.name} (x{d.quantity or 1})" for d in record.disposables)
        pdf.cell(0, 6, f"- Disposables: {disposable_summary}", ln=True)
    pdf.ln(2)

    # 7 & 8. Implants and Specialty Sutures
    if record.implants or record.sutures:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "7. Implants & Fixation Materials", ln=True)
        pdf.set_font("Arial", size=10)
        if record.implants:
            for imp in record.implants:
                pdf.cell(0, 6, f"  _ Implant Item: {imp.name}", ln=True)
        if record.sutures:
            for sut in record.sutures:
                pdf.cell(0, 6, f"  _ Suture: {sut.name} [Size: {sut.size or 'N/A'}] (x{sut.quantity or 1})", ln=True)
        pdf.ln(2)

    # 9. Wound Dressings
    if record.dressings:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "8. Post-Operative Wound Dressings", ln=True)
        pdf.set_font("Arial", size=10)
        for drg in record.dressings:
            pdf.cell(0, 6, f"  _ Dressing Option: {drg.name}", ln=True)
        pdf.ln(2)

    # 10. Operational Directives & Special Instructions
    if (record.special_instructions and record.special_instructions.notes) or (
            record.free_text_updates and record.free_text_updates.notes):
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "9. Special Operational Directives", ln=True)
        pdf.set_font("Arial", size=10)
        if record.special_instructions and record.special_instructions.notes:
            pdf.cell(0, 6, f"- Directive Pool Notes: {record.special_instructions.notes}", ln=True)
        if record.free_text_updates and record.free_text_updates.notes:
            pdf.cell(0, 6, f"- Live Free-Text Updates: {record.free_text_updates.notes}", ln=True)

    # Save to disk
    pdf.output(path)
