# Starting with Orthopaedic data and scaling out to other specialities later
import random

# 1. Staff Profiles
SURGEON_NAMES = [
    "Mr. James Gate","Miss Sarah Jenkins", "Mr. Alex Patel", "Prof. Claire Dubois",
    "Miss Elena Rostova", "Mr. Marcus Vance", "Mr. Kenji Tanaka", "Prof. Amara Okafor",
    "Mr. David MacLeod", "Miss Fatima Al-Sayed", "Mr Davidson"
]

GLOVE_SIZES = ["6.0", "6.5", "7.0", "7.5", "8.0", "8.5", None]

UPDATER_NAMES = ["Admin_User", "Surg_Tech_Lead", "EPR_Sync_Bot", "Theatre_Manager_Beta"]

# 2. System Settings
SYSTEMS = ["streamlit", "excel", "epr"]

# 3. Preparation & Theatre Environment
POSITIONING_OPTIONS = [
    "Supine on standard table", "Lateral decubitus", "Prone with Wilson frame",
    "Beach chair position", "Lithotomy position", "Fracture Table Positioning", "Trendelenburg Position"
]

SKIN_PREPS = [
    "ChloraPrep 2% chlorhexidine gluconate", "Betadine aqueous solution",
    "DuraPrep IV", "Hydrex pink 0.5% chlorhexidine in alcohol", "Povidone-iodine 10%"
]

PREP_TYPES = ["Alcoholic", "Aqueous", "Standard Tinted", None]

THEATRE_DESCRIPTIONS = [
    "Laminar Flow Theatre 04", "Ultra-Clean Air Orthopaedic Suite 01"]

# 4. Equipment Requirements
THEATRE_EQUIPMENT = [
    "Stryker SmartPump Tourniquet System",
    "Arthroscopy stack system with HD camera",
    "C-Arm Image Intensifier",
    "Stryker System 8 Power Tool Kit",
    "Zimmer Biomet A.T.S. 4000 Tourniquet",
    "Smith & Nephew LENS Surgical Imaging System",
    "Midas Rex Spine Shaver / Drill",
    "Jackson Spinal Surgery Table",
    "Marquet Alphamaquet Orthopaedic Fracture Table",
    "ConMed Linvatec Hall Powered Instruments",
    "Arthrex Synergy UHD4 Imaging Console",
    "Stryker Neptune 3 Waste Management System",
    "Bair Hugger Patient Warming Unit",
    "Cell Saver Autologous Blood Recovery System",
    "Covidien Valleylab FT10 Energy Platform"
]

# 5. Anaesthetic Configurations
ANAESTHETIC_MODES = [
    "General Anaesthesia + Laryngeal Mask Airway (LMA)",
    "General Anaesthesia with endotracheal intubation + Muscle Relaxant",
    "Spinal Anaesthesia with 0.5% Heavy Bupivacaine",
    "Target Controlled Infusion (TCI) Propofol Sedation",
    "Interscalene Brachial Plexus Block + Light Sedation"
]

# 6. Surgical Materials & Draping
DRAPE_PACKS = [
    "Universal Extremity Drape Pack",
    "Shoulder Split Sheet Pack",
    "Total Knee Arthroplasty Drape Pack",
    "Total Hip Bilateral U-Drape Pack",
    "Hand and Foot Aperture Drape Pack",
    "Spine Surgical Drape Pack"
]


CONSUMABLES_ITEMS = [
    "Suction liner 2L",
    "Diathermy scratch pad",
    "Skin staples (35 Wide)",
    "Light handle covers",
    "Surgical marker pen",
    "Pulse lavage tubing layout",
    "Bone wax 2.5g",
    "Bone cement mixing bowl kit",
    "Orthopaedic high-tensile suture (e.g., FiberWire)"
]

DISPOSABLES_ITEMS = [
    "Size 10 Scalpel blade",
    "Diathermy pencil with holster",
    "Needle counter (20 count)",
    "Syringe 10ml Luer Lock",
    "Sagittal bone saw blade",
    "ChloraPrep 26ml tint applicator",
    "Arthroscopy fluid collection pouch"
]


# 7. Implants
IMPLANT_TYPES = [
    "Cannulated Screw 4.0mm x 35mm Titanium", "K-Wire 1.6mm x 150mm",
    "Cortical Screw 3.5mm x 24mm", "MTPJ Fusion Plate Left", "Bone Cement (40g Low Viscosity)"
]

# 8. Specialty Sutures
SUTURE_NAMES = [
    {"name": "Vicryl (Polyglactin 910)", "size": "2-0"},
    {"name": "Monocryl (Poliglecaprone 25)", "size": "3-0"},
    {"name": "PDS II (Polydioxanone)", "size": "0"},
    {"name": "Ethilon (Nylon)", "size": "4-0"},
    {"name": "Prolene (Polypropylene)", "size": "5-0"},
]

# 9. Wound Dressings
DRESSING_OPTIONS = [
    "Opsite Post-Op visible dressing 20cm x 10cm", "Mepilex Border EM 10cm x 10cm",
    "Inadine iodine-impregnated non-adherent dressing", "Steristrips 6mm x 75mm",
    "Jelonet paraffin gauze dressing", "Aquacel Ag+ Extra ribbon"
]

# 10. Operational Directives
SPECIAL_INSTRUCTIONS_POOL = [
    "Keep tourniquet pressure to a strict maximum of 250 mmHg.",
    "Surgeon requests infiltration of local anaesthetic at the end of the procedure.",
    "Surgeon does not use small swabs",
    "Ensure x-ray clearance is arranged and image intensifier is draped prior to incision.",
    "If Patient has documented allergy to penicillin. Double check alternative antibiotics.",
    "Do not open implants until the joint surface sizing has been checked with trial components."
]
