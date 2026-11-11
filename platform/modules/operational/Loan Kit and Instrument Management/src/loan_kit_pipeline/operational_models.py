from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ItemCategory(str, Enum):
    INSTRUMENT = "instrument"
    IMPLANT = "implant"
    CONSUMABLE = "consumable"


class ReconciliationStatus(str, Enum):
    EXPECTED = "expected"
    RECEIVED = "received"
    MISSING = "missing"
    DAMAGED = "damaged"
    USED = "used"
    IMPLANTED = "implanted"
    WASTED = "wasted"
    RETURNED = "returned"


@dataclass(frozen=True)
class LoanRequest:
    kit_request_id: str
    case_id: str
    procedure_name: str
    surgeon_id: str
    requested_at: datetime
    required_by: datetime
    priority: str
    approval_status: str


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    supplier_name: str
    approved: bool
    specialty: str
    contact_channel: str


@dataclass(frozen=True)
class LoanKit:
    kit_id: str
    kit_request_id: str
    supplier_id: str
    kit_name: str
    expected_tray_count: int
    received_tray_count: int
    current_location: str
    return_due_at: datetime | None


@dataclass(frozen=True)
class LoanItem:
    item_id: str
    kit_id: str
    item_name: str
    category: ItemCategory
    catalogue_number: str
    serial_or_lot_number: str
    expected_quantity: int
    received_quantity: int
    used_quantity: int
    returned_quantity: int
    expiry_date: str
    status: ReconciliationStatus
