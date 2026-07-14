"""Hospital data structures for synthetic data generator."""

HOSPITALS = [
    "Local NHS Trust",
    "Northbank Orthopaedic Centre",
    "Riverside Elective Surgical Hub",
]

THEATRES = [
    "Theatre 1 - Orthopaedic Elective",
    "Theatre 2 - Trauma",
    "Theatre 3 - Day Case",
    "Theatre 4 - Laminar Flow",
]

STOCKROOMS = [
    "Main Theatre Sterile Store",
    "Orthopaedic Implant Store",
    "Day Surgery Store",
    "Trauma Emergency Cupboard",
    "Vendor Loan Kit Holding Bay",
]

SUPPLIERS = [
    ("SUP-STRYKER", "Stryker UK", "scanner_api"),
    ("SUP-DEPUY", "DePuy Synthes", "epr_export"),
    ("SUP-ARTHREX", "Arthrex", "epr_export"),
    ("SUP-SN", "Smith & Nephew", "epr_export"),
    ("SUP-MEDTRONIC", "Medtronic", "vendor_portal"),
    ("SUP-ZIMMER", "Zimmer Biomet", "vendor_portal"),
    ("SUP-NHS-SUPPLY", "NHS Supply Chain", "spreadsheet_upload"),
    ("SUP-UNISURGE", "Unisurge", "spreadsheet_upload"),
]

MANUAL_STOCKTAKE_STAFF = [
    "Theatre Stores Coordinator",
    "Stock and Procurement Manager",
    "Team Leader",
    "Deputy Team Leader",
]

ITEM_TYPE_ORDER = [
    "instrument",
    "equipment",
    "drape",
    "consumable",
    "disposable",
    "implant",
    "suture",
    "dressing",
]
