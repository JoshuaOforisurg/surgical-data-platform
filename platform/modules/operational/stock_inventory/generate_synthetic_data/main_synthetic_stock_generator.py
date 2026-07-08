from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


MODULE_ROOT = Path(__file__).resolve().parents[1]
OPERATIONAL_ROOT = MODULE_ROOT.parent
SURGEON_PREFERENCE_ROOT = OPERATIONAL_ROOT / "surgeon_preference"
DEFAULT_OUTPUT_DIR = MODULE_ROOT / "synthetic_data" / "generated"


def ensure_dependency_paths() -> None:
    for path in (OPERATIONAL_ROOT, SURGEON_PREFERENCE_ROOT):
        path_value = str(path)
        if path_value not in sys.path:
            sys.path.insert(0, path_value)


ensure_dependency_paths()
from surgeon_preference.generate_synthetic_data.catalogue.clinical_profiles import (  # noqa: E402
    CLINICAL_PREFERENCE_PROFILES,
)
from surgeon_preference.generate_synthetic_data.catalogue.procedures import PROCEDURES  # noqa: E402
from surgeon_preference.generate_synthetic_data.catalogue.supplies import (  # noqa: E402
    CONSUMABLES_ITEMS,
    DISPOSABLES_ITEMS,
    DRESSING_OPTIONS,
    SUTURE_NAMES,
)
from surgeon_preference.generate_synthetic_data.catalogue.surgeons import SURGEON_NAMES  # noqa: E402

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
    "Scrub Practitioner",
    "Theatre Stores Coordinator",
    "Implant Coordinator",
    "Theatre Support Worker",
    "Senior ODP",
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


@dataclass(frozen=True)
class GenerationConfig:
    output_dir: Path = DEFAULT_OUTPUT_DIR
    count: int = 250
    seed: int = 42


@dataclass(frozen=True)
class CatalogueItem:
    item_id: str
    canonical_name: str
    item_type: str
    clinical_category: str
    manufacturer: str
    supplier_id: str
    supplier_name: str
    catalogue_number: str
    barcode_gtin: str
    unit_of_measure: str
    sterile_required: bool
    single_use: bool
    implantable: bool
    controlled_item: bool
    active_status: str
    source_profile_count: int
    related_procedures: str


def _slug(value: str) -> str:
    clean = "".join(ch if ch.isalnum() else "_" for ch in value.upper())
    return "_".join(part for part in clean.split("_") if part)


def _item_id(name: str, item_type: str) -> str:
    return f"INV-{_slug(item_type)[:4]}-{_slug(name)[:30]}"


def _catalogue_number(name: str, item_type: str) -> str:
    digest = hashlib.sha256(f"{item_type}|{name}".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16) % 900000
    return f"{item_type[:3].upper()}-{100000 + seed}"


def _gtin(rng: random.Random) -> str:
    return "050" + "".join(str(rng.randint(0, 9)) for _ in range(11))


def _manufacturer_for(name: str, item_type: str, rng: random.Random) -> str:
    value = name.lower()
    if "stryker" in value:
        return "Stryker"
    if "depuy" in value or "synthes" in value:
        return "DePuy Synthes"
    if "arthrex" in value:
        return "Arthrex"
    if "smith" in value or "nephew" in value:
        return "Smith & Nephew"
    if "medtronic" in value or "midas" in value:
        return "Medtronic"
    if "zimmer" in value or "biomet" in value:
        return "Zimmer Biomet"
    if "wright" in value:
        return "Wright Medical"
    if item_type in {"consumable", "drape", "dressing", "suture"}:
        return rng.choice(["NHS Supply Chain", "Unisurge", "Ethicon", "Molnlycke"])
    if item_type == "implant":
        return rng.choice(["DePuy Synthes", "Stryker", "Smith & Nephew", "Arthrex"])
    return rng.choice(["Stryker", "DePuy Synthes", "Arthrex", "Smith & Nephew"])


def _supplier_for(manufacturer: str, rng: random.Random) -> tuple[str, str, str]:
    lower = manufacturer.lower()
    for supplier_id, supplier_name, mode in SUPPLIERS:
        if supplier_name.lower().split()[0] in lower or lower.split()[0] in supplier_name.lower():
            return supplier_id, supplier_name, mode
    return rng.choice(SUPPLIERS)


def _unit_for(item_type: str, name: str, rng: random.Random) -> str:
    if item_type == "instrument":
        return "tray"
    if item_type == "equipment":
        return "device"
    if item_type == "implant":
        return "each"
    if item_type == "drape":
        return "pack"
    if item_type == "suture":
        return "box"
    if "fluid" in name.lower():
        return "bottle"
    if "gloves" in name.lower():
        return "pair"
    return rng.choice(["each", "box", "pack"])


def _clinical_category(item_type: str, name: str) -> str:
    lower = name.lower()
    if "arthroscopy" in lower:
        return "Arthroscopy"
    if "cement" in lower:
        return "Bone cement and cementing"
    if "drill" in lower or "blade" in lower or "reamer" in lower:
        return "Power tool consumables"
    if item_type == "implant":
        return "Implants"
    if item_type == "instrument":
        return "Instrument trays"
    if item_type == "equipment":
        return "Reusable theatre equipment"
    if item_type == "suture":
        return "Sutures"
    if item_type == "dressing":
        return "Dressings"
    if item_type == "drape":
        return "Draping"
    return "Theatre consumables"


def _profile_items() -> dict[tuple[str, str], set[str]]:
    items: dict[tuple[str, str], set[str]] = {}

    def add(item_type: str, name: str, procedure: str) -> None:
        if not name:
            return
        key = (item_type, " ".join(str(name).split()))
        items.setdefault(key, set()).add(procedure)

    for procedure, profile in CLINICAL_PREFERENCE_PROFILES.items():
        for item in profile.get("instruments") or []:
            add("instrument", item.get("name", ""), procedure)
        for name in profile.get("equipment") or []:
            add("equipment", name, procedure)
        for name in [profile.get("drape_pack"), *profile.get("draping_order", [])]:
            add("drape", name, procedure)
        for name in profile.get("consumables") or []:
            add("consumable", name, procedure)
        for name in profile.get("disposables") or []:
            add("disposable", name, procedure)
        for name in profile.get("implants") or []:
            add("implant", name, procedure)
        for name in profile.get("sutures") or []:
            add("suture", name, procedure)
        for name in profile.get("dressings") or []:
            add("dressing", name, procedure)

    for name in CONSUMABLES_ITEMS:
        add("consumable", name, "General orthopaedic theatre")
    for name in DISPOSABLES_ITEMS:
        add("disposable", name, "General orthopaedic theatre")
    for name in SUTURE_NAMES:
        add("suture", name, "General orthopaedic theatre")
    for name in DRESSING_OPTIONS:
        add("dressing", name, "General orthopaedic theatre")

    return items


def build_item_catalogue(rng: random.Random, limit: int | None = None) -> list[dict[str, Any]]:
    source_items = _profile_items()
    ordered = sorted(
        source_items.items(),
        key=lambda item: (ITEM_TYPE_ORDER.index(item[0][0]), item[0][1]),
    )
    if limit:
        ordered = ordered[:limit]

    catalogue: list[dict[str, Any]] = []
    for (item_type, name), procedures in ordered:
        manufacturer = _manufacturer_for(name, item_type, rng)
        supplier_id, supplier_name, _ = _supplier_for(manufacturer, rng)
        sterile_required = item_type in {
            "instrument",
            "implant",
            "drape",
            "consumable",
            "disposable",
            "suture",
            "dressing",
        }
        single_use = item_type in {"implant", "drape", "consumable", "disposable", "suture", "dressing"}
        implantable = item_type == "implant"
        controlled_item = implantable or "blade" in name.lower() or "k-wire" in name.lower()

        catalogue.append(
            asdict(
                CatalogueItem(
                    item_id=_item_id(name, item_type),
                    canonical_name=name,
                    item_type=item_type,
                    clinical_category=_clinical_category(item_type, name),
                    manufacturer=manufacturer,
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    catalogue_number=_catalogue_number(name, item_type),
                    barcode_gtin=_gtin(rng),
                    unit_of_measure=_unit_for(item_type, name, rng),
                    sterile_required=sterile_required,
                    single_use=single_use,
                    implantable=implantable,
                    controlled_item=controlled_item,
                    active_status="active",
                    source_profile_count=len(procedures),
                    related_procedures="; ".join(sorted(procedures)),
                )
            )
        )
    return catalogue


def build_supplier_catalogue(
    catalogue: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    supplier_ids = {item["supplier_id"] for item in catalogue}
    suppliers = []
    for supplier_id, supplier_name, preferred_mode in SUPPLIERS:
        if supplier_id not in supplier_ids:
            continue
        suppliers.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "preferred_ingestion_mode": preferred_mode,
                "standard_lead_time_days": rng.choice([1, 2, 3, 5, 7, 14]),
                "minimum_order_value_gbp": rng.choice([0, 50, 100, 250, 500]),
                "emergency_order_available": preferred_mode != "spreadsheet_upload",
                "contract_status": rng.choice(["contracted", "framework", "vendor_managed"]),
            }
        )
    return suppliers


def build_locations(rng: random.Random) -> list[dict[str, Any]]:
    locations = []
    for idx, stockroom in enumerate(STOCKROOMS, start=1):
        locations.append(
            {
                "location_id": f"LOC-STOCK-{idx:02d}",
                "hospital": rng.choice(HOSPITALS),
                "location_name": stockroom,
                "location_type": "stockroom",
                "sterile_store": "Sterile" in stockroom or "Implant" in stockroom,
                "barcode_enabled": stockroom != "Trauma Emergency Cupboard",
            }
        )
    for idx, theatre in enumerate(THEATRES, start=1):
        locations.append(
            {
                "location_id": f"LOC-THEATRE-{idx:02d}",
                "hospital": "Local NHS Trust",
                "location_name": theatre,
                "location_type": "theatre",
                "sterile_store": False,
                "barcode_enabled": idx in {1, 2, 4},
            }
        )
    return locations


def _base_quantity(item_type: str, rng: random.Random) -> int:
    if item_type == "instrument":
        return rng.randint(1, 10)
    if item_type == "equipment":
        return rng.randint(1, 4)
    if item_type == "implant":
        return rng.randint(0, 18)
    if item_type == "drape":
        return rng.randint(4, 45)
    if item_type in {"suture", "dressing"}:
        return rng.randint(6, 85)
    return rng.randint(8, 160)


def _cost_for(item_type: str, rng: random.Random) -> float:
    ranges = {
        "instrument": (250.0, 4000.0),
        "equipment": (800.0, 12000.0),
        "implant": (350.0, 6500.0),
        "drape": (12.0, 85.0),
        "consumable": (0.25, 95.0),
        "disposable": (8.0, 280.0),
        "suture": (4.5, 58.0),
        "dressing": (1.5, 42.0),
    }
    low, high = ranges[item_type]
    return round(rng.uniform(low, high), 2)


def build_stock_lots(
    catalogue: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    run_date: datetime,
    rng: random.Random,
) -> list[dict[str, Any]]:
    lots = []
    stock_locations = [loc for loc in locations if loc["location_type"] == "stockroom"]
    for item in catalogue:
        lot_count = 1 if item["item_type"] in {"instrument", "equipment"} else rng.randint(1, 4)
        for lot_idx in range(1, lot_count + 1):
            expiry_days = rng.choice([-20, 7, 30, 90, 180, 365, 720])
            if item["item_type"] in {"instrument", "equipment"}:
                expiry_date = ""
                sterility_status = rng.choice(["sterile", "in_use", "awaiting_sterilisation"])
            else:
                expiry_date = (run_date + timedelta(days=expiry_days)).date().isoformat()
                sterility_status = "sterile"

            recall_status = rng.choices(
                ["clear", "supplier_notice", "quarantined"],
                weights=[94, 4, 2],
                k=1,
            )[0]
            quantity_on_hand = _base_quantity(item["item_type"], rng)
            if recall_status == "quarantined":
                quantity_on_hand = max(0, quantity_on_hand // 2)

            location = rng.choice(stock_locations)
            lot_id = f"LOT-{item['item_id'].replace('INV-', '')}-{lot_idx:02d}"
            lots.append(
                {
                    "lot_id": lot_id,
                    "item_id": item["item_id"],
                    "canonical_name": item["canonical_name"],
                    "item_type": item["item_type"],
                    "catalogue_number": item["catalogue_number"],
                    "barcode_gtin": item["barcode_gtin"],
                    "unit_of_measure": item["unit_of_measure"],
                    "location_id": location["location_id"],
                    "location_name": location["location_name"],
                    "batch_number": f"B{rng.randint(100000, 999999)}",
                    "serial_number": f"S{rng.randint(1000000, 9999999)}"
                    if item["item_type"] in {"instrument", "equipment", "implant"}
                    else "",
                    "expiry_date": expiry_date,
                    "recall_status": recall_status,
                    "sterility_status": sterility_status,
                    "quantity_on_hand": quantity_on_hand,
                    "quantity_reserved": rng.randint(0, min(5, quantity_on_hand)),
                    "unit_cost_gbp": _cost_for(item["item_type"], rng),
                    "last_counted_at": (run_date - timedelta(days=rng.randint(0, 21))).isoformat(),
                    "source_system": rng.choice(
                        ["Manual Theatre Stocktake", "ScanTrack Theatre Inventory", "ERP Materials Management"]
                    ),
                }
            )
    return lots


def build_erp_balances(
    stock_lots: list[dict[str, Any]],
    catalogue: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    item_lookup = {item["item_id"]: item for item in catalogue}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for lot in stock_lots:
        grouped.setdefault((lot["item_id"], lot["location_id"]), []).append(lot)

    balances = []
    for (item_id, location_id), lots in grouped.items():
        item = item_lookup[item_id]
        on_hand = sum(int(lot["quantity_on_hand"]) for lot in lots)
        reserved = sum(int(lot["quantity_reserved"]) for lot in lots)
        par_level = max(2, round(_base_quantity(item["item_type"], rng) * rng.uniform(0.6, 1.6)))
        reorder_point = max(1, round(par_level * rng.uniform(0.25, 0.45)))
        balances.append(
            {
                "erp_item_code": item["catalogue_number"],
                "item_id": item_id,
                "item_description": item["canonical_name"],
                "location_id": location_id,
                "quantity_on_hand": on_hand,
                "quantity_reserved": reserved,
                "quantity_available": on_hand - reserved,
                "unit_of_measure": item["unit_of_measure"],
                "par_level": par_level,
                "reorder_point": reorder_point,
                "reorder_required": on_hand - reserved <= reorder_point,
                "supplier_id": item["supplier_id"],
                "estimated_stock_value_gbp": round(on_hand * float(lots[0]["unit_cost_gbp"]), 2),
            }
        )
    return balances


def build_manual_stocktake(
    stock_lots: list[dict[str, Any]],
    run_date: datetime,
    rng: random.Random,
) -> list[dict[str, Any]]:
    sampled_lots = rng.sample(stock_lots, k=min(len(stock_lots), max(25, len(stock_lots) // 2)))
    unit_aliases = {
        "each": ["each", "ea"],
        "box": ["box", "bx"],
        "pack": ["pack", "pk"],
        "tray": ["tray"],
        "device": ["device", "unit"],
        "pair": ["pair", "pr"],
        "bottle": ["bottle", "btl"],
    }
    rows = []
    for lot in sampled_lots:
        counted_quantity = max(0, int(lot["quantity_on_hand"]) + rng.choice([-2, -1, 0, 0, 0, 1]))
        captured_unit = rng.choice(unit_aliases.get(lot["unit_of_measure"], [lot["unit_of_measure"]]))
        rows.append(
            {
                "Hospital": rng.choice(HOSPITALS),
                "Stock Area": lot["location_name"],
                "Shelf/Bin": rng.choice(["A1", "A2", "B1", "B4", "C2", "Implant Cabinet", "Top-up Trolley"]),
                "Item Description": lot["canonical_name"],
                "Catalogue No": lot["catalogue_number"],
                "Batch/Lot": lot["batch_number"],
                "Expiry": lot["expiry_date"] or "N/A",
                "Qty Counted": counted_quantity,
                "Unit": captured_unit,
                "Checked By": rng.choice(MANUAL_STOCKTAKE_STAFF),
                "Checked At": (run_date - timedelta(hours=rng.randint(1, 72))).isoformat(),
                "Notes": rng.choice(
                    [
                        "",
                        "Counted during morning theatre check",
                        "Top-up requested",
                        "Packaging damaged - review",
                        "Implant coordinator to confirm sizes",
                    ]
                ),
            }
        )
    return rows


def build_scanner_events(
    stock_lots: list[dict[str, Any]],
    run_date: datetime,
    count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    event_types = ["receipt_scan", "issue_to_case", "transfer", "stock_count", "return_to_store", "quarantine_scan"]
    events = []
    for idx in range(1, count + 1):
        lot = rng.choice(stock_lots)
        event_type = rng.choices(
            event_types,
            weights=[16, 34, 14, 20, 10, 6],
            k=1,
        )[0]
        events.append(
            {
                "event_id": f"SCAN-{run_date.strftime('%Y%m%d')}-{idx:06d}",
                "scanner_id": rng.choice(["SCAN-T1-01", "SCAN-T2-01", "SCAN-STORE-01", "SCAN-IMPLANT-01"]),
                "event_type": event_type,
                "barcode_gtin": lot["barcode_gtin"],
                "item_id": lot["item_id"],
                "item_description": lot["canonical_name"],
                "lot_id": lot["lot_id"],
                "batch_number": lot["batch_number"],
                "location_id": lot["location_id"],
                "quantity_delta": rng.choice([1, 1, 2, -1, -1, -2, -3]),
                "event_timestamp": (run_date - timedelta(minutes=rng.randint(0, 60 * 24 * 14))).isoformat(),
                "case_id": f"CASE-{rng.randint(240000, 249999)}" if event_type == "issue_to_case" else "",
                "operator_role": rng.choice(["Scrub Practitioner", "ODP", "Stores Coordinator"]),
                "source_system": "ScanTrack Theatre Inventory",
            }
        )
    return events


def build_stock_movements(
    stock_lots: list[dict[str, Any]],
    run_date: datetime,
    count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    movement_types = ["receipt", "issue", "transfer", "adjustment", "waste", "return", "quarantine"]
    movements = []
    for idx in range(1, count + 1):
        lot = rng.choice(stock_lots)
        movement_type = rng.choices(
            movement_types,
            weights=[18, 38, 14, 8, 6, 12, 4],
            k=1,
        )[0]
        movements.append(
            {
                "movement_id": f"MOVE-{run_date.strftime('%Y%m%d')}-{idx:06d}",
                "item_id": lot["item_id"],
                "canonical_name": lot["canonical_name"],
                "lot_id": lot["lot_id"],
                "from_location_id": lot["location_id"] if movement_type in {"issue", "transfer", "waste", "quarantine"} else "",
                "to_location_id": lot["location_id"] if movement_type in {"receipt", "return", "adjustment"} else rng.choice(
                    ["LOC-THEATRE-01", "LOC-THEATRE-02", "LOC-THEATRE-03", "LOC-THEATRE-04"]
                ),
                "movement_type": movement_type,
                "quantity": rng.randint(1, 8),
                "movement_at": (run_date - timedelta(minutes=rng.randint(0, 60 * 24 * 30))).isoformat(),
                "case_id": f"CASE-{rng.randint(240000, 249999)}" if movement_type == "issue" else "",
                "source_system": rng.choice(
                    ["ERP Materials Management", "Manual Theatre Stocktake", "ScanTrack Theatre Inventory"]
                ),
            }
        )
    return movements


def _procedure_catalogue() -> list[dict[str, Any]]:
    rows = []
    for subspecialty, procedures in PROCEDURES.items():
        for procedure in procedures:
            rows.append(
                {
                    "procedure_name": procedure["name"],
                    "subspecialty": subspecialty,
                    "procedure_code": ";".join(procedure["codes"]["procedure"]),
                    "diagnosis_code": ";".join(procedure["codes"]["diagnosis"]),
                }
            )
    return rows


def _required_items_for_procedure(
    procedure_name: str,
    catalogue_lookup: dict[tuple[str, str], str],
    rng: random.Random,
) -> list[dict[str, Any]]:
    profile = CLINICAL_PREFERENCE_PROFILES[procedure_name]
    requirements: list[dict[str, Any]] = []

    def add(item_type: str, name: str, quantity: int = 1, criticality: str = "required") -> None:
        item_id = catalogue_lookup.get((item_type, name))
        requirements.append(
            {
                "item_id": item_id or "",
                "expected_item_name": name,
                "item_type": item_type,
                "required_quantity": quantity,
                "clinical_criticality": criticality,
            }
        )

    for item in profile.get("instruments") or []:
        add("instrument", item["name"], int(item.get("quantity") or 1), "required")
    for name in profile.get("equipment") or []:
        add("equipment", name, 1, "required")
    if profile.get("drape_pack"):
        add("drape", profile["drape_pack"], 1, "required")
    for name in profile.get("consumables") or []:
        add("consumable", name, rng.randint(1, 5), "required")
    for name in profile.get("disposables") or []:
        add("disposable", name, rng.randint(1, 2), "required")
    for name in profile.get("implants") or []:
        add("implant", name, 1, "critical")
    for name in profile.get("sutures") or []:
        add("suture", name, rng.randint(1, 3), "preference")
    for name in profile.get("dressings") or []:
        add("dressing", name, 1, "required")

    return requirements


def build_upcoming_case_demand(
    catalogue: list[dict[str, Any]],
    run_date: datetime,
    case_count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    catalogue_lookup = {
        (item["item_type"], item["canonical_name"]): item["item_id"]
        for item in catalogue
    }
    procedures = _procedure_catalogue()
    rows = []
    for idx in range(1, case_count + 1):
        procedure = rng.choice(procedures)
        procedure_name = procedure["procedure_name"]
        scheduled_start = run_date + timedelta(days=rng.randint(0, 21), hours=rng.randint(7, 16))
        case_id = f"CASE-{250000 + idx:06d}"
        surgeon_name = rng.choice(SURGEON_NAMES)
        preference_card_uid = f"pref_{_slug(surgeon_name)[:10]}_{_slug(procedure_name)[:18]}".lower()

        for requirement in _required_items_for_procedure(procedure_name, catalogue_lookup, rng):
            rows.append(
                {
                    "case_id": case_id,
                    "scheduled_start": scheduled_start.isoformat(),
                    "hospital": "Local NHS Trust",
                    "theatre": rng.choice(THEATRES),
                    "surgeon_name": surgeon_name,
                    "procedure_name": procedure_name,
                    "procedure_code": procedure["procedure_code"],
                    "diagnosis_code": procedure["diagnosis_code"],
                    "subspecialty": procedure["subspecialty"],
                    "preference_card_uid": preference_card_uid,
                    "preference_source": "surgeon_preference_gold_synthetic",
                    "required_by_time": (scheduled_start - timedelta(hours=2)).isoformat(),
                    **requirement,
                }
            )
    return rows


def build_substitution_rules(
    catalogue: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in catalogue:
        by_type.setdefault(item["item_type"], []).append(item)

    rules = []
    idx = 1
    for item_type in ["suture", "dressing", "consumable", "disposable"]:
        candidates = by_type.get(item_type, [])
        if len(candidates) < 2:
            continue
        for preferred in rng.sample(candidates, k=min(12, len(candidates))):
            substitute = rng.choice([item for item in candidates if item["item_id"] != preferred["item_id"]])
            rules.append(
                {
                    "substitution_rule_id": f"SUB-{idx:04d}",
                    "preferred_item_id": preferred["item_id"],
                    "preferred_item_name": preferred["canonical_name"],
                    "substitute_item_id": substitute["item_id"],
                    "substitute_item_name": substitute["canonical_name"],
                    "substitution_type": rng.choice(["equivalent", "compatible", "fallback", "requires_approval"]),
                    "approval_required": rng.choice([True, False, False]),
                    "applies_to_subspecialty": rng.choice(
                        ["Any", "Joint Replacement", "Sports Medicine", "Trauma", "Hand Surgery", "Foot and Ankle"]
                    ),
                    "clinical_notes": rng.choice(
                        [
                            "Use only when preferred stock unavailable.",
                            "Confirm with scrub practitioner before opening.",
                            "Equivalent product on current local contract.",
                            "Requires surgeon approval for implant-adjacent use.",
                        ]
                    ),
                }
            )
            idx += 1
    return rules


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_table_pair(output_dir: Path, name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    csv_path = output_dir / f"{name}.csv"
    json_path = output_dir / f"{name}.json"
    write_csv(csv_path, rows)
    write_json(json_path, rows)
    return {"csv": str(csv_path), "json": str(json_path), "records": len(rows)}


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


def generate_stock_sources(config: GenerationConfig = GenerationConfig()) -> dict[str, Any]:
    if config.count < 0:
        raise ValueError("count must be greater than or equal to 0")

    rng = random.Random(config.seed)
    run_date = datetime.now(UTC).replace(microsecond=0)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    catalogue = build_item_catalogue(rng)
    suppliers = build_supplier_catalogue(catalogue, rng)
    locations = build_locations(rng)
    stock_lots = build_stock_lots(catalogue, locations, run_date, rng)
    erp_balances = build_erp_balances(stock_lots, catalogue, rng)
    manual_stocktake = build_manual_stocktake(stock_lots, run_date, rng)
    scanner_events = build_scanner_events(stock_lots, run_date, count=config.count, rng=rng)
    stock_movements = build_stock_movements(stock_lots, run_date, count=config.count, rng=rng)
    case_demand = build_upcoming_case_demand(
        catalogue,
        run_date,
        case_count=max(10, config.count // 10),
        rng=rng,
    )
    substitution_rules = build_substitution_rules(catalogue, rng)

    artifacts = {
        "item_catalogue": write_table_pair(config.output_dir, "item_catalogue", catalogue),
        "supplier_catalogue": write_table_pair(config.output_dir, "supplier_catalogue", suppliers),
        "stock_locations": write_table_pair(config.output_dir, "stock_locations", locations),
        "stock_lots": write_table_pair(config.output_dir, "stock_lots", stock_lots),
        "erp_stock_balances": write_table_pair(config.output_dir, "erp_stock_balances", erp_balances),
        "manual_stocktake_spreadsheet": write_table_pair(
            config.output_dir,
            "manual_stocktake_spreadsheet",
            manual_stocktake,
        ),
        "scanner_stock_events": write_table_pair(config.output_dir, "scanner_stock_events", scanner_events),
        "stock_movements": write_table_pair(config.output_dir, "stock_movements", stock_movements),
        "upcoming_case_demand": write_table_pair(config.output_dir, "upcoming_case_demand", case_demand),
        "substitution_rules": write_table_pair(config.output_dir, "substitution_rules", substitution_rules),
    }
    scanner_jsonl_path = config.output_dir / "scanner_stock_events.jsonl"
    write_jsonl(scanner_jsonl_path, scanner_events)
    artifacts["scanner_stock_events"]["jsonl"] = str(scanner_jsonl_path)

    manifest = {
        "generated_at": run_date.isoformat(),
        "seed": config.seed,
        "source_basis": "surgeon_preference.generate_synthetic_data.catalogue.clinical_profiles",
        "clinical_profile_count": len(CLINICAL_PREFERENCE_PROFILES),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "notes": [
            "Manual stocktake output represents spreadsheet-based hospital checks.",
            "Scanner stock events represent barcode/scanning inventory systems.",
            "Upcoming case demand is derived from surgeon preference clinical profiles.",
            "Item names are clinically aligned to the completed surgeon preference module.",
        ],
    }
    manifest_path = config.output_dir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate clinically aligned synthetic stock inventory source files."
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where generated source files should be written.",
    )
    parser.add_argument(
        "--count",
        type=non_negative_int,
        default=250,
        help="Number of scanner events and stock movements to generate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible source generation.",
    )
    args = parser.parse_args()

    manifest = generate_stock_sources(
        GenerationConfig(
            output_dir=Path(args.output_dir),
            count=args.count,
            seed=args.seed,
        )
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
