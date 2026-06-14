import csv
import json
from pathlib import Path
from fpdf import FPDF


# ---------------------------------------------------------
# UNIVERSAL SAFE ACCESSOR
# ---------------------------------------------------------
def safe(obj, field, default=""):
    """Safely get an attribute from an object, returning a default if missing."""
    return getattr(obj, field, default)


def safe_list(obj, field):
    """Safely get a list attribute, always returning a list."""
    return getattr(obj, field, []) or []


# ---------------------------------------------------------
# CSV EXPORTER
# ---------------------------------------------------------
def export_to_csv(record, path: str):
    flat = {}

    # 1. Staff Profiles
    flat["surgeon_id"] = safe(record.surgeon, "id")
    flat["surgeon_name"] = safe(record.surgeon, "full_name")
    flat["surgeon_specialty"] = safe(record.surgeon, "specialty")
    flat["surgeon_glove_size"] = safe(record.surgeon, "glove_size")

    # Core Specialties
    flat["specialty"] = safe(record, "specialty")

    # Procedure metadata (SAFE)
    flat["procedure_codes"] = ", ".join(safe_list(record.procedure, "procedure_codes"))
    flat["diagnosis_codes"] = ", ".join(safe_list(record.procedure, "diagnosis_codes"))
    flat["procedure_name"] = safe(record.procedure, "name")
    flat["subspecialty"] = safe(record.procedure, "subspecialty")
    flat["surgery_type"] = safe(record.procedure, "surgery_type", "Open")

    # 3. Preparation & Theatre Environment
    flat["positioning_description"] = safe(record.positioning, "description")
    flat["positioning_equipment"] = ", ".join(safe_list(record.positioning, "equipment"))
    flat["skin_prep_desc"] = safe(record.skin_prep, "description")
    flat["skin_prep_type"] = safe(record.skin_prep, "prep")
    flat["operating_theatre_desc"] = safe(record.operating_theatre, "description")

    # 4. Equipment Requirements
    flat["equipment"] = ", ".join(
        f"{e.name} (Req: {e.required})" for e in safe_list(record, "equipment")
    )

    # 5. Anaesthetic Configurations
    flat["anaesthetic_mode"] = safe(record.anaesthetic, "mode")
    flat["anaesthetic_notes"] = safe(record.anaesthetic, "notes")

    # 6. Surgical Materials & Draping
    flat["draping"] = ", ".join(d.name for d in safe_list(record, "draping"))
    flat["consumables"] = ", ".join(
        f"{c.name} (x{safe(c, 'quantity', 1)})" for c in safe_list(record, "consumables")
    )
    flat["disposables"] = ", ".join(
        f"{d.name} (x{safe(d, 'quantity', 1)})" for d in safe_list(record, "disposables")
    )

    # Clinical Instruments
    flat["instruments"] = ", ".join(
        f"{i.name} (x{safe(i, 'quantity', 1)})" for i in safe_list(record, "instruments")
    )

    # 7. Implants
    flat["implants"] = ", ".join(i.name for i in safe_list(record, "implants"))

    # 8. Specialty Sutures
    flat["sutures"] = ", ".join(
        f"{s.name} [Size: {safe(s, 'size', 'N/A')}] (x{safe(s, 'quantity', 1)})"
        for s in safe_list(record, "sutures")
    )

    # 9. Wound Dressings
    flat["dressings"] = ", ".join(d.name for d in safe_list(record, "dressings"))

    # 10. Operational Directives
    flat["special_instructions"] = safe(record.special_instructions, "notes")
    flat["free_text_updates"] = safe(record.free_text_updates, "notes")

    # Version tracking
    flat["version_num"] = safe(record.version, "version")
    flat["version_updated_by"] = safe(record.version, "updated_by")
    flat["version_updated_at"] = safe(record.version, "updated_at")
    flat["version_change_summary"] = safe(record.version, "change_summary")
    flat["source_system"] = safe(record, "source_system")

    # Write file
    path = Path(path)
    write_header = not path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(flat)


# ---------------------------------------------------------
# TXT EXPORTER
# ---------------------------------------------------------
def export_to_txt(record, path: str):
    instruments_str = ", ".join(i.name for i in safe_list(record, "instruments")) or "None"
    implants_str = ", ".join(i.name for i in safe_list(record, "implants")) or "None"
    position_str = safe(record.positioning, "description", "Standard")
    anaesthetic_str = safe(record.anaesthetic, "mode", "Standard GA")

    proc_codes = ", ".join(safe_list(record.procedure, "procedure_codes"))

    line = " | ".join([
        safe(record.surgeon, "full_name"),
        f"Glove: {safe(record.surgeon, 'glove_size', 'N/A')}",
        f"{proc_codes} - {safe(record.procedure, 'name')}",
        f"Position: {position_str}",
        f"Anaesthetic: {anaesthetic_str}",
        f"Instruments: [{instruments_str}]",
        f"Implants: [{implants_str}]",
        f"v{safe(record.version, 'version')}",
        safe(record, "source_system")
    ])

    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------
# JSON EXPORTER
# ---------------------------------------------------------
def export_to_json(record, path: str):
    data_dict = record.model_dump(mode='json')
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data_dict) + "\n")

def export_to_pdf(record, path: str):
    """
    PDF exporter using core FPDF fonts only.
    All Unicode characters are sanitized to avoid encoding errors.
    """

    def ascii_safe(text):
        if not text:
            return ""
        # Replace common Unicode characters with ASCII equivalents
        replacements = {
            "–": "-", "—": "-", "•": "*", "×": "x",
            "“": '"', "”": '"', "‘": "'", "’": "'",
            "°": " deg ", "®": "(R)", "™": "(TM)"
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)
        # Remove any remaining non-ASCII characters
        return text.encode("ascii", "ignore").decode()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------
    pdf.set_font("Arial", style="B", size=14)
    pdf.cell(0, 10, ascii_safe(f"SURGEON PREFERENCE CARD (v{safe(record.version, 'version')})"), ln=True)

    pdf.set_font("Arial", size=10)
    pdf.cell(
        0,
        6,
        ascii_safe(
            f"Source System: {safe(record, 'source_system').upper()} | Updated By: {safe(record.version, 'updated_by')}"
        ),
        ln=True
    )
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # ---------------------------------------------------------
    # 1. Key Profile Information
    # ---------------------------------------------------------
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 8, "1. Key Profile Information", ln=True)

    pdf.set_font("Arial", size=10)
    pdf.cell(
        0,
        6,
        ascii_safe(
            f"- Surgeon Name: {safe(record.surgeon, 'full_name')} "
            f"[Glove Size: {safe(record.surgeon, 'glove_size', 'N/A')}]"
        ),
        ln=True
    )

    pdf.cell(
        0,
        6,
        ascii_safe(
            f"- Clinical Specialty: {safe(record.surgeon, 'specialty')} "
            f"-> Subspecialty: {safe(record.procedure, 'subspecialty', 'N/A')}"
        ),
        ln=True
    )

    proc_codes = ", ".join(safe_list(record.procedure, "procedure_codes"))
    surgery_type = safe(record.procedure, "surgery_type", "Open")

    pdf.cell(
        0,
        6,
        ascii_safe(
            f"- Procedure: [{proc_codes}] {safe(record.procedure, 'name')} ({surgery_type})"
        ),
        ln=True
    )
    pdf.ln(2)

    # ---------------------------------------------------------
    # 2. Setup & Environment
    # ---------------------------------------------------------
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 8, "2. Setup & Environment Setup", ln=True)

    pdf.set_font("Arial", size=10)
    pdf.cell(
        0,
        6,
        ascii_safe(f"- Patient Positioning: {safe(record.positioning, 'description', 'N/A')}"),
        ln=True
    )

    if safe(record.skin_prep, "description"):
        pdf.cell(
            0,
            6,
            ascii_safe(
                f"- Skin Prep Requirements: {safe(record.skin_prep, 'description')} "
                f"[Type: {safe(record.skin_prep, 'prep', 'Standard')}]"
            ),
            ln=True
        )

    if safe(record.operating_theatre, "description"):
        pdf.cell(
            0,
            6,
            ascii_safe(f"- Target Theatre Location: {safe(record.operating_theatre, 'description')}"),
            ln=True
        )
    pdf.ln(2)

    # ---------------------------------------------------------
    # 3. Theatre Equipment
    # ---------------------------------------------------------
    equipment = safe_list(record, "equipment")
    if equipment:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "3. Theatre Equipment Requirements", ln=True)

        pdf.set_font("Arial", size=10)
        for eq in equipment:
            req_tag = "[REQUIRED]" if safe(eq, "required") else "[OPTIONAL]"
            pdf.cell(0, 6, ascii_safe(f"  _ {eq.name} {req_tag}"), ln=True)
        pdf.ln(2)

    # ---------------------------------------------------------
    # 4. Anaesthetic
    # ---------------------------------------------------------
    if record.anaesthetic:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "4. Anaesthetic Configuration", ln=True)

        pdf.set_font("Arial", size=10)
        pdf.cell(
            0,
            6,
            ascii_safe(f"- Planned Mode: {safe(record.anaesthetic, 'mode', 'N/A')}"),
            ln=True
        )

        if safe(record.anaesthetic, "notes"):
            pdf.cell(
                0,
                6,
                ascii_safe(f"- Specific Instructions: {safe(record.anaesthetic, 'notes')}"),
                ln=True
            )
        pdf.ln(2)

    # ---------------------------------------------------------
    # 5. Instruments
    # ---------------------------------------------------------
    instruments = safe_list(record, "instruments")
    if instruments:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "5. Sterile Instrument Trays", ln=True)

        pdf.set_font("Arial", size=10)
        for inst in instruments:
            pdf.cell(
                0,
                6,
                ascii_safe(f"  _ {inst.name} (x{safe(inst, 'quantity', 1)})"),
                ln=True
            )
        pdf.ln(2)

    # ---------------------------------------------------------
    # 6. Materials & Consumables
    # ---------------------------------------------------------
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 8, "6. Surgical Materials & Consumables", ln=True)

    pdf.set_font("Arial", size=10)

    draping = safe_list(record, "draping")
    if draping:
        pdf.cell(0, 6, ascii_safe(f"- Drape Systems: {', '.join(d.name for d in draping)}"), ln=True)

    consumables = safe_list(record, "consumables")
    if consumables:
        pdf.cell(
            0,
            6,
            ascii_safe(
                f"- Consumables: {', '.join(f'{c.name} (x{safe(c, 'quantity', 1)})' for c in consumables)}"
            ),
            ln=True
        )

    disposables = safe_list(record, "disposables")
    if disposables:
        pdf.cell(
            0,
            6,
            ascii_safe(
                f"- Disposables: {', '.join(f'{d.name} (x{safe(d, 'quantity', 1)})' for d in disposables)}"
            ),
            ln=True
        )
    pdf.ln(2)

    # ---------------------------------------------------------
    # 7. Implants & Sutures
    # ---------------------------------------------------------
    implants = safe_list(record, "implants")
    sutures = safe_list(record, "sutures")

    if implants or sutures:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "7. Implants & Fixation Materials", ln=True)

        pdf.set_font("Arial", size=10)

        for imp in implants:
            pdf.cell(0, 6, ascii_safe(f"  _ Implant Item: {imp.name}"), ln=True)

        for sut in sutures:
            pdf.cell(
                0,
                6,
                ascii_safe(
                    f"  _ Suture: {sut.name} [Size: {safe(sut, 'size', 'N/A')}] "
                    f"(x{safe(sut, 'quantity', 1)})"
                ),
                ln=True
            )
        pdf.ln(2)

    # ---------------------------------------------------------
    # 8. Dressings
    # ---------------------------------------------------------
    dressings = safe_list(record, "dressings")
    if dressings:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "8. Post-Operative Wound Dressings", ln=True)

        pdf.set_font("Arial", size=10)
        for drg in dressings:
            pdf.cell(0, 6, ascii_safe(f"  _ Dressing Option: {drg.name}"), ln=True)
        pdf.ln(2)

    # ---------------------------------------------------------
    # 9. Special Instructions
    # ---------------------------------------------------------
    if safe(record.special_instructions, "notes") or safe(record.free_text_updates, "notes"):
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 8, "9. Special Operational Directives", ln=True)

        pdf.set_font("Arial", size=10)

        if safe(record.special_instructions, "notes"):
            pdf.cell(
                0,
                6,
                ascii_safe(f"- Directive Pool Notes: {safe(record.special_instructions, 'notes')}"),
                ln=True
            )

        if safe(record.free_text_updates, "notes"):
            pdf.cell(
                0,
                6,
                ascii_safe(f"- Live Free-Text Updates: {safe(record.free_text_updates, 'notes')}"),
                ln=True
            )

    # ---------------------------------------------------------
    # Save PDF
    # ---------------------------------------------------------
    pdf.output(path)
